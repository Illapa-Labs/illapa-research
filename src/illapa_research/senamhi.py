"""Respectful client for the public data endpoints of the SENAMHI research portal.

What it does: reads the public station catalogue and the series that the portal's own
"Datos hidrometeorológicos" page shows to any visitor, one station and one month at a time, with a
pause between calls and a local cache in ``datos/senamhi/``; and the public WMS/WFS services of the
SENAMHI GeoServer (IDESEP), which the portal offers "sin registrarte".

What it never does: log in, use a key, create an account, or touch the documented REST API that asks
for a registered key. If an endpoint answers 401 or 403 the client stops and says so.

Terms of use (https://www.senamhi.gob.pe/?p=terminos-condiciones, read on 30 October 2026): the
information is public and free; it may be used with or without profit if the SENAMHI is recognised
as its owner with the legend below, in every medium; it may not be sold or presented as official; the
user answers for any modification of the series. The portal adds that the data have no quality
control. This client credits the legend (``LEYENDA``) and the repository's outputs repeat it.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

API = "https://servicios.senamhi.gob.pe/api"
USER_AGENT = "illapa-research/0.1 (+https://github.com/Illapa-Labs/illapa-research; research, low rate)"
PAUSA_S = 2.0
LEYENDA = (
    "Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. "
    "El uso que se le da a esta información es de mi (nuestra) entera responsabilidad"
)
CITA = f"{LEYENDA}. Fuente: SENAMHI, Observatorio Nacional del Tiempo, Agua y Clima del Perú, https://observatorio.senamhi.gob.pe"


class PideCredenciales(RuntimeError):
    """The endpoint asks for credentials (an account or a key): the client stops there and never uses them."""


class Cliente:
    def __init__(self, carpeta: Path = Path("datos/senamhi"), pausa: float = PAUSA_S):
        self.carpeta = Path(carpeta)
        self.cache = self.carpeta / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.pausa = pausa
        self._ultimo = 0.0

    def _ruta(self, ruta: str, params: dict | None) -> Path:
        clave = ruta.strip("/").replace("/", "__")
        if params:
            clave += "__" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        return self.cache / f"{clave}.json"

    def get(self, ruta: str, params: dict | None = None, refrescar: bool = False) -> dict:
        """GET `API/ruta` as JSON, from the cache when it is there."""
        archivo = self._ruta(ruta, params)
        if archivo.exists() and not refrescar:
            return json.loads(archivo.read_text(encoding="utf-8"))
        espera = self.pausa - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        for intento in range(4):
            resp = requests.get(f"{API}/{ruta.strip('/')}", params=params, headers={"User-Agent": USER_AGENT}, timeout=120)
            self._ultimo = time.monotonic()
            if resp.status_code in (401, 403):
                raise PideCredenciales(f"{ruta}: {resp.status_code}; este endpoint pide credenciales y no se usa")
            if resp.status_code < 500 and resp.status_code != 429:
                break
            time.sleep(10 * (intento + 1))
        resp.raise_for_status()
        datos = resp.json()
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return datos

    # --- catalogue (metadata: it can be published)
    def estaciones(self) -> pd.DataFrame:
        d = self.get("station/stations")["data"]
        df = pd.DataFrame(d)
        for c in ("longitude", "latitude"):
            df[c] = pd.to_numeric(df[c])
        return df

    def historicas(self) -> pd.DataFrame:
        """Stations with a long daily series in the researcher download (legacy codes)."""
        return pd.DataFrame(self.get("researchers/historical-download/stations")["data"])

    # --- series (data: local only)
    def periodos(self, estacion: str) -> list[str]:
        """Months (YYYYMM) with data for a station, newest first."""
        try:
            return [p["id"] for p in self.get(f"station/stations/{estacion}/periods")["data"]]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:  # station without published series
                return []
            raise

    def lecturas(self, estacion: str, periodo: str) -> pd.DataFrame:
        """One month of readings of a station (daily or sub-daily, whatever the station reports)."""
        d = self.get(f"station/stations/{estacion}/readings", {"period": periodo})["data"]
        filas = []
        for r in d["readings"]:
            fila = {"fecha": r["date"], "hora": r.get("time") or ""}
            fila.update({v["column"]: v["value"] for v in r["values"]})
            filas.append(fila)
        return pd.DataFrame(filas)

    def serie(self, estacion: str, periodos: list[str] | None = None) -> pd.DataFrame:
        """All the months (or the given ones) of a station, joined."""
        partes = [self.lecturas(estacion, p) for p in (periodos or sorted(self.periodos(estacion)))]
        partes = [p for p in partes if len(p)]
        if not partes:
            return pd.DataFrame()
        df = pd.concat(partes, ignore_index=True)
        hora = df["hora"].replace("", "00:00")
        if df["fecha"].str.contains("/").any():  # automatic stations: dd/mm/yyyy
            df["momento"] = pd.to_datetime(df["fecha"] + " " + hora, format="%d/%m/%Y %H:%M")
        else:
            df["momento"] = pd.to_datetime(df["fecha"] + " " + hora)
        return df.set_index("momento").drop(columns=["fecha", "hora"])

    def diaria_historica(self, codigo_historico: str) -> pd.DataFrame:
        """Daily precipitation and extreme temperatures from the researcher download (since 1989 or so)."""
        d = self.get(f"researchers/historical-download/stations/{codigo_historico}/series")["data"]
        df = pd.DataFrame(d)
        if df.empty:
            return df
        df["fecha"] = pd.to_datetime(df["fecha"] if "fecha" in df else df["date"])
        return df.drop(columns=["date"], errors="ignore").set_index("fecha").rename(
            columns={"precipitation": "lluvia_mm", "maximumTemperature": "tmax", "minimumTemperature": "tmin"}
        )


def distancia_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in km."""
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def cercanas(est: pd.DataFrame, lon: float, lat: float, radio_km: float, tipo: str | None = None) -> pd.DataFrame:
    """Stations within `radio_km` of a point, nearest first (`tipo`: "M" meteorological, "H" hydrological)."""
    d = est.copy()
    d["km"] = [distancia_km(lon, lat, x, y) for x, y in zip(d["longitude"], d["latitude"], strict=True)]
    d = d[d["km"] <= radio_km]
    if tipo:
        d = d[d["typeId"] == tipo]
    return d.sort_values("km")


