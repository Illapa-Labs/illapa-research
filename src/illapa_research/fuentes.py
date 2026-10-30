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
    )
}
