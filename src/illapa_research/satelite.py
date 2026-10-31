"""Objective activation labels from satellite change detection (pilot).

Why: every label of the catalogue exists because somebody reported it. A debris flow leaves a scar
(scoured channel, fresh sediment on the fan and the road) whether or not anyone writes about it, so
the change between a clear scene before and a clear scene after an event is an observation that does
not depend on reporting. This module reads Sentinel-2 L2A (2017 on) and Landsat collection 2
(1982 on) from the open Planetary Computer catalogue (anonymous, no account; the client only asks the
public endpoint to sign the file URLs) and summarises the change per quebrada basin.

Nothing here decides that a quebrada "activated": it produces change scores that are compared with the
scores of control pairs (scenes with no event in between) and with the catalogue, see
`docs/25-etiquetas-con-satelite.md`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

COLECCION_S2 = "sentinel-2-l2a"
COLECCION_LANDSAT = "landsat-c2-l2"
# Classes of the Sentinel-2 scene classification that are not usable ground: cloud shadow, cloud
# (medium, high), thin cirrus, snow; plus saturated/defective and no data.
SCL_INVALIDAS = (0, 1, 3, 8, 9, 10, 11)


@dataclass
class Escena:
    fecha: str
    nubes_escena: float
    item: object


def buscar(coleccion: str, bbox: tuple[float, float, float, float], desde: str, hasta: str, nubes_max: float = 100.0):
    """Scenes of a collection over a lon/lat box, newest last."""
    import planetary_computer as pc
    import pystac_client

    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
    items = list(cat.search(collections=[coleccion], bbox=list(bbox), datetime=f"{desde}/{hasta}", max_items=400).items())
    out = [Escena(i.datetime.date().isoformat(), float(i.properties.get("eo:cloud_cover", 100.0)), i) for i in items]
    return sorted([e for e in out if e.nubes_escena <= nubes_max], key=lambda e: e.fecha)


def cubre(item, lon: float, lat: float) -> bool:
    from shapely.geometry import Point, shape

    return shape(item.geometry).contains(Point(lon, lat))


def leer_ventana(href: str, bbox_ll: tuple[float, float, float, float], paso_m: float = 20.0):
    """Read a COG over a lon/lat box into a grid of `paso_m` metres. Returns (array, transform, crs)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with rasterio.open(href) as ds:
        x0, y0, x1, y1 = transform_bounds("EPSG:4326", ds.crs, *bbox_ll)
        ancho, alto = round((x1 - x0) / paso_m), round((y1 - y0) / paso_m)
        ventana = from_bounds(x0, y0, x1, y1, ds.transform)
        a = ds.read(1, window=ventana, out_shape=(alto, ancho), resampling=Resampling.nearest, boundless=True,
                    fill_value=0)
        return a.astype(np.float32), from_origin(x0, y1, paso_m, paso_m), ds.crs


def indices(b04: np.ndarray, b08: np.ndarray, b11: np.ndarray, b12: np.ndarray) -> dict[str, np.ndarray]:
    """NDVI, NBR, bare-soil index and a SWIR brightness, from reflectance (0-1)."""
    eps = 1e-6
    ndvi = (b08 - b04) / (b08 + b04 + eps)
    nbr = (b08 - b12) / (b08 + b12 + eps)
    bsi = ((b11 + b04) - (b08 + 0.0)) / ((b11 + b04) + (b08 + 0.0) + eps)
    return {"ndvi": ndvi, "nbr": nbr, "bsi": bsi, "swir": b11}


def leer_s2(escena: Escena, bbox_ll: tuple[float, float, float, float], paso_m: float = 20.0):
    """Sentinel-2 L2A bands of one scene over the box: indices, valid-pixel mask, transform, crs."""
    a = escena.item.assets
    b = {}
    refl = {}
    for k in ("B04", "B08", "B11", "B12", "SCL"):
        arr, tr, crs = leer_ventana(a[k].href, bbox_ll, paso_m)
        b[k] = arr
        if k != "SCL":  # scale and offset come with the asset (the offset changed with baseline 04.00, 2022)
            r = (a[k].extra_fields.get("raster:bands") or [{}])[0]
            refl[k] = np.clip(arr * float(r.get("scale", 1e-4)) + float(r.get("offset", 0.0)), 0, 1.5)
    valido = ~np.isin(b["SCL"].astype(int), SCL_INVALIDAS) & (refl["B08"] > 0)
    return indices(refl["B04"], refl["B08"], refl["B11"], refl["B12"]), valido, tr, crs


