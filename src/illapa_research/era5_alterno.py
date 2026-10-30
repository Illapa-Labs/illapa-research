"""ERA5 at a point without the Open-Meteo API: the same files, read from their public S3 bucket.

Open-Meteo keeps its ERA5 archive as `.om` files in the open-data bucket `s3://openmeteo/data/
copernicus_era5/<variable>/` (anonymous reads, no key, no daily call quota): `year_YYYY.om` for
1940 to 2021 and `chunk_N.om` (504 hours each) from December 2021 on. Every file is a global grid
(721 latitudes from -90, 1440 longitudes from -180, 0.25 degrees) chunked so that a point's time
series needs only a few range requests.

What the API adds on top of the raw grid, and what is done here:

* the API returns the series for the DEM elevation of the point, shifting temperature with the
  difference between the elevation of the ERA5 cell (`static/HSURF.om`) and the point. Here
  temperature and dew point get the same shift with a lapse rate (`LAPSE_T`, `LAPSE_TD`),
  measured against the points already downloaded from the API (see docs/13);
* hours are UTC in the files and local time (America/Lima, UTC-5) in the caches;
* relative humidity and vapour pressure deficit are derived from temperature and dew point.

The output has the layout of `datos/predictores_cache/<point>_1983.json` and `_2000.json`, so
`predictores.cargar_con_respaldo` reads it unchanged.

Licence: ERA5 is Copernicus Climate Change Service data (free, with attribution); the files are
distributed by Open-Meteo under CC BY 4.0 ("Weather data by Open-Meteo.com").
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BUCKET = "openmeteo/data/copernicus_era5"
PASO_GRADOS = 0.25
LAT0, LON0 = -90.0, -180.0
HORAS_POR_CHUNK = 504
PRIMER_CHUNK = 904  # first hour of chunk 904 is 2021-12-23 00:00 UTC
ULTIMO_ANIO_ARCHIVO = 2021
DESFASE_LIMA_H = -5

LAPSE_T = 0.0065  # K per metre, applied to temperature
LAPSE_TD = 0.0020  # K per metre, applied to dew point (it falls more slowly with height)

# Open-Meteo hourly name -> directory in the bucket (None: derived)
VARIABLES = {
    "temperature_2m": "temperature_2m",
    "dew_point_2m": "dew_point_2m",
    "pressure_msl": "pressure_msl",
    "cloud_cover": "cloud_cover",
    "precipitation": "precipitation",
    "snowfall": "snowfall_water_equivalent",
    "soil_moisture_0_to_7cm": "soil_moisture_0_to_7cm",
    "shortwave_radiation": "shortwave_radiation",
    "relative_humidity_2m": None,
    "vapour_pressure_deficit": None,
    "wind_speed_10m": None,
}
DERIVADAS_DE = {
    "relative_humidity_2m": ("temperature_2m", "dew_point_2m"),
    "vapour_pressure_deficit": ("temperature_2m", "dew_point_2m"),
    "wind_speed_10m": ("wind_u_component_10m", "wind_v_component_10m"),
}


# ---------------------------------------------------------------- pure helpers (no network)
def indice_celda(lat: float, lon: float) -> tuple[int, int]:
    """Row and column of the grid cell nearest to a point."""
    i = int(round((lat - LAT0) / PASO_GRADOS))
    j = int(round((lon - LON0) / PASO_GRADOS)) % 1440
    return i, j


def horas_utc(inicio: datetime, fin: datetime) -> pd.DatetimeIndex:
    return pd.date_range(inicio, fin, freq="h")


def archivo_de(hora: datetime) -> tuple[str, int, int]:
    """File that holds a UTC hour, with its first hour index and the index of the hour inside it."""
    ref = datetime(1970, 1, 1, tzinfo=UTC)
    h = hora.replace(tzinfo=UTC) if hora.tzinfo is None else hora
    if h.year <= ULTIMO_ANIO_ARCHIVO:
        ini = datetime(h.year, 1, 1, tzinfo=UTC)
        return f"year_{h.year}.om", 0, int((h - ini).total_seconds() // 3600)
    n = int((h - ref).total_seconds() // 3600)
    chunk = n // HORAS_POR_CHUNK
    return f"chunk_{chunk}.om", chunk * HORAS_POR_CHUNK, n - chunk * HORAS_POR_CHUNK


def segmentos(inicio: datetime, fin: datetime) -> list[tuple[str, int, int, datetime]]:
    """Files and hour ranges needed for [inicio, fin] (UTC, inclusive): (file, from, to, first hour)."""
    out = []
    h = inicio
    while h <= fin:
        nombre, _, k = archivo_de(h)
        if nombre.startswith("year_"):
            ini_arch = datetime(h.year, 1, 1, tzinfo=UTC)
            fin_arch = datetime(h.year, 12, 31, 23, tzinfo=UTC)
        else:
            c = int(nombre[len("chunk_") : -len(".om")])
            ini_arch = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(hours=c * HORAS_POR_CHUNK)
            fin_arch = ini_arch + timedelta(hours=HORAS_POR_CHUNK - 1)
        ultimo = min(fin, fin_arch)
        out.append((nombre, k, k + int((ultimo - h).total_seconds() // 3600) + 1, h))
        h = ultimo + timedelta(hours=1)
    return out


def corregir_altura(serie: pd.Series, z_celda: float, z_punto: float, lapse: float) -> pd.Series:
    """Shift a temperature-like series from the cell elevation to the point elevation."""
    return serie + lapse * (z_celda - z_punto)


def _es_hpa(t_c: np.ndarray) -> np.ndarray:
    """Saturation vapour pressure (hPa), Magnus form over water."""
    return 6.1094 * np.exp(17.625 * t_c / (t_c + 243.04))


def humedad_relativa(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    return np.clip(100.0 * _es_hpa(td_c) / _es_hpa(t_c), 0.0, 100.0)


def deficit_presion_vapor_kpa(t_c: np.ndarray, td_c: np.ndarray) -> np.ndarray:
    """Vapour pressure deficit in kPa: saturation pressure at T minus the actual (at the dew point)."""
    return np.maximum(_es_hpa(t_c) - _es_hpa(td_c), 0.0) / 10.0


# ---------------------------------------------------------------- network
def _sistema_archivos():
    import s3fs

    return s3fs.S3FileSystem(anon=True)


def elevacion_celda(lat: float, lon: float, fs=None) -> float:
    """Elevation (m) of the ERA5 cell in `static/HSURF.om`."""
    from omfiles import OmFileReader

    fs = fs or _sistema_archivos()
    r = OmFileReader.from_fsspec(fs, f"{BUCKET}/static/HSURF.om")
    i, j = indice_celda(lat, lon)
    return float(r.read_array((slice(i, i + 1), slice(j, j + 1))).ravel()[0])


def _leer_segmento(fs, variable: str, nombre: str, i: int, j: int, a: int, b: int) -> np.ndarray:
    from omfiles import OmFileReader

    r = OmFileReader.from_fsspec(fs, f"{BUCKET}/{variable}/{nombre}")
    try:
        return r.read_array((slice(i, i + 1), slice(j, j + 1), slice(a, b))).ravel().astype("float64")
    finally:
        r.close()


def serie_cruda(variable: str, lat: float, lon: float, inicio: datetime, fin: datetime,
                hilos: int = 4) -> pd.Series:
    """Hourly series (UTC index) of one bucket variable at the nearest ERA5 cell, no corrections."""
    fs = _sistema_archivos()
    i, j = indice_celda(lat, lon)
    segs = segmentos(inicio, fin)

    def uno(s):
        nombre, a, b, h0 = s
        for intento in range(4):
            try:
                v = _leer_segmento(fs, variable, nombre, i, j, a, b)
                return pd.Series(v, index=pd.date_range(h0, periods=len(v), freq="h"))
            except Exception:  # noqa: BLE001 (transient S3 errors: wait and retry)
                time.sleep(2 * (intento + 1))
        raise RuntimeError(f"No se pudo leer {variable}/{nombre}")

    with ThreadPoolExecutor(hilos) as ex:
        partes = list(ex.map(uno, segs))
    s = pd.concat(partes)
    s.index = s.index.tz_localize(None)
    return s[~s.index.duplicated()]


def ultima_hora_disponible(fs=None) -> datetime:
    """Last UTC hour published in the bucket (from the metadata of the newest chunk)."""
    import urllib.request

    meta = json.loads(urllib.request.urlopen("https://openmeteo.s3.amazonaws.com/data/copernicus_era5/static/meta.json",
                                             timeout=60).read())
    return datetime.fromtimestamp(meta["data_end_time"], UTC)


def serie_punto(
    variables: list[str], lat: float, lon: float, z_punto: float, inicio: datetime, fin: datetime,
    lapse_t: float = LAPSE_T, lapse_td: float = LAPSE_TD, hilos: int = 4,
) -> pd.DataFrame:
    """Hourly table in local (America/Lima) time with the Open-Meteo names, at point elevation."""
    fs = _sistema_archivos()
    z_celda = elevacion_celda(lat, lon, fs)
    necesarias: set[str] = set()
    for v in variables:
        if VARIABLES.get(v) is None:
            if v == "wind_speed_10m":
                necesarias |= set(DERIVADAS_DE[v])
            else:
                necesarias |= {"temperature_2m", "dew_point_2m"}
        else:
            necesarias.add(v)
    crudas: dict[str, pd.Series] = {}
    for v in sorted(necesarias):
        carpeta = VARIABLES.get(v) or v
        crudas[v] = serie_cruda(carpeta, lat, lon, inicio, fin, hilos)
    t = corregir_altura(crudas["temperature_2m"], z_celda, z_punto, lapse_t) if "temperature_2m" in crudas else None
    td = corregir_altura(crudas["dew_point_2m"], z_celda, z_punto, lapse_td) if "dew_point_2m" in crudas else None
    if t is not None and td is not None:
        td = td.clip(upper=t)  # a dew point above the temperature cannot happen
    out = {}
    for v in variables:
        if v == "temperature_2m":
            out[v] = t
        elif v == "dew_point_2m":
            out[v] = td
        elif v == "relative_humidity_2m":
            out[v] = pd.Series(humedad_relativa(t.to_numpy(), td.to_numpy()), index=t.index)
        elif v == "vapour_pressure_deficit":
            out[v] = pd.Series(deficit_presion_vapor_kpa(t.to_numpy(), td.to_numpy()), index=t.index)
        elif v == "wind_speed_10m":
            u, w = crudas["wind_u_component_10m"], crudas["wind_v_component_10m"]
            out[v] = np.hypot(u, w) * 3.6  # m/s -> km/h, as the API
        else:
            out[v] = crudas[v]
    df = pd.DataFrame(out)
    df.index = df.index + pd.Timedelta(hours=DESFASE_LIMA_H)  # UTC -> America/Lima
    return df


def escribir_cache(df: pd.DataFrame, nombre: str, z_punto: float, destino: Path, hasta: str) -> list[Path]:
    """Write the two cache files (1983-1999 and 2000-today) in the layout of `descargar-datos`."""
    destino.mkdir(parents=True, exist_ok=True)
    rutas = []
    for ini, fin, etiqueta in (("1983-01-01", "1999-12-31", "1983"), ("2000-01-01", None, "2000")):
        sub = df.loc[ini:fin] if fin else df.loc[ini:]
        js = {
            "elevation": z_punto,
            "hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in sub.index],
                       **{c: [None if pd.isna(x) else round(float(x), 3) for x in sub[c]] for c in sub.columns}},
            "_hasta": hasta,
            "_fuente": "Open-Meteo ERA5 en AWS (s3://openmeteo), celda más cercana con corrección de altura",
        }
        ruta = destino / f"{nombre}_{etiqueta}.json"
        ruta.write_text(json.dumps(js), encoding="utf-8")
        rutas.append(ruta)
    return rutas
