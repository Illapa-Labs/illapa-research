"""Public data of Peruvian state agencies (INGEMMET, CENEPRED/SIGRID, ANA, ANIN, INDECI).

Polite clients with a local cache under ``datos/<fuente>/`` (ignored by git): one thread, a pause
between requests, and no credentials of any kind. Anything behind a login or an ArcGIS token is
left alone and documented in docs/18-datos-del-estado.md as "needs a request".

INGEMMET's server sends an incomplete certificate chain, so the operating system's trust store is
used (truststore), never ``verify=False``.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import requests

try:  # the OS trust store knows the intermediate certificate INGEMMET forgets to send
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover
    pass

USER_AGENT = "illapa-research/0.1 (+https://github.com/Illapa-Labs/illapa-research)"
PAUSA_S = 1.5
VENTANA_ESTUDIO = (-77.0, -12.1, -76.4, -11.8)  # west, south, east, north
INGEMMET = "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services"
SIGRID = "https://sigrid.cenepred.gob.pe/sigridv3"


class ClienteEstado:
    """GET with a pause, an on-disk cache and an explicit stop when a token is asked for."""

    def __init__(self, carpeta: Path, pausa: float = PAUSA_S):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.pausa = pausa
        self._ultimo = 0.0
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT

    def _esperar(self) -> None:
        falta = self.pausa - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()

    def get(self, url: str, params: dict | None = None, cache: str | None = None, **kw) -> requests.Response:
        ruta = self.carpeta / cache if cache else None
        if ruta is not None and ruta.exists():
            r = requests.Response()
            r.status_code = 200
            r._content = ruta.read_bytes()
            return r
        self._esperar()
        r = self.s.get(url, params=params, timeout=kw.pop("timeout", 90), **kw)
        r.raise_for_status()
        if ruta is not None:
            ruta.write_bytes(r.content)
        return r


def arcgis_json(c: ClienteEstado, url: str, params: dict | None = None, cache: str | None = None) -> dict:
    """ArcGIS REST call; raises PermissionError on «Token Required» instead of looking for a token."""
    j = c.get(url, {"f": "json", **(params or {})}, cache=cache).json()
    err = j.get("error")
    if err:
        if err.get("code") in (498, 499):
            raise PermissionError(f"{url}: token required, no credentials are used")
        raise RuntimeError(f"{url}: {err}")
    return j


def arcgis_consulta(
    c: ClienteEstado, servicio: str, capa: int, ventana=VENTANA_ESTUDIO, donde: str = "1=1", base: str = INGEMMET,
    nombre_cache: str | None = None, lote: int = 400,
) -> list[dict]:
    """All features of a layer inside `ventana` as ArcGIS JSON features (WGS 84).

    Some servers (INGEMMET) do not page: ask for the object ids first, then for the features by
    batches of ids.
    """
    url = f"{base}/{servicio}/MapServer/{capa}/query"
    nombre = nombre_cache or f"{servicio}_{capa}"
    geo = {"geometry": ",".join(map(str, ventana)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
           "spatialRel": "esriSpatialRelIntersects", "where": donde}
    ids = arcgis_json(c, url, {**geo, "returnIdsOnly": "true"}, cache=f"{nombre}_ids.json").get("objectIds") or []
    out: list[dict] = []
    for i in range(0, len(ids), lote):
        trozo = ids[i : i + lote]
        j = arcgis_json(c, url, {"objectIds": ",".join(map(str, trozo)), "outFields": "*", "outSR": 4326,
                                 "returnGeometry": "true"}, cache=f"{nombre}_{i}.json")
        out += j.get("features", [])
    return out


def a_geojson(features: list[dict]) -> dict:
    """ArcGIS JSON features (point or polygon) to a GeoJSON FeatureCollection."""
    fs = []
    for f in features:
        g = f.get("geometry") or {}
        if "x" in g:
            geom = {"type": "Point", "coordinates": [g["x"], g["y"]]}
        elif "rings" in g:
            geom = {"type": "Polygon", "coordinates": g["rings"]}
        else:
            continue
        fs.append({"type": "Feature", "properties": f.get("attributes", {}), "geometry": geom})
    return {"type": "FeatureCollection", "features": fs}


def fecha_arcgis(valor) -> str | None:
    """Epoch milliseconds or text to an ISO date, None if empty."""
    if valor in (None, "", 0):
        return None
    if isinstance(valor, (int, float)):
        return time.strftime("%Y-%m-%d", time.gmtime(valor / 1000))
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(valor)) or re.search(r"(\d{2})/(\d{2})/(\d{4})", str(valor))
    if not m:
        return None
    a, b, c_ = m.groups()
    return f"{a}-{b}-{c_}" if len(a) == 4 else f"{c_}-{b}-{a}"


def ambito_sigrid(c: ClienteEstado, doc_id: int) -> list[str]:
    """WKT polygons of the «ámbito» of a SIGRID library document (embedded in its public page)."""
    html = c.get(f"{SIGRID}/documento/{doc_id}", cache=f"sigrid_doc_{doc_id}.html").text
    return re.findall(r"wkt='((?:MULTI)?POLYGON\(.*?\))'", html)


def buscar_sigrid(c: ClienteEstado, termino: str) -> list[tuple[int, str]]:
    """(document id, title) of the SIGRID library search results for a term."""
    html = c.get(f"{SIGRID}/documento/biblioteca", {"c": termino},
                 cache=f"sigrid_busqueda_{re.sub(r'[^a-z0-9]+', '_', termino.lower())}.html").text
    ids = sorted({int(i) for i in re.findall(r"/documento/(\d+)", html)})
    return [(i, "") for i in ids]


def normalizar(texto) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", base).split())


def puntos_a_tabla(geojson: dict) -> pandas.DataFrame:  # noqa: F821
    """Point features to a DataFrame with `lon` and `lat` columns."""
    import pandas as pd

    filas = []
    for f in geojson["features"]:
        if f["geometry"]["type"] != "Point":
            continue
        x, y = f["geometry"]["coordinates"]
        filas.append({**f["properties"], "lon": x, "lat": y})
    return pd.DataFrame(filas)


class IndiceCuencas:
    """Basins of catalogo/cuencas.geojson in UTM, to place many points quickly."""

    def __init__(self, cuencas: dict):
        import numpy as np
        import shapely
        from pyproj import Transformer
        from shapely.geometry import shape

        self._a_utm = Transformer.from_crs(4326, 32718, always_xy=True)
        self.slugs, self.areas, self.geoms = [], [], []
        for f in cuencas["features"]:
            g = shape(f["geometry"])
            self.geoms.append(shapely.transform(g, lambda xy: np.column_stack(self._a_utm.transform(xy[:, 0], xy[:, 1]))))
            self.slugs.append(f["properties"]["slug"])
            self.areas.append(f["properties"]["area_km2"])

    def de_punto(self, lon: float, lat: float, tolerancia_m: float = 150.0) -> tuple[str | None, bool, float]:
        """(slug, inside, distance in m): the smallest basin containing the point, else the nearest within
        the tolerance; (None, False, distance to the nearest basin) when none is that close."""
        from shapely.geometry import Point

        p = Point(*self._a_utm.transform(lon, lat))
        d = [g.distance(p) for g in self.geoms]
        dentro = [i for i, x in enumerate(d) if x == 0]
        if dentro:
            i = min(dentro, key=lambda k: self.areas[k])
            return self.slugs[i], True, 0.0
        i = min(range(len(d)), key=d.__getitem__)
        if d[i] <= tolerancia_m:
            return self.slugs[i], False, float(d[i])
        return None, False, float(d[i])


SINPAD = "https://prod4.indeci.gob.pe/portal-sinpad/api/v1/public"
SINPAD_UBIGEOS = "https://sinpadgrd.indeci.gob.pe/c4-emergencia/api/v1/public/ubigeos"


def sinpad_ubigeos(c: ClienteEstado) -> list[dict]:
    """District codes of the public SINPAD portal (department, province, district, code)."""
    return c.get(SINPAD_UBIGEOS, cache="sinpad_ubigeos.json").json()["data"]["list"]


def sinpad_emergencias(c: ClienteEstado, ubigeo: str, desde: str, hasta: str, tamano: int = 100) -> list[dict]:
    """Public SINPAD emergencies of a district between two dates (dd/MM/yyyy), all pages.

    Anonymous JSON endpoint behind https://sinpad.indeci.gob.pe/portal/coe/emergencias/lista-emergencias;
    it lists only SINPAD v2.1 (2020 on): earlier years return nothing.
    """
    out: list[dict] = []
    pagina = 1
    while True:
        j = c.get(f"{SINPAD}/emergencias", {"pageNumber": pagina, "pageSize": tamano, "fechaInicio": desde,
                                             "fechaFin": hasta, "ubigeo": ubigeo},
                  cache=f"sinpad_{ubigeo}_{desde.replace('/', '')}_{hasta.replace('/', '')}_{pagina}.json").json()
        datos = j["data"]
        out += datos["items"]
        if pagina >= datos["page"]["totalPages"]:
            return out
        pagina += 1


DISTRITOS_SINPAD = {
    "LURIGANCHO-CHOSICA": "150118", "CHACLACAYO": "150107", "ATE": "150103", "CIENEGUILLA": "150109",
    "RICARDO PALMA": "260714", "SANTA EULALIA": "260728", "MATUCANA": "260701", "CALLAHUANCA": "260703",
    "SAN BARTOLOME": "260717", "SAN MATEO": "260722", "SANTA CRUZ DE COCACHACRA": "260727",
}
# Districts of the study area proper (Chosica, Chaclacayo, Santa Eulalia valley); Matucana and the
# others are upstream or neighbouring and are kept out of the huaico catalogue.
DISTRITOS_ZONA = {"LURIGANCHO-CHOSICA", "CHACLACAYO", "RICARDO PALMA", "SANTA EULALIA", "CALLAHUANCA"}
PELIGROS_LLUVIA = ("LLUVIAS INTENSAS", "HUAICO", "INUNDACIÓN", "DESLIZAMIENTO", "DERRUMBE", "COLAPSO DE ESTRUCTURA POR AGENTE")

# Quebradas that state agencies name as priorities for the 2026-27 El Niño (all from public news
# of the agencies; the lists are partial where the source says so).
PRIORIZADAS = [
    # ANIN: cartera de 13 quebradas de la cuenca del Rímac (Andina, 10-09-2026)
    *[("ANIN", q, "obras (10 primeras, más de S/150 millones)" if i < 10 else "diseño (se suman en septiembre)",
       "https://andina.pe/agencia/noticia-anin-destinara-mas-s360-millones-para-intervenir-13-quebradas-de-cuenca-del-rimac-1091298.aspx",
       "2026-09-10")
      for i, q in enumerate(["La Libertad", "Carosio", "Mariscal Castilla", "Santo Domingo", "Rayito de Sol", "Yanacoto",
                             "Chacrasana", "La Ronda", "Quirio", "Pedregal", "La Laguna", "San Francisco Ñaña", "Vizcachera"])],
    # CENEPRED: quebradas que se activan con lluvias de menor intensidad / quebradas secas de Lima Este
    *[("CENEPRED", q, "se activan incluso con lluvias de menor intensidad",
       "https://andina.pe/agencia/noticia-lluvias-por-nino-quebradas-podrian-activarse-y-zonas-estarian-riesgo-1093833.aspx", "2026-10")
      for q in ("Pedregal", "Quirio", "Carapongo")],
    *[("CENEPRED", q, "quebrada seca de Lima Este con exposición alta",
       "https://m.panamericana.pe/24horas/locales/470007-fenomeno-nino-12-distritos-enfrentan-riesgo-alto-activacion-quebradas",
       "2026-06-17") for q in ("Santo Domingo", "Cusipata", "Huascarán")],
    # ANA: barreras dinámicas (12 en Lima y Huarochirí) y priorizadas
    *[("ANA", q, "barrera dinámica", "https://ahora.com.pe/policiales/ana-barreras-dinamicas-huaicos-lima-huarochiri", "2026-10")
      for q in ("Huayaringa", "Cupiche", "La Ronda", "Señor de los Milagros", "Cashahuacra 1", "Cashahuacra 2", "Quirio")],
    ("ANA", "Los Cóndores 1 y 2", "priorizadas para barreras dinámicas y diques",
     "https://www.infobae.com/peru/2026/10/12/el-aluvion-de-chile-y-la-advertencia-para-lima-las-quebradas-de-chaclacayo-bajo-alerta-tras-riesgos-de-huaicos-por-el-fenomeno-el-nino/",
     "2026-10-12"),
]


def comparar_priorizadas(referencias: list[dict], ranking: pandas.DataFrame) -> pandas.DataFrame:  # noqa: F821
    """Official priority lists next to our posterior rank (Niño season), when the name has a basin.

    `referencias` come from `quebradas.cargar_referencias`; `ranking` is ranking_bayes_quebradas_nino.csv
    with columns `slug`, `rango_mediano`, `p_top5`.
    """
    import pandas as pd

    alias = {}
    for r in referencias:
        for a in (r["nombre"], *r["alias"]):
            alias[normalizar(a)] = r
    rk = ranking.set_index("slug")
    filas = []
    for entidad, q, medida, url, fecha in PRIORIZADAS:
        ref = alias.get(normalizar(q)) or alias.get(normalizar(re.sub(r"\s*\d+( y \d+)?$", "", q)))
        slug = ref.get("cuenca_slug") if ref else None
        if ref and not slug:  # named by point or by name only: the slug is the one the geojson gives
            slug = ref["nombre"].lower()
        fila = {"entidad": entidad, "quebrada_oficial": q, "medida": medida, "fecha_fuente": fecha, "fuente": url,
                "nombre_en_referencias": ref["nombre"] if ref else None}
        filas.append((fila, slug))
    out = []
    from .quebradas import slug as _slug

    for fila, slug in filas:
        s = _slug(fila["nombre_en_referencias"]) if fila["nombre_en_referencias"] else None
        s = slug if slug and slug in rk.index else s
        if s in rk.index:
            fila |= {"slug": s, "rango_mediano": float(rk.loc[s, "rango_mediano"]), "p_top5": float(rk.loc[s, "p_top5"])}
        else:
            fila |= {"slug": s, "rango_mediano": None, "p_top5": None}
        out.append(fila)
    return pd.DataFrame(out)


def emergencias_de_lluvia(df: pandas.DataFrame) -> pandas.DataFrame:  # noqa: F821
    """Rain, flood, landslide and mass-movement emergencies of a SINPAD table, with an ISO date."""
    import pandas as pd

    m = df["peligroPrincipal"].fillna("").str.upper().str.contains("|".join(PELIGROS_LLUVIA), regex=True)
    out = df[m].copy()
    f = pd.to_datetime(out["fechaHoraEvento"], format="%d/%m/%Y %H:%M", errors="coerce")
    out["fecha"] = f.dt.strftime("%Y-%m-%d")
    out["hora_local"] = f.dt.strftime("%H:%M")
    return out.sort_values(["fecha", "hora_local"])


def huaicos_sinpad_nuevos(df: pandas.DataFrame, fechas_catalogo: set) -> pandas.DataFrame:  # noqa: F821
    """SINPAD «HUAICO» emergencies in the study districts whose day is not yet in the catalogue,
    in the schema of catalogo/eventos*.csv."""
    import pandas as pd

    e = emergencias_de_lluvia(df)
    h = e[e["peligroPrincipal"].str.upper().str.contains("HUAICO") & e["distrito"].isin(DISTRITOS_ZONA)]
    h = h[~pd.to_datetime(h["fecha"]).dt.date.isin(fechas_catalogo)]
    filas = []
    for r in h.itertuples():
        filas.append({
            "fecha": r.fecha, "precision_fecha": "dia", "hora_local": r.hora_local,
            "distrito": r.distrito.title().replace("Lurigancho-Chosica", "Lurigancho-Chosica"),
            "quebradas": "(sin quebrada)",
            "fuente": f"INDECI, SINPAD portal público, emergencia N° {r.codigoSinpad}, peligro principal «HUAICO», "
                      f"nivel {r.nivel} (https://sinpad.indeci.gob.pe/portal/coe/emergencias/lista-emergencias, consultada el 31-10-2026)",
            "confianza": "alta", "notas": "Registro oficial de emergencia; no dice qué quebrada se activó",
        })
    return pd.DataFrame(filas)