def mascara_cuenca(geom_ll: dict, transform, crs, forma: tuple[int, int]) -> np.ndarray:
    """Boolean raster of a lon/lat polygon on the scene grid."""
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom

    g = transform_geom("EPSG:4326", crs, geom_ll)
    return geometry_mask([g], out_shape=forma, transform=transform, invert=True)


def mascara_salida(lon: float, lat: float, radio_m: float, transform, crs, forma: tuple[int, int]) -> np.ndarray:
    """Boolean raster of a disc around the outlet of a basin (where the fan and the road are)."""
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    cols = transform.c + (np.arange(forma[1]) + 0.5) * transform.a
    filas = transform.f + (np.arange(forma[0]) + 0.5) * transform.e
    X, Y = np.meshgrid(cols, filas)
    return (X - x) ** 2 + (Y - y) ** 2 <= radio_m**2


def cambio(antes: dict[str, np.ndarray], despues: dict[str, np.ndarray], validos: np.ndarray) -> dict[str, np.ndarray]:
    """Per-pixel change (after minus before), NaN where either scene is not usable."""
    return {k: np.where(validos, despues[k] - a, np.nan) for k, a in antes.items()}


def resumen_cuenca(d: dict[str, np.ndarray], mascara: np.ndarray, minimo_valido: float = 0.5) -> dict[str, float]:
    """Mean and 10th/90th percentile of each change index inside a mask; NaN if too few valid pixels."""
    out: dict[str, float] = {"pixeles": int(mascara.sum())}
    n = max(int(mascara.sum()), 1)
    for k, a in d.items():
        v = a[mascara]
        ok = v[~np.isnan(v)]
        out["validos_" + k] = len(ok) / n
        if len(ok) / n < minimo_valido or len(ok) < 10:
            out.update({f"{k}_media": np.nan, f"{k}_p10": np.nan, f"{k}_p90": np.nan})
        else:
            out.update({f"{k}_media": float(ok.mean()), f"{k}_p10": float(np.percentile(ok, 10)),
                        f"{k}_p90": float(np.percentile(ok, 90))})
    return out


# ---------------------------------------------------------------------------- seasonal pilot
VENTANA_ANTES = ("-10-15", "-12-15")  # of the previous year
VENTANA_DESPUES = ("-05-01", "-08-31")
RADIO_SALIDA_M = 700.0
VALIDO_MIN = 0.8
PRIMARIA = ("nbr_media", -1)  # pre-registered: a scar lowers NBR
SECUNDARIAS = (("ndvi_media", -1), ("swir_media", +1))


def _fraccion_valida(escena: Escena, bbox, salidas, paso_m: float = 20.0):
    scl, tr, crs = leer_ventana(escena.item.assets["SCL"].href, bbox, paso_m)
    val = ~np.isin(scl.astype(int), SCL_INVALIDAS)
    fr = []
    for lon, lat in salidas:
        m = mascara_salida(lon, lat, RADIO_SALIDA_M, tr, crs, val.shape)
        fr.append(float(val[m].mean()) if m.sum() else np.nan)
    return float(np.nanmean(fr)), fr


def elegir_escena(escenas: list[Escena], bbox, salidas, objetivo: str):
    """Scene with most valid pixels at the outlets (ties: closest to `objetivo`, ISO date)."""
    mejor = None
    for e in escenas:
        try:
            media, _ = _fraccion_valida(e, bbox, salidas)
        except Exception:  # noqa: BLE001, S112 - a broken asset only removes that scene
            continue
        dist = abs((np.datetime64(e.fecha) - np.datetime64(objetivo)).astype(int))
        clave = (round(media, 2), -dist)
        if mejor is None or clave > mejor[0]:
            mejor = (clave, e, media)
    return (mejor[1], mejor[2]) if mejor else (None, 0.0)