def completitud(serie: pd.Series, inicio: str, fin: str) -> float:
    """Share of days in [inicio, fin] with a value."""
    dias = pd.date_range(inicio, fin, freq="D")
    s = serie.dropna()
    s = s[~s.index.duplicated()]
    return float(len(s.reindex(dias).dropna()) / len(dias)) if len(dias) else float("nan")


def lluvia_diaria_horaria(serie: pd.DataFrame, columna: str = "N_LLUVIA", minimo_horas: int = 20) -> pd.Series:
    """Daily rain (calendar day) from an hourly gauge; days with fewer than `minimo_horas` hours are NaN."""
    h = serie[columna].astype(float)
    cuenta = h.resample("D").count()
    suma = h.resample("D").sum(min_count=1)
    return suma.where(cuenta >= minimo_horas)


def acuerdo(a: pd.Series, b: pd.Series, dias_evento: list | None = None, rezago: int = 0) -> dict[str, float]:
    """How two daily rain series agree (gauge `a` against reanalysis `b`).

    `rezago` shifts `a` by that many days before comparing (the conventional gauges are read at
    07:00 and report the previous 24 h). Pearson on log(1+x), Spearman, the ratio of the 95th
    percentiles of the wet days, and, for the dates in `dias_evento`, the median of `a` and `b`.
    """
    from scipy.stats import pearsonr, spearmanr

    j = pd.concat([a.shift(rezago).rename("a"), b.rename("b")], axis=1).dropna()
    out = {"n": float(len(j)),
           "pearson_log": float(pearsonr(np.log1p(j["a"].clip(lower=0)), np.log1p(j["b"].clip(lower=0)))[0]),
           "spearman": float(spearmanr(j["a"], j["b"])[0])}
    humedos = j[(j["a"] > 0.5) | (j["b"] > 0.5)]
    out["p95_a"], out["p95_b"] = float(humedos["a"].quantile(0.95)), float(humedos["b"].quantile(0.95))
    if dias_evento:
        ev = j.reindex(pd.DatetimeIndex(dias_evento)).dropna()
        out["n_eventos"] = float(len(ev))
        out["mediana_eventos_a"], out["mediana_eventos_b"] = float(ev["a"].median()), float(ev["b"].median())
    return out


