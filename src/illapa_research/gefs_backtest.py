"""Backtest of "forecast rain -> probability of a huaico day" with the GEFSv12 reforecast (2000-2019).

Pre-registered design (written before any score was looked at; see docs/19):

* **Test rows**: rainy-season days (December to April) of the seasons 2000 to 2019 whose reforecast
  exists. Always reported with and without 2017 (23 of the 56 catalogued huaico days).
* **PP, perfect prognosis**: the day model (ridge-logistic, C = 0.03, as in chapters 05 and 15) is
  trained on *ERA5-built* inputs of every other season (1984-2026, leave one season out) and applied
  to the held-out season with the rain of the day *replaced* by the forecast. Rain features that the
  reforecast cannot give (peak hour, 3-hour maximum) are left out of this model. Variants:
  ``pp_qm`` (forecast rain mapped to the ERA5 distribution by empirical quantiles, fitted on the
  other test seasons), ``pp_crudo`` (no mapping) and ``techo`` (the same model with ERA5 rain: the
  best a perfect rain forecast could do).
* **Lead k** (1, 2, 3 days): rain from the run issued k-1 days before the day (see
  `gefs_reforecast`). Antecedent features are the observed ones shifted by k days, so nothing that
  was not known at issue time is used.
* **MOS**: ridge-logistic trained *inside* 2000-2019 (leave one season out) on forecast
  statistics of the 5 boxes: ``mos_media`` (ensemble mean), ``mos_ens`` (+ maximum, spread and
  exceedance probabilities) and ``mos_ant`` (+ antecedents). Fixed regularisation (C = 0.3, 0.1,
  0.03), chosen before looking.
* **References**: raw forecast ranking (``gefs_media``: the ensemble mean of the valley box; a
  threshold only cuts this ranking), and the monthly climatology.
* **Nulls**: labels shifted cyclically inside each season (same events per season, same clustering),
  the whole pipeline refitted: thousands of worlds on the GPU.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import gefs_reforecast as G
from . import gpu

C_PP = 0.03
C_MOS = {"mos_media": 0.3, "mos_ens": 0.1, "mos_ant": 0.03, "mos_ens_conv": 0.1}
# ERA5 daily-rain column -> GEFS box (fixed in advance). The 3-day column is the rolling sum.
MAPEO_LLUVIA = {
    "ch_lluvia_1d": "chosica",
    "chosica_h_lluvia_1d": "chosica",
    "sea_lluvia_1d": "santa-eulalia-alta",
    "mat_lluvia_1d": "matucana",
    "cuenca-alta_h_lluvia_1d": "matucana",
    "tic_lluvia_1d": "ticlio",
}
COLS_1D = tuple(MAPEO_LLUVIA)
COLS_3D = tuple(c.replace("1d", "3d") for c in COLS_1D)
TEMPORADAS_PRUEBA = tuple(range(2000, 2020))


def temporada_de_fecha(idx: pd.DatetimeIndex) -> np.ndarray:
    """Rainy season of each date: November and December belong to the next year's season."""
    return np.where(idx.month >= 11, idx.year + 1, idx.year)


# ------------------------------------------------------------------ quantile mapping
def cuantiles(x_entrena: np.ndarray, y_entrena: np.ndarray, nuevos: np.ndarray) -> np.ndarray:
    """Empirical quantile mapping: the value of `nuevos` goes to the same quantile of `y_entrena`."""
    xs = np.sort(x_entrena)
    n = len(xs)
    u = (np.searchsorted(xs, nuevos, "left") + np.searchsorted(xs, nuevos, "right")) / (2 * n)
    return np.quantile(y_entrena, np.clip(u, 0, 1))


def mapear_fuera_de_temporada(gefs: pd.Series, obs: pd.Series, en_temporada: pd.Series) -> pd.Series:
    """Quantile-map the forecast of every season with a fit that never saw that season.

    `gefs` and `obs` are daily series; the fit uses only the days with `en_temporada` True and both
    values present. Days outside the rainy season (the 29-30 November needed for 3-day sums) use the
    fit of the season they belong to.
    """
    ts = pd.Series(temporada_de_fecha(gefs.index), index=gefs.index)
    ambos = pd.concat([gefs, obs], axis=1, keys=["g", "o"]).dropna()
    ambos = ambos[en_temporada.reindex(ambos.index).fillna(False).to_numpy(dtype=bool)]
    ts_ambos = pd.Series(temporada_de_fecha(ambos.index), index=ambos.index)
    out = pd.Series(np.nan, index=gefs.index)
    for s in np.unique(ts.dropna()):
        fit = ambos[ts_ambos != s]
        sel = ts == s
        if len(fit) >= 50:
            out[sel] = cuantiles(fit["g"].to_numpy(), fit["o"].to_numpy(), gefs[sel].to_numpy())
    return out


