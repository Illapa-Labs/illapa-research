"""Bias correction of the UK Met Office rain forecast against SENAMHI's observed rain (PISCOp).

Question: the UK Met Office model (the one Illapa serves) marks two to five times more rain than PISCOp over the
ravines of Chosica and Chaclacayo. Does correcting that bias make it more useful on the days of huaicos?

Method, kept honest on purpose:

* The forecast is the first day of each run saved by Open-Meteo (its historical-forecast archive), added up over
  SENAMHI's rain day (7 a.m. to 7 a.m., Lima time) and averaged over the six 0.1° cells that PISCOp has over the
  Rímac valley between Chaclacayo and Chosica.
* Two corrections are fitted on the days of the rainy seasons (December to April): a single scale factor and an
  empirical quantile mapping. Each season is corrected with a fit that never saw it (leave one season out).
* A monotone correction never changes the order of the days, so it cannot improve what is measured with percentiles
  (the rank correlation, or "the top 5 % of days"). It can only fix calibration: how many days pass a threshold given
  in mm. That is why the tests use thresholds in mm taken from the observed rain, and show the results before and
  after.
* The catalog only holds reported huaicos, so the alarm rates on the other days are an upper bound on false alarms
  (a day without a report may still have had one).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

MODELO = "ukmo_global_deterministic_10km"
API_ARCHIVO = "https://historical-forecast-api.open-meteo.com/v1/forecast"
# The six 0.1° cells of PISCOp over the Rímac valley (longitudes, latitudes).
LONGITUDES = (-76.75, -76.65, -76.55)
LATITUDES = (-11.85, -11.95)
# Rainy seasons with an archive of the model (it starts in late 2022): first day, last day.
TEMPORADAS = {
    2022: ("2022-12-01", "2023-04-30"),
    2023: ("2023-12-01", "2024-04-30"),
    2024: ("2024-12-01", "2025-04-30"),
}
# SENAMHI's rain day runs from 7 a.m. to 7 a.m. Lima time, that is 12:00 to 12:00 UTC. Open-Meteo's hourly rain at
# time t is the rain of the hour before, so the hours t = 13:00 of day D to 12:00 of day D+1 cover that rain day.
INICIO_DIA_UTC = 13
PERCENTILES_UMBRAL = (90.0, 95.0, 99.0)


def temporada_de(fecha: date | pd.Timestamp) -> int:
    """The year in which the rainy season (December to April) of this date began."""
    return fecha.year if fecha.month >= 12 else fecha.year - 1


def en_temporada(indice: pd.DatetimeIndex) -> np.ndarray:
    return (indice.month >= 12) | (indice.month <= 4)


# ---------------------------------------------------------------------------- observed rain (PISCOp)


def serie_pisco(ruta_nc: Path, cache: Path | None = None) -> pd.Series:
    """Daily rain (mm), mean of the six cells over the Rímac valley, from the PISCOp v3.0 daily file."""
    if cache is not None and Path(cache).exists():
        s = pd.read_csv(cache, index_col=0, parse_dates=True)["pp_mm"]
        return s
    import netCDF4

    ds = netCDF4.Dataset(str(ruta_nc))
    lon, lat = ds.variables["longitude"][:], ds.variables["latitude"][:]
    ci = sorted(int(np.argmin(abs(lon - x))) for x in LONGITUDES)
    cj = sorted(int(np.argmin(abs(lat - y))) for y in LATITUDES)
    bloque = ds.variables["precipitation"][:, cj[0] : cj[-1] + 1, ci[0] : ci[-1] + 1]
    bloque = np.ma.filled(bloque.astype(float), np.nan)
    medias = np.nanmean(bloque, axis=(1, 2))
    # PISCOp v3.0 daily starts on 1981-01-01
    s = pd.Series(medias, index=pd.date_range("1981-01-01", periods=len(medias), freq="D"), name="pp_mm")
    if cache is not None:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(cache, index_label="fecha")
    return s


# ---------------------------------------------------------------------------- forecast (Open-Meteo archive)


def descargar_modelo(destino: Path, pausa: float = 3.0) -> Path:
    """Hourly rain of the model at the six cells, for the three rainy seasons. One file with the raw answers."""
    lats = ",".join(str(y) for y in LATITUDES for _ in LONGITUDES)
    lons = ",".join(str(x) for _ in LATITUDES for x in LONGITUDES)
    salida: dict[str, list] = {}
    for anio, (desde, hasta) in TEMPORADAS.items():
        # One more day at the end, to close the last rain day
        hasta_mas_uno = (date.fromisoformat(hasta) + timedelta(days=1)).isoformat()
        params = {
            "latitude": lats,
            "longitude": lons,
            "start_date": desde,
            "end_date": hasta_mas_uno,
            "hourly": "precipitation",
            "timezone": "GMT",
            "models": MODELO,
        }
        for intento in range(3):
            r = requests.get(API_ARCHIVO, params=params, timeout=120)
            if r.status_code == 200:
                break
            time.sleep(20)
        r.raise_for_status()
        cuerpo = r.json()
        salida[str(anio)] = cuerpo if isinstance(cuerpo, list) else [cuerpo]
        time.sleep(pausa)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_text(json.dumps(salida), encoding="utf-8")
    return Path(destino)


def serie_modelo(ruta: Path) -> pd.Series:
    """Daily rain (mm) of the model, mean of the six cells, over SENAMHI's rain day, indexed by the day it starts."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    partes = []
    for puntos in datos.values():
        horas = pd.to_datetime(puntos[0]["hourly"]["time"])
        valores = np.array(
            [[np.nan if v is None else v for v in p["hourly"]["precipitation"]] for p in puntos], dtype=float
        )
        partes.append(pd.Series(np.nanmean(valores, axis=0), index=horas))
    horas = pd.concat(partes).sort_index()
    horas = horas[~horas.index.duplicated()]
    # Shifting 12 hours makes each rain day start at midnight, so a plain daily sum closes it
    desplazada = horas.copy()
    desplazada.index = desplazada.index - pd.Timedelta(hours=INICIO_DIA_UTC)
    por_dia = desplazada.resample("D").agg(["sum", "count"])
    s = por_dia["sum"].where(por_dia["count"] == 24)
    s.name = "pp_mm"
    return s