def caracteristicas_pluviometros(lluvia: pd.DataFrame, idx: pd.DatetimeIndex, prefijo: str = "pluv") -> pd.DataFrame:
    """Daily features of a network of gauges (one column per station, mm per day).

    Rain of the day (mean, maximum, number of wet stations) and antecedent rain (previous 7 and
    30 days, mean over stations). Missing stations are ignored day by day, so a feature exists
    whenever at least two stations reported.
    """
    r = lluvia.reindex(idx)
    ok = r.notna().sum(axis=1) >= 2
    f = pd.DataFrame(index=idx)
    media = r.mean(axis=1).where(ok)
    f[f"{prefijo}_media_1d"] = media
    f[f"{prefijo}_max_1d"] = r.max(axis=1).where(ok)
    f[f"{prefijo}_humedas"] = (r > 1.0).sum(axis=1).where(ok)
    f[f"{prefijo}_media_3d"] = media.rolling(3, min_periods=2).sum()
    f[f"{prefijo}_media_7d_previa"] = media.shift(1).rolling(7, min_periods=4).sum()
    f[f"{prefijo}_media_30d_previa"] = media.shift(1).rolling(30, min_periods=15).sum()
    return f


HISTORICAS_NOMBRES = {
    "151209": "chosica", "000543": "nana", "000548": "matucana", "155213": "santa_eulalia",
    "155122": "autisha", "155223": "carampoma", "151205": "canchacalla", "155224": "santiago_tuna",
    "155218": "huaros", "155217": "lachaqui", "151213": "sheque",
}
AUTOMATICAS_NOMBRES = {
    "47278214": "chosica_auto", "472CE45A": "matucana_auto", "111290": "nana_auto",
    "472EC742": "san_mateo_otao_auto", "472CA750": "santiago_tuna_auto", "472E24B0": "santa_eulalia_auto",
}
VALLE = ["chosica", "nana", "chosica_auto", "nana_auto"]


def red_historica(c: Cliente) -> pd.DataFrame:
    """Daily rain (mm) of the conventional gauges near the Rímac and Santa Eulalia valleys."""
    return pd.DataFrame({n: c.diaria_historica(k)["lluvia_mm"] for k, n in HISTORICAS_NOMBRES.items()})


def red_automatica(c: Cliente) -> pd.DataFrame:
    """Daily rain (mm, calendar day) of the automatic stations, summed from hourly readings."""
    out = {}
    for k, n in AUTOMATICAS_NOMBRES.items():
        s = c.serie(k)
        if len(s) and "N_LLUVIA" in s:
            out[n] = lluvia_diaria_horaria(s)
    return pd.DataFrame(out)


def diferencia_ap(y: np.ndarray, p1: np.ndarray, p2: np.ndarray, ts: np.ndarray, n: int = 400, semilla: int = 0) -> dict:
    """Paired bootstrap over whole seasons of AP(p1) - AP(p2): median and 90 % interval."""
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    d = []
    for _ in range(n):
        b = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        if y[b].sum() < 3:
            continue
        d.append(average_precision_score(y[b], p1[b]) - average_precision_score(y[b], p2[b]))
    lo, med, hi = np.percentile(d, [5, 50, 95])
    return {"diferencia_mediana": float(med), "p5": float(lo), "p95": float(hi), "p_mayor_que_0": float(np.mean(np.array(d) > 0))}


