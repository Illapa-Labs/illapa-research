"""Correct the UK Met Office rain of the alert map against PISCOp, cell by cell (docs/26, stage 1).

Chapter 14 corrected one series (the mean of the six PISCOp cells over the Rímac valley) and found
the model marks about 2.6 times the observed rain. The alert map serves the forecast on the nodes of
0.1° grids (`catalogo/zonas_pronostico.json`): node (row, col) is at latitude `north - row*step` and
longitude `west + col*step`, as `illapa-engine/src/forecast.rs` asks Open-Meteo. This module fits
one correction per node, so the map can show amounts that mean what they say.

* **Observed rain at a node.** PISCOp v3.0 cell centres sit at x.x5°, so every node is the common
  corner of four cells: the node gets their mean.
* **Rain day.** SENAMHI's day runs from 7 a.m. to 7 a.m. Lima time (12 to 12 UTC); model hours are
  summed over the same window (only complete days), as in `correccion_sesgo.serie_modelo`.
* **Two regimes.** December to April (rains) and May to November (dry), each fitted on its own.
* **Pooling.** Three rainy seasons are few for one node, so each node is fitted on the days of the
  nodes around it (a 3 x 3 window by default) with the same relative ranks: a quantile map learns
  the shape of the bias, which changes smoothly in space.
* **No look-ahead.** `corregir_fuera_de_anio` corrects every hydrological year (July to June) with a
  fit made on the other years only.

A monotone correction does not change the order of the days at a node, so it cannot catch more
huaico days by itself (chapter 14): it fixes how many millimetres the map shows.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .correccion_sesgo import Escala, MapeoCuantiles, metricas

ZONAS = Path(__file__).resolve().parents[2] / "catalogo" / "zonas_pronostico.json"
INICIO_DIA_UTC = 12  # 7 a.m. in Lima
MESES_LLUVIAS = (12, 1, 2, 3, 4)
PERCENTILES = (90, 95, 99)


def zona(id_: str, ruta: Path = ZONAS) -> dict:
    for z in json.loads(Path(ruta).read_text(encoding="utf-8"))["zonas"]:
        if z["id"] == id_:
            return z
    raise KeyError(id_)


def nodos(z: dict) -> pd.DataFrame:
    """The nodes the engine asks for: cell index, row, column, latitude and longitude."""
    filas = []
    for c in z["cells"]:
        r, k = divmod(c, z["cols"])
        filas.append({"celda": c, "fila": r, "col": k, "lat": round(z["north"] - r * z["step"], 4),
                      "lon": round(z["west"] + k * z["step"], 4)})
    return pd.DataFrame(filas).set_index("celda")


def regimen(fechas: pd.DatetimeIndex) -> np.ndarray:
    return np.where(np.isin(fechas.month, MESES_LLUVIAS), "lluvias", "seca")


def anio_hidrologico(fechas: pd.DatetimeIndex) -> np.ndarray:
    """July to June years, named by the year in which they end (the rainy season's January)."""
    return np.where(fechas.month >= 7, fechas.year + 1, fechas.year)


def diario_desde_horas(horas: pd.DataFrame) -> pd.DataFrame:
    """Hourly UTC rain (hours x nodes) to SENAMHI rain days (12 to 12 UTC), indexed by the day they start.

    Days with fewer than 24 hours are NaN.
    """
    h = horas.sort_index()
    h = h[~h.index.duplicated()]
    h.index = h.index - pd.Timedelta(hours=INICIO_DIA_UTC)
    suma = h.resample("D").sum(min_count=24)
    cuenta = h.resample("D").count()
    return suma.where(cuenta == 24)


def pisco_en_nodos(ruta_nc: Path, nd: pd.DataFrame) -> pd.DataFrame:
    """Daily PISCOp at every node: mean of the four cells around it (days x nodes)."""
    import netCDF4

    ds = netCDF4.Dataset(str(ruta_nc))
    lon = np.asarray(ds.variables["longitude"][:], dtype=float)
    lat = np.asarray(ds.variables["latitude"][:], dtype=float)
    pad = 0.06
    ii = np.flatnonzero((lat >= nd["lat"].min() - pad) & (lat <= nd["lat"].max() + pad))
    jj = np.flatnonzero((lon >= nd["lon"].min() - pad) & (lon <= nd["lon"].max() + pad))
    bloque = ds.variables["precipitation"][:, ii.min() : ii.max() + 1, jj.min() : jj.max() + 1]
    bloque = np.ma.filled(bloque.astype("float32"), np.nan)
    la, lo = lat[ii.min() : ii.max() + 1], lon[jj.min() : jj.max() + 1]
    tiempo = ds.variables[ds.variables["precipitation"].dimensions[0]]
    if " since " in getattr(tiempo, "units", ""):
        fechas = pd.DatetimeIndex(netCDF4.num2date(tiempo[:], tiempo.units, only_use_cftime_datetimes=False,
                                                   only_use_python_datetimes=True)).normalize()
    else:  # PISCOp v3.0 daily: `Z1` counts days 1, 2, ... from 1981-01-01, with units "unknown"
        fechas = pd.Timestamp("1981-01-01") + pd.to_timedelta(np.asarray(tiempo[:], dtype=int) - 1, unit="D")
    out = {}
    for c, r in nd.iterrows():
        i = np.flatnonzero(np.abs(la - r["lat"]) < 0.051)
        j = np.flatnonzero(np.abs(lo - r["lon"]) < 0.051)
        out[c] = np.nanmean(bloque[:, i][:, :, j].reshape(len(fechas), -1), axis=1)
    return pd.DataFrame(out, index=fechas)


def vecinos(nd: pd.DataFrame, radio: int = 1) -> dict[int, list[int]]:
    """Nodes within `radio` rows and columns of each node (itself included)."""
    pos = {(r.fila, r.col): c for c, r in nd.iterrows()}
    return {c: [pos[(r.fila + a, r.col + b)] for a in range(-radio, radio + 1) for b in range(-radio, radio + 1)
                if (r.fila + a, r.col + b) in pos] for c, r in nd.iterrows()}


def ajustar(mod: pd.DataFrame, obs: pd.DataFrame, nd: pd.DataFrame, metodo=MapeoCuantiles, radio: int = 1,
            **kw) -> dict[tuple[str, int], object]:
    """One fit per (regime, node), pooled over the node's neighbourhood, on the days both have."""
    dias = mod.index.intersection(obs.index)
    m, o = mod.loc[dias], obs.loc[dias]
    reg = regimen(dias)
    vec = vecinos(nd, radio)
    out = {}
    for g in ("lluvias", "seca"):
        mg, og = m[reg == g], o[reg == g]
        for c in nd.index:
            cols = [v for v in vec[c] if v in mg.columns]
            a = mg[cols].to_numpy().ravel()
            b = og[cols].to_numpy().ravel()
            ok = ~np.isnan(a) & ~np.isnan(b)
            if ok.sum() < 30:
                continue
            out[(g, c)] = metodo.ajustar(pd.Series(a[ok]), pd.Series(b[ok]), **kw)
    return out


def aplicar(mod: pd.DataFrame, ajustes: dict) -> pd.DataFrame:
    """Apply the fits of `ajustar` (nodes without a fit are left as they are)."""
    out = mod.copy()
    reg = regimen(mod.index)
    for (g, c), f in ajustes.items():
        if c in out.columns:
            sel = reg == g
            out.loc[sel, c] = f.aplicar(mod.loc[sel, c].to_numpy())
    return out


def corregir_fuera_de_anio(mod: pd.DataFrame, obs: pd.DataFrame, nd: pd.DataFrame, metodo=MapeoCuantiles,
                           radio: int = 1, **kw) -> pd.DataFrame:
    """Every hydrological year corrected with a fit on the other years only."""
    dias = mod.index.intersection(obs.index)
    m = mod.loc[dias]
    anios = anio_hidrologico(dias)
    out = pd.DataFrame(np.nan, index=dias, columns=m.columns)
    for a in sorted(set(anios)):
        dentro = anios == a
        aj = ajustar(m[~dentro], obs.loc[dias][~dentro], nd, metodo, radio, **kw)
        out.loc[dentro] = aplicar(m[dentro], aj).to_numpy()
    return out


def evaluar(obs: pd.DataFrame, pred: pd.DataFrame, solo: str = "lluvias") -> pd.DataFrame:
    """Per node: bias, error, correlation and POD/FAR at the node's PISCOp percentiles 90, 95 and 99."""
    dias = obs.index.intersection(pred.index)
    dias = dias[regimen(dias) == solo] if solo else dias
    filas = []
    for c in pred.columns:
        o, p = obs.loc[dias, c].dropna(), pred.loc[dias, c].dropna()
        comun = o.index.intersection(p.index)
        if len(comun) < 30 or o.loc[comun].sum() <= 0:
            continue
        fila = {"celda": c, "dias": len(comun)}
        for q in PERCENTILES:
            u = float(np.percentile(o.loc[comun], q))
            r = metricas(o.loc[comun], p.loc[comun], u)
            fila |= {"sesgo": r["sesgo"], "mae_mm": r["mae_mm"], "r": r["r"], f"pod_p{q}": r["pod"],
                     f"far_p{q}": r["far"], f"umbral_p{q}_mm": u}
        filas.append(fila)
    return pd.DataFrame(filas).set_index("celda")


def resumen(tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Median over nodes of every metric, one row per version (raw, scale, quantile map...)."""
    return pd.DataFrame({k: t.median() for k, t in tablas.items()}).T


def a_json(ajustes: dict, z: dict, metodo: str, fuente: str) -> dict:
    """The correction table the engine can load: per regime and node, the model and observed quantiles
    (or one factor)."""
    tabla: dict = {"zona": z["id"], "metodo": metodo, "dia_lluvia": "12 a 12 UTC (7 a. m. a 7 a. m. de Lima)",
                   "meses_lluvias": list(MESES_LLUVIAS), "fuente": fuente, "regimenes": {"lluvias": {}, "seca": {}}}
    for (g, c), f in sorted(ajustes.items()):
        if isinstance(f, Escala):
            tabla["regimenes"][g][str(c)] = {"factor": round(f.factor, 4)}
        else:
            tabla["regimenes"][g][str(c)] = {"q_modelo": [round(float(x), 3) for x in f.q_modelo],
                                             "q_obs": [round(float(x), 3) for x in f.q_obs]}
    return tabla


# ---------------------------------------------------------------------------- UKMO history from the Open-Meteo bucket
# Measured on 2026-11-04: the Open-Meteo archive of `ukmo_global_deterministic_10km` in the public bucket
# (`s3://openmeteo/data/ukmo_global_deterministic_10km/precipitation/chunk_N.om`, N * 193 hours since 1970, from
# about February 2022) gives exactly the hourly values of the historical-forecast API at the cell the API picks
# (difference 0.0 mm on the six valley cells of chapter 14, February 2024). The API does not take the nearest cell:
# it picks a neighbour with a closer elevation and returns that cell's centre. So the cell of every node is asked
# once from the API (`celdas_api`) and its whole history is then read from the bucket (`ukmo_bucket`), with no quota.
UKMO = "openmeteo/data/ukmo_global_deterministic_10km/precipitation"
UKMO_HORAS_POR_CHUNK = 193
UKMO_NLAT, UKMO_NLON = 1920, 2560
UKMO_DLAT, UKMO_DLON = 180 / UKMO_NLAT, 360 / UKMO_NLON  # 0.09375 and 0.140625 degrees
API_PRONOSTICO = "https://api.open-meteo.com/v1/forecast"


def indice_ukmo(lat: float, lon: float) -> tuple[int, int]:
    """Row and column of the native UKMO cell whose centre is (lat, lon), as the API returns it."""
    return round((lat + 90) / UKMO_DLAT), round((lon + 180) / UKMO_DLON) % UKMO_NLON


def celdas_api(nd: pd.DataFrame, lote: int = 100, pausa: float = 5.0) -> pd.DataFrame:
    """The native UKMO cell the Open-Meteo API uses for every node (one hour asked per node)."""
    import time

    import requests

    filas = []
    ids = list(nd.index)
    for k in range(0, len(ids), lote):
        parte = nd.loc[ids[k : k + lote]]
        params = {"latitude": ",".join(f"{x:.2f}" for x in parte["lat"]),
                  "longitude": ",".join(f"{x:.2f}" for x in parte["lon"]),
                  "hourly": "precipitation", "forecast_hours": 1, "timezone": "GMT",
                  "models": "ukmo_global_deterministic_10km"}
        r = requests.get(API_PRONOSTICO, params=params, timeout=60)
        r.raise_for_status()
        cuerpo = r.json()
        cuerpo = cuerpo if isinstance(cuerpo, list) else [cuerpo]
        for c, res in zip(parte.index, cuerpo, strict=True):
            i, j = indice_ukmo(res["latitude"], res["longitude"])
            filas.append({"celda": c, "lat_ukmo": res["latitude"], "lon_ukmo": res["longitude"], "i": i, "j": j,
                          "elevacion_api": res.get("elevation")})
        time.sleep(pausa)
    return nd.join(pd.DataFrame(filas).set_index("celda"))


def ukmo_bucket(celdas: pd.DataFrame, inicio: str, fin: str, hilos: int = 8) -> pd.DataFrame:
    """Hourly UTC rain (hours x nodes) from the bucket, reading one rectangle of native cells per chunk."""
    from concurrent.futures import ThreadPoolExecutor

    import s3fs
    from omfiles import OmFileReader

    fs = s3fs.S3FileSystem(anon=True)
    i0, i1, j0, j1 = celdas["i"].min(), celdas["i"].max() + 1, celdas["j"].min(), celdas["j"].max() + 1

    def h(t) -> int:
        return int((pd.Timestamp(t) - pd.Timestamp("1970-01-01")).total_seconds() // 3600)

    disponibles = {int(k.rsplit("_", 1)[-1][:-3]) for k in fs.ls(UKMO)}
    chunks = [c for c in range(h(inicio) // UKMO_HORAS_POR_CHUNK, h(fin) // UKMO_HORAS_POR_CHUNK + 1) if c in disponibles]

    def uno(c: int) -> pd.DataFrame:
        for intento in range(4):
            try:
                r = OmFileReader.from_fsspec(fs, f"{UKMO}/chunk_{c}.om")
                try:
                    if len(r.shape) == 2:  # older files: (lat*lon, time)
                        filas = [r.read_array((slice(i * UKMO_NLON + j0, i * UKMO_NLON + j1), slice(0, r.shape[1])))
                                 for i in range(i0, i1)]
                        bloque = np.stack(filas)
                    else:
                        bloque = r.read_array((slice(i0, i1), slice(j0, j1), slice(0, r.shape[2])))
                finally:
                    r.close()
                horas = pd.date_range(pd.Timestamp("1970-01-01") + pd.Timedelta(hours=c * UKMO_HORAS_POR_CHUNK),
                                      periods=bloque.shape[2], freq="h")
                return pd.DataFrame({cel: bloque[r_.i - i0, r_.j - j0] for cel, r_ in celdas.iterrows()}, index=horas)
            except Exception:  # noqa: BLE001 (transient S3 errors: wait and retry)
                import time

                time.sleep(3 * (intento + 1))
        raise RuntimeError(f"No se pudo leer {UKMO}/chunk_{c}.om")

    with ThreadPoolExecutor(hilos) as ex:
        partes = list(ex.map(uno, chunks))
    out = pd.concat(partes).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out.loc[pd.Timestamp(inicio) : pd.Timestamp(fin)]
