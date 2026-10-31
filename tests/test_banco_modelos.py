import numpy as np
import pandas as pd

from illapa_research import banco_modelos as B


def test_ventanas_terminan_en_la_posicion_y_rellenan_con_ceros():
    G = np.arange(10, dtype=float).reshape(5, 2)
    w = B.ventanas(G, np.array([0, 3]), largo=3)
    assert w.shape == (2, 3, 2)
    assert w[1, -1].tolist() == G[3].tolist() and w[1, 0].tolist() == G[1].tolist()
    assert w[0, 0].tolist() == [0.0, 0.0] and w[0, -1].tolist() == G[0].tolist()


def test_logistica_y_boosting_devuelven_una_probabilidad_por_dia():
    rng = np.random.default_rng(0)
    n = 300
    ts = np.repeat(np.arange(6), n // 6)
    lluvia = rng.gamma(1.0, 3.0, n)
    y = (lluvia + rng.normal(0, 1.5, n) > 8).astype(int)
    X = pd.DataFrame({"lluvia_1d": lluvia, "ruido": rng.normal(size=n)})
    for p in (B.logistica(X.to_numpy(), y, ts), B.boosting_monotono(X, y, ts)):
        assert p.shape == (n,) and np.all((p >= 0) & (p <= 1))
        assert p[y == 1].mean() > p[y == 0].mean()


def test_gru_devuelve_probabilidades():
    rng = np.random.default_rng(1)
    n, d = 120, 3
    Z = rng.normal(size=(n, d)).astype(np.float32)
    y = (Z[:, 0] > 0.8).astype(int)
    ts = np.repeat(np.arange(4), n // 4)
    p = B.gru(Z, np.arange(n), y, ts, largo=4, semillas=1, epocas=3, dispositivo_="cpu")
    assert p.shape == (n,) and np.all((p >= 0) & (p <= 1))
