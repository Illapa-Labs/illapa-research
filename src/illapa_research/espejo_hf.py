"""Mirror of the downloaded data in a Hugging Face dataset repository.

Why: the free APIs (Open-Meteo above all) limit calls per hour, so rebuilding `datos/` from the
original sources can take hours. A mirror lets a new machine, or a worker, fetch the files in
minutes. The mirror is a copy of what `descargar-datos` leaves, with the same `MANIFIESTO.json`
and a dataset card (README.md) that lists every source with its licence and attribution.

The repository is created **private**: make it public only after checking that each source allows
redistribution (see DATOS.md). Credentials come from `hf auth login`; this module never reads or
stores a token.
"""

from __future__ import annotations

import json
from pathlib import Path

# Folders and files of `datos/` that are mirrored, with the source ids of the manifest they belong to.
ARCHIVOS = {
    "dem": "copernicus-dem",
    "enso/oisst_diario.csv": "noaa-oisst",
    "enso/noaa_oni.txt": "noaa-enso",
    "enso/noaa_nino12.txt": "noaa-enso",
    "enso/igp_icen.txt": "igp-icen",
    "enso/igp_eventos_el_nino_costero.csv": "igp-icen",
    "open_meteo_predictores_diarios.json": "open-meteo-predictores",
    "predictores_cache": "open-meteo-predictores",
    "open_meteo_caudal_glofas.json": "open-meteo-caudal",
    "nasa_power_diario.json": "nasa-power",
    "open_meteo_horario_estudio.json": "open-meteo-horario",
    "open_meteo_lluvia_diaria.json": "open-meteo",
    "osm_aguas_chosica.json": "osm-aguas",
    "osm_edificios_centros.json": "osm-edificios",
    "MANIFIESTO.json": "",
}


# Sources left out of a public mirror: no explicit licence (the IGP publishes the ICEN without one).
# They are small and `descargar-datos --solo igp-icen` fetches them from the IGP.
EXCLUIDAS_EN_PUBLICO = {"igp-icen"}

# Extra credit lines that the licences of some sources ask for in any redistribution.
ATRIBUCIONES = {
    "copernicus-dem": "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and "
    "Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.",
    "open-meteo-predictores": "Weather data by Open-Meteo.com (CC BY 4.0); contains modified Copernicus Climate "
    "Change Service information (ERA5).",
    "open-meteo-horario": "Weather data by Open-Meteo.com (CC BY 4.0); contains modified Copernicus Climate "
    "Change Service information (ERA5-Land).",
    "open-meteo": "Weather data by Open-Meteo.com (CC BY 4.0).",
    "open-meteo-caudal": "Weather data by Open-Meteo.com (CC BY 4.0); GloFAS, Copernicus Emergency Management Service.",
    "osm-aguas": "© OpenStreetMap contributors, ODbL 1.0. A database derived from these files must stay under ODbL.",
    "osm-edificios": "© OpenStreetMap contributors, ODbL 1.0. A database derived from these files must stay under ODbL.",
    "nasa-power": "NASA Prediction Of Worldwide Energy Resources (POWER) Project, MERRA-2.",
    "noaa-oisst": "NOAA OISST v2.1 (Huang et al., 2021), public domain.",
}


def tarjeta(manifiesto: dict, publico: bool = False) -> str:
    """Dataset card with licence and attribution of every mirrored source."""
    ids = {i for i in ARCHIVOS.values() if i}
    filas = [
        f"| `{k}` | {v['nombre']} | {v['licencia']} | {v['atribucion']} | {v['descargado'][:10]} |"
        for k, v in sorted(manifiesto.items())
        if k in ids and not (publico and k in EXCLUIDAS_EN_PUBLICO)
    ]
    creditos = [ATRIBUCIONES[k] for k in sorted(manifiesto) if k in ATRIBUCIONES and k in ids]
    return (
        "---\nlicense: other\nlanguage:\n- es\ntags:\n- hazards\n- peru\n- debris-flow\n---\n\n"
        "# Datos de illapa-research\n\n"
        "Copia de los datos que baja `descargar-datos` en "
        "[Illapa-Labs/illapa-research](https://github.com/Illapa-Labs/illapa-research), para no "
        "repetir las descargas (las APIs gratuitas limitan las llamadas por hora). **Cada fuente "
        "conserva su licencia y su atribución**; la licencia AGPL del repositorio cubre el código, "
        "no estos datos. No es un sistema de alerta.\n\n"
        "| Fuente | Nombre | Licencia | Atribución | Descargado |\n|---|---|---|---|---|\n"
        + "\n".join(filas)
        + "\n\n## Atribuciones\n\n"
        + "\n".join(f"- {c}" for c in creditos)
        + "\n\n## Condiciones\n\n"
        "- Cada archivo conserva la licencia de su fuente; la tabla de arriba manda sobre la etiqueta `other`.\n"
        "- OpenStreetMap (ODbL): una base derivada que se publique debe seguir bajo ODbL.\n"
        "- Open-Meteo: los datos se ofrecen bajo CC BY 4.0; su API gratuita es solo para uso no comercial, "
        "así que quien vuelva a pedirlos a la API debe respetar esa condición.\n"
        + ("- Los datos del IGP (ICEN y lista de eventos El Niño costero) no se incluyen en la copia pública "
           "porque no traen licencia explícita: `uv run descargar-datos --solo igp-icen` los baja del IGP.\n"
           if publico else "")
    )


def subir(repo: str, datos: Path = Path("datos"), publico: bool = False) -> list[str]:
    """Upload the mirrored files of `datos/` to the dataset repo `repo` ("usuario/nombre")."""
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo, repo_type="dataset", private=not publico, exist_ok=True)
    manifiesto = json.loads((datos / "MANIFIESTO.json").read_text(encoding="utf-8"))
    subidos = []
    for ruta, fuente in ARCHIVOS.items():
        if publico and fuente in EXCLUIDAS_EN_PUBLICO:
            continue
        local = datos / ruta
        if not local.exists():
            continue
        if local.is_dir():
            api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=str(local), path_in_repo=ruta)
        else:
            api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=str(local), path_in_repo=ruta)
        subidos.append(ruta)
    if publico:  # MANIFIESTO.json lists every source: publish only the mirrored ones
        manifiesto = {k: v for k, v in manifiesto.items() if k not in EXCLUIDAS_EN_PUBLICO}
        api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=json.dumps(manifiesto, ensure_ascii=False, indent=2).encode("utf-8"), path_in_repo="MANIFIESTO.json")
    api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=tarjeta(manifiesto, publico).encode("utf-8"),
                    path_in_repo="README.md")
    return subidos


def bajar(repo: str, destino: Path = Path("datos")) -> Path:
    """Fetch the mirror into `destino`, keeping what is already there."""
    from huggingface_hub import snapshot_download

    destino.mkdir(parents=True, exist_ok=True)
    return Path(snapshot_download(repo_id=repo, repo_type="dataset", local_dir=str(destino),
                                  allow_patterns=[*ARCHIVOS, *(f"{a}/*" for a in ARCHIVOS)]))
