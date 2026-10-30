"""El Niño seasons from NOAA CPC monthly indices.

A rainy season (December to April) is named after the year of its January. It counts as a
global Niño when the mean ONI (Niño 3.4) of the DJF, JFM and FMA windows is at least +0.5 °C,
and as a coastal Niño when the mean Niño 1+2 anomaly of January to April is at least +1.0 °C.
Both thresholds were fixed before looking at the huaico dates. The coastal index is a proxy:
the official one for Peru is the ICEN of ENFEN/IGP, which this repository does not download yet.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

UMBRAL_ONI = 0.5
UMBRAL_NINO12 = 1.0


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


def temporadas(oni: pd.DataFrame, nino12: pd.DataFrame) -> pd.DataFrame:
    """One row per rainy season with both indices and the Niño flags."""
    filas = []
    for anio in sorted(set(nino12["anio"]) & set(oni["anio"])):
        o = oni[(oni["anio"] == anio) & oni["trimestre"].isin(["DJF", "JFM", "FMA"])]["oni"]
        n = nino12[(nino12["anio"] == anio) & nino12["mes"].between(1, 4)]["nino12"]
        if len(o) < 3 or len(n) < 4:
            continue  # incomplete season (the current one)
        filas.append({"temporada": anio, "oni": o.mean(), "nino12": n.mean()})
    df = pd.DataFrame(filas)
    df["nino_global"] = df["oni"] >= UMBRAL_ONI
    df["nino_costero"] = df["nino12"] >= UMBRAL_NINO12
    df["nino"] = df["nino_global"] | df["nino_costero"]
    return df.set_index("temporada")


def temporada_de(fecha: date) -> int:
    """Rainy season of a date: November and December belong to the next year's season."""
    return fecha.year + 1 if fecha.month >= 11 else fecha.year