def cambio_temporada(anio: int, cuencas: list[dict], bbox) -> list[dict]:
    """Change between a clean scene before and one after the rainy season of `anio`, per basin."""
    lon_c, lat_c = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    salidas = [(c["salida_lon"], c["salida_lat"]) for c in cuencas]
    antes = [e for e in buscar(COLECCION_S2, bbox, f"{anio - 1}{VENTANA_ANTES[0]}", f"{anio - 1}{VENTANA_ANTES[1]}")
             if cubre(e.item, lon_c, lat_c)]
    despues = [e for e in buscar(COLECCION_S2, bbox, f"{anio}{VENTANA_DESPUES[0]}", f"{anio}{VENTANA_DESPUES[1]}")
               if cubre(e.item, lon_c, lat_c)]
    e0, _v0 = elegir_escena(antes, bbox, salidas, f"{anio - 1}-12-01")
    e1, _v1 = elegir_escena(despues, bbox, salidas, f"{anio}-06-15")
    if e0 is None or e1 is None:
        return []
    i0, val0, tr, crs = leer_s2(e0, bbox)
    i1, val1, _, _ = leer_s2(e1, bbox)
    val = val0 & val1
    d = cambio(i0, i1, val)
    filas = []
    for c in cuencas:
        m = mascara_salida(c["salida_lon"], c["salida_lat"], RADIO_SALIDA_M, tr, crs, val.shape)
        x = resumen_cuenca(d, m, VALIDO_MIN)
        x.update(slug=c["slug"], temporada=anio, antes=e0.fecha, despues=e1.fecha)
        filas.append(x)
    return filas


def auc_dentro_de_temporada(tabla, columna: str, signo: int, n_perm: int = 2000, semilla: int = 0) -> dict[str, float]:
    """AUC of the evidence (expected direction `signo` times the within-season z-score) against activation.

    `signo` is the direction the index is expected to move when the basin activated (-1: it falls).
    The p-value shuffles the labels inside each season.
    """
    from sklearn.metrics import roc_auc_score

    t = tabla.dropna(subset=[columna]).copy()
    t["z"] = signo * t.groupby("temporada")[columna].transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    t = t[t.groupby("temporada")["activa"].transform(lambda s: 0 < s.sum() < len(s))]
    if t.empty or t["activa"].nunique() < 2:
        return {"auc": float("nan"), "p": float("nan"), "n": len(t), "positivos": int(t["activa"].sum()) if len(t) else 0}
    y = t["activa"].to_numpy().astype(int)
    score = t["z"].to_numpy()  # higher = more evidence of a scar
    auc = float(roc_auc_score(y, score))
    rng = np.random.default_rng(semilla)
    grupos = [np.flatnonzero(t["temporada"].to_numpy() == k) for k in t["temporada"].unique()]
    mayores = 0
    for _ in range(n_perm):
        yp = y.copy()
        for g in grupos:
            yp[g] = rng.permutation(y[g])
        mayores += roc_auc_score(yp, score) >= auc
    return {"auc": auc, "p": float((1 + mayores) / (1 + n_perm)), "n": len(t), "positivos": int(y.sum())}


# ---------------------------------------------------------------------------- pilot v2
# Fixed before the v2 run (see docs/25): channel mask from the DEM instead of a disc around the outlet,
# 10 m bands, median composites of up to three clean scenes per window, two-way standardisation by
# basin and season, primary index NBR (expected to fall), 2 000 within-season permutations.
# Decision rule: "supported" only if the primary AUC is at least 0.65 with p < 0.05.
UMBRAL_CAUCE_KM2 = 0.1
RADIO_CAUCE_M = 20.0
PASO_V2_M = 10.0
N_COMPUESTO = 3
PIXELES_MIN = 30
AUC_MIN_V2 = 0.65