def experimento_pluviometros(
    raiz: Path, red: pd.DataFrame, desde: int, hasta: int, n_jobs: int = 4, separar_valle: bool = True
) -> dict:
    """Does a rain-gauge network improve the daily huaico-day model of chapter 05?

    Window `desde`-`hasta` (the years the network covers). Feature sets are compared with season-out
    cross-validation: date only, ERA5 rain, gauges, ERA5 + gauges, and the same with antecedents.
    With `separar_valle` the mountain stations and the valley stations (Chosica, Ñaña) make two
    groups of features. Gauge rain is the rain *of the day* (it is a nowcast: the daily value is read the next morning).
    """
    from . import evaluacion_diaria as E
    from . import modelo_diario as md

    D = md.cargar_datos(Path(raiz))
    X, y, ts, mes = md.matrices(D)
    mask = D.inventario["mask"]
    idx = D.F.index
    sel = ((idx.year >= desde) & (idx.year <= hasta))[mask]
    if separar_valle:
        montana = red.drop(columns=[c for c in VALLE if c in red], errors="ignore")
        valle = red[[c for c in VALLE if c in red]]
        partes = [caracteristicas_pluviometros(montana, idx, "cuenca")]
        if valle.shape[1] >= 2:
            partes.append(caracteristicas_pluviometros(valle, idx, "valle"))
    else:  # a short network: use every station together
        partes = [caracteristicas_pluviometros(red, idx, "red")]
    G = pd.concat(partes, axis=1)[mask][sel]
    G_dia = G[[c for c in G.columns if "7d" not in c and "30d" not in c]]
    ys, tss, ms = y[sel].reset_index(drop=True), ts[sel], mes[sel]
    folds = [f for f in E.pliegues(tss, "temporada") if len(f)]
    era_dia, era_ant = X["lluvia_dia"][sel].reset_index(drop=True), X["antecedentes"][sel].reset_index(drop=True)
    G, G_dia = G.reset_index(drop=True), G_dia.reset_index(drop=True)
    conjuntos = {
        "ERA5 lluvia del día": era_dia,
        "pluviómetros del día": G_dia,
        "pluviómetros del día + previa": G,
        "ERA5 + pluviómetros del día": pd.concat([era_dia, G_dia], axis=1),
        "ERA5 día + antecedentes": pd.concat([era_dia, era_ant], axis=1),
        "ERA5 día + antecedentes + pluviómetros": pd.concat([era_dia, era_ant, G], axis=1),
    }
    pref = E.p_climatologia(ys, ms, folds)
    p = {"solo fecha": pref}
    for k, Xk in conjuntos.items():
        p[k] = md.validar_anidado(Xk, ys, tss, folds, n_jobs=n_jobs).p
    tabla = pd.DataFrame({k: md.metricas_completas(ys.to_numpy(), v, pref) for k, v in p.items()}).T
    return {"tabla": tabla, "p": p, "y": ys.to_numpy(), "ts": tss, "ref": pref, "n_dias": len(ys),
            "n_eventos": int(ys.sum()), "n_temporadas": len(np.unique(tss)), "G": G,
            "fechas": idx[mask][sel]}


# --- IDESEP GeoServer (public OGC services, "sin registrarte"); read-only, cached, one thread
IDESEP = "https://idesep.senamhi.gob.pe/geoserver"


