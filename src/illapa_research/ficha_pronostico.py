"""Probability sheet fed by a rain forecast, calibrated by lead time.

The out-of-sample probabilities of the GEFSv12 reforecast backtest (`gefs_backtest`, chapter 19)
say how a probability built from a *forecast* behaves against the catalogue: it overstates
(observed/predicted 0.66 to 0.78) and it loses value with the lead. This module turns that
history into a usable sheet:

1. a recalibration per lead (Platt on the logit, fitted leaving one season out and refitted with
   season bootstraps for its interval);
2. empirical reliability bands per lead (days, huaicos and a Wilson interval of the observed share);
3. `ficha_desde_pronostico`: given the raw probability of the forecast-driven model and the lead,
   the calibrated probability with interval, the band it falls in, how much it depends on 2017,
   the conditions that were given, and the fixed statement of limits.

The event is always "a huaico day catalogued in the study zone". This is not an alert and not a
forecast to decide evacuations; it is the historical frequency of catalogued huaico days under
similar forecasts.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression

PLAZOS = {1: "24 h", 2: "48 h", 3: "72 h"}
BANDAS = (0.0, 0.02, 0.10, 0.25, 1.01)
EPS = 1e-4
LIMITES = (
    "No es una alerta ni una predicción para decidir evacuaciones. Es la frecuencia histórica de días con "
    "huaico catalogado (Chosica, Chaclacayo, Santa Eulalia, Ricardo Palma) bajo pronósticos parecidos, medida "
    "con el reforecast de 2000 a 2019. El catálogo registra lo que se reportó, no todo lo que ocurrió. Un solo "
    "año (2017, 23 de 55 días con huaico) pesa mucho. Ante una emergencia llama al 115 (INDECI)."
)


def _logit(p: np.ndarray) -> np.ndarray:
    return logit(np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS))


def ajustar_platt(p_crudo: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Platt scaling: calibrated = sigmoid(a + b * logit(raw)). Returns (a, b)."""
    x = _logit(p_crudo)[:, None]
    m = LogisticRegression(C=1e6, max_iter=1000).fit(x, y)
    return float(m.intercept_[0]), float(m.coef_[0, 0])


def aplicar_platt(p_crudo: np.ndarray | float, a: float, b: float) -> np.ndarray:
    return expit(a + b * _logit(np.atleast_1d(p_crudo)))


def calibrar_fuera_de_temporada(p_crudo: np.ndarray, y: np.ndarray, temporada: np.ndarray) -> np.ndarray:
    """Platt fitted leaving each season out and applied to it: honest calibrated probabilities."""
    out = np.empty(len(y))
    for s in np.unique(temporada):
        test = temporada == s
        a, b = ajustar_platt(p_crudo[~test], y[~test])
        out[test] = aplicar_platt(p_crudo[test], a, b)
    return out


def metricas(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray) -> dict[str, float]:
    p = np.clip(p, EPS, 1 - EPS)
    br, br_ref = float(np.mean((p - y) ** 2)), float(np.mean((p_ref - y) ** 2))
    ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return {"brier": br, "brier_skill": 1 - br / br_ref, "logloss": ll, "obs_sobre_pred": float(y.sum() / p.sum())}


def bandas(y: np.ndarray, p: np.ndarray, cortes: tuple[float, ...] = BANDAS) -> pd.DataFrame:
    """Days and huaicos by probability band, with the Wilson 80 % interval of the observed share."""
    from .probabilidad import wilson

    filas = []
    for a, b in pairwise(cortes):
        m = (p >= a) & (p < b)
        n, k = int(m.sum()), int(y[m].sum())
        lo, hi = wilson(k, n) if n else (np.nan, np.nan)
        filas.append({"banda": f"{a:.0%} a {min(b, 1):.0%}", "desde": a, "hasta": min(b, 1.0), "dias": n,
                      "huaicos": k, "observado": k / n if n else np.nan, "ic80_bajo": lo, "ic80_alto": hi,
                      "predicho_medio": float(p[m].mean()) if n else np.nan})
    return pd.DataFrame(filas)


def cargar_oof(ruta: Path) -> pd.DataFrame:
    """Out-of-sample probabilities of the GEFS backtest (`catalogo/gefs_probabilidades_fuera_de_muestra.csv.gz`)."""
    return pd.read_csv(ruta, parse_dates=["dia"])