def celdas_cauce(teselas, ruta_osm, cuencas_geo: list[dict], umbral_km2: float = UMBRAL_CAUCE_KM2) -> dict[str, np.ndarray]:
    """UTM 18S centres (x, y) of the channel cells (upstream area >= threshold) inside each basin.

    `cuencas_geo`: GeoJSON features with ``properties.slug`` and a lon/lat polygon. Uses the same
    conditioned DEM and flow accumulation as the basin delineation.
    """
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom

    from . import quebradas as Q

    z, tr = Q.mosaico_utm(list(teselas))
    t = Q.acondicionar(z, tr, Q.rios_osm(ruta_osm))
    celda_km2 = Q.RESOLUCION_M**2 / 1e6
    es_cauce = t.acc * celda_km2 >= umbral_km2
    out: dict[str, np.ndarray] = {}
    for f in cuencas_geo:
        slug = f["properties"].get("slug")
        if not slug:
            continue
        g = transform_geom("EPSG:4326", Q.CRS_UTM, f["geometry"])
        dentro = geometry_mask([g], out_shape=z.shape, transform=tr, invert=True)
        filas, cols = np.nonzero(es_cauce & dentro)
        xs = tr.c + (cols + 0.5) * tr.a
        ys = tr.f + (filas + 0.5) * tr.e
        out[slug] = np.column_stack([xs, ys])
    return out


def mascara_en_rejilla(puntos: np.ndarray, transform, forma: tuple[int, int], radio_m: float = RADIO_CAUCE_M) -> np.ndarray:
    """Boolean raster with the given UTM points burnt on the scene grid and dilated by `radio_m`."""
    from scipy.ndimage import binary_dilation

    m = np.zeros(forma, dtype=bool)
    if len(puntos) == 0:
        return m
    cols = np.floor((puntos[:, 0] - transform.c) / transform.a).astype(int)
    filas = np.floor((puntos[:, 1] - transform.f) / transform.e).astype(int)
    ok = (cols >= 0) & (cols < forma[1]) & (filas >= 0) & (filas < forma[0])
    m[filas[ok], cols[ok]] = True
    r = max(round(radio_m / abs(transform.a)), 1)
    yy, xx = np.ogrid[-r : r + 1, -r : r + 1]
    return binary_dilation(m, structure=(xx**2 + yy**2 <= r**2))


def leer_s2_paso(escena: Escena, bbox_ll, paso_m: float = PASO_V2_M):
    """Like `leer_s2` but 10 m bands are read at 10 m and the 20 m ones are repeated onto that grid."""
    a = escena.item.assets
    refl, tr, crs = {}, None, None
    for k in ("B04", "B08", "B11", "B12"):
        nativo = 10.0 if k in ("B04", "B08") else 20.0
        arr, tr_k, crs = leer_ventana(a[k].href, bbox_ll, nativo)
        if nativo != paso_m:
            f = round(nativo / paso_m)
            arr = np.kron(arr, np.ones((f, f), dtype=arr.dtype))
        r = (a[k].extra_fields.get("raster:bands") or [{}])[0]
        refl[k] = np.clip(arr * float(r.get("scale", 1e-4)) + float(r.get("offset", 0.0)), 0, 1.5)
        if tr is None:
            tr = from_origin_like(tr_k, paso_m)
    scl, _, _ = leer_ventana(a["SCL"].href, bbox_ll, 20.0)
    f = round(20.0 / paso_m)
    scl = np.kron(scl, np.ones((f, f), dtype=scl.dtype))
    forma = refl["B08"].shape
    scl = scl[: forma[0], : forma[1]]
    valido = ~np.isin(scl.astype(int), SCL_INVALIDAS) & (refl["B08"][: scl.shape[0], : scl.shape[1]] > 0)
    for k in refl:
        refl[k] = refl[k][: scl.shape[0], : scl.shape[1]]
    return indices(refl["B04"], refl["B08"], refl["B11"], refl["B12"]), valido, tr, crs


