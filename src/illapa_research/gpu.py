"""Batched statistics on the GPU (PyTorch), with the same results on the CPU.

What is expensive in this project is not one model but thousands of them: null distributions (labels
shifted inside each season, refitted in every leave-one-season-out fold), season bootstraps, and
parallel Markov chains. Each fit is a small ridge-logistic problem, so the work is a big batch of
independent small solves, which a GPU does in one pass.

`ajustar_logit_lote` solves B logistic regressions with the same L2 penalty as scikit-learn's
`LogisticRegression(C=...)` (intercept not penalised) by Newton / IRLS steps, all B at once.
Features are used as given: standardise and impute them before (statistics that use no labels).

Everything falls back to the CPU when there is no CUDA device (or no PyTorch), only slower.
"""

from __future__ import annotations

import numpy as np

try:  # PyTorch is an optional extra: `uv sync --extra gpu`
    import torch
except ImportError:  # pragma: no cover
    torch = None


def dispositivo(preferido: str | None = None) -> str:
    """"cuda", "mps" or "cpu", whichever is available (or `preferido` if it is)."""
    if torch is None:
        return "cpu"
    if preferido == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() and preferido != "cuda":
        return "mps"
    return "cpu"


def estandarizar(X: np.ndarray) -> np.ndarray:
    """Median-impute and z-score each column (no labels involved)."""
    X = np.asarray(X, dtype=np.float64).copy()
    med = np.nanmedian(X, axis=0)
    idx = np.where(np.isnan(X))
    X[idx] = np.take(med, idx[1])
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    return (X - X.mean(axis=0)) / sd


def ajustar_logit_lote(
    X: np.ndarray, Y: np.ndarray, M: np.ndarray, C: float = 0.05, iteraciones: int = 15,
    dispositivo_: str | None = None, trozo: int = 256,
) -> np.ndarray:
    """Predicted probabilities of B logistic fits, shape (B, n).

    X: (n, d) shared design. Y: (B, n) labels per fit. M: (B, n) bool, rows used for training of
    each fit (the others are only predicted). Minimises  sum_i m_i·logloss_i + (1/(2C))·|beta|^2.
    """
    dev = dispositivo(dispositivo_)
    dtype = torch.float64 if dev == "cpu" else torch.float32
    n, d = X.shape
    Xb = torch.cat([torch.as_tensor(X, dtype=dtype), torch.ones(n, 1, dtype=dtype)], dim=1).to(dev)
    D = d + 1
    X2 = (Xb[:, :, None] * Xb[:, None, :]).reshape(n, D * D)
    lam = torch.full((D,), 1.0 / C, dtype=dtype, device=dev)
    lam[-1] = 0.0  # intercept free
    reg = torch.diag(lam)
    out = np.empty((Y.shape[0], n), dtype=np.float64)
    for i in range(0, Y.shape[0], trozo):
        y = torch.as_tensor(Y[i : i + trozo], dtype=dtype, device=dev)
        m = torch.as_tensor(M[i : i + trozo], dtype=dtype, device=dev)
        b = torch.zeros(y.shape[0], D, dtype=dtype, device=dev)
        for _ in range(iteraciones):
            p = torch.sigmoid(b @ Xb.T)
            g = ((m * (p - y)) @ Xb) + b * lam
            W = m * p * (1 - p) + 1e-9 * m
            H = (W @ X2).reshape(-1, D, D) + reg
            b = b - torch.linalg.solve(H, g[:, :, None])[:, :, 0]
        out[i : i + trozo] = torch.sigmoid(b @ Xb.T).cpu().numpy()
    return out


