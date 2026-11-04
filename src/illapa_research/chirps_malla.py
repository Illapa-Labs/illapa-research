"""CHIRPS v3 daily rainfall on its 0.05° grid over the forecast zones of the alert map.

The alert map (illapa-engine) serves the rain forecast on 0.1° grids over five zones with ravines
(`catalogo/zonas_pronostico.json`, a copy of `illapa-engine/data/zonas-pronostico.json`). This module
keeps CHIRPS v3 on its own 0.05° grid over each zone plus a margin, for the downscaling work
(docs/26), instead of the box means of `fuentes._chirps_dia`.

What CHIRPS daily is (CHC readme of `daily/final/`): CHIRPS is a pentad and monthly product
(stations + CHIRP satellite); the daily values spread each pentad total over its days with the
timing of ERA5 (`rnl`, 1981 on) or IMERG Late (`sat`, 1998 on). Days are UTC days. So the 0.05°
detail is real at pentad and monthly scale; daily timing is ERA5's or IMERG's, resampled
bilinearly. Use pentad sums where the science allows.

Server facts measured on 2026-11-04: the daily GeoTIFFs are about 16 MB, LZW, stored in strips
of one row (not tiled), global 7200 x 2400 cells from 60° N to 60° S, sea = -9999 with no nodata
flag. A windowed read through `/vsicurl/` only fetches the rows of the window: about 1.7 s per day
for a 1.8° x 1.6° box.

Licence: CHIRPS is public domain / CC BY 4.0 (Climate Hazards Center, UC Santa Barbara). Cite
Funk, C. et al. (2026), CHIRPS v3, Scientific Data 13, 718, doi:10.1038/s41597-026-07096-4.
"""

from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/{producto}/{a}/chirps-v3.0.{producto}.{a}.{m:02d}.{d:02d}.tif"
INICIO = {"rnl": "1981-01-01", "sat": "1998-01-01"}
RES = 0.05
OESTE, NORTE = -180.0, 60.0  # upper-left corner of the global CHIRPS v3 grid
ZONAS = Path(__file__).resolve().parents[2] / "catalogo" / "zonas_pronostico.json"
MARGEN = 0.2


def cajas_zonas(ruta: Path = ZONAS, margen: float = MARGEN) -> dict[str, tuple[float, float, float, float]]:
    """(west, south, east, north) of every forecast zone, widened by `margen` degrees."""
    zonas = json.loads(Path(ruta).read_text(encoding="utf-8"))["zonas"]
    out = {}
    for z in zonas:
        w, n = z["west"], z["north"]
        e, s = w + z["cols"] * z["step"], n - z["rows"] * z["step"]
        out[z["id"]] = (round(w - margen, 4), round(s - margen, 4), round(e + margen, 4), round(n + margen, 4))
    return out


def ventana(caja: tuple[float, float, float, float], oeste: float = OESTE, norte: float = NORTE,
            res: float = RES) -> tuple[int, int, int, int]:
    """(col_off, row_off, width, height) of the whole cells of the grid that cover `caja`.

    Computed from the box alone (not from a file), so every day gives the same shape.
    """
    w, s, e, n = caja
    c0 = math.floor((w - oeste) / res + 1e-9)
    c1 = math.ceil((e - oeste) / res - 1e-9)
    r0 = math.floor((norte - n) / res + 1e-9)
    r1 = math.ceil((norte - s) / res - 1e-9)
    return c0, r0, c1 - c0, r1 - r0


def coordenadas(caja, oeste: float = OESTE, norte: float = NORTE, res: float = RES) -> tuple[np.ndarray, np.ndarray]:
    """Cell-centre latitudes (north to south) and longitudes (west to east) of `ventana(caja)`."""
    c0, r0, ancho, alto = ventana(caja, oeste, norte, res)
    lat = norte - (r0 + np.arange(alto) + 0.5) * res
    lon = oeste + (c0 + np.arange(ancho) + 0.5) * res
    return np.round(lat, 4), np.round(lon, 4)


def leer(fuente, cajas: dict) -> dict[str, np.ndarray]:
    """The window of every box from an open rasterio dataset, as float32 with NaN on the sea."""
    from rasterio.windows import Window

    t = fuente.transform
    # The files store the cell size in float32 (0.05000000074505806): rounded, so a window has the
    # same whole number of cells as `coordenadas` gives.
    oeste, norte, res = round(t.c, 6), round(t.f, 6), round(t.a, 6)
    out = {}
    for nombre, caja in cajas.items():
        c0, r0, ancho, alto = ventana(caja, oeste, norte, res)
        a = fuente.read(1, window=Window(c0, r0, ancho, alto), boundless=True, fill_value=-9999).astype("float32")
        a[a < 0] = np.nan
        out[nombre] = a
    return out


