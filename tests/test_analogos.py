import numpy as np
import pytest

pytest.importorskip("torch")

from illapa_research import analogos as A
from illapa_research import gpu


def _datos(n=600, d=3, semilla=0):
    rng = np.random.default_rng(semilla)
    X = rng.normal(size=(n, d))
    ts = np.repeat(np.arange(12), n // 12)
    p = 1 / (1 + np.exp(-(2.5 * X[:, 0] - 3.5)))
    y = (rng.random(n) < p).astype(float)
    return X, y, ts


def test_constante_coincide_con_fuerza_bruta():
    rng = np.random.default_rng(1)
    Ze, Zp = rng.normal(size=(200, 3)), rng.normal(size=(5, 3))
    y = (rng.random(200) < 0.2).astype(float)
    idx, d2 = A.vecinos(Zp, Ze, 20, "cpu")
    c, s = A.coeficientes(Zp, Ze, idx, d2, 20, 1.0, None, "cpu")
    est = np.clip((c * y[idx]).sum(1) + s * y.mean(), 0, 1)
    for i in range(5):
        dd = ((Ze - Zp[i]) ** 2).sum(1)
        o = np.argsort(dd)[:20]
        w = np.exp(-dd[o] / dd[o].mean())
        esperado = ((w * y[o]).sum() + A.PRIOR * y.mean()) / (w.sum() + A.PRIOR)
        assert est[i] == pytest.approx(esperado, abs=1e-9)


def test_lineal_recupera_una_recta_exacta():
    rng = np.random.default_rng(2)
    Ze = rng.normal(size=(400, 2))
    y = 0.3 + 0.1 * Ze[:, 0] - 0.05 * Ze[:, 1]
    Zp = rng.normal(size=(6, 2)) * 0.5
    idx, d2 = A.vecinos(Zp, Ze, 80, "cpu")
    c, _ = A.coeficientes(Zp, Ze, idx, d2, 80, 2.0, 1e-8, "cpu")
    est = (c * y[idx]).sum(1)
    assert np.allclose(est, 0.3 + 0.1 * Zp[:, 0] - 0.05 * Zp[:, 1], atol=1e-4)


def test_la_prediccion_de_una_temporada_no_usa_sus_propias_etiquetas():
    X, y, ts = _datos()
    pl = A.planear(X, y, ts, A.REJILLA_CONSTANTE[:3], "cpu")
    p1 = A.predecir(pl, y)
    y2 = y.copy()
    y2[ts == 4] = 1 - y2[ts == 4]
    p2 = A.predecir(pl, y2)
    assert np.allclose(p1[ts == 4], p2[ts == 4])


def test_mundos_dan_lo_mismo_que_el_camino_directo():
    X, y, ts = _datos()
    pl = A.planear(X, y, ts, A.REJILLA_CONSTANTE[:3], "cpu", config_fija=(30, 1.0, 0.0))
    mundos = gpu.mundos_desplazados(y, ts, 3, 0)
    Pn = A.predecir_mundos(pl, mundos, dispositivo_="cpu")
    for b in range(3):
        assert np.allclose(Pn[b], A.predecir(pl, mundos[b]), atol=1e-9)


def test_tiene_senal_donde_la_hay_y_las_nulas_no():
    X, y, ts = _datos(n=1200)
    r = A.evaluar(X, y, ts, "constante", n_nulas=60, dispositivo_="cpu")
    assert r["ap"] > 2 * r["ap_base"]
    assert r["ap_nula_media"] < r["ap"] and r["p_valor"] < 0.1


def test_normalizar_pone_los_faltantes_en_cero_y_no_ve_la_prueba():
    ref = np.array([[1.0], [2.0], [3.0], [np.nan]])
    a, b = A.normalizar(np.array([[2.0], [np.nan], [100.0]]), ref)
    assert a[1, 0] == 0 and b[3, 0] == 0 and a[2, 0] > a[0, 0] > -1e-9 - 0.1