# ------------------------------------------------------------------ inputs
def tabla_de_ensamble(corridas: pd.DataFrame) -> pd.DataFrame:
    """Ensemble summaries per (day, lead, box): mean, max, spread and exceedance probabilities."""
    ll = G.lluvia_por_dia_y_plazo(corridas)
    return G.resumen_de_ensamble(ll)


def serie_gefs(ens: pd.DataFrame, plazo: int, caja: str, col: str = "media") -> pd.Series:
    s = ens.xs((plazo, caja), level=("plazo", "caja"))[col]
    s.index = pd.DatetimeIndex(s.index)
    return s.sort_index()


def _estandarizar_ref(X: np.ndarray, n_ref: int) -> np.ndarray:
    """Median-impute and z-score with the statistics of the first `n_ref` rows (no labels)."""
    X = np.asarray(X, dtype=np.float64).copy()
    med = np.nanmedian(X[:n_ref], axis=0)
    idx = np.where(np.isnan(X))
    X[idx] = np.take(med, idx[1])
    sd = X[:n_ref].std(axis=0)
    sd[sd == 0] = 1.0
    return (X - X[:n_ref].mean(axis=0)) / sd


class Filas:
    """Rainy-season rows of the daily model (from `modelo_diario.cargar_datos`)."""

    def __init__(self, D):
        self.F = D.F
        self.mask = D.inventario["mask"]
        self.idx = D.F.index[self.mask]
        self.ts = np.asarray(D.temporada)[self.mask]
        self.y = D.y[self.mask].to_numpy().astype(float)
        self.mes = np.asarray(D.mes)[self.mask]
        self.todas = [c for c in D.F.columns if not c.startswith("icen_")]

    def antecedentes(self, k: int) -> pd.DataFrame:
        return self.F[self.todas].shift(k)[self.mask]


def entradas_pp(filas: Filas, ens: pd.DataFrame, plazo: int, dias_prueba: pd.DatetimeIndex):
    """ERA5 rows and forecast rows (quantile-mapped and raw) of the PP model for one lead."""
    F = filas.F
    en_temp = pd.Series(np.zeros(len(F), dtype=bool), index=F.index)
    en_temp[filas.idx] = True
    crudo, mapeado = {}, {}
    for c1, caja in MAPEO_LLUVIA.items():
        g = serie_gefs(ens, plazo, caja, "media").reindex(F.index)
        crudo[c1] = g
        mapeado[c1] = mapear_fuera_de_temporada(g, F[c1], en_temp)
    out = {}
    ant = filas.antecedentes(plazo)
    for nombre, d in (("fc_qm", mapeado), ("fc_crudo", crudo)):
        d1 = pd.DataFrame(d)
        d3 = d1.rolling(3).sum().rename(columns=lambda c: c.replace("1d", "3d"))
        out[nombre] = pd.concat([d1.loc[dias_prueba], d3.loc[dias_prueba], ant.loc[dias_prueba]], axis=1)
    era = pd.concat([F[list(COLS_1D) + list(COLS_3D)][filas.mask], ant], axis=1)
    return era, out["fc_qm"][era.columns], out["fc_crudo"][era.columns]


def ajustar_por_pliegue(
    X_grande: np.ndarray, y: np.ndarray, ts: np.ndarray, temporadas_prueba, n_era: int,
    quitar_de_entrenamiento: tuple[int, ...] = (), dispositivo: str | None = None,
) -> np.ndarray:
    """Probabilities of every row of `X_grande` from the leave-one-season-out fits (shape folds x rows)."""
    N = X_grande.shape[0]
    Y = np.zeros((len(temporadas_prueba), N))
    M = np.zeros((len(temporadas_prueba), N), dtype=bool)
    Y[:, :n_era] = y
    for f, s in enumerate(temporadas_prueba):
        M[f, :n_era] = (ts != s) & ~np.isin(ts, quitar_de_entrenamiento)
    return gpu.ajustar_logit_lote(X_grande, Y, M, C=C_PP, dispositivo_=dispositivo)