def auc_ap_lote(Y: np.ndarray, P: np.ndarray, mascara: np.ndarray | None = None, dispositivo_: str | None = None):
    """ROC AUC and average precision of each row (B, n); `mascara` (B, n) picks the rows scored."""
    dev = dispositivo(dispositivo_)
    dtype = torch.float64 if dev == "cpu" else torch.float32
    y = torch.as_tensor(Y, dtype=dtype, device=dev)
    p = torch.as_tensor(P, dtype=dtype, device=dev)
    m = torch.ones_like(y) if mascara is None else torch.as_tensor(mascara, dtype=dtype, device=dev)
    p = torch.where(m > 0, p, torch.full_like(p, -1.0))  # unscored rows sort last
    orden = torch.argsort(-p, dim=1)
    ys = torch.gather(y * m, 1, orden)
    ms = torch.gather(m, 1, orden)
    tp = torch.cumsum(ys, dim=1)
    n_pos = ys.sum(dim=1).clamp(min=1)
    n_scored = ms.sum(dim=1)
    precision = tp / torch.cumsum(ms, dim=1).clamp(min=1)
    ap = (precision * ys).sum(dim=1) / n_pos
    # AUC from ranks of the positives among the scored rows (ties are broken by the sort)
    rango_desc = torch.cumsum(ms, dim=1)
    suma_rangos = (rango_desc * ys).sum(dim=1)
    n_neg = (n_scored - n_pos).clamp(min=1)
    auc = 1.0 - (suma_rangos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return auc.cpu().numpy(), ap.cpu().numpy()


def nulas_desplazadas(
    X: np.ndarray, y: np.ndarray, temporada: np.ndarray, C: float = 0.05, n_nulas: int = 200,
    semilla: int = 0, dispositivo_: str | None = None, trozo: int = 256,
) -> np.ndarray:
    """Average precision of `n_nulas` null worlds, leaving one season out at a time.

    A null world shifts the labels cyclically inside every season (same number of events, same
    clustering, no link to the weather), then the model is fitted in every leave-one-season-out
    fold and scored on the pooled out-of-fold probabilities.
    """
    rng = np.random.default_rng(semilla)
    temporadas = np.unique(temporada)
    por_temp = {s: np.flatnonzero(temporada == s) for s in temporadas}
    n = len(y)
    Z = estandarizar(X)
    aps = []
    mundos = np.empty((n_nulas, n))
    for b in range(n_nulas):
        ys = y.astype(float).copy()
        for s, i in por_temp.items():
            ys[i] = np.roll(y[i], int(rng.integers(5, max(6, len(i) - 5))))
        mundos[b] = ys
    # Fit every (world, fold) at once in chunks; predictions of a fold are read back on its rows.
    pares = [(b, s) for b in range(n_nulas) for s in temporadas]
    P = np.full((n_nulas, n), np.nan)
    for i in range(0, len(pares), trozo * 4):
        lote = pares[i : i + trozo * 4]
        Y = np.stack([mundos[b] for b, _ in lote])
        Mk = np.stack([~np.isin(np.arange(n), por_temp[s]) for _, s in lote])
        Pl = ajustar_logit_lote(Z, Y, Mk, C=C, dispositivo_=dispositivo_, trozo=trozo)
        for (b, s), fila in zip(lote, Pl, strict=True):
            P[b, por_temp[s]] = fila[por_temp[s]]
    _, ap = auc_ap_lote(mundos, P, dispositivo_=dispositivo_)
    aps = ap
    return aps


def ap_real_y_nulas(
    X: np.ndarray, y: np.ndarray, temporada: np.ndarray, C: float = 0.05, n_nulas: int = 1000,
    semilla: int = 0, dispositivo_: str | None = None,
) -> dict[str, float]:
    """Out-of-fold average precision of the real labels and of `n_nulas` shifted-label worlds.

    Both use the same fixed-C ridge-logistic fit and the same leave-one-season-out folds, so they
    are comparable. `p` is the share of null worlds that reach the real AP (plus one).
    """
    temporadas = np.unique(temporada)
    n = len(y)
    Z = estandarizar(X)
    Y = np.tile(y.astype(float), (len(temporadas), 1))
    Mk = np.stack([~np.isin(np.arange(n), np.flatnonzero(temporada == s)) for s in temporadas])
    Pl = ajustar_logit_lote(Z, Y, Mk, C=C, dispositivo_=dispositivo_)
    P = np.empty(n)
    for s, fila in zip(temporadas, Pl, strict=True):
        i = np.flatnonzero(temporada == s)
        P[i] = fila[i]
    auc, ap = auc_ap_lote(y[None, :].astype(float), P[None, :], dispositivo_=dispositivo_)
    nulas = nulas_desplazadas(X, y, temporada, C=C, n_nulas=n_nulas, semilla=semilla, dispositivo_=dispositivo_)
    return {
        "ap_real": float(ap[0]), "auc_real": float(auc[0]), "ap_base": float(y.mean()),
        "ap_nula_media": float(nulas.mean()), "ap_nula_p95": float(np.percentile(nulas, 95)),
        "ap_nula_max": float(nulas.max()), "p": float((1 + (nulas >= ap[0]).sum()) / (1 + len(nulas))),
        "n_nulas": len(nulas),
    }
