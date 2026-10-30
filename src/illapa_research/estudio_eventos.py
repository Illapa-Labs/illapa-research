"""Event study: how extreme was the rain on the days huaicos were reported?

A huaico day is compared with every other day of the rainy season (December to
April). The catalog only holds reported events, so the alarm rates computed
here are an upper bound on false alarms, never a measured false-alarm rate.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd


def cargar_horario(ruta: Path) -> dict[str, pd.DataFrame]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    out = {}
    for punto, horas in datos.items():
        df = pd.DataFrame(horas)
        df["time"] = pd.to_datetime(df["time"])
        out[punto] = df.set_index("time")
    return out


def diario(horas: pd.DataFrame, prefijo: str) -> pd.DataFrame:
    """Daily rain features. Antecedent sums (7 and 30 days) exclude the day itself."""
    p = horas["precipitation"]
    d = pd.DataFrame(
        {
            f"{prefijo}_p1d": p.resample("D").sum(),
            f"{prefijo}_pmaxh": p.resample("D").max(),
            f"{prefijo}_suelo": horas["soil_moisture_0_to_7cm"].resample("D").mean(),
        }
    )
    d[f"{prefijo}_p3d"] = d[f"{prefijo}_p1d"].rolling(3).sum()
    d[f"{prefijo}_p7d"] = d[f"{prefijo}_p1d"].shift(1).rolling(7).sum()
    d[f"{prefijo}_p30d"] = d[f"{prefijo}_p1d"].shift(1).rolling(30).sum()
    return d


def temporada(d: pd.DataFrame, hasta: int) -> pd.DataFrame:
    """Rainy-season days (December to April) up to the given year."""
    return d[((d.index.month >= 12) | (d.index.month <= 4)) & (d.index.year <= hasta)]


def percentil_evento(d: pd.DataFrame, temp: pd.DataFrame, fecha: date, col: str) -> float:
    """Percentile of the event's value (the day or the day before) among season days."""
    t = pd.Timestamp(fecha)
    v = d.loc[t - pd.Timedelta(days=1) : t, col].max()
    return float((temp[col] < v).mean() * 100)


def puntaje(temp: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Daily score: the highest percentile rank among the given variables."""
    return pd.concat([temp[c].rank(pct=True) * 100 for c in cols], axis=1).max(axis=1)


def tasa_aciertos(score: pd.Series, fechas: list[date], umbral: float) -> tuple[int, float]:
    """Events caught (score over the threshold on the day or the day before) and alarm days per year."""
    aciertos = 0
    for f in fechas:
        t = pd.Timestamp(f)
        if (score.loc[t - pd.Timedelta(days=1) : t] >= umbral).any():
            aciertos += 1
    anios = score.index.year.nunique()
    return aciertos, float((score >= umbral).sum() / anios)