def leer_dia(fecha, cajas: dict, producto: str = "rnl", intentos: int = 8) -> dict[str, np.ndarray] | None:
    """Windows of one day straight from the CHC server; None if the file is not published (404)."""
    import rasterio
    from rasterio.errors import RasterioIOError

    url = "/vsicurl/" + URL.format(producto=producto, a=fecha.year, m=fecha.month, d=fecha.day)
    entorno = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
               "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "2", "GDAL_HTTP_TIMEOUT": "30"}
    for i in range(intentos):
        try:
            with rasterio.Env(**entorno), rasterio.open(url) as src:
                if src.width != 7200 or abs(src.transform.c - OESTE) > 1e-6 or abs(src.transform.f - NORTE) > 1e-6:
                    raise ValueError(f"geotransform inesperado en {url}")
                return leer(src, cajas)
        except RasterioIOError as e:
            if "404" in str(e) or "does not exist" in str(e):
                return None
            time.sleep(min(60, 5 * 2**i))
    raise RuntimeError(f"CHIRPS no respondió para {fecha:%Y-%m-%d} ({producto})")


def _leer_o_marcar(fecha, cajas: dict, producto: str, faltantes: Path) -> dict[str, np.ndarray] | None:
    """`leer_dia`, but a day the server keeps failing becomes NaN and is written to `faltantes`."""
    try:
        return leer_dia(fecha, cajas, producto)
    except RuntimeError:
        with open(faltantes, "a", encoding="utf-8") as f:
            f.write(f"{fecha:%Y-%m-%d}\n")
        return {z: np.full(ventana(c)[3:1:-1], np.nan, dtype="float32") for z, c in cajas.items()}


def _mes(destino: Path, anio: int, mes: int, cajas: dict, producto: str, hilos: int, hasta) -> bool:
    """Download one month into `cache/<producto>_<YYYY>_<MM>.npz`; True if the month is complete."""
    import pandas as pd

    ruta = destino / "cache" / f"{producto}_{anio}_{mes:02d}.npz"
    if ruta.exists():
        return True
    ini = pd.Timestamp(anio, mes, 1)
    dias = [d for d in pd.date_range(ini, ini + pd.offsets.MonthEnd(0), freq="D") if d <= hasta]
    with ThreadPoolExecutor(hilos) as pool:
        faltantes = destino / f"{producto}_dias_fallidos.txt"
        leidos = list(pool.map(lambda d: _leer_o_marcar(d, cajas, producto, faltantes), dias))
    completos = [(d, x) for d, x in zip(dias, leidos, strict=True) if x is not None]
    entero = len(completos) == len(pd.date_range(ini, ini + pd.offsets.MonthEnd(0), freq="D"))
    if not completos:
        return False
    datos = {z: np.stack([x[z] for _, x in completos]) for z in cajas}
    if entero:  # a partial month (the newest one) is not cached, so it is read again next time
        ruta.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(ruta, fechas=np.array([d.strftime("%Y-%m-%d") for d, _ in completos]), **datos)
    else:
        np.savez_compressed(destino / "cache" / f"{producto}_parcial.npz",
                            fechas=np.array([d.strftime("%Y-%m-%d") for d, _ in completos]), **datos)
    return entero


def descargar(destino: Path, producto: str = "rnl", desde: str | None = None, hasta: str | None = None,
              hilos: int = 4, zonas: Path = ZONAS) -> list[Path]:
    """Every published day from `desde` (default: start of the product) to `hasta` (default: today),
    month by month (resumable), then one NetCDF per zone: `<zona>_<producto>.nc` (time, lat, lon)."""
    import pandas as pd

    destino = Path(destino)
    (destino / "cache").mkdir(parents=True, exist_ok=True)
    cajas = cajas_zonas(zonas)
    ini = pd.Timestamp(desde or INICIO[producto])
    fin = pd.Timestamp(hasta) if hasta else pd.Timestamp.today().normalize()
    for p in pd.period_range(ini, fin, freq="M"):
        t = time.monotonic()
        entero = _mes(destino, p.year, p.month, cajas, producto, hilos, fin)
        print(f"  CHIRPS {producto} {p}: {'completo' if entero else 'parcial o sin publicar'} "
              f"({time.monotonic() - t:.0f} s)", flush=True)
        if not entero:
            break  # the final product lags a few weeks: later months are not out yet
    return armar(destino, producto, cajas)