def from_origin_like(transform, paso_m: float):
    from rasterio.transform import from_origin

    return from_origin(transform.c, transform.f, paso_m, paso_m)


def compuesto(escenas: list[Escena], bbox_ll, paso_m: float = PASO_V2_M):
    """Pixel-wise median of the indices of several clean scenes (invalid pixels ignored)."""
    pilas: dict[str, list[np.ndarray]] = {}
    tr = crs = None
    for e in escenas:
        ind, val, tr, crs = leer_s2_paso(e, bbox_ll, paso_m)  # grid is the same for every scene
        for k, v in ind.items():
            pilas.setdefault(k, []).append(np.where(val, v, np.nan))
    if not pilas:
        return None
    med = {k: np.nanmedian(np.stack(v), axis=0) for k, v in pilas.items()}
    return med, tr, crs


def elegir_varias(escenas: list[Escena], bbox, salidas, objetivo: str, n: int = N_COMPUESTO, minimo: float = VALIDO_MIN):
    """Up to `n` scenes with at least `minimo` valid pixels at the outlets, best first."""
    ranking = []
    for e in escenas:
        try:
            media, _ = _fraccion_valida(e, bbox, salidas)
        except Exception:  # noqa: BLE001, S112 - a broken asset only removes that scene
            continue
        if media >= minimo:
            dist = abs((np.datetime64(e.fecha) - np.datetime64(objetivo)).astype(int))
            ranking.append((round(media, 2), -dist, e))
    ranking.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [r[2] for r in ranking[:n]]


def cambio_temporada_v2(anio: int, bbox, salidas, cauces: dict[str, np.ndarray]) -> list[dict]:
    """Season change per basin over the channel mask, from median composites before and after."""
    lon_c, lat_c = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    antes = [e for e in buscar(COLECCION_S2, bbox, f"{anio - 1}{VENTANA_ANTES[0]}", f"{anio - 1}{VENTANA_ANTES[1]}")
             if cubre(e.item, lon_c, lat_c)]
    despues = [e for e in buscar(COLECCION_S2, bbox, f"{anio}{VENTANA_DESPUES[0]}", f"{anio}{VENTANA_DESPUES[1]}")
               if cubre(e.item, lon_c, lat_c)]
    e0 = elegir_varias(antes, bbox, salidas, f"{anio - 1}-12-01")
    e1 = elegir_varias(despues, bbox, salidas, f"{anio}-06-15")
    if not e0 or not e1:
        return []
    c0, tr, _ = compuesto(e0, bbox)
    c1, _, _ = compuesto(e1, bbox)
    forma = c0["nbr"].shape
    d = {k: c1[k] - c0[k] for k in c0}
    filas = []
    for slug, pts in cauces.items():
        m = mascara_en_rejilla(pts, tr, forma)
        x = resumen_cuenca(d, m, 0.5)
        if x.get("validos_nbr", 0) * x["pixeles"] < PIXELES_MIN:
            x.update({k: np.nan for k in x if k.endswith(("_media", "_p10", "_p90"))})
        x.update(slug=slug, temporada=anio, antes=";".join(e.fecha for e in e0), despues=";".join(e.fecha for e in e1))
        filas.append(x)
    return filas


def dos_vias(tabla, columna: str):
    """Remove basin and season means (alternating projections); returns a long table."""
    x = tabla.pivot(index="slug", columns="temporada", values=columna).dropna(how="all")
    x = x.loc[x.notna().sum(axis=1) >= 4]
    for _ in range(10):
        x = x.sub(x.mean(axis=1), axis=0).sub(x.mean(axis=0), axis=1)
    return x.stack(future_stack=True).rename(columna).dropna().reset_index()


def auc_dos_vias(tabla, columna: str, signo: int, n_perm: int = 2000, semilla: int = 0) -> dict[str, float]:
    """AUC after two-way standardisation, with within-season permutations."""
    z = dos_vias(tabla, columna).merge(tabla[["slug", "temporada", "activa"]], on=["slug", "temporada"])
    return auc_dentro_de_temporada(z, columna, signo, n_perm, semilla)