def wfs(c: Cliente, workspace: str, capa: str, bbox: tuple[float, float, float, float] | None = None,
        cql: str | None = None, count: int | None = None, propiedades: list[str] | None = None,
        refrescar: bool = False) -> dict:
    """GeoJSON of a WFS layer (`bbox` in lon/lat: west, south, east, north), cached under `datos/senamhi/ogc/`."""
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": f"{workspace}:{capa}",
              "outputFormat": "application/json"}
    if bbox:
        params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},urn:ogc:def:crs:OGC:1.3:CRS84"
    if cql:
        params["CQL_FILTER"] = cql
    if count:
        params["count"] = count
    if propiedades:
        params["propertyName"] = ",".join(propiedades)
    carpeta = c.carpeta / "ogc"
    carpeta.mkdir(parents=True, exist_ok=True)
    clave = "_".join(f"{k}-{v}" for k, v in sorted(params.items()) if k not in ("service", "version", "request", "outputFormat"))
    nombre = "".join(ch if ch.isalnum() or ch in "-_.," else "~" for ch in clave)[:180]
    archivo = carpeta / f"{nombre}.json"
    if archivo.exists() and not refrescar:
        return json.loads(archivo.read_text(encoding="utf-8"))
    espera = c.pausa - (time.monotonic() - c._ultimo)
    if espera > 0:
        time.sleep(espera)
    resp = requests.get(f"{IDESEP}/{workspace}/ows", params=params, headers={"User-Agent": USER_AGENT}, timeout=180)
    c._ultimo = time.monotonic()
    if resp.status_code in (401, 403):
        raise PideCredenciales(f"{workspace}:{capa}: {resp.status_code}")
    resp.raise_for_status()
    datos = resp.json()
    archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos


# --- products built on the OGC layers ----------------------------------------------------------------
PUNTOS_ESTUDIO = {"Chosica": (-76.70, -11.93), "Santa Eulalia": (-76.667, -11.92),
                  "Matucana": (-76.378, -11.84), "Ticlio": (-76.20, -11.60)}
BBOX_ESTUDIO = (-76.95, -12.06, -76.45, -11.78)
CAPAS_NINOS = {  # (workspace, layer): (event year, trimester); IDESEP precipitation anomaly of the Niño events
    ("g_02_01", "02_01_001_03_001_512_1983_00_00"): (1983, "DEF"), ("g_02_01", "02_01_002_03_001_512_1983_00_00"): (1983, "EFM"),
    ("g_02_01", "02_01_003_03_001_512_1983_00_00"): (1983, "FMA"), ("g_02_02", "02_02_001_03_001_512_1998_00_00"): (1998, "DEF"),
    ("g_02_02", "02_02_002_03_001_512_1998_00_00"): (1998, "EFM"), ("g_02_02", "02_02_003_03_001_512_1998_00_00"): (1998, "FMA"),
    ("g_02_04", "02_04_001_03_001_512_2017_00_00"): (2017, "DEF"), ("g_02_04", "02_04_002_03_001_512_2017_00_00"): (2017, "EFM"),
    ("g_02_04", "02_04_003_03_001_512_2017_00_00"): (2017, "FMA"), ("g_02_05", "02_05_002_03_001_512_2023_00_00"): (2023, "EFM"),
    ("g_02_05", "02_05_003_03_001_512_2023_00_00"): (2023, "FMA"), ("g_02_06", "02_06_001_03_001_512_2024_00_00"): (2024, "DEF"),
    ("g_02_06", "02_06_002_03_001_512_2024_00_00"): (2024, "EFM"),
}
_MESES_TRIM = {"DEF": [(-1, 12), (0, 1), (0, 2)], "EFM": [(0, 1), (0, 2), (0, 3)], "FMA": [(0, 2), (0, 3), (0, 4)]}


def umbrales(c: Cliente) -> pd.DataFrame:
    """Official rain thresholds of the SENAMHI stations (layer `g_umbrales:umbrales_precipitacion`).

    `umbral` is the daily rain (mm) and `umb_acum` the accumulated rain (mm) that raise the alert; the
    snapshot is the day it was read (columns `pp`, `pp_acum`, `fecha` are that day's observation).
    """
    j = wfs(c, "g_umbrales", "umbrales_precipitacion")
    filas = []
    for f in j["features"]:
        x, y = f["geometry"]["coordinates"][:2]
        filas.append({**f["properties"], "lon": x, "lat": y})
    return pd.DataFrame(filas)