def armar(destino: Path, producto: str, cajas: dict) -> list[Path]:
    """Join the monthly caches (and the partial newest month) into one NetCDF per zone."""
    import xarray as xr

    destino = Path(destino)
    partes = sorted((destino / "cache").glob(f"{producto}_[12][0-9][0-9][0-9]_[01][0-9].npz"))
    parcial = destino / "cache" / f"{producto}_parcial.npz"
    if parcial.exists():
        partes.append(parcial)
    if not partes:
        return []
    cargados = [np.load(p) for p in partes]
    fechas = np.concatenate([c["fechas"] for c in cargados]).astype("datetime64[D]")
    orden = np.argsort(fechas, kind="stable")
    _, unicos = np.unique(fechas[orden], return_index=True)
    sel = orden[unicos]
    rutas = []
    for zona, caja in cajas.items():
        lat, lon = coordenadas(caja)
        valores = np.concatenate([c[zona] for c in cargados])[sel]
        ds = xr.Dataset(
            {"precip": (("time", "lat", "lon"), valores, {"units": "mm/day", "long_name": "CHIRPS v3 daily rainfall"})},
            coords={"time": fechas[sel].astype("datetime64[ns]"), "lat": lat, "lon": lon},
            attrs={"source": URL.split("{")[0], "product": f"CHIRPS v3.0 daily final, {producto}",
                   "zone": zona, "box_west_south_east_north": list(caja),
                   "time_convention": "UTC calendar day of the disaggregation (CHC readme)",
                   "license": "public domain / CC BY 4.0, Climate Hazards Center (UCSB)",
                   "citation": "Funk, C. et al. (2026), CHIRPS v3, Scientific Data 13, 718, doi:10.1038/s41597-026-07096-4"},
        )
        ruta = destino / f"{zona}_{producto}.nc"
        ds.to_netcdf(ruta, encoding={"precip": {"zlib": True, "complevel": 4, "dtype": "float32"}})
        rutas.append(ruta)
    return rutas


def media_caja(da, caja: tuple[float, float, float, float]) -> np.ndarray:
    """Daily mean of the cells whose centres fall inside `caja` (the box means of the older source)."""
    w, s, e, n = caja
    sub = da.sel(lat=slice(n, s), lon=slice(w, e))
    return sub.mean(dim=("lat", "lon"), skipna=True).to_numpy()


def pentadas(da):
    """CHIRPS pentad totals (days 1-5, 6-10, 11-15, 16-20, 21-25 and 26 to month end) from the daily grid.

    Daily rnl and sat add up to the same pentad total, so this recovers the product's real unit.
    """
    import pandas as pd

    t = pd.DatetimeIndex(da["time"].to_numpy())
    p = np.minimum((t.day - 1) // 5, 5)
    clave = (t.year * 100 + t.month) * 10 + p
    return da.assign_coords(pentada=("time", clave)).groupby("pentada").sum(skipna=False)


# The six PISCOp cells over the Rímac valley (correccion_sesgo.LONGITUDES x LATITUDES): their outer edges.
CAJA_VALLE_PISCO = (-76.80, -12.00, -76.50, -11.80)
MESES_LLUVIA = (12, 1, 2, 3, 4)


def serie_punto(da, lon: float, lat: float):
    """Daily series of the CHIRPS cell that contains a point (a station)."""
    import pandas as pd

    s = da.sel(lon=lon, lat=lat, method="nearest")
    return pd.Series(s.to_numpy(), index=pd.DatetimeIndex(da["time"].to_numpy()), name="chirps")


def comparar(chirps, obs, meses: tuple[int, ...] = MESES_LLUVIA) -> dict[str, float]:
    """How a CHIRPS series agrees with an observed daily series in the rainy months.

    CHIRPS days are UTC days and SENAMHI's are read at 7 a.m. local, so the daily correlation is
    given at lags -1, 0 and +1 (CHIRPS shifted against the observation). Pentads and months are
    the scales CHIRPS is built at, and they do not depend on the day convention.
    """
    import pandas as pd

    j = pd.concat({"c": chirps, "o": obs}, axis=1).dropna()
    j = j[j.index.month.isin(meses)]
    out: dict[str, float] = {"dias": float(len(j))}
    if len(j) < 30:
        return out
    for k in (-1, 0, 1):
        x = pd.concat({"c": chirps.shift(k), "o": obs}, axis=1).dropna()
        x = x[x.index.month.isin(meses)]
        out[f"r_diaria_rezago{k:+d}"] = float(x["c"].corr(x["o"]))
    p = np.minimum((j.index.day - 1) // 5, 5)
    clave = (j.index.year * 100 + j.index.month) * 10 + p
    pent = j.groupby(clave).sum()
    out["r_pentada"] = float(pent["c"].corr(pent["o"]))
    mens = j.groupby(j.index.year * 100 + j.index.month).sum()
    out["r_mensual"] = float(mens["c"].corr(mens["o"]))
    out["razon_medias"] = float(j["c"].mean() / j["o"].mean()) if j["o"].mean() > 0 else float("nan")
    for m in meses:
        jm = j[j.index.month == m]
        out[f"razon_mes_{m:02d}"] = float(jm["c"].mean() / jm["o"].mean()) if jm["o"].mean() > 0 else float("nan")
    return out
