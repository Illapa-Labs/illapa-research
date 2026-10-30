"""El Niño seasons from NOAA CPC monthly indices.

A rainy season (December to April) is named after the year of its January. It counts as a
global Niño when the mean ONI (Niño 3.4) of the DJF, JFM and FMA windows is at least +0.5 °C.
It counts as a coastal Niño when the official ICEN (ENFEN/IGP) says so: an event of the IGP
list covers at least two of February, March and April, or, for the years after that list, the
mean ICEN of January to April is at least +0.4 °C (the ENFEN threshold for a weak warm
condition). The older proxy (mean Niño 1+2 anomaly of January to April at least +1.0 °C) is
kept as `nino_costero_n12` for sensitivity. All thresholds were fixed before looking at the
huaico dates.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

UMBRAL_ONI = 0.5
UMBRAL_NINO12 = 1.0
UMBRAL_ICEN = 0.4


def cargar_oni(ruta: Path) -> pd.DataFrame:
    """ONI by overlapping season (`oni.ascii.txt`)."""
    df = pd.read_csv(ruta, sep=r"\s+")
    return df.rename(columns={"SEAS": "trimestre", "YR": "anio", "ANOM": "oni"})[
        ["trimestre", "anio", "oni"]
    ]


def cargar_nino12(ruta: Path) -> pd.DataFrame:
    """Monthly Niño 1+2 anomaly (`sstoi.indices`)."""
    df = pd.read_csv(ruta, sep=r"\s+")
    # Columns repeat: NINO1+2 ANOM, NINO3 ANOM.1, NINO4 ANOM.2, NINO3.4 ANOM.3.
    return df.rename(columns={"YR": "anio", "MON": "mes", "ANOM": "nino12"})[
        ["anio", "mes", "nino12"]
    ]


def cargar_icen(ruta: Path) -> pd.DataFrame:
    """Monthly official ICEN (`igp_icen.txt`)."""
    return pd.read_csv(ruta, sep=r"\s+", comment="%", names=["anio", "mes", "icen"])


def cargar_eventos_costeros(ruta: Path) -> pd.DataFrame:
    """IGP list of coastal El Niño events with their magnitude."""
    return pd.read_csv(ruta)


def _meses_en_evento(anio: int, eventos: pd.DataFrame) -> tuple[int, str]:
    """How many of February, March and April of `anio` fall inside a listed event, and its size."""
    n, mag = 0, ""
    for mes in (2, 3, 4):
        k = anio * 12 + mes
        for e in eventos.itertuples():
            if e.anio_inicial * 12 + e.mes_inicial <= k <= e.anio_final * 12 + e.mes_final:
                n += 1
                mag = e.magnitud
    return n, mag


def temporadas(
    oni: pd.DataFrame,
    nino12: pd.DataFrame,
    icen: pd.DataFrame | None = None,
    eventos_costeros: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per rainy season with the indices and the Niño flags."""
    filas = []
    for anio in sorted(set(nino12["anio"]) & set(oni["anio"])):
        o = oni[(oni["anio"] == anio) & oni["trimestre"].isin(["DJF", "JFM", "FMA"])]["oni"]
        n = nino12[(nino12["anio"] == anio) & nino12["mes"].between(1, 4)]["nino12"]
        if len(o) < 3 or len(n) < 4:
            continue  # incomplete season (the current one)
        filas.append({"temporada": anio, "oni": o.mean(), "nino12": n.mean()})
    df = pd.DataFrame(filas)
    df["nino_global"] = df["oni"] >= UMBRAL_ONI
    df["nino_costero_n12"] = df["nino12"] >= UMBRAL_NINO12
    if icen is not None and eventos_costeros is not None:
        ultimo_evento = int(eventos_costeros["anio_final"].max())
        icen_ene_abr, n_evento, magnitud = [], [], []
        for a in df["temporada"]:
            x = icen[(icen["anio"] == a) & icen["mes"].between(1, 4)]["icen"]
            icen_ene_abr.append(x.mean() if len(x) == 4 else float("nan"))
            n, mag = _meses_en_evento(int(a), eventos_costeros)
            n_evento.append(n)
            magnitud.append(mag)
        df["icen"] = icen_ene_abr
        df["magnitud_icen"] = magnitud
        listado = df["temporada"] <= ultimo_evento
        df["nino_costero"] = np.where(listado, np.array(n_evento) >= 2, df["icen"] >= UMBRAL_ICEN)
    else:
        df["nino_costero"] = df["nino_costero_n12"]
    df["nino"] = df["nino_global"] | df["nino_costero"]
    return df.set_index("temporada")


def temporada_de(fecha: date) -> int:
    """Rainy season of a date: November and December belong to the next year's season."""
    return fecha.year + 1 if fecha.month >= 11 else fecha.year


def cargar_temporadas(datos: Path) -> pd.DataFrame:
    """Seasons table from the files `descargar-datos` leaves in `datos/enso/`.

    Uses the official ICEN when `igp-icen` was downloaded, and the Niño 1+2 proxy otherwise.
    """
    carpeta = Path(datos) / "enso"
    icen = carpeta / "igp_icen.txt"
    eventos = carpeta / "igp_eventos_el_nino_costero.csv"
    return temporadas(
        cargar_oni(carpeta / "noaa_oni.txt"),
        cargar_nino12(carpeta / "noaa_nino12.txt"),
        cargar_icen(icen) if icen.exists() and eventos.exists() else None,
        cargar_eventos_costeros(eventos) if icen.exists() and eventos.exists() else None,
    )


def episodios(temporadas: pd.DataFrame) -> list[list[int]]:
    """Runs of consecutive Niño seasons (2015-2016, 2019-2020...) are one episode."""
    out: list[list[int]] = []
    for a in sorted(temporadas.index[temporadas["nino"]]):
        if out and a - out[-1][-1] == 1:
            out[-1].append(a)
        else:
            out.append([a])
    return out