def anomalias_ninos(c: Cliente) -> pd.DataFrame:
    """Rain-anomaly class (IDESEP layers of the Niño events) at the study points, by event and trimester."""
    from shapely.geometry import Point, shape

    filas = []
    for (ws, capa), (anio, trim) in CAPAS_NINOS.items():
        for punto, (x, y) in PUNTOS_ESTUDIO.items():
            j = wfs(c, ws, capa, bbox=(x - 0.05, y - 0.05, x + 0.05, y + 0.05))
            p = Point(x, y)
            rangos = {f["properties"].get("rango") for f in j["features"] if shape(f["geometry"]).buffer(0).contains(p)}
            filas.append({"evento": anio, "trimestre": trim, "punto": punto, "rango": "; ".join(sorted(map(str, rangos))) or None})
    d = pd.DataFrame(filas)
    d["anomalia_centro"] = d["rango"].map(_centro_rango)
    return d


def _centro_rango(r) -> float:
    import re

    m = re.match(r"(-?\d+) - (-?\d+)", r) if isinstance(r, str) else None
    return (int(m.group(1)) + int(m.group(2))) / 2 if m else float("nan")


def dias_huaico_por_trimestre(fechas: list, anio: int, trim: str) -> int:
    """Catalogued huaico days in the three months of a DEF / EFM / FMA window of an event year."""
    return sum(1 for f in set(fechas) if any(f.year == anio + off and f.month == m for off, m in _MESES_TRIM[trim]))


def avisos_2020(ruta: Path) -> pd.DataFrame:
    """Meteorological warnings of 2020 that touch the study area (from the cached extraction)."""
    d = pd.DataFrame(json.loads(Path(ruta).read_text(encoding="utf-8")))
    for col in ("f_emi", "fech_ini", "fech_fin"):
        d[col] = pd.to_datetime(d[col], format="%d_%m_%Y", errors="coerce")
    d["nivel_n"] = d["nivel"].str.extract(r"(\d)").astype(float)
    return d.dropna(subset=["fech_ini", "fech_fin"])


def serie_diaria_avisos(av: pd.DataFrame, idx: pd.DatetimeIndex, solo_lluvia: bool = True) -> pd.DataFrame:
    """Highest warning level per day (0 = none) from the 2020 warnings (rain phenomena by default)."""
    if solo_lluvia:  # rain phenomena of the sierra or the coast (rain in the jungle alone does not reach the study area)
        f = av["fenomeno"].fillna("")
        lluvia = f.str.contains("PP|PRECIP|LLUVIA", case=False)
        solo_selva = f.str.contains("SELVA", case=False) & ~f.str.contains("SIERRA|COSTA", case=False)
        av = av[lluvia & ~solo_selva]
    nivel = pd.Series(0.0, index=idx)
    for r in av.itertuples():
        rango = pd.date_range(r.fech_ini, r.fech_fin, freq="D")
        rango = rango.intersection(idx)
        nivel.loc[rango] = np.maximum(nivel.loc[rango], r.nivel_n)
    return pd.DataFrame({"nivel_max": nivel, "aviso": nivel > 0})


