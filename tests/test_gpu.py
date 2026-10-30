import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from illapa_research import gpu


def _datos(n=400, d=6, semilla=0):
    rng = np.random.default_rng(semilla)
    X = rng.normal(size=(n, d))
    y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(size=n) > 1.2).astype(float)
    return gpu.estandarizar(X), y


def test_logit_lote_coincide_con_scikit_learn():
    X, y = _datos()
    mask = np.ones(len(y), dtype=bool)
    mask[:100] = False
    p = gpu.ajustar_logit_lote(X, y[None, :], mask[None, :], C=0.1, dispositivo_="cpu")[0]
    m = LogisticRegression(C=0.1, max_iter=5000).fit(X[mask], y[mask])
    assert np.allclose(p, m.predict_proba(X)[:, 1], atol=2e-3)


def test_logit_lote_ajusta_varios_a_la_vez():
    X, y = _datos()
    Y = np.stack([y, 1 - y])
    M = np.ones_like(Y, dtype=bool)
    p = gpu.ajustar_logit_lote(X, Y, M, C=0.1, dispositivo_="cpu")
    assert p.shape == (2, len(y)) and np.corrcoef(p[0], p[1])[0, 1] < -0.9


def test_auc_ap_lote_coincide_con_scikit_learn():
    rng = np.random.default_rng(1)
    y = (rng.random((3, 300)) < 0.1).astype(float)
    p = rng.random((3, 300)) + 0.5 * y
    auc, ap = gpu.auc_ap_lote(y, p, dispositivo_="cpu")
    for i in range(3):
        assert auc[i] == pytest.approx(roc_auc_score(y[i], p[i]), abs=1e-6)
        assert ap[i] == pytest.approx(average_precision_score(y[i], p[i]), abs=1e-6)


def test_nulas_desplazadas_quedan_cerca_de_la_base_y_el_real_las_supera():
    rng = np.random.default_rng(2)
    n, d = 600, 5
    temporada = np.repeat(np.arange(10), n // 10)
    X = rng.normal(size=(n, d))
    y = (X[:, 0] + rng.normal(size=n) > 2.0).astype(int)
    nulas = gpu.nulas_desplazadas(X, y, temporada, C=0.1, n_nulas=8, dispositivo_="cpu", trozo=64)
    assert len(nulas) == 8 and nulas.max() < 0.3
