"""Daily rain from sources independent of ERA5, for the points of the daily model (hypothesis T28).

CHIRPS (the Climate Hazards Center server) did not answer, so two other public series are used:

* **PERSIANN-CDR** (NOAA NCEI, 0.25 degrees, daily, 1983 to a few months ago): infrared satellite
  rain adjusted to monthly gauge totals (GPCP). Public domain (NOAA).
* **CPC Global Unified Gauge-Based Analysis** (NOAA PSL, 0.5 degrees, daily): interpolated rain
  gauges only, no satellite and no reanalysis. Public domain (NOAA).

Both are read at the grid cell that contains the centre of each predictor point. The centres were
fixed before looking at any result (they are the centres of the CHIRPS boxes of `fuentes.py`).
"""

from __future__ import annotations

import re
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
CPC_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_global_precip/precip.{a}.nc"
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
    """CPC daily gauge-analysis rain at each centre for one year, read by OPeNDAP (a few kB)."""
    import xarray as xr

    with xr.open_dataset(CPC_URL.format(a=anio)) as ds:
        cols = {}
        for nombre, (x, y) in CENTROS.items():
            i = celda_mas_cercana(ds["lat"].values, y)
            j = celda_mas_cercana(ds["lon"].values, lon360(x))
            v = ds["precip"].isel(lat=i, lon=j).values.astype(float)
            cols[nombre] = np.where(v < 0, np.nan, v)
        return pd.DataFrame(cols, index=pd.to_datetime(ds["time"].values).normalize())


def descargar_cpc(destino: Path, desde: int = 1983) -> Path:
    """One request per year to PSL; writes `lluvia_sat/cpc_diario.csv`."""
    carpeta = destino / "lluvia_sat"
    carpeta.mkdir(parents=True, exist_ok=True)
    partes = []
    for a in range(desde, pd.Timestamp.today().year + 1):
        partes.append(serie_cpc(a))
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
