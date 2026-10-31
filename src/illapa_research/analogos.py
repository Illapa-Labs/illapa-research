"""Analog ("nearest days") estimate of the huaico-day probability, on the GPU, season-out validated.

Idea from Lguensat et al. (2017, Monthly Weather Review, "The Analog Data Assimilation"): instead of
a parametric model, look up the K most similar days in the catalogue and read what happened. The
paper's warnings are respected: analogs only work in a low-dimensional space (intrinsic dimension
below about 10), so the caller passes a handful of columns, not the 118 of the full model; and
extremes fall outside the convex hull of their neighbours, so a locally linear variant is offered
next to the locally constant one (Nadaraya-Watson).

Both variants are *linear smoothers* of the training labels: the estimate for a test day is
``sum_k c_k * y[neighbour_k] + s * base_rate``. The neighbours and the coefficients do not depend
on the labels, so a null world (labels shifted inside each season) only needs a gather. That is
what makes thousands of null worlds cheap on the GPU.

Everything is leave-one-season-out. The feature transform (normal scores of the training days) is
fitted on the training seasons of each fold; K, bandwidth and ridge are chosen *inside* each
training set by an inner season-out validation, never with the test season.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import gpu

try:  # PyTorch is an optional extra: `uv sync --extra gpu`
    import torch
except ImportError:  # pragma: no cover
    torch = None

REJILLA_CONSTANTE = tuple((k, hm, 0.0) for k in (60, 240, 480, 960) for hm in (1.0, 2.0, 4.0, 8.0))
REJILLA_LINEAL = tuple((k, hm, r) for k in (240, 480, 960) for hm in (2.0, 4.0, 8.0) for r in (0.05, 0.3))
PRIOR = 1.0  # strength of the shrinkage to the base rate, in units of one neighbour at distance 0


@dataclass
class Plan:
    """What a fold needs to turn any label vector into predictions: neighbours and coefficients."""

    prueba: np.ndarray  # (m,) rows predicted
    entrenamiento: np.ndarray  # (n_train,) rows that may be neighbours
    vecinos: np.ndarray  # (m, K) indices into the full arrays
    c: np.ndarray  # (m, K) coefficients on the neighbours' labels
    s: np.ndarray  # (m,) coefficient on the training base rate
    config: tuple[int, float, float]


def normalizar(X: np.ndarray, ref: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Normal scores of every column, from the empirical distribution of `ref` (no labels used).

    Rain and discharge are heavily skewed; ranks make distances mean "how unusual", and a day more
    extreme than any in `ref` simply sits at the edge. Missing values take the median (score 0).
    """
    from scipy.special import ndtri

    X = np.asarray(X, dtype=float)
    ref = np.asarray(ref, dtype=float)
    A, B = np.zeros_like(X), np.zeros_like(ref)
    for j in range(X.shape[1]):
        r = np.sort(ref[~np.isnan(ref[:, j]), j])
        n = len(r)
        for src, dst in ((X, A), (ref, B)):
            v = src[:, j]
            lo = np.searchsorted(r, v, side="left")
            hi = np.searchsorted(r, v, side="right")
            u = np.clip(((lo + hi) / 2 + 0.5) / (n + 1), 1e-4, 1 - 1e-4)
            dst[:, j] = np.where(np.isnan(v), 0.0, ndtri(u))
    return A, B


def _dtype(dev: str):
    return torch.float64 if dev == "cpu" else torch.float32


