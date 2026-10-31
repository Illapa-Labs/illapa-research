"""Benchmark of model families for the daily huaico probability, all under the same validation.

Question: does a more flexible model beat the regularised logistic regression when there are only
about 120 positive days in 43 seasons? Four candidates, each scored out of sample leaving one whole
season out (same folds, same labels, same features):

* ``logistica``: ridge-logistic with fixed C (the model of chapters 05 and 15), fitted on the GPU.
* ``boosting_monotono``: gradient boosting with shallow trees, strong L2, and monotone constraints
  (more rain, more soil moisture or more discharge never lowers the probability).
* ``gru``: a small recurrent network on the last ``largo`` days of the same variables, averaged
  over several seeds. Rain of the day enters at lag 0; every other variable is shifted one day.
* ``conjunto``: mean of the three probabilities.

The comparison is reported as average precision, AUC and hit rate with 5 % of days in alarm, plus
the paired difference of AP against the logistic regression with a season bootstrap.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from . import evaluacion_diaria as E
from . import gpu
from . import modelo_diario as M
from . import predictores as P
from .quebradas_dia import diferencia_ap

MODELOS = ("logistica", "boosting_monotono", "gru", "conjunto")
PALABRAS_MONOTONAS = ("lluvia", "pico", "caudal", "suelo")


def pliegues_por_temporada(ts: np.ndarray) -> list[np.ndarray]:
    return [np.flatnonzero(ts == s) for s in np.unique(ts)]


def ventanas(G: np.ndarray, posiciones: np.ndarray, largo: int) -> np.ndarray:
    """(n, largo, d) windows ending at each position; earlier rows missing at the start are zeros."""
    n, d = len(posiciones), G.shape[1]
    out = np.zeros((n, largo, d), dtype=np.float32)
    for k in range(largo):
        origen = posiciones - (largo - 1 - k)
        ok = origen >= 0
        out[ok, k, :] = G[origen[ok]]
    return out


def matriz_secuencia(D: M.Datos) -> tuple[np.ndarray, np.ndarray]:
    """Standardised daily matrix of the whole calendar and the position of each rainy-season day.

    Rain of the day keeps lag 0; all other variables are shifted by one day, as in the chapter 05
    models. Statistics for standardising use no labels.
    """
    F = D.F
    cols = [c for c in F.columns if not c.startswith("icen_")]
    lluvia = [c for c in cols if P.familia(c) == "lluvia_mismo_dia"]
    otras = [c for c in cols if c not in lluvia]
    G = pd.concat([F[lluvia], F[otras].shift(1), F[["icen_mes_previo", "icen_3m_previos"]]], axis=1)
    Z = gpu.estandarizar(G.to_numpy(dtype=float))
    _X, y, _ts, _mes = M.matrices(D)
    pos = F.index.get_indexer(y.index)
    return Z.astype(np.float32), pos


def logistica(X: np.ndarray, y: np.ndarray, ts: np.ndarray, C: float = 0.03) -> np.ndarray:
    Z = gpu.estandarizar(X)
    folds = pliegues_por_temporada(ts)
    n = len(y)
    Y = np.tile(y.astype(float), (len(folds), 1))
    Mk = np.stack([~np.isin(np.arange(n), f) for f in folds])
    P = gpu.ajustar_logit_lote(Z, Y, Mk, C=C)
    p = np.empty(n)
    for f, fila in zip(folds, P, strict=True):
        p[f] = fila[f]
    return p


def boosting_monotono(X: pd.DataFrame, y: np.ndarray, ts: np.ndarray) -> np.ndarray:
    cst = [1 if any(k in c for k in PALABRAS_MONOTONAS) else 0 for c in X.columns]
    A = X.to_numpy(dtype=float)
    p = np.empty(len(y))
    for f in pliegues_por_temporada(ts):
        train = np.setdiff1d(np.arange(len(y)), f)
        med = np.nanmedian(A[train], axis=0)
        At = np.where(np.isnan(A[train]), med, A[train])
        Af = np.where(np.isnan(A[f]), med, A[f])
        m = HistGradientBoostingClassifier(
            max_depth=3, max_leaf_nodes=6, learning_rate=0.05, max_iter=120, l2_regularization=10.0,
            min_samples_leaf=40, early_stopping=False, monotonic_cst=cst, random_state=0)
        p[f] = m.fit(At, y[train]).predict_proba(Af)[:, 1]
    return p


def gru(Z: np.ndarray, pos: np.ndarray, y: np.ndarray, ts: np.ndarray, largo: int = 14, semillas: int = 3,
        epocas: int = 25, ocultas: int = 32, dispositivo_: str | None = None) -> np.ndarray:
    import torch
    from torch import nn

    dev = gpu.dispositivo(dispositivo_)
    W = torch.as_tensor(ventanas(Z, pos, largo), device=dev)
    yt = torch.as_tensor(y.astype(np.float32), device=dev)
    n, _, d = W.shape

    class Red(nn.Module):
        def __init__(self):
            super().__init__()
            self.rnn = nn.GRU(d, ocultas, batch_first=True)
            self.drop = nn.Dropout(0.3)
            self.out = nn.Linear(ocultas, 1)

        def forward(self, x):
            h = self.rnn(x)[1][-1]
            return self.out(self.drop(h))[:, 0]

    p = np.zeros(n)
    for f in pliegues_por_temporada(ts):
        train = torch.as_tensor(np.setdiff1d(np.arange(n), f), device=dev)
        test = torch.as_tensor(f, device=dev)
        acum = np.zeros(len(f))
        for semilla in range(semillas):
            torch.manual_seed(semilla)
            red = Red().to(dev)
            opt = torch.optim.AdamW(red.parameters(), lr=2e-3, weight_decay=1e-2)
            perdida = nn.BCEWithLogitsLoss()
            for _ in range(epocas):
                red.train()
                orden = train[torch.randperm(len(train), device=dev)]
                for i in range(0, len(orden), 256):
                    b = orden[i : i + 256]
                    opt.zero_grad()
                    perdida(red(W[b]), yt[b]).backward()
                    opt.step()
            red.eval()
            with torch.no_grad():
                acum += torch.sigmoid(red(W[test])).cpu().numpy()
        p[f] = acum / semillas
    return p


def comparar(D: M.Datos, **kw_gru) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray]]:
    X, y, ts, mes = M.matrices(D)
    Xm = X["+nino"]
    yv = y.to_numpy()
    Z, pos = matriz_secuencia(D)
    ps = {
        "logistica": logistica(Xm.to_numpy(dtype=float), yv, ts),
        "boosting_monotono": boosting_monotono(Xm, yv, ts),
        "gru": gru(Z, pos, yv, ts, **kw_gru),
    }
    ps["conjunto"] = np.mean([ps["logistica"], ps["boosting_monotono"], ps["gru"]], axis=0)
    ref = E.p_climatologia(y, mes, pliegues_por_temporada(ts))
    filas = []
    for nombre in MODELOS:
        m = M.metricas_completas(yv, ps[nombre], ref)
        m["modelo"] = nombre
        filas.append(m)
    tabla = pd.DataFrame(filas).set_index("modelo")
    d = pd.DataFrame({"temporada": ts, "y": yv, **ps})
    difs = pd.DataFrame([diferencia_ap(d, a, "logistica") for a in MODELOS[1:]])
    return tabla, difs, ps


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Banco de modelos para el modelo diario.")
    ap.add_argument("--solo-zona", action="store_true")
    ap.add_argument("--epocas", type=int, default=25)
    ap.add_argument("--semillas", type=int, default=3)
    a = ap.parse_args(argv)
    D = M.cargar_datos(Path("."), solo_zona=a.solo_zona)
    tabla, difs, _ = comparar(D, epocas=a.epocas, semillas=a.semillas)
    print(tabla[["ap", "auc", "brier_skill", "aciertos_con_5pc_alarmas"]].round(3).to_string())
    print(difs.round(3).to_string(index=False))
    sufijo = "_solo_zona" if a.solo_zona else ""
    tabla.round(5).to_csv(Path("catalogo") / f"banco_modelos{sufijo}.csv")
    difs.round(5).to_csv(Path("catalogo") / f"banco_modelos_diferencias{sufijo}.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