def consolidar(c: Cliente, avisos_json: Path | None = None) -> list[Path]:
    """Write the compact tables that the Hugging Face mirror carries (`datos/senamhi/tablas/`).

    One CSV per station series (daily conventional; hourly automatic, gzip), the station catalogue,
    the thresholds, the Niño-event anomaly classes and, if present, the 2020 warnings and the two
    ODC-By datasets of datosabiertos.gob.pe. Raw API caches are not mirrored.
    """
    tablas = c.carpeta / "tablas"
    tablas.mkdir(parents=True, exist_ok=True)
    salida = []
    est = c.estaciones()
    est.to_csv(tablas / "estaciones.csv", index=False)
    salida.append(tablas / "estaciones.csv")
    for k, n in HISTORICAS_NOMBRES.items():
        f = tablas / f"diaria_historica_{n}.csv"
        c.diaria_historica(k).to_csv(f)
        salida.append(f)
    for k, n in AUTOMATICAS_NOMBRES.items():
        s = c.serie(k)
        if len(s):
            f = tablas / f"horaria_{n}.csv.gz"
            s.to_csv(f)
            salida.append(f)
    umbrales(c).to_csv(tablas / "umbrales_precipitacion_2026-10-30.csv", index=False)
    anomalias_ninos(c).to_csv(tablas / "anomalias_ninos_puntos.csv", index=False)
    salida += [tablas / "umbrales_precipitacion_2026-10-30.csv", tablas / "anomalias_ninos_puntos.csv"]
    if avisos_json and Path(avisos_json).exists():
        av = avisos_2020(avisos_json)
        av.to_csv(tablas / "avisos_meteorologicos_2020_zona.csv", index=False)
        salida.append(tablas / "avisos_meteorologicos_2020_zona.csv")
    da = c.carpeta / "datosabiertos"
    if (da / "marcapomacocha.csv").exists():
        pd.read_csv(da / "marcapomacocha.csv").to_csv(tablas / "datosabiertos_marcapomacocha_ODC-By.csv", index=False)
        salida.append(tablas / "datosabiertos_marcapomacocha_ODC-By.csv")
    if (da / "intercambio.csv").exists():
        i = pd.read_csv(da / "intercambio.csv", low_memory=False)
        i[i["ESTACION"].isin(["MATUCANA", "CARANIA"])].to_csv(tablas / "datosabiertos_intercambio_matucana_carania_ODC-By.csv.gz", index=False)
        salida.append(tablas / "datosabiertos_intercambio_matucana_carania_ODC-By.csv.gz")
    return salida


# station of our series -> station of the official threshold table (mm/day, mm accumulated in 3 days)
UMBRAL_DE = {
    "chosica": "CHOSICA", "chosica_auto": "CHOSICA", "nana": "ÑAÑA", "nana_auto": "ÑAÑA", "matucana": "MATUCANA",
    "matucana_auto": "MATUCANA", "santa_eulalia": "SANTA EULALIA", "santa_eulalia_auto": "SANTA EULALIA",
    "san_mateo_otao_auto": "SAN MATEO DE OTAO",
}


def alarma_por_umbral(lluvia: pd.Series, umbral: float, umb_acum: float, idx: pd.DatetimeIndex) -> pd.Series:
    """Day with an official-style alarm: the day's rain reaches `umbral` or the last 3 days reach `umb_acum`.

    The 3-day window is our reading of `umb_acum` (it is three times `umbral` at every station of the
    study area); the SENAMHI does not state the window in the layer.
    """
    r = lluvia.reindex(idx)
    return ((r >= umbral) | (r.rolling(3, min_periods=3).sum() >= umb_acum)).where(r.notna())


def evalua_alarmas(alarma: pd.Series, y: pd.Series, mascara) -> dict[str, float]:
    """POD, false-alarm ratio by days (tolerance +-1 day) and alarm days per 151-day season."""
    a = alarma[mascara]
    yy = y[mascara]
    ok = a.notna()
    a, yy = a[ok].astype(bool), yy[ok]
    yt = (yy | yy.shift(1, fill_value=0) | yy.shift(-1, fill_value=0)).astype(int)
    return {"dias": len(a), "eventos": int(yy.sum()), "dias_alarma_por_temporada": float(a.mean() * 151),
            "POD": float(a[yy == 1].mean()), "FAR_dias": float((yt[a] == 0).mean()) if a.sum() else float("nan")}


def probabilidad_con_presupuesto(p: np.ndarray, y: np.ndarray, fraccion: float) -> dict[str, float]:
    """POD and false-alarm ratio (+-1 day) of a model that alarms on its top `fraccion` of days."""
    corte = np.quantile(p, 1 - fraccion)
    a = p >= corte
    yt = (y | np.r_[0, y[:-1]] | np.r_[y[1:], 0]).astype(int)
    return {"POD": float(y[a].sum() / y.sum()), "FAR_dias": float((yt[a] == 0).mean())}