def mejor_desfase(modelo: pd.Series, obs: pd.Series) -> int:
    """Days to shift the model so that it lines up with the observed series (-1, 0 or 1), by correlation.

    PISCOp may label its 7 a.m. to 7 a.m. day with the day it starts or the one it ends, so the alignment is measured
    instead of assumed.
    """
    mejor, r_mejor = 0, -2.0
    for desfase in (-1, 0, 1):
        m = modelo.copy()
        m.index = m.index + pd.Timedelta(days=desfase)
        dias = m.index.intersection(obs.index)
        dias = dias[en_temporada(dias)]
        a, b = m.loc[dias].dropna(), obs.loc[dias]
        comun = a.index.intersection(b.dropna().index)
        r = float(np.corrcoef(a.loc[comun], b.loc[comun])[0, 1])
        if r > r_mejor:
            mejor, r_mejor = desfase, r
    return mejor


# ---------------------------------------------------------------------------- corrections


@dataclass(frozen=True)
class Escala:
    """One factor: observed total over modelled total, on the days used to fit."""

    factor: float

    @staticmethod
    def ajustar(modelo: pd.Series, obs: pd.Series) -> Escala:
        return Escala(float(obs.sum() / modelo.sum()))

    def aplicar(self, x: pd.Series | np.ndarray) -> pd.Series | np.ndarray:
        return x * self.factor


@dataclass(frozen=True)
class MapeoCuantiles:
    """Empirical quantile mapping: the model's value at each quantile becomes the observed one.

    Values above the largest modelled one are shifted by the difference at the top, so extremes keep growing.
    """

    q_modelo: np.ndarray
    q_obs: np.ndarray

    @staticmethod
    def ajustar(modelo: pd.Series, obs: pd.Series, n: int = 100) -> MapeoCuantiles:
        qs = np.linspace(0, 100, n + 1)
        qm = np.percentile(modelo.to_numpy(), qs)
        qo = np.percentile(obs.to_numpy(), qs)
        # Strictly increasing model quantiles, or the interpolation is undefined
        qm = qm + np.arange(len(qm)) * 1e-9
        return MapeoCuantiles(qm, qo)

    def aplicar(self, x: pd.Series | np.ndarray) -> pd.Series | np.ndarray:
        valores = np.asarray(x, dtype=float)
        sal = np.interp(valores, self.q_modelo, self.q_obs)
        arriba = valores > self.q_modelo[-1]
        sal = np.where(arriba, self.q_obs[-1] + (valores - self.q_modelo[-1]), sal)
        sal = np.maximum(sal, 0.0)
        return pd.Series(sal, index=x.index, name=x.name) if isinstance(x, pd.Series) else sal