def ensamblar(P: np.ndarray, temporadas_prueba, ts_prueba: np.ndarray, pos_era_prueba: np.ndarray,
              n_era: int) -> dict[str, np.ndarray]:
    """Out-of-fold probability of every test row, read from the fold of its own season.

    Row layout of the big design matrix: ERA5 rows (n_era), quantile-mapped forecast rows (nt),
    raw forecast rows (nt). Returns the ERA5 ceiling (``techo``), ``pp_qm`` and ``pp_crudo``.
    """
    nt = len(ts_prueba)
    out = {k: np.empty(nt) for k in ("techo", "pp_qm", "pp_crudo")}
    for f, s in enumerate(temporadas_prueba):
        j = np.flatnonzero(ts_prueba == s)
        out["techo"][j] = P[f, pos_era_prueba[j]]
        out["pp_qm"][j] = P[f, n_era + j]
        out["pp_crudo"][j] = P[f, n_era + nt + j]
    return out


# ------------------------------------------------------------------ metrics
def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def metricas(y: np.ndarray, p: np.ndarray, p_clim: np.ndarray | None = None, es_prob: bool = True) -> dict[str, float]:
    from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

    out = {"n": len(y), "eventos": int(y.sum()), "ap": float(average_precision_score(y, p)),
           "ap_base": float(y.mean()), "auc": float(roc_auc_score(y, p))}
    for presup in (0.05, 0.10):
        corte = np.quantile(p, 1 - presup)
        out[f"aciertos_{int(presup * 100)}pc"] = float(y[p >= corte].sum() / max(1, y.sum()))
    if es_prob:
        pp = np.clip(p, 1e-6, 1 - 1e-6)
        out["brier"] = brier(y, pp)
        out["logloss"] = float(log_loss(y, pp))
        out["obs_sobre_pred"] = float(y.sum() / pp.sum())
        if p_clim is not None:
            out["brier_skill"] = float(1 - brier(y, pp) / brier(y, np.clip(p_clim, 1e-6, 1 - 1e-6)))
    return out


def valor_costo_perdida(y: np.ndarray, p: np.ndarray, razones=(0.02, 0.05, 0.1, 0.2, 0.3, 0.5)) -> pd.DataFrame:
    """Relative economic value (cost-loss): alarm when p >= C/L; 1 = perfect forecast, 0 = climatology."""
    base = y.mean()
    filas = []
    for c in razones:
        alarma = p >= c
        gasto = (c * alarma.sum() + ((y == 1) & ~alarma).sum()) / len(y)
        clima = min(c, base)
        perfecto = base * c
        filas.append({"coste_sobre_perdida": c, "alarmas_pc": float(alarma.mean()),
                      "valor": float((clima - gasto) / (clima - perfecto)) if clima > perfecto else np.nan})
    return pd.DataFrame(filas)


def bootstrap_temporadas(y, ts, columnas: dict[str, np.ndarray], n: int = 1000, semilla: int = 0,
                         funcion=None) -> pd.DataFrame:
    """Season-block bootstrap: 5-95 % intervals of `funcion(y, p)` for each column of predictions."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    funcion = funcion or {"ap": average_precision_score, "auc": roc_auc_score}
    res = {k: {f: [] for f in funcion} for k in columnas}
    for _ in range(n):
        ii = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        if y[ii].sum() == 0:
            continue
        for k, p in columnas.items():
            for f, fn in funcion.items():
                res[k][f].append(fn(y[ii], p[ii]))
    filas = []
    for k in columnas:
        fila = {"modelo": k}
        for f in funcion:
            lo, hi = np.percentile(res[k][f], [5, 95])
            fila[f"{f}_p5"], fila[f"{f}_p95"] = lo, hi
        filas.append(fila)
    return pd.DataFrame(filas)


def diferencia_pareada(y, ts, p_a, p_b, n: int = 2000, semilla: int = 0) -> dict[str, float]:
    """AP(a) - AP(b) on the same season resamples: mean and 90 % interval."""
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    d = []
    for _ in range(n):
        ii = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        if y[ii].sum() == 0:
            continue
        d.append(average_precision_score(y[ii], p_a[ii]) - average_precision_score(y[ii], p_b[ii]))
    lo, hi = np.percentile(d, [5, 95])
    return {"delta_ap": float(np.mean(d)), "p5": float(lo), "p95": float(hi), "p_positivo": float(np.mean(np.array(d) > 0))}