def evaluar_calibracion(oof: pd.DataFrame, columna: str = "pp_qm") -> pd.DataFrame:
    """Raw against calibrated (season-out) per lead, on all days and without 2017.

    Calibration on "all" is fitted with every other season. The "sin 2017" rows fit the calibrator
    without 2017 and score the other seasons, so the 2017 cluster never helps nor hurts.
    """
    filas = []
    for plazo in sorted(oof["plazo"].unique()):
        d = oof[oof["plazo"] == plazo].reset_index(drop=True)
        y, p, ts, clim = d["huaico"].to_numpy(), d[columna].to_numpy(), d["temporada"].to_numpy(), d["climatologia"].to_numpy()
        for etiqueta, mask in (("todo", np.ones(len(d), bool)), ("sin 2017", ts != 2017)):
            cal = np.empty(len(d))
            for s in np.unique(ts[mask]):
                fit = mask & (ts != s)
                a, b = ajustar_platt(p[fit], y[fit])
                cal[ts == s] = aplicar_platt(p[ts == s], a, b)
            m = mask
            filas.append({"plazo": PLAZOS[plazo], "dias": int(m.sum()), "huaicos": int(y[m].sum()), "subconjunto": etiqueta,
                          "version": "cruda", **metricas(y[m], p[m], clim[m])})
            filas.append({"plazo": PLAZOS[plazo], "dias": int(m.sum()), "huaicos": int(y[m].sum()), "subconjunto": etiqueta,
                          "version": "calibrada", **metricas(y[m], cal[m], clim[m])})
    return pd.DataFrame(filas)


def bootstrap_platt(p_crudo: np.ndarray, y: np.ndarray, temporada: np.ndarray, n: int = 500, semilla: int = 0) -> np.ndarray:
    """(a, b) of Platt refitted on `n` season bootstraps, shape (n, 2)."""
    rng = np.random.default_rng(semilla)
    seasons = np.unique(temporada)
    por = {s: np.flatnonzero(temporada == s) for s in seasons}
    out = np.empty((n, 2))
    for i in range(n):
        idx = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        out[i] = ajustar_platt(p_crudo[idx], y[idx])
    return out


class FichaPronostico:
    """Calibrators, bands and bootstraps per lead, fitted once from the out-of-sample table."""

    def __init__(self, oof: pd.DataFrame, columna: str = "pp_qm", n_boot: int = 500):
        self.columna = columna
        self.por_plazo: dict[int, dict] = {}
        for plazo in sorted(oof["plazo"].unique()):
            d = oof[oof["plazo"] == plazo]
            y, p, ts = d["huaico"].to_numpy(), d[columna].to_numpy(), d["temporada"].to_numpy()
            a, b = ajustar_platt(p, y)
            a2, b2 = ajustar_platt(p[ts != 2017], y[ts != 2017])
            cal_oof = calibrar_fuera_de_temporada(p, y, ts)
            self.por_plazo[int(plazo)] = {
                "platt": (a, b), "platt_sin2017": (a2, b2), "boot": bootstrap_platt(p, y, ts, n_boot),
                "bandas": bandas(y, cal_oof), "bandas_sin2017": bandas(y[ts != 2017], cal_oof[ts != 2017]),
                "clima": float(y.mean()), "dias": len(y), "huaicos": int(y.sum()),
            }

    @staticmethod
    def _advertencias(plazo: int, p: float, banda: dict, banda_s: dict) -> list[str]:
        return _advertencias_texto(plazo, p, banda, banda_s)

    def ficha(self, p_crudo: float, plazo: int, condiciones: dict | None = None, quebradas: list[dict] | None = None) -> dict:
        """Sheet for one forecast: `p_crudo` is the forecast-driven model's probability, `plazo` 1, 2 or 3 days."""
        if plazo not in self.por_plazo:
            raise ValueError(f"plazo {plazo} sin calibrar: use {sorted(self.por_plazo)}")
        c = self.por_plazo[plazo]
        p = float(aplicar_platt(p_crudo, *c["platt"])[0])
        p_sin = float(aplicar_platt(p_crudo, *c["platt_sin2017"])[0])
        boots = expit(c["boot"][:, 0] + c["boot"][:, 1] * float(_logit(np.array([p_crudo]))[0]))
        lo, hi = (float(v) for v in np.percentile(boots, [10, 90]))
        banda = c["bandas"][(c["bandas"]["desde"] <= p) & (p < c["bandas"]["hasta"] + 1e-9)].iloc[0].to_dict()
        banda_s = c["bandas_sin2017"][(c["bandas_sin2017"]["desde"] <= p) & (p < c["bandas_sin2017"]["hasta"] + 1e-9)].iloc[0].to_dict()
        avisos = self._advertencias(plazo, p, banda, banda_s)
        if banda["dias"] > 0:
            p_ref, (lo_ref, hi_ref) = float(banda["observado"]), (float(banda["ic80_bajo"]), float(banda["ic80_alto"]))
            origen = "frecuencia observada en la banda de fiabilidad"
            if p > 2 * p_ref and p - p_ref > 0.05:
                avisos.append(
                    f"La curva calibrada da {p:.0%}, pero de los {banda['dias']} días históricos de la banda solo "
                    f"{banda['observado']:.0%} tuvo huaico: se informa la frecuencia observada, no la curva."
                )
        else:
            p_ref, lo_ref, hi_ref, origen = p, lo, hi, "curva calibrada (banda sin días históricos)"
        return {
            "plazo": PLAZOS[plazo], "probabilidad": p_ref, "intervalo_80": (lo_ref, hi_ref), "origen_de_la_cifra": origen,
            "probabilidad_modelo_calibrada": p, "intervalo_80_modelo": (lo, hi), "probabilidad_cruda": float(p_crudo),
            "probabilidad_sin_2017": float(banda_s["observado"]) if banda_s["dias"] else p_sin,
            "banda_de_fiabilidad": {k: banda[k] for k in ("banda", "dias", "huaicos", "observado", "ic80_bajo", "ic80_alto")},
            "banda_sin_2017": {k: banda_s[k] for k in ("banda", "dias", "huaicos", "observado", "ic80_bajo", "ic80_alto")},
            "frecuencia_base": c["clima"],
            "veces_la_base": p_ref / c["clima"] if c["clima"] else float("nan"),
            "advertencias": avisos,
            "condiciones": condiciones or {}, "quebradas": quebradas or [], "limites": LIMITES,
            "evento": "día con huaico catalogado en Chosica, Chaclacayo, Santa Eulalia o Ricardo Palma",
        }