def vecinos(Zp: np.ndarray, Ze: np.ndarray, k: int, dispositivo_: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(indices, squared distances) of the `k` nearest rows of `Ze` for every row of `Zp`, sorted."""
    dev = gpu.dispositivo(dispositivo_)
    a = torch.as_tensor(Zp, dtype=_dtype(dev), device=dev)
    b = torch.as_tensor(Ze, dtype=_dtype(dev), device=dev)
    d2 = torch.cdist(a, b).pow(2)
    v, i = torch.topk(d2, min(k, b.shape[0]), dim=1, largest=False)
    return i.cpu().numpy(), v.cpu().numpy().astype(float)


def coeficientes(Zp: np.ndarray, Ze: np.ndarray, idx: np.ndarray, d2: np.ndarray, k: int, hm: float,
                 ridge: float | None, dispositivo_: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Coefficients (c, s) of the smoother using the first `k` neighbours.

    Gaussian weights w = exp(-d2 / (hm * mean d2 of the k neighbours)): the bandwidth follows the
    local density. ``ridge`` None or 0 gives the locally constant estimate (shrunk to the base
    rate with strength PRIOR); a value gives the locally linear one: weighted least squares of y on
    the neighbours' offsets from the test day, with a ridge penalty ``ridge * sum(w)`` on the
    slopes, whose intercept is the estimate.
    """
    dev = gpu.dispositivo(dispositivo_)
    dt = _dtype(dev)
    d2k = torch.as_tensor(d2[:, :k], dtype=dt, device=dev)
    w = torch.exp(-d2k / (hm * d2k.mean(dim=1, keepdim=True) + 1e-12))
    sw = w.sum(dim=1, keepdim=True)
    if not ridge:
        c = w / (sw + PRIOR)
        s = (PRIOR / (sw + PRIOR))[:, 0]
        return c.cpu().numpy().astype(float), s.cpu().numpy().astype(float)
    Zt = torch.as_tensor(Ze, dtype=dt, device=dev)
    Z0 = torch.as_tensor(Zp, dtype=dt, device=dev)
    ind = torch.as_tensor(idx[:, :k], device=dev)
    off = Zt[ind] - Z0[:, None, :]  # (m, k, d)
    A = torch.cat([torch.ones(off.shape[0], k, 1, dtype=dt, device=dev), off], dim=2)  # (m, k, d+1)
    M = (A * w[:, :, None]).transpose(1, 2) @ A  # (m, d+1, d+1)
    pen = torch.eye(M.shape[1], dtype=dt, device=dev)
    pen[0, 0] = 0.0
    M = M + ridge * sw[:, :, None] * pen[None] + 1e-6 * torch.eye(M.shape[1], dtype=dt, device=dev)[None]
    e1 = torch.zeros(M.shape[0], M.shape[1], 1, dtype=dt, device=dev)
    e1[:, 0, 0] = 1.0
    v = torch.linalg.solve(M, e1)  # (m, d+1, 1)
    c = w * (A @ v)[:, :, 0]
    return c.cpu().numpy().astype(float), np.zeros(len(Zp))


def ap_rapido(y: np.ndarray, p: np.ndarray) -> float:
    """Average precision (ties broken by order), for model selection only."""
    o = np.argsort(-p, kind="stable")
    ys = y[o]
    if ys.sum() == 0:
        return 0.0
    return float(((np.cumsum(ys) / np.arange(1, len(ys) + 1)) * ys).sum() / ys.sum())


def _predecir(plan_c: np.ndarray, plan_s: np.ndarray, vec: np.ndarray, y: np.ndarray, p0: float) -> np.ndarray:
    return np.clip((plan_c * y[vec]).sum(axis=1) + plan_s * p0, 0.0, 1.0)


def elegir_config(Z: np.ndarray, y: np.ndarray, ts: np.ndarray, rejilla, dispositivo_: str | None = None) -> tuple:
    """Configuration with the best pooled AP in an inner leave-one-season-out over (Z, y, ts)."""
    kmax = max(k for k, _, _ in rejilla)
    temporadas = np.unique(ts)
    pooled = {cfg: np.full(len(y), np.nan) for cfg in rejilla}
    for s in temporadas:
        te = np.flatnonzero(ts == s)
        tr = np.flatnonzero(ts != s)
        idx, d2 = vecinos(Z[te], Z[tr], kmax, dispositivo_)
        p0 = float(y[tr].mean())
        for cfg in rejilla:
            k, hm, r = cfg
            c, sc = coeficientes(Z[te], Z[tr], idx, d2, k, hm, r, dispositivo_)
            pooled[cfg][te] = _predecir(c, sc, idx[:, :k], y[tr], p0)
    return max(rejilla, key=lambda cfg: ap_rapido(y, pooled[cfg]))


def planear(X: np.ndarray, y: np.ndarray, ts: np.ndarray, rejilla=REJILLA_CONSTANTE,
            dispositivo_: str | None = None, config_fija: tuple | None = None) -> list[Plan]:
    """Leave-one-season-out plan: for every season, neighbours and coefficients from the others.

    The configuration is chosen inside each training set unless `config_fija` is given (used to
    keep the null worlds on the configuration the real labels settled on).
    """
    planes = []
    for s in np.unique(ts):
        te = np.flatnonzero(ts == s)
        tr = np.flatnonzero(ts != s)
        Zte, Ztr = normalizar(X[te], X[tr])
        cfg = config_fija or elegir_config(Ztr, y[tr], ts[tr], rejilla, dispositivo_)
        k, hm, r = cfg
        idx, d2 = vecinos(Zte, Ztr, k, dispositivo_)
        c, sc = coeficientes(Zte, Ztr, idx, d2, k, hm, r, dispositivo_)
        planes.append(Plan(te, tr, tr[idx], c, sc, cfg))
    return planes


def predecir(planes: list[Plan], y: np.ndarray) -> np.ndarray:
    """Out-of-season probabilities for the labels `y`."""
    p = np.full(len(y), np.nan)
    for pl in planes:
        p[pl.prueba] = _predecir(pl.c, pl.s, pl.vecinos, y, float(y[pl.entrenamiento].mean()))
    return p


def predecir_mundos(planes: list[Plan], mundos: np.ndarray, trozo: int = 250,
                    dispositivo_: str | None = None) -> np.ndarray:
    """Probabilities of every label world (B, n) with the same plan, as one gather per fold."""
    dev = gpu.dispositivo(dispositivo_)
    dt = _dtype(dev)
    B, n = mundos.shape
    P = np.full((B, n), np.nan)
    Y = torch.as_tensor(mundos, dtype=dt, device=dev)
    for pl in planes:
        vec = torch.as_tensor(pl.vecinos, device=dev)
        c = torch.as_tensor(pl.c, dtype=dt, device=dev)
        s = torch.as_tensor(pl.s, dtype=dt, device=dev)
        tr = torch.as_tensor(pl.entrenamiento, device=dev)
        for i in range(0, B, trozo):
            Yb = Y[i : i + trozo]
            p0 = Yb[:, tr].mean(dim=1)  # (b,)
            est = (Yb[:, vec] * c[None]).sum(dim=2) + s[None] * p0[:, None]
            P[i : i + trozo, pl.prueba] = est.clamp(0, 1).cpu().numpy()
    return P


def evaluar(X: np.ndarray, y: np.ndarray, ts: np.ndarray, variante: str = "constante", n_nulas: int = 2000,
            semilla: int = 0, dispositivo_: str | None = None) -> dict:
    """Real out-of-season AP/AUC of the analog estimate and the distribution of the null worlds.

    The null worlds use the configuration most often chosen for the real labels.
    """
    rejilla = REJILLA_CONSTANTE if variante == "constante" else REJILLA_LINEAL
    y = np.asarray(y, dtype=float)
    planes = planear(X, y, ts, rejilla, dispositivo_)
    p = predecir(planes, y)
    cfgs = [pl.config for pl in planes]
    moda = max(set(cfgs), key=cfgs.count)
    planes_fijos = planear(X, y, ts, rejilla, dispositivo_, config_fija=moda)
    mundos = gpu.mundos_desplazados(y, ts, n_nulas, semilla)
    Pn = predecir_mundos(planes_fijos, mundos, dispositivo_=dispositivo_)
    _, ap_n = gpu.auc_ap_lote(mundos, Pn, dispositivo_=dispositivo_)
    auc, ap = gpu.auc_ap_lote(y[None], p[None], dispositivo_=dispositivo_)
    ap_fijo = gpu.auc_ap_lote(y[None], predecir(planes_fijos, y)[None], dispositivo_=dispositivo_)[1][0]
    corte = np.quantile(p, 0.95)
    return {
        "p": p, "ap": float(ap[0]), "auc": float(auc[0]), "ap_base": float(y.mean()),
        "ap_config_fija": float(ap_fijo), "config_moda": moda,
        "configs": {str(c): cfgs.count(c) for c in set(cfgs)},
        "top5": float(y[p >= corte].sum() / y.sum()),
        "ap_nula_media": float(ap_n.mean()), "ap_nula_p95": float(np.percentile(ap_n, 95)),
        "ap_nula_max": float(ap_n.max()),
        "p_valor": float((1 + (ap_n >= ap_fijo).sum()) / (1 + len(ap_n))), "n_nulas": n_nulas,
    }


CONJUNTOS = {
    "11": None,  # SELECCION_PARSIMONIOSA
    "6": ("chosica_h_lluvia_1d", "chosica_h_lluvia_3d", "chosica_suelo_prev", "chosica_h_lluvia_7d_previa_prev",
          "caudal_rimac-chosica_max_7d_prev", "icen_mes_previo"),
    "3": ("chosica_h_lluvia_1d", "chosica_h_lluvia_3d", "chosica_suelo_prev"),
}


def informe(raiz, n_nulas: int = 2000, dispositivo_: str | None = None):
    """Table of chapter 20: logistic L2 vs constant and linear analogs, on 11, 6 and 3 variables."""
    import pandas as pd

    from . import modelo_diario as M

    D = M.cargar_datos(raiz)
    X, y, ts, _ = M.matrices(D)
    Xn, yv = X["+nino"], y.to_numpy(dtype=float)
    filas = []
    for nombre, cols in CONJUNTOS.items():
        cols = [c for c in (cols or M.SELECCION_PARSIMONIOSA) if c in Xn.columns]
        Xa = Xn[cols].to_numpy(dtype=float)
        b = gpu.ap_real_y_nulas(Xa, y.to_numpy(), ts, C=0.03, n_nulas=n_nulas, dispositivo_=dispositivo_)
        filas.append({"variables": nombre, "modelo": "logistica_L2", "ap": b["ap_real"], "auc": b["auc_real"],
                      "ap_nula_p95": b["ap_nula_p95"], "p_valor": b["p"], "configuracion": "C=0.03"})
        for var in ("constante", "lineal"):
            r = evaluar(Xa, yv, ts, var, n_nulas=n_nulas, dispositivo_=dispositivo_)
            filas.append({"variables": nombre, "modelo": f"analogos_{var}", "ap": r["ap"], "auc": r["auc"],
                          "top5": r["top5"], "ap_nula_p95": r["ap_nula_p95"], "p_valor": r["p_valor"],
                          "configuracion": str(r["config_moda"])})
    return pd.DataFrame(filas)


def main() -> None:
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Capítulo 22: análogos contra regresión logística.")
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--nulas", type=int, default=2000)
    ap.add_argument("--salida", default=None, help="CSV de salida (por defecto catalogo/analogos_resultados.csv)")
    a = ap.parse_args()
    tabla = informe(Path(a.raiz), a.nulas)
    salida = Path(a.salida or Path(a.raiz) / "catalogo" / "analogos_resultados.csv")
    tabla.round(4).to_csv(salida, index=False)
    print(tabla.round(3).to_string(index=False))
    print(f"-> {salida}")
