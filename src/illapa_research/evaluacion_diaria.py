"""Daily huaico-day model: labels, single-feature screening, cross-validation and null tests.

The target is "a huaico day was catalogued in Chosica, Chaclacayo, Santa Eulalia or Ricardo
Palma". Positives are few (about 2 % of rainy-season days) and cluster inside a handful of
seasons, so everything here is validated by leaving whole seasons (or whole Niño episodes) out,
and every score is read against the base rate and against a model that only knows the date.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .catalogo import Evento
from .nino import temporada_de


def etiquetas(eventos: Iterable[Evento], idx: pd.DatetimeIndex, dias_antes: int = 0) -> pd.Series:
    """1 on days with a catalogued huaico (optionally also the `dias_antes` days before it).

    The catalogue date is the day the press or the institution reported; night events can be
    filed a day late, which is what `dias_antes=1` allows for.
    """
    y = pd.Series(0, index=idx, dtype=int)
    for e in eventos:
        for k in range(dias_antes + 1):
            d = pd.Timestamp(e.fecha - timedelta(days=k))
            if d in y.index:
                y.loc[d] = 1
    return y


def temporadas_de(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.array([temporada_de(date(d.year, d.month, d.day)) for d in idx])


def auc_rangos(x: np.ndarray, y: np.ndarray) -> float:
    """ROC AUC of a single feature (0.5 = no information); NaN-safe."""
    ok = ~np.isnan(x)
    if y[ok].sum() < 5 or (1 - y[ok]).sum() < 5:
        return float("nan")
    return float(roc_auc_score(y[ok], x[ok]))


def cribado(
    F: pd.DataFrame, y: pd.Series, temporada: np.ndarray, n_boot: int = 300, semilla: int = 0
) -> pd.DataFrame:
    """AUC of every feature with a 90 % interval from a bootstrap over whole seasons."""
    rng = np.random.default_rng(semilla)
    seasons = np.unique(temporada)
    por_temp = {s: np.flatnonzero(temporada == s) for s in seasons}
    yv = y.to_numpy()
    filas = []
    boots = [np.concatenate([por_temp[s] for s in rng.choice(seasons, len(seasons))]) for _ in range(n_boot)]
    for c in F.columns:
        x = F[c].to_numpy(dtype=float)
        a = auc_rangos(x, yv)
        bs = np.array([auc_rangos(x[b], yv[b]) for b in boots])
        lo, hi = np.nanpercentile(bs, [5, 95]) if np.isfinite(bs).any() else (np.nan, np.nan)
        filas.append({"variable": c, "auc": a, "auc_p5": lo, "auc_p95": hi,
                      "signo": "+" if a >= 0.5 else "-", "separa": bool(lo > 0.5 or hi < 0.5)})
    out = pd.DataFrame(filas)
    out["fuerza"] = (out["auc"] - 0.5).abs()
    return out.sort_values("fuerza", ascending=False).reset_index(drop=True)


def _logit(c: float = 0.1) -> object:
    return make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=2000, class_weight=None))


def _imputar(X: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    return X.fillna(ref.median())


def pliegues(temporada: np.ndarray, tipo: str, episodios: list[list[int]] | None = None) -> list[np.ndarray]:
    """Test-index groups: one season per fold, or one Niño episode (set of seasons)."""
    if tipo == "temporada":
        return [np.flatnonzero(temporada == s) for s in np.unique(temporada)]
    if tipo == "episodio":
        usados = set()
        out = []
        for ep in episodios or []:
            out.append(np.flatnonzero(np.isin(temporada, ep)))
            usados |= set(ep)
        resto = [s for s in np.unique(temporada) if s not in usados]
        # non-Niño seasons are grouped in blocks of three consecutive seasons
        for i in range(0, len(resto), 3):
            out.append(np.flatnonzero(np.isin(temporada, resto[i : i + 3])))
        return out
    raise ValueError(tipo)


def validar(
    F: pd.DataFrame,
    y: pd.Series,
    columnas: list[str],
    folds: list[np.ndarray],
    c: float = 0.1,
) -> np.ndarray:
    """Out-of-fold probability for every row, with a logistic model on `columnas`."""
    p = np.full(len(y), np.nan)
    X = F[columnas]
    yv = y.to_numpy()
    for test in folds:
        train = np.setdiff1d(np.arange(len(y)), test)
        Xtr = _imputar(X.iloc[train], X.iloc[train])
        Xte = _imputar(X.iloc[test], X.iloc[train])
        m = _logit(c).fit(Xtr, yv[train])
        p[test] = m.predict_proba(Xte)[:, 1]
    return p


def p_climatologia(y: pd.Series, mes: np.ndarray, folds: list[np.ndarray]) -> np.ndarray:
    """Base rate by calendar month learned out of fold: the model that only knows the date."""
    p = np.full(len(y), np.nan)
    yv = y.to_numpy()
    for test in folds:
        train = np.setdiff1d(np.arange(len(y)), test)
        tasa = pd.Series(yv[train]).groupby(mes[train]).mean()
        p[test] = pd.Series(mes[test]).map(tasa).fillna(yv[train].mean()).to_numpy()
    return p


def metricas(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray, presupuesto: float = 0.05) -> dict[str, float]:
    """AP, AUC, Brier skill and log-loss gain against the reference, and the hit rate when the top
    `presupuesto` share of days raises an alarm."""
    ok = ~np.isnan(p)
    y, p, p_ref = y[ok], np.clip(p[ok], 1e-6, 1 - 1e-6), np.clip(p_ref[ok], 1e-6, 1 - 1e-6)
    corte = np.quantile(p, 1 - presupuesto)
    return {
        "ap": float(average_precision_score(y, p)),
        "ap_base": float(y.mean()),
        "auc": float(roc_auc_score(y, p)),
        "brier": float(np.mean((p - y) ** 2)),
        "brier_skill": float(1 - np.mean((p - y) ** 2) / np.mean((p_ref - y) ** 2)),
        "logloss_ganancia": float(log_loss(y, p_ref) - log_loss(y, p)),
        "aciertos_con_5pc_alarmas": float(y[p >= corte].sum() / y.sum()),
    }


def prueba_nula(
    F: pd.DataFrame, y: pd.Series, columnas: list[str], temporada: np.ndarray, folds: list[np.ndarray],
    n: int = 30, semilla: int = 0,
) -> np.ndarray:
    """Average precision when the labels are cyclically shifted inside each season.

    The shift keeps the number of events and their clustering in every season but breaks their
    link with the weather, so it is the fair "no skill" distribution for the real score.
    """
    rng = np.random.default_rng(semilla)
    yv = y.to_numpy()
    res = []
    for _ in range(n):
        ys = yv.copy()
        for s in np.unique(temporada):
            i = np.flatnonzero(temporada == s)
            ys[i] = np.roll(yv[i], int(rng.integers(5, max(6, len(i) - 5))))
        p = validar(F, pd.Series(ys, index=y.index), columnas, folds)
        res.append(average_precision_score(ys[~np.isnan(p)], p[~np.isnan(p)]))
    return np.array(res)


def rezagos(
    F: pd.DataFrame, y: pd.Series, columnas: list[str], temporada: np.ndarray, lags: range = range(15),
    mask: np.ndarray | None = None, n_boot: int = 200, semilla: int = 0,
) -> pd.DataFrame:
    """AUC of each feature as it was `lag` days before the day, with a season bootstrap interval.

    `F` must cover consecutive days (the shift is done before the rainy-season mask is applied).
    A lag of 0 uses the value of the day itself, so only lags of 1 or more are usable before the
    event; lag 0 shows what the day looks like once it is happening.
    """
    mask = np.ones(len(F), dtype=bool) if mask is None else mask
    rng = np.random.default_rng(semilla)
    yv = y.to_numpy()[mask]
    ts = temporada[mask]
    seasons = np.unique(ts)
    por_temp = {s: np.flatnonzero(ts == s) for s in seasons}
    boots = [np.concatenate([por_temp[s] for s in rng.choice(seasons, len(seasons))]) for _ in range(n_boot)]
    filas = []
    for c in columnas:
        for lag in lags:
            x = F[c].shift(lag).to_numpy(dtype=float)[mask]
            a = auc_rangos(x, yv)
            bs = np.array([auc_rangos(x[b], yv[b]) for b in boots])
            lo, hi = np.nanpercentile(bs, [5, 95]) if np.isfinite(bs).any() else (np.nan, np.nan)
            filas.append({"variable": c, "lag": lag, "auc": a, "auc_p5": lo, "auc_p95": hi,
                          "separa": bool(lo > 0.5 or hi < 0.5)})
    return pd.DataFrame(filas)


def centrar_por_temporada(F: pd.DataFrame, temporada: np.ndarray) -> pd.DataFrame:
    """Remove each season's mean: what is left is the day-to-day timing inside a season."""
    G = F.copy()
    for c in G.columns:
        G[c] = G[c] - G.groupby(temporada)[c].transform("mean")
    return G