def _advertencias_texto(plazo: int, p: float, banda: dict, banda_s: dict) -> list[str]:
    avisos = []
    if plazo >= 2:
        avisos.append(
            f"A {PLAZOS[plazo]} la calibración corrige el nivel, pero la habilidad sobre la climatología queda cerca de "
            "cero en Brier: útil para ordenar días, no para leer la cifra como probabilidad fiable."
        )
        if p >= 0.25:
            avisos.append(
                f"En la banda de 25 % o más a {PLAZOS[plazo]} solo {banda['huaicos']} de {banda['dias']} días tuvieron huaico "
                f"({banda['observado']:.0%}): esa banda NO es fiable."
            )
    if banda["dias"] < 30:
        avisos.append(f"La banda «{banda['banda']}» tiene solo {banda['dias']} días históricos: poca potencia.")
    if banda["observado"] > 0 and banda_s["observado"] < 0.6 * banda["observado"]:
        avisos.append(
            f"Sin 2017 la frecuencia observada de la banda baja de {banda['observado']:.0%} a {banda_s['observado']:.0%}: "
            "depende de un solo año."
        )
    return avisos


def correr(raiz: Path = Path("."), n_boot: int = 500) -> dict:
    """Evaluation tables and the fitted sheet from the committed GEFS backtest output."""
    oof = cargar_oof(Path(raiz) / "catalogo" / "gefs_probabilidades_fuera_de_muestra.csv.gz")
    modelo = FichaPronostico(oof, n_boot=n_boot)
    tabla_bandas = pd.concat(
        [c["bandas"].assign(plazo=PLAZOS[p], subconjunto="todo") for p, c in modelo.por_plazo.items()]
        + [c["bandas_sin2017"].assign(plazo=PLAZOS[p], subconjunto="sin 2017") for p, c in modelo.por_plazo.items()],
        ignore_index=True,
    )
    return {"oof": oof, "modelo": modelo, "calibracion": evaluar_calibracion(oof), "bandas": tabla_bandas}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Calibra por plazo la probabilidad basada en pronóstico y guarda las tablas")
    ap.add_argument("--raiz", type=Path, default=Path("."))
    ap.add_argument("--n-boot", type=int, default=500)
    args = ap.parse_args(argv)
    R = correr(args.raiz, args.n_boot)
    cat = args.raiz / "catalogo"
    R["calibracion"].round(4).to_csv(cat / "ficha_pronostico_calibracion.csv", index=False)
    R["bandas"].round(4).to_csv(cat / "ficha_pronostico_bandas.csv", index=False)
    print(R["calibracion"].round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
