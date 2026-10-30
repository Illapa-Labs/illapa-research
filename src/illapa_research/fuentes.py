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
# Boxes (south, north, west, east, stride) for the daily sea surface temperature of OISST.
CAJAS_SST = {
    "nino12": (-10.0, 0.0, -90.0, -80.0, 4),
    "costa_peru": (-14.0, -8.0, -82.0, -77.0, 4),
    "costa_lima": (-13.5, -11.5, -78.5, -76.5, 1),
}


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
                                    "hourly": VARIABLES_HORARIAS, "timezone": "America/Lima"},
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
            d = df.set_index("time").resample("D").agg(
                {
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
            )
            d.columns = ["_".join(c) if c[1] not in ("", "mean") else c[0] for c in d.columns]
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
    """Daily NOAA OISST v2.1 sea surface temperature, area means of three Pacific boxes."""
    import io

    import pandas as pd

    carpeta = destino / "enso"
    carpeta.mkdir(parents=True, exist_ok=True)
    series = {}
    for nombre, (s, n, w, e, paso) in CAJAS_SST.items():
        partes = []
        for anio in range(1982, int(time.strftime("%Y")) + 1):
            ini = f"{anio}-01-01" if anio > 1982 else "1982-01-01"
            fin = f"{anio}-12-31" if anio < int(time.strftime("%Y")) else time.strftime("%Y-%m-%d")
            url = (
                "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180.csv?"
                f"sst[({ini}):1:({fin})][(0.0):1:(0.0)][({s}):{paso}:({n})][({w}):{paso}:({e})]"
            )
            for _ in range(5):
                try:
                    texto = _get(url, timeout=300).text
                    break
                except requests.RequestException:
                    time.sleep(20)
            else:
                raise RuntimeError(f"ERDDAP no respondió para {nombre} {anio}")
            df = pd.read_csv(io.StringIO(texto), skiprows=[1])
            partes.append(df.groupby("time")["sst"].mean())
            time.sleep(1)
        serie = pd.concat(partes)
        serie.index = pd.to_datetime(serie.index).tz_localize(None).normalize()
        series[nombre] = serie
    out = pd.DataFrame(series)
    out.index.name = "fecha"
    archivo = carpeta / "oisst_diario.csv"
    out.round(3).to_csv(archivo)
    return [str(archivo.relative_to(destino.parent))]


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
    )
}
