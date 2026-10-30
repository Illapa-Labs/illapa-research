"""Open data sources with a clear licence.

Every source carries its own licence and attribution, because the AGPL of this
repository covers the code, not the data. SENAMHI and INEI are left out on
purpose until they authorise reuse in writing (see DATOS.md).
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

USER_AGENT = "illapa-research/0.1 (+https://github.com/Illapa-Labs/illapa-research)"

# Study area: the Rímac valley between Chaclacayo and Chosica (south, west, north, east).
CHOSICA_BBOX = (-12.00, -76.95, -11.88, -76.60)

OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# Points inside the study area for the rain history (name, latitude, longitude).
PUNTOS_LLUVIA = (
    ("chosica", -11.93, -76.70),
    ("chaclacayo", -11.98, -76.77),
    ("chaclacayo-alto", -11.93, -76.55),
)


@dataclass(frozen=True)
class Fuente:
    id: str
    nombre: str
    url: str
    licencia: str
    atribucion: str
    descargar: Callable[[Path], list[str]]


def _get(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 120)
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    resp = requests.get(url, headers=headers, **kwargs)
    resp.raise_for_status()
    return resp


def _natural_earth(destino: Path) -> list[str]:
    base = "https://naciscdn.org/naturalearth/10m/"
    capas = {
        "physical/ne_10m_rivers_lake_centerlines": "rios",
        "cultural/ne_10m_admin_1_states_provinces": "departamentos",
    }
    escritos = []
    for ruta, nombre in capas.items():
        carpeta = destino / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        data = _get(f"{base}{ruta}.zip").content
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(carpeta)
        escritos.append(str(carpeta.relative_to(destino.parent)))
    return escritos


def consulta_aguas(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox
    return (
        "[out:json][timeout:90];"
        f'way["waterway"~"^(river|stream|canal|drain)$"]({s},{w},{n},{e});'
        "out geom;"
    )


def _osm_aguas(destino: Path) -> list[str]:
    ultimo = None
    for _ in range(2):
        for espejo in OVERPASS_MIRRORS:
            try:
                resp = requests.post(
                    espejo,
                    data={"data": consulta_aguas(CHOSICA_BBOX)},
                    headers={"User-Agent": USER_AGENT},
                    timeout=150,
                )
                resp.raise_for_status()
                datos = resp.json()
            except (requests.RequestException, ValueError) as err:
                ultimo = err
                time.sleep(3)
                continue
            salida = destino / "osm_aguas_chosica.json"
            salida.write_text(json.dumps(datos), encoding="utf-8")
            return [str(salida.relative_to(destino.parent))]
    raise RuntimeError(f"Overpass no respondió en ningún espejo: {ultimo}")


def _open_meteo(destino: Path) -> list[str]:
    hoy = time.strftime("%Y-%m-%d")
    salida = {}
    for nombre, lat, lon in PUNTOS_LLUVIA:
        resp = _get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": "2015-01-01",
                "end_date": hoy,
                "daily": "precipitation_sum",
                "timezone": "America/Lima",
            },
        )
        salida[nombre] = resp.json()
        time.sleep(1)  # Stay well under the free-tier limits.
    archivo = destino / "open_meteo_lluvia_diaria.json"
    archivo.write_text(json.dumps(salida), encoding="utf-8")
    return [str(archivo.relative_to(destino.parent))]


# Rain-study points: the town of Chosica and the upper basin (Santa Eulalia and San Mateo side).
PUNTOS_ESTUDIO = (("chosica", -11.93, -76.70), ("cuenca-alta", -11.85, -76.50))


def _open_meteo_horario(destino: Path) -> list[str]:
    """Hourly rain and soil moisture since 1983, in two chunks (the API limits large requests)."""
    hoy = time.strftime("%Y-%m-%d")
    salida = {}
    for nombre, lat, lon in PUNTOS_ESTUDIO:
        horas: dict[str, list] = {}
        for ini, fin in (("1983-01-01", "2004-12-31"), ("2005-01-01", hoy)):
            for intento in range(5):
                resp = requests.get(
                    "https://archive-api.open-meteo.com/v1/archive",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": ini,
                        "end_date": fin,
                        "hourly": "precipitation,soil_moisture_0_to_7cm",
                        "timezone": "America/Lima",
                    },
                    headers={"User-Agent": USER_AGENT},
                    timeout=300,
                )
                if resp.ok and "hourly" in resp.json():
                    break
                time.sleep(65)  # Minutely request limit: wait a full minute.
            else:
                raise RuntimeError(f"Open-Meteo no respondió para {nombre} {ini}")
            for k, v in resp.json()["hourly"].items():
                horas.setdefault(k, []).extend(v)
            time.sleep(10)
        salida[nombre] = horas
    archivo = destino / "open_meteo_horario_estudio.json"
    archivo.write_text(json.dumps(salida), encoding="utf-8")
    return [str(archivo.relative_to(destino.parent))]


DEM_TESELAS = ("S12_00_W077_00", "S13_00_W077_00")
# Study window for buildings (south, west, north, east): the valley from Huachipa to Ricardo Palma.
VENTANA_EDIFICIOS = (-12.03, -76.92, -11.85, -76.52)
NOAA_INDICES = {
    "oni": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "nino12": "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
}


def _copernicus_dem(destino: Path) -> list[str]:
    """Copernicus GLO-30 tiles (30 m) from the public AWS open-data bucket."""
    carpeta = destino / "dem"
    carpeta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for tesela in DEM_TESELAS:
        nombre = f"Copernicus_DSM_COG_10_{tesela}_DEM"
        url = f"https://copernicus-dem-30m.s3.amazonaws.com/{nombre}/{nombre}.tif"
        salida = carpeta / f"Copernicus_{tesela}.tif"
        with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(salida, "wb") as f:
                f.writelines(r.iter_content(1 << 20))
        escritos.append(str(salida.relative_to(destino.parent)))
    return escritos


def _overpass(consulta: str) -> dict:
    ultimo = None
    for _ in range(2):
        for espejo in OVERPASS_MIRRORS:
            try:
                resp = requests.post(
                    espejo, data={"data": consulta}, headers={"User-Agent": USER_AGENT}, timeout=300
                )
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as err:
                ultimo = err
                time.sleep(3)
    raise RuntimeError(f"Overpass no respondió en ningún espejo: {ultimo}")


def _osm_edificios(destino: Path) -> list[str]:
    """Centres of the OSM building footprints, in four strips so Overpass does not time out."""
    s, w, n, e = VENTANA_EDIFICIOS
    cortes = [w + (e - w) * i / 4 for i in range(5)]
    centros = []
    for i in range(4):
        consulta = (
            "[out:json][timeout:240];"
            f'way["building"]({s},{cortes[i]},{n},{cortes[i + 1]});out center qt;'
        )
        for el in _overpass(consulta)["elements"]:
            c = el.get("center")
            if c:
                centros.append([round(c["lon"], 6), round(c["lat"], 6)])
        time.sleep(2)
    # A building on a strip border can come twice: drop exact duplicates.
    centros = sorted({tuple(c) for c in centros})
    salida = destino / "osm_edificios_centros.json"
    salida.write_text(json.dumps({"bbox_swne": VENTANA_EDIFICIOS, "centros": centros}), encoding="utf-8")
    return [str(salida.relative_to(destino.parent))]


def _noaa_enso(destino: Path) -> list[str]:
    """NOAA CPC monthly indices: ONI (Niño 3.4, global) and the Niño 1+2 SST anomaly (coastal)."""
    carpeta = destino / "enso"
    carpeta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nombre, url in NOAA_INDICES.items():
        salida = carpeta / f"noaa_{nombre}.txt"
        salida.write_text(_get(url).text, encoding="utf-8")
        escritos.append(str(salida.relative_to(destino.parent)))
    return escritos


# Predictor points for the daily event model (name, latitude, longitude): high Rímac headwaters,
# the Santa Eulalia valley, the town, the coast and the Amazon side of the divide.
PUNTOS_PREDICTORES = (
    ("ticlio", -11.60, -76.20),
    ("santa-eulalia-alta", -11.70, -76.40),
    ("matucana", -11.84, -76.38),
    ("chosica", -11.93, -76.70),
    ("costa-lima", -12.05, -77.12),
    ("selva-tarma", -11.42, -75.69),
)
VARIABLES_HORARIAS = (
    "temperature_2m,relative_humidity_2m,dew_point_2m,pressure_msl,cloud_cover,precipitation,"
    "snowfall,wind_speed_10m,soil_moisture_0_to_7cm,vapour_pressure_deficit,shortwave_radiation"
)
# The free API counts a call by variables x days, so the points added later ask only for what
# the features use. Points missing here use all of `VARIABLES_HORARIAS`.
VARIABLES_POR_PUNTO = {
    "chosica": "temperature_2m,relative_humidity_2m,pressure_msl,cloud_cover,precipitation,vapour_pressure_deficit",
    "costa-lima": "dew_point_2m,cloud_cover,pressure_msl",
    "selva-tarma": "dew_point_2m,pressure_msl,cloud_cover,precipitation",
}
# Boxes (south, north, west, east, stride) for the daily sea surface temperature of OISST.
CAJAS_SST = {
    "nino12": (-10.0, 0.0, -90.0, -80.0, 4),
    "costa_peru": (-14.0, -8.0, -82.0, -77.0, 4),
    "costa_lima": (-13.5, -11.5, -78.5, -76.5, 1),
}


def _agregar_diario(df):
    """Daily means, sums and extremes of the hourly columns that are present."""
    reglas = {
        "temperature_2m": ["mean", "max", "min"],
        "relative_humidity_2m": "mean",
        "dew_point_2m": "mean",
        "pressure_msl": "mean",
        "cloud_cover": "mean",
        "precipitation": ["sum", "max"],
        "snowfall": "sum",
        "wind_speed_10m": "mean",
        "soil_moisture_0_to_7cm": "mean",
        "vapour_pressure_deficit": "mean",
        "shortwave_radiation": "sum",
    }
    d = df.set_index("time").resample("D").agg({k: v for k, v in reglas.items() if k in df.columns})
    d.columns = ["_".join(c) if c[1] not in ("", "mean") else c[0] for c in d.columns]
    return d


def _open_meteo_predictores(destino: Path) -> list[str]:
    """Daily summaries of ERA5 variables at several points, 1983 to today.

    Each point and period is cached in `predictores_cache/`: the free API limits calls per hour,
    so a rerun continues where the last one stopped and waits out the limit when it hits it.
    """
    import pandas as pd

    cache = destino / "predictores_cache"
    cache.mkdir(parents=True, exist_ok=True)
    hoy = time.strftime("%Y-%m-%d")
    salida = {}
    for nombre, lat, lon in PUNTOS_PREDICTORES:
        partes = []
        for ini, fin in (("1983-01-01", "1999-12-31"), ("2000-01-01", hoy)):
            ruta = cache / f"{nombre}_{ini[:4]}.json"
            if ruta.exists() and ini == "1983-01-01":
                js = json.loads(ruta.read_text(encoding="utf-8"))
            else:
                if ruta.exists() and json.loads(ruta.read_text(encoding="utf-8")).get("_hasta") == hoy:
                    js = json.loads(ruta.read_text(encoding="utf-8"))
                else:
                    for _ in range(12):
                        resp = requests.get(
                            "https://archive-api.open-meteo.com/v1/archive",
                            params={"latitude": lat, "longitude": lon, "start_date": ini, "end_date": fin,
                                    "hourly": VARIABLES_POR_PUNTO.get(nombre, VARIABLES_HORARIAS),
                                    "timezone": "America/Lima"},
                            headers={"User-Agent": USER_AGENT},
                            timeout=300,
                        )
                        if resp.ok and "hourly" in resp.json():
                            break
                        print(f"  límite de Open-Meteo ({resp.status_code}); espero 10 min", flush=True)
                        time.sleep(600)
                    else:
                        raise RuntimeError(f"Open-Meteo no respondió para {nombre} {ini}")
                    js = resp.json()
                    js["_hasta"] = hoy
                    ruta.write_text(json.dumps(js), encoding="utf-8")
                    time.sleep(20)
            df = pd.DataFrame(js["hourly"])
            df["time"] = pd.to_datetime(df["time"])
            d = _agregar_diario(df)
            partes.append(d)
            salida.setdefault(nombre, {})["elevation"] = js.get("elevation")
        total = pd.concat(partes)
        salida[nombre]["fecha"] = [t.strftime("%Y-%m-%d") for t in total.index]
        salida[nombre]["columnas"] = {c: [None if pd.isna(v) else round(float(v), 3) for v in total[c]]
                                       for c in total.columns}
    archivo = destino / "open_meteo_predictores_diarios.json"
    archivo.write_text(json.dumps(salida), encoding="utf-8")
    return [str(archivo.relative_to(destino.parent))]


def _open_meteo_caudal(destino: Path) -> list[str]:
    """GloFAS river discharge (Open-Meteo flood API) near Chosica, Matucana and the Santa Eulalia."""
    puntos = (("rimac-chosica", -11.93, -76.70), ("rimac-matucana", -11.84, -76.38),
              ("santa-eulalia", -11.90, -76.60))
    salida = {}
    for nombre, lat, lon in puntos:
        for _ in range(6):
            resp = requests.get(
                "https://flood-api.open-meteo.com/v1/flood",
                params={"latitude": lat, "longitude": lon, "start_date": "1984-01-01",
                        "end_date": time.strftime("%Y-%m-%d"), "daily": "river_discharge"},
                headers={"User-Agent": USER_AGENT},
                timeout=300,
            )
            if resp.ok and "daily" in resp.json():
                break
            time.sleep(65)
        else:
            raise RuntimeError(f"Flood API no respondió para {nombre}")
        js = resp.json()
        salida[nombre] = {"lat": js["latitude"], "lon": js["longitude"], "elevation": js.get("elevation"),
                          "fecha": js["daily"]["time"], "river_discharge": js["daily"]["river_discharge"]}
        time.sleep(5)
    archivo = destino / "open_meteo_caudal_glofas.json"
    archivo.write_text(json.dumps(salida), encoding="utf-8")
    return [str(archivo.relative_to(destino.parent))]


def _noaa_oisst(destino: Path) -> list[str]:
    """Daily NOAA OISST v2.1 sea surface temperature, area means of three Pacific boxes.

    Each box and year is cached in `enso/oisst_cache/`, so a rerun only asks for what is missing
    (the current year is always asked again).
    """
    import io

    import pandas as pd

    carpeta = destino / "enso"
    cache = carpeta / "oisst_cache"
    cache.mkdir(parents=True, exist_ok=True)
    anio_actual = int(time.strftime("%Y"))
    series = {}
    for nombre, (s, n, w, e, paso) in CAJAS_SST.items():
        partes = []
        for anio in range(1982, anio_actual + 1):
            ruta = cache / f"{nombre}_{anio}.csv"
            if not ruta.exists() or anio == anio_actual:
                ini = f"{anio}-01-01" if anio > 1982 else "1982-01-01"
                fin = f"{anio}-12-31" if anio < anio_actual else "last"
                url = (
                    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180.csv?"
                    f"sst[({ini}):1:({fin})][(0.0):1:(0.0)][({s}):{paso}:({n})][({w}):{paso}:({e})]"
                )
                for _ in range(8):
                    try:
                        texto = _get(url, timeout=600).text
                        break
                    except requests.RequestException:
                        time.sleep(30)
                else:
                    raise RuntimeError(f"ERDDAP no respondió para {nombre} {anio}")
                df = pd.read_csv(io.StringIO(texto), skiprows=[1])
                dia = df.groupby("time")["sst"].mean()
                dia.index = pd.to_datetime(dia.index).tz_localize(None).normalize()
                dia.rename("sst").to_csv(ruta)
            partes.append(pd.read_csv(ruta, index_col=0, parse_dates=True)["sst"])
        series[nombre] = pd.concat(partes)
    out = pd.DataFrame(series)
    out.index.name = "fecha"
    archivo = carpeta / "oisst_diario.csv"
    out.round(3).to_csv(archivo)
    return [str(archivo.relative_to(destino.parent))]


def _igp_icen(destino: Path) -> list[str]:
    """ICEN (ENFEN 2024, official) and the list of coastal El Niño events of the IGP."""
    import html
    import re

    carpeta = destino / "enso"
    carpeta.mkdir(parents=True, exist_ok=True)
    icen = carpeta / "igp_icen.txt"
    icen.write_text(_get("http://met.igp.gob.pe/datos/ICEN.txt").text, encoding="utf-8")
    bruto = _get("http://met.igp.gob.pe/elnino/lista_eventos.html").content.decode("latin-1")
    bruto = re.sub(r"<script.*?</script>|<style.*?</style>", "", bruto, flags=re.DOTALL)
    texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto)))
    nino = texto.split("El Niño Costero", 1)[1].split("La Niña Costera", 1)[0]
    filas = re.findall(r"(\d{4}) (\d{1,2}) (\d{4}) (\d{1,2}) (\d+) (Débil|Moderado|Fuerte|Extraordinario)", nino)
    eventos = carpeta / "igp_eventos_el_nino_costero.csv"
    eventos.write_text(
        "anio_inicial,mes_inicial,anio_final,mes_final,duracion_meses,magnitud\n"
        + "\n".join(",".join(f) for f in filas)
        + "\n",
        encoding="utf-8",
    )
    return [str(icen.relative_to(destino.parent)), str(eventos.relative_to(destino.parent))]


def _nasa_power(destino: Path) -> list[str]:
    """NASA POWER (MERRA-2) daily values at the predictor points; no key and no hourly cap.

    A second reanalysis: it fills the points that Open-Meteo (ERA5) cannot serve while its daily
    quota is spent, and lets the analyses check that a signal does not belong to one dataset.
    """
    parametros = "T2M,T2M_MAX,T2M_MIN,T2MDEW,RH2M,QV2M,PS,WS10M,CLOUD_AMT,PRECTOTCORR,ALLSKY_SFC_SW_DWN"
    salida = {}
    for nombre, lat, lon in PUNTOS_PREDICTORES:
        resp = _get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={"parameters": parametros, "community": "RE", "longitude": lon, "latitude": lat,
                    "start": "19830101", "end": time.strftime("%Y%m%d"), "format": "JSON"},
            timeout=300,
        )
        js = resp.json()
        par = js["properties"]["parameter"]
        fechas = sorted(next(iter(par.values())))
        salida[nombre] = {
            "lat": lat, "lon": lon, "elevation": js["geometry"]["coordinates"][2],
            "fecha": [f"{f[:4]}-{f[4:6]}-{f[6:]}" for f in fechas],
            "columnas": {k: [None if v[f] == -999 else v[f] for f in fechas] for k, v in par.items()},
        }
        time.sleep(2)
    archivo = destino / "nasa_power_diario.json"
    archivo.write_text(json.dumps(salida), encoding="utf-8")
    return [str(archivo.relative_to(destino.parent))]


# Boxes (south, north, west, east; longitudes in 0-360) fixed before any analysis, see docs/08-circulacion.md.
CAJAS_CIRCULACION = {
    "u200_altiplano": ("uwnd", 200, (-20.0, -12.0, 285.0, 295.0)),
    "u850_selva": ("uwnd", 850, (-14.0, -8.0, 288.0, 294.0)),
    "v850_selva": ("vwnd", 850, (-14.0, -8.0, 288.0, 294.0)),
    "q850_selva": ("shum", 850, (-14.0, -8.0, 288.0, 294.0)),
    "z500_chile_peru": ("hgt", 500, (-30.0, -15.0, 275.0, 288.0)),
}
CAJA_OLR = (-15.0, -5.0, 290.0, 305.0)
PSL_NCSS = "https://psl.noaa.gov/thredds/ncss/grid/Datasets"


def _ncss_media(ruta: str, variable: str, caja: tuple, ini: str, fin: str, nivel: int | None, destino: Path):
    """Daily area mean of one variable from a PSL THREDDS subset (NetCDF), weighted by cos(lat)."""
    import numpy as np
    import xarray as xr

    s, n, w, e = caja
    params = {"var": variable, "north": n, "south": s, "west": w, "east": e,
              "time_start": f"{ini}T00:00:00Z", "time_end": f"{fin}T00:00:00Z", "accept": "netcdf"}
    if nivel is not None:
        params["vertCoord"] = nivel
    for intento in range(8):
        try:
            resp = requests.get(f"{PSL_NCSS}/{ruta}", params=params, headers={"User-Agent": USER_AGENT}, timeout=300)
        except requests.RequestException:
            time.sleep(15 * (intento + 1))
            continue
        if resp.ok and resp.content[:3] == b"CDF":
            break
        time.sleep(30 * (intento + 1))
    else:
        raise RuntimeError(f"PSL no respondió para {ruta} {variable} {ini}")
    tmp = destino / "_tmp_ncss.nc"
    tmp.write_bytes(resp.content)
    with xr.open_dataset(tmp) as ds:
        da = ds[variable]
        pesos = np.cos(np.deg2rad(da["lat"]))
        serie = da.squeeze().weighted(pesos).mean(dim=[d for d in da.squeeze().dims if d != "time"]).to_series()
    tmp.unlink()
    serie.index = serie.index.normalize()
    return serie


def _noaa_circulacion(destino: Path) -> list[str]:
    """Daily NCEP/NCAR R1 winds and humidity and NOAA OLR over fixed boxes, plus the OMI and the SOI.

    Each variable and year is cached in `circulacion/cache/`. NCEP/NCAR Reanalysis 1 and the
    interpolated OLR are NOAA PSL products; the OMI index and the SOI are NOAA PSL / CPC.
    """
    import pandas as pd

    carpeta = destino / "circulacion"
    cache = carpeta / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    anio_final = int(time.strftime("%Y"))
    columnas = {}
    for nombre, (variable, nivel, caja) in CAJAS_CIRCULACION.items():
        partes = []
        for anio in range(1983, anio_final + 1):
            ruta = cache / f"{nombre}_{anio}.csv"
            if not ruta.exists() or anio == anio_final:
                serie = _ncss_media(
                    f"ncep.reanalysis.dailyavgs/pressure/{variable}.{anio}.nc", variable, caja,
                    f"{anio}-01-01", f"{anio}-12-31", nivel, carpeta,
                )
                serie.rename(nombre).to_csv(ruta)
                time.sleep(1)
            partes.append(pd.read_csv(ruta, index_col=0, parse_dates=True).iloc[:, 0])
        columnas[nombre] = pd.concat(partes)
    ruta = cache / "olr_amazonia.csv"
    serie = _ncss_media("interp_OLR/olr.day.mean.nc", "olr", CAJA_OLR, "1983-01-01", time.strftime("%Y-%m-%d"), None, carpeta)
    serie.rename("olr_amazonia").to_csv(ruta)
    columnas["olr_amazonia"] = serie
    out = pd.DataFrame(columnas)
    out = out[~out.index.duplicated(keep="last")]
    out.index.name = "fecha"
    archivo = carpeta / "ncep_olr_diario.csv"
    out.round(3).to_csv(archivo)
    escritos = [str(archivo.relative_to(destino.parent))]
    for nombre, url in (("omi.txt", "https://psl.noaa.gov/mjo/mjoindex/omi.1x.txt"),
                        ("soi_cpc.txt", "https://www.cpc.ncep.noaa.gov/data/indices/soi")):
        f = carpeta / nombre
        f.write_text(_get(url).text, encoding="utf-8")
        escritos.append(str(f.relative_to(destino.parent)))
    return escritos


def _bom_rmm(destino: Path) -> list[str]:
    """Wheeler-Hendon RMM index (Australian Bureau of Meteorology), daily since 1974."""
    carpeta = destino / "circulacion"
    carpeta.mkdir(parents=True, exist_ok=True)
    f = carpeta / "rmm.txt"
    resp = requests.get("http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt",
                        headers={"User-Agent": "Mozilla/5.0 (illapa-research)"}, timeout=120)
    resp.raise_for_status()
    f.write_text(resp.text, encoding="utf-8")
    return [str(f.relative_to(destino.parent))]


# Boxes (west, south, east, north) of the CHIRPS series: the ERA5 predictor points +-0.1 degrees,
# fixed before looking at any result. Each box is 4 x 4 cells of 0.05 degrees.
CAJAS_CHIRPS = {
    "chosica": (-76.80, -12.03, -76.60, -11.83),
    "santa-eulalia-alta": (-76.50, -11.80, -76.30, -11.60),
    "matucana": (-76.48, -11.94, -76.28, -11.74),
    "ticlio": (-76.30, -11.70, -76.10, -11.50),
    "selva-tarma": (-75.79, -11.52, -75.59, -11.32),
}
CHIRPS_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/{a}/chirps-v3.0.sat.{a}.{m:02d}.{d:02d}.tif"


def _chirps_dia(fecha) -> dict:
    """Mean of the box cells for one day, read with a windowed request (a few kB per box)."""
    import rasterio
    from rasterio.windows import from_bounds

    url = "/vsicurl/" + CHIRPS_URL.format(a=fecha.year, m=fecha.month, d=fecha.day)
    fila = {"fecha": fecha.strftime("%Y-%m-%d")}
    for _ in range(5):
        try:
            entorno = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                                   GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2", GDAL_HTTP_TIMEOUT="30")
            with entorno, rasterio.open(url) as src:
                if abs(src.bounds.left + 180) > 0.1 or src.width != 7200:
                    raise OSError("geotransform inesperado")
                for nombre, (w, s, e, n) in CAJAS_CHIRPS.items():
                    a = src.read(1, window=from_bounds(w, s, e, n, src.transform), masked=True)
                    fila[nombre] = float(a.mean()) if a.count() else None
            return fila
        except Exception:  # noqa: BLE001 - network errors of many kinds; retried
            time.sleep(5)
    raise RuntimeError(f"CHIRPS no respondió para {fecha:%Y-%m-%d}")


def _chirps_v3(destino: Path) -> list[str]:
    """CHIRPS v3 daily rainfall (IMERG-timed, 'sat'), box means, November to April, 1998 to today.

    CHIRPS' daily values are its pentad totals (stations + satellite) spread over the days with the
    timing of NASA IMERG; the timing is therefore independent of ERA5. Each season is cached in
    `chirps_cache/`.
    """
    from concurrent.futures import ThreadPoolExecutor

    import pandas as pd

    cache = destino / "chirps_cache"
    cache.mkdir(parents=True, exist_ok=True)
    hoy = pd.Timestamp.today().normalize()
    partes = []
    for temporada in range(1998, hoy.year + 1):
        ruta = cache / f"temporada_{temporada}.csv"
        ini = max(pd.Timestamp(f"{temporada - 1}-11-01"), pd.Timestamp("1998-01-01"))
        fin = min(pd.Timestamp(f"{temporada}-04-30"), hoy - pd.Timedelta(days=45))
        if fin < ini:
            continue
        if not ruta.exists() or temporada == hoy.year:
            dias = pd.date_range(ini, fin, freq="D")
            with ThreadPoolExecutor(4) as pool:
                filas = list(pool.map(_chirps_dia, dias))
            pd.DataFrame(filas).to_csv(ruta, index=False)
            print(f"  CHIRPS temporada {temporada}: {len(filas)} días", flush=True)
        partes.append(pd.read_csv(ruta, parse_dates=["fecha"]))
    total = pd.concat(partes).drop_duplicates("fecha").sort_values("fecha")
    archivo = destino / "chirps_v3_sat_diario.csv"
    total.round(3).to_csv(archivo, index=False)
    return [str(archivo.relative_to(destino.parent))]


def _igp_ec(destino: Path) -> list[str]:
    """E and C indices (Takahashi et al. 2011, ERSSTv5) as published by the IGP."""
    carpeta = destino / "enso"
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = carpeta / "igp_ec_ersstv5.txt"
    salida.write_text(_get("http://met.igp.gob.pe/datos/ecindex_ersstv5.txt").text, encoding="utf-8")
    return [str(salida.relative_to(destino.parent))]


FUENTES: dict[str, Fuente] = {
    f.id: f
    for f in (
        Fuente(
            id="natural-earth",
            nombre="Natural Earth (ríos y departamentos)",
            url="https://www.naturalearthdata.com",
            licencia="Dominio público",
            atribucion="Made with Natural Earth.",
            descargar=_natural_earth,
        ),
        Fuente(
            id="osm-aguas",
            nombre="OpenStreetMap: ríos y quebradas (Rímac, Chaclacayo a Chosica)",
            url="https://www.openstreetmap.org/copyright",
            licencia="ODbL 1.0",
            atribucion="© colaboradores de OpenStreetMap",
            descargar=_osm_aguas,
        ),
        Fuente(
            id="open-meteo",
            nombre="Open-Meteo: lluvia diaria histórica (2015 a hoy)",
            url="https://open-meteo.com",
            licencia="CC BY 4.0 (API gratuita solo para uso no comercial)",
            atribucion="Weather data by Open-Meteo.com",
            descargar=_open_meteo,
        ),
        Fuente(
            id="open-meteo-horario",
            nombre="Open-Meteo: lluvia horaria y humedad del suelo desde 1983 (2 puntos)",
            url="https://open-meteo.com",
            licencia="CC BY 4.0 (API gratuita solo para uso no comercial)",
            atribucion="Weather data by Open-Meteo.com",
            descargar=_open_meteo_horario,
        ),
        Fuente(
            id="copernicus-dem",
            nombre="Copernicus DEM GLO-30: teselas S12 y S13, W077 (30 m)",
            url="https://registry.opendata.aws/copernicus-dem/",
            licencia="Uso libre con atribución (Copernicus)",
            atribucion="© Unión Europea / ESA, Copernicus DEM GLO-30",
            descargar=_copernicus_dem,
        ),
        Fuente(
            id="osm-edificios",
            nombre="OpenStreetMap: centros de edificaciones (Huachipa a Ricardo Palma)",
            url="https://www.openstreetmap.org/copyright",
            licencia="ODbL 1.0",
            atribucion="© colaboradores de OpenStreetMap",
            descargar=_osm_edificios,
        ),
        Fuente(
            id="noaa-enso",
            nombre="NOAA CPC: ONI (Niño 3.4) y anomalía de TSM Niño 1+2, mensuales",
            url="https://www.cpc.ncep.noaa.gov/data/indices/",
            licencia="Dominio público (gobierno de EE. UU.)",
            atribucion="NOAA Climate Prediction Center",
            descargar=_noaa_enso,
        ),
        Fuente(
            id="open-meteo-predictores",
            nombre="Open-Meteo (ERA5): resumen diario de 11 variables en 6 puntos, 1983 a hoy",
            url="https://open-meteo.com",
            licencia="CC BY 4.0 (API gratuita solo para uso no comercial)",
            atribucion="Weather data by Open-Meteo.com",
            descargar=_open_meteo_predictores,
        ),
        Fuente(
            id="open-meteo-caudal",
            nombre="Open-Meteo (GloFAS): caudal diario del Rímac y Santa Eulalia, 1984 a hoy",
            url="https://open-meteo.com/en/docs/flood-api",
            licencia="CC BY 4.0 (API gratuita solo para uso no comercial)",
            atribucion="Weather data by Open-Meteo.com; GloFAS (Copernicus Emergency Management Service)",
            descargar=_open_meteo_caudal,
        ),
        Fuente(
            id="noaa-oisst",
            nombre="NOAA OISST v2.1: temperatura diaria del mar (Niño 1+2, costa de Perú y Lima)",
            url="https://www.ncei.noaa.gov/products/optimum-interpolation-sst",
            licencia="Dominio público (gobierno de EE. UU.)",
            atribucion="NOAA OISST v2.1 (Huang et al. 2021), vía ERDDAP de CoastWatch",
            descargar=_noaa_oisst,
        ),
        Fuente(
            id="igp-icen",
            nombre="IGP/ENFEN: ICEN oficial y lista de eventos El Niño costero",
            url="http://met.igp.gob.pe/elnino/indices.html",
            licencia="Datos públicos del IGP; sin licencia explícita (se citan)",
            atribucion="Instituto Geofísico del Perú (IGP) y ENFEN, ICEN y lista de eventos El Niño/La Niña costeros",
            descargar=_igp_icen,
        ),
        Fuente(
            id="nasa-power",
            nombre="NASA POWER (MERRA-2): resumen diario en los 6 puntos de predictores, 1983 a hoy",
            url="https://power.larc.nasa.gov/",
            licencia="Datos abiertos de la NASA; cítese POWER",
            atribucion="NASA Prediction Of Worldwide Energy Resources (POWER) Project, MERRA-2",
            descargar=_nasa_power,
        ),
        Fuente(
            id="noaa-circulacion",
            nombre="NOAA PSL: viento y humedad NCEP/NCAR R1 y OLR sobre cajas fijas, OMI y SOI",
            url="https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.html",
            licencia="Dominio público (gobierno de EE. UU.)",
            atribucion="NOAA PSL: NCEP/NCAR Reanalysis 1 (Kalnay et al. 1996), Interpolated OLR, OMI; CPC: SOI",
            descargar=_noaa_circulacion,
        ),
        Fuente(
            id="bom-rmm",
            nombre="BoM: índice MJO RMM diario",
            url="http://www.bom.gov.au/climate/mjo/",
            licencia="Datos públicos de la Oficina de Meteorología de Australia; se citan",
            atribucion="Wheeler & Hendon (2004), Australian Bureau of Meteorology (RMM)",
            descargar=_bom_rmm,
        ),
        Fuente(
            id="chirps-v3",
            nombre="CHIRPS v3 diario (sat, tiempo de IMERG): medias de 5 cajas, noviembre a abril, 1998 a hoy",
            url="https://www.chc.ucsb.edu/data/chirps3",
            licencia="Dominio público y CC BY 4.0 (Climate Hazards Center)",
            atribucion="Funk, C. et al. (2026), CHIRPS v3, Scientific Data 13, 718, doi:10.1038/s41597-026-07096-4",
            descargar=_chirps_v3,
        ),
        Fuente(
            id="igp-ec",
            nombre="IGP: índices E y C mensuales (Takahashi et al. 2011, ERSSTv5)",
            url="http://met.igp.gob.pe/variabclim/indices.html",
            licencia="Datos públicos del IGP; sin licencia explícita (se citan)",
            atribucion="Instituto Geofísico del Perú (IGP); Takahashi et al. (2011), doi:10.1029/2011GL047364",
            descargar=_igp_ec,
        ),
    )
}