def corregir_por_temporada(modelo: pd.Series, obs: pd.Series, metodo) -> pd.Series:
    """Correct each season with a fit made on the other seasons only (rainy-season days)."""
    dias = modelo.index.intersection(obs.index)
    dias = dias[en_temporada(dias)]
    m, o = modelo.loc[dias].dropna(), obs.loc[dias].dropna()
    dias = m.index.intersection(o.index)
    m, o = m.loc[dias], o.loc[dias]
    temporadas = np.array([temporada_de(d) for d in dias])
    salida = pd.Series(np.nan, index=dias, name="corregido")
    for t in sorted(set(temporadas)):
        fuera = temporadas == t
        ajuste = metodo.ajustar(m[~fuera], o[~fuera])
        salida[fuera] = ajuste.aplicar(m[fuera])
    return salida


# ---------------------------------------------------------------------------- measures


def umbrales_mm(obs: pd.Series, percentiles: tuple[float, ...] = PERCENTILES_UMBRAL) -> dict[float, float]:
    """Thresholds in mm: percentiles of the observed rain on the season days studied."""
    return {p: float(np.percentile(obs.to_numpy(), p)) for p in percentiles}


def metricas(obs: pd.Series, pred: pd.Series, umbral_mm: float) -> dict[str, float]:
    """Bias, error and the contingency scores for "the day reaches `umbral_mm`"."""
    dias = obs.index.intersection(pred.index)
    o, p = obs.loc[dias].to_numpy(), pred.loc[dias].to_numpy()
    real, alarma = o >= umbral_mm, p >= umbral_mm
    aciertos = int((real & alarma).sum())
    falsas = int((~real & alarma).sum())
    perdidas = int((real & ~alarma).sum())
    return {
        "dias": len(dias),
        "sesgo": float(p.sum() / o.sum()),
        "mae_mm": float(np.abs(p - o).mean()),
        "r": float(np.corrcoef(o, p)[0, 1]),
        "aciertos": aciertos,
        "falsas_alarmas": falsas,
        "perdidos": perdidas,
        "pod": aciertos / max(1, aciertos + perdidas),
        "far": falsas / max(1, aciertos + falsas),
        "csi": aciertos / max(1, aciertos + falsas + perdidas),
    }


def dias_con_huaico(eventos, desde: date, hasta: date) -> list[date]:
    """Days with a reported huaico and an exact date inside the studied seasons."""
    dias = {e.fecha for e in eventos if e.precision_fecha == "dia" and desde <= e.fecha <= hasta}
    return sorted(d for d in dias if temporada_de(d) in TEMPORADAS and d.month in (12, 1, 2, 3, 4))


def evaluar_dias_huaico(pred: pd.Series, huaicos: list[date], umbral_mm: float, ventana: int = 1) -> dict[str, float]:
    """Hit rate on huaico days, and alarm rate on the other days.

    A huaico counts as caught when the forecast of its day, or of the `ventana` days before, reaches the threshold
    (the date in the press can be the day after the rain).
    """
    fechas = [pd.Timestamp(d) for d in huaicos if pd.Timestamp(d) in pred.index]
    capturados = 0
    for f in fechas:
        previos = pred.loc[f - pd.Timedelta(days=ventana) : f]
        capturados += int((previos >= umbral_mm).any())
    cerca = set()
    for f in fechas:
        cerca.update(pd.date_range(f - pd.Timedelta(days=ventana), f + pd.Timedelta(days=ventana)))
    otros = pred[~pred.index.isin(cerca)]
    return {
        "huaicos": len(fechas),
        "capturados": capturados,
        "tasa_aciertos": capturados / max(1, len(fechas)),
        "dias_otros": len(otros),
        "tasa_alarma_otros": float((otros >= umbral_mm).mean()),
    }


