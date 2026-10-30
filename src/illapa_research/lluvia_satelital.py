"""Daily rain from sources independent of ERA5, for the points of the daily model (hypothesis T28).

CHIRPS (the Climate Hazards Center server) did not answer, so two other public series are used:

* **PERSIANN-CDR** (NOAA NCEI, 0.25 degrees, daily, 1983 to a few months ago): infrared satellite
  rain adjusted to monthly gauge totals (GPCP). Public domain (NOAA).
* **CPC Global Unified Gauge-Based Analysis** (NOAA PSL, 0.5 degrees, daily; yearly files): interpolated rain
  gauges only, no satellite and no reanalysis. Public domain (NOAA).

Both are read at the grid cell that contains the centre of each predictor point. The centres were
fixed before looking at any result (they are the centres of the CHIRPS boxes of `fuentes.py`).
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# Centres (lon, lat) of the predictor points, fixed in advance.
CENTROS = {
    "chosica": (-76.70, -11.93),
    "santa-eulalia-alta": (-76.40, -11.70),
    "matucana": (-76.38, -11.84),
    "ticlio": (-76.20, -11.60),
    "selva-tarma": (-75.69, -11.42),
}
PERSIANN_RAIZ = "https://www.ncei.noaa.gov/data/precipitation-persiann/access"
_HDF5 = threading.Lock()  # the HDF5 library is not thread-safe: download in parallel, parse one at a time
CPC_URL = "https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.{a}.nc"
USER_AGENT = "illapa-research/0.1 (+https://github.com/Illapa-Labs/illapa-research)"


def celda_mas_cercana(valores: np.ndarray, x: float) -> int:
    """Index of the grid value closest to `x` (the cell that contains it on a regular grid)."""
    return int(np.abs(np.asarray(valores, dtype=float) - x).argmin())


def lon360(lon: float) -> float:
    return lon % 360.0


def archivos_persiann(anio: int, sesion: requests.Session | None = None) -> dict[str, str]:
    """Map 'YYYY-MM-DD' to the file name of the NCEI yearly listing (the name carries a creation date)."""
    s = sesion or requests
    html = s.get(f"{PERSIANN_RAIZ}/{anio}/", headers={"User-Agent": USER_AGENT}, timeout=60).text
    out = {}
    for m in re.finditer(r"(PERSIANN-CDR_v01r01_(\d{8})_c\d{8}\.nc)", html):
        d = m.group(2)
        out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = m.group(1)
    return out


def extraer_persiann(contenido: bytes) -> dict[str, float]:
    """Rain (mm/day) at each centre from one NCEI PERSIANN-CDR daily file (read from memory)."""
    import netCDF4

    ds = netCDF4.Dataset("persiann.nc", mode="r", memory=contenido)
    try:
        var = "precipitation" if "precipitation" in ds.variables else next(
            k for k, v in ds.variables.items() if v.ndim >= 2
        )
        lat, lon = np.asarray(ds["lat"][:]), np.asarray(ds["lon"][:])
        a = np.ma.filled(ds[var][:].astype(float), np.nan)
        dims = [d for d in ds[var].dimensions if d != "time"]
        a = a.reshape(a.shape[-2:])
        if dims == ["lon", "lat"]:  # PERSIANN-CDR stores (time, lon, lat)
            a = a.T
        out = {}
        for nombre, (x, y) in CENTROS.items():
            v = float(a[celda_mas_cercana(lat, y), celda_mas_cercana(lon, lon360(x))])
            out[nombre] = np.nan if v < 0 else v  # fill values are negative
        return out
    finally:
        ds.close()


def serie_cpc(anio: int) -> pd.DataFrame:
    """CPC daily gauge-analysis rain at each centre for one year (a 60 MB file, read from memory)."""
    import netCDF4

    r = requests.get(CPC_URL.format(a=anio), headers={"User-Agent": USER_AGENT}, timeout=600)
    r.raise_for_status()
    with _HDF5:
        ds = netCDF4.Dataset("cpc.nc", mode="r", memory=r.content)
        try:
            lat, lon = np.asarray(ds["lat"][:]), np.asarray(ds["lon"][:])
            tiempo = netCDF4.num2date(ds["time"][:], ds["time"].units, only_use_cftime_datetimes=False,
                                      only_use_python_datetimes=True)
            cols = {}
            for nombre, (x, y) in CENTROS.items():
                i, j = celda_mas_cercana(lat, y), celda_mas_cercana(lon, lon360(x))
                v = np.ma.filled(ds["precip"][:, i, j].astype(float), np.nan)
                cols[nombre] = np.where(v < 0, np.nan, v)
            return pd.DataFrame(cols, index=pd.to_datetime([t.strftime("%Y-%m-%d") for t in tiempo]))
        finally:
            ds.close()


def descargar_cpc(destino: Path, desde: int = 1983) -> Path:
    """One request per year to PSL; writes `lluvia_sat/cpc_diario.csv`."""
    carpeta = destino / "lluvia_sat"
    carpeta.mkdir(parents=True, exist_ok=True)
    partes = []
    for a in range(desde, pd.Timestamp.today().year + 1):
        for intento in range(5):
            try:
                partes.append(serie_cpc(a))
                break
            except (OSError, requests.RequestException):
                time.sleep(10 * (intento + 1))
        else:
            raise RuntimeError(f"PSL no respondió para {a}")
        time.sleep(1)
    out = pd.concat(partes)
    out.index.name = "fecha"
    ruta = carpeta / "cpc_diario.csv"
    out.round(3).to_csv(ruta)
    return ruta


def descargar_persiann(destino: Path, desde_temporada: int = 1984, hilos: int = 3, pausa: float = 0.2) -> Path:
    """November to April of every season, three connections at a time, cached by season.

    About 6 500 files of 1.3 MB: it is polite (a pause after each file), restartable (finished
    seasons are not asked again) and writes `lluvia_sat/persiann_cdr_diario.csv`.
    """
    from concurrent.futures import ThreadPoolExecutor

    carpeta = destino / "lluvia_sat"
    cache = carpeta / "persiann_cache"
    cache.mkdir(parents=True, exist_ok=True)
    hoy = pd.Timestamp.today().normalize()
    sesion = requests.Session()
    listados: dict[int, dict[str, str]] = {}

    def un_dia(fecha: str) -> dict:
        a = int(fecha[:4])
        nombre = listados[a].get(fecha)
        if nombre is None:
            return {"fecha": fecha}
        for _ in range(6):
            try:
                r = sesion.get(f"{PERSIANN_RAIZ}/{a}/{nombre}", headers={"User-Agent": USER_AGENT}, timeout=120)
                r.raise_for_status()
                time.sleep(pausa)
                with _HDF5:
                    return {"fecha": fecha, **extraer_persiann(r.content)}
            except (requests.RequestException, OSError):
                time.sleep(10)
        raise RuntimeError(f"PERSIANN-CDR no respondió para {fecha}")

    partes = []
    for t in range(desde_temporada, hoy.year + 1):
        ruta = cache / f"temporada_{t}.csv"
        if not ruta.exists() or t == hoy.year:
            dias = pd.date_range(f"{t - 1}-11-01", f"{t}-04-30", freq="D")
            for a in {d.year for d in dias}:
                if a not in listados:
                    listados[a] = archivos_persiann(a, sesion)
            fechas = [d.strftime("%Y-%m-%d") for d in dias if d.strftime("%Y-%m-%d") in listados[d.year]]
            with ThreadPoolExecutor(hilos) as pool:
                filas = list(pool.map(un_dia, fechas))
            pd.DataFrame(filas).to_csv(ruta, index=False)
            print(f"  PERSIANN-CDR temporada {t}: {len(filas)} días", flush=True)
        partes.append(pd.read_csv(ruta, parse_dates=["fecha"]))
    out = pd.concat(partes).drop_duplicates("fecha").sort_values("fecha").set_index("fecha")
    destino_csv = carpeta / "persiann_cdr_diario.csv"
    out.round(3).to_csv(destino_csv)
    return destino_csv


def cargar(ruta: Path) -> pd.DataFrame:
    """A daily rain table (index = date, one column per point)."""
    return pd.read_csv(ruta, parse_dates=["fecha"], index_col="fecha")


def variables(lluvia: pd.DataFrame, idx: pd.DatetimeIndex, prefijo: str) -> pd.DataFrame:
    """Rain of the day, of 3 days and of the previous 7 days, per point (`<prefijo>_<punto>_...`)."""
    c = lluvia.reindex(idx)
    out = {}
    for punto in c.columns:
        r = c[punto]
        p = f"{prefijo}_{punto.replace('-', '_')}"
        out[f"{p}_1d"] = r
        out[f"{p}_3d"] = r.rolling(3, min_periods=2).sum()
        out[f"{p}_7d_previa"] = r.shift(1).rolling(7, min_periods=4).sum()
    return pd.DataFrame(out, index=idx)


def delta_ap_gpu(
    X_base: np.ndarray, extra: np.ndarray, y: np.ndarray, ts: np.ndarray, C: float = 0.03,
    n_nulas: int = 200, semilla: int = 0, dispositivo: str | None = None,
) -> dict[str, float]:
    """Change in out-of-fold average precision from adding `extra` columns, with a shifted-block null.

    Same fixed-C ridge-logistic fit and season-out folds for the base, the real block and
    `n_nulas` worlds in which the block is shifted cyclically inside every season (keeping its
    values and autocorrelation, losing its link with the day). Runs on the GPU when there is one.
    """
    from . import gpu as G

    temporadas = np.unique(ts)
    n = len(y)
    por_temp = {s: np.flatnonzero(ts == s) for s in temporadas}
    Mk = np.stack([~np.isin(np.arange(n), por_temp[s]) for s in temporadas])
    Y = np.tile(y.astype(float), (len(temporadas), 1))

    def ap_de(X: np.ndarray) -> float:
        Pl = G.ajustar_logit_lote(G.estandarizar(X), Y, Mk, C=C, dispositivo_=dispositivo)
        P = np.empty(n)
        for s, fila in zip(temporadas, Pl, strict=True):
            P[por_temp[s]] = fila[por_temp[s]]
        return float(G.auc_ap_lote(y[None, :].astype(float), P[None, :], dispositivo_=dispositivo)[1][0])

    ap_base = ap_de(X_base)
    ap_real = ap_de(np.hstack([X_base, extra]))
    rng = np.random.default_rng(semilla)
    nulas = []
    for _ in range(n_nulas):
        ex = extra.copy()
        for i in por_temp.values():
            ex[i] = np.roll(extra[i], int(rng.integers(5, max(6, len(i) - 5))), axis=0)
        nulas.append(ap_de(np.hstack([X_base, ex])) - ap_base)
    nulas = np.array(nulas)
    d = ap_real - ap_base
    return {"ap_base": ap_base, "ap_con_bloque": ap_real, "delta_ap": d, "nula_media": float(nulas.mean()),
            "nula_p95": float(np.percentile(nulas, 95)), "p": float((1 + (nulas >= d).sum()) / (1 + len(nulas)))}


# ------------------------------------------------------------------------------ analysis of T28
CORRESPONDENCIA_ERA5 = {
    "chosica": "chosica_h_lluvia_1d",
    "santa-eulalia-alta": "sea_lluvia_1d",
    "matucana": "mat_lluvia_1d",
    "ticlio": "tic_lluvia_1d",
}


def analizar(raiz: Path = Path("."), n_nulas: int = 500, desde_modelo: int = 1984) -> dict[str, pd.DataFrame]:
    """Everything T28 needs, from the files in `datos/lluvia_sat/` that exist.

    Returns tables: `acuerdo` (daily agreement with ERA5), `dias_huaico` (rain on huaico days and
    single-feature AUC with a season bootstrap), `modelo` (add / substitute tests of the nested
    daily model) and `nula_gpu` (the fixed-C GPU version with a shifted-block null).
    """
    from . import evaluacion_diaria as E
    from . import hipotesis_literatura as H

    raiz = Path(raiz)
    carpeta = raiz / "datos" / "lluvia_sat"
    fuentes = {n: cargar(carpeta / f"{f}_diario.csv") for n, f in (("psn", "persiann_cdr"), ("cpc", "cpc"))
               if (carpeta / f"{f}_diario.csv").exists()}
    D, X, y, ts, _mes, _folds = H.contexto_modelo(raiz)
    F = D.F
    out: dict[str, pd.DataFrame] = {}

    out["acuerdo"] = pd.concat(
        [H.comparar_con_era5(c, F, CORRESPONDENCIA_ERA5).assign(fuente=n) for n, c in fuentes.items()],
        ignore_index=True,
    )

    # rain on huaico days, ERA5 against each source (point-wise single-feature AUC)
    from .catalogo import cargar_todos

    yd = E.etiquetas(cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True), F.index)
    mask = D.inventario["mask"]
    ts_todas = D.temporada
    filas = []
    for punto, col in CORRESPONDENCIA_ERA5.items():
        for nombre, serie in [("era5", F[col])] + [(n, c[punto].reindex(F.index)) for n, c in fuentes.items()]:
            x = serie.rolling(3, min_periods=2).sum()
            dentro = mask & x.notna().to_numpy()
            c = E.cribado(pd.DataFrame({"lluvia_3d": x[dentro]}), yd[dentro], ts_todas[dentro], n_boot=200)
            filas.append({"punto": punto, "fuente": nombre, "dias": int(dentro.sum()),
                          "media_mm_dias_huaico": float(serie[dentro & (yd.to_numpy() == 1)].mean()),
                          "media_mm_otros": float(serie[dentro & (yd.to_numpy() == 0)].mean()),
                          "auc_3d": float(c["auc"].iloc[0]), "auc_p5": float(c["auc_p5"].iloc[0]),
                          "auc_p95": float(c["auc_p95"].iloc[0])})
    out["dias_huaico"] = pd.DataFrame(filas)

    # model: add and substitute (nested tuning, season-out folds), and the GPU null
    filas, nulas = [], []
    for nombre, c in fuentes.items():
        extra = H.alinear(variables(c, F.index, nombre), D)
        extra = extra.loc[:, extra.notna().any()]
        r = H.evaluar_chirps(X["lluvia+antecedentes"], extra, y, ts, desde=desde_modelo)
        filas.append(r.assign(fuente=nombre))
        dentro = (ts >= desde_modelo) & extra.notna().any(axis=1).to_numpy()
        base = X["lluvia+antecedentes"][dentro].to_numpy(dtype=float)
        nulas.append(pd.Series(delta_ap_gpu(base, extra[dentro].to_numpy(dtype=float), y[dentro].to_numpy(),
                                            ts[dentro], n_nulas=n_nulas)).rename(nombre))
    if filas:
        out["modelo"] = pd.concat(filas, ignore_index=True)
        out["nula_gpu"] = pd.concat(nulas, axis=1).T
    return out