def comparar(modelo: pd.Series, obs: pd.Series, huaicos: list[date]) -> pd.DataFrame:
    """Table: for each correction and threshold, the scores overall and on huaico days."""
    dias = modelo.index.intersection(obs.index)
    dias = dias[en_temporada(dias)]
    base = modelo.loc[dias].dropna()
    obs_t = obs.loc[base.index]
    umbrales = umbrales_mm(obs_t)
    variantes = {
        "sin corregir": base,
        "escala": corregir_por_temporada(modelo, obs, Escala),
        "cuantiles": corregir_por_temporada(modelo, obs, MapeoCuantiles),
    }
    filas = []
    for nombre, pred in variantes.items():
        for p, umbral in umbrales.items():
            comun = pred.dropna().index
            m = metricas(obs_t.loc[comun], pred.loc[comun], umbral)
            h = evaluar_dias_huaico(pred.dropna(), huaicos, umbral)
            filas.append({"correccion": nombre, "percentil_obs": p, "umbral_mm": round(umbral, 2), **m, **h})
    return pd.DataFrame(filas)


def comparar_a_igual_alarma(
    modelo: pd.Series, obs: pd.Series, huaicos: list[date], tasas: tuple[float, ...] = (0.05, 0.10, 0.25)
) -> pd.DataFrame:
    """Huaicos caught by each variant when each one is allowed the same share of alarms on the other days.

    This is the fair test of skill: it does not depend on which mm each variant calls an alarm, so a correction that
    only changes calibration scores the same as the raw forecast (apart from the small cost of fitting it out of
    sample).
    """
    dias = modelo.index.intersection(obs.index)
    dias = dias[en_temporada(dias)]
    base = modelo.loc[dias].dropna()
    variantes = {
        "sin corregir": base,
        "escala": corregir_por_temporada(modelo, obs, Escala),
        "cuantiles": corregir_por_temporada(modelo, obs, MapeoCuantiles),
    }
    fechas = [pd.Timestamp(d) for d in huaicos if pd.Timestamp(d) in base.index]
    cerca = set()
    for f in fechas:
        cerca.update(pd.date_range(f - pd.Timedelta(days=1), f + pd.Timedelta(days=1)))
    filas = []
    for nombre, pred in variantes.items():
        pred = pred.dropna()
        otros = pred[~pred.index.isin(cerca)]
        for tasa in tasas:
            umbral = float(np.quantile(otros.to_numpy(), 1 - tasa))
            capturados = sum(int((pred.loc[f - pd.Timedelta(days=1) : f] > umbral).any()) for f in fechas)
            filas.append(
                {"correccion": nombre, "tasa_alarma_otros": tasa, "umbral_mm": round(umbral, 2),
                 "huaicos": len(fechas), "capturados": capturados, "tasa_aciertos": capturados / max(1, len(fechas))}
            )
    return pd.DataFrame(filas)


def principal(ruta_pisco: Path, raiz: Path = Path("datos")) -> pd.DataFrame:
    """Run the whole comparison: reads or downloads the series, prints and returns the table."""
    from .catalogo import cargar_todos

    pisco = serie_pisco(ruta_pisco, cache=raiz / "pisco" / "rimac_diario.csv")
    ruta_modelo = raiz / "open_meteo_ukmo_archivo.json"
    if not ruta_modelo.exists():
        descargar_modelo(ruta_modelo)
    modelo = serie_modelo(ruta_modelo)
    desfase = mejor_desfase(modelo, pisco)
    modelo.index = modelo.index + pd.Timedelta(days=desfase)
    print(f"Alineación del modelo con PISCOp: {desfase:+d} días")
    desde, hasta = date(2022, 12, 1), date(2025, 4, 30)
    huaicos = dias_con_huaico(cargar_todos(sin_baja_confianza=True), desde, hasta)
    tabla = comparar(modelo, pisco, huaicos)
    igual = comparar_a_igual_alarma(modelo, pisco, huaicos)
    print("\nA igual proporción de alarmas en los otros días:")
    print(igual.round(2).to_string())
    print(f"\nHuaicos con día exacto en las temporadas 2022-23 a 2024-25: {[d.isoformat() for d in huaicos]}")
    return tabla


if __name__ == "__main__":  # pragma: no cover
    import sys

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(principal(Path(sys.argv[1])).round(2).to_string())
