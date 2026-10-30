import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from illapa_research import probabilidad as pr


def _datos(n_temp=12, dias=60, semilla=0):
    rng = np.random.default_rng(semilla)
    ts = np.repeat(np.arange(2000, 2000 + n_temp), dias)
    n = len(ts)
    X = pd.DataFrame(
        {
            "chosica_h_lluvia_3d": rng.gamma(1.0, 3.0, n),
            "mat_lluvia_1d_prev": rng.gamma(1.0, 2.0, n),
            "chosica_suelo_prev": rng.normal(0.2, 0.05, n),
            "sst_nino12_anom_prev": rng.normal(0, 1, n),
            "ruido_a": rng.normal(size=n),
            "ruido_b": rng.normal(size=n),
        }
    )
    eta = -5.0 + 0.5 * X["chosica_h_lluvia_3d"] + 4 * (X["chosica_suelo_prev"] - 0.2) / 0.05 * 0.2
    y = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(float)
    fam = np.array(["lluvia_mismo_dia", "lluvia_mismo_dia", "suelo", "mar", "calor_altura", "calor_altura"])
    return X, y, ts, fam


def test_ajustar_lote_coincide_con_scikit_learn_con_pesos_y_mascara():
    from sklearn.linear_model import LogisticRegression

    X, y, _ts, _fam = _datos()
    Z, _ = pr.ajustar_estandar(X)
    w = np.ones((1, len(y)))
    w[0, :100] = 0.0
    mask = np.array([[True, True, True, False, False, False]])
    b = pr.ajustar_lote(Z, y, w, mask, np.array([1 / 0.1]), dispositivo="cpu")[0]
    m = LogisticRegression(C=0.1, max_iter=5000).fit(Z[100:][:, :3], y[100:])
    assert np.allclose(b[:3], m.coef_[0], atol=2e-3) and np.allclose(b[3:6], 0)
    assert abs(b[6] - m.intercept_[0]) < 2e-3


def test_seleccionar_deja_dos_por_familia_y_prefiere_lo_informativo():
    X, y, _ts, fam = _datos()
    Z, _ = pr.ajustar_estandar(X)
    m = pr.seleccionar(Z, y, fam, k=1)
    assert m[0] and m[2]  # the informative columns win their families
    assert m.sum() == len(np.unique(fam))


def test_loso_anidado_da_probabilidades_mejores_que_el_azar():
    from sklearn.metrics import roc_auc_score

    X, y, ts, fam = _datos()
    Z, _ = pr.ajustar_estandar(X)
    r = pr.loso_anidado(Z, y, ts, fam, reducido=True, dispositivo="cpu")
    assert np.isfinite(r.logit).all() and set(r.c_elegida.values()) <= set(pr.REJILLA_C)
    assert roc_auc_score(y, r.logit) > 0.7


def test_calibracion_loso_no_empeora_el_brier_de_una_constante():
    X, y, ts, fam = _datos()
    Z, _ = pr.ajustar_estandar(X)
    r = pr.loso_anidado(Z, y, ts, fam, reducido=False, dispositivo="cpu")
    p = pr.calibrar_loso(r.logit, y, ts)
    assert np.mean((p - y) ** 2) < np.mean((y.mean() - y) ** 2)


def test_tabla_bandas_cuenta_todos_los_dias():
    rng = np.random.default_rng(1)
    p = rng.random(500) ** 3
    y = (rng.random(500) < p).astype(float)
    t = pr.tabla_bandas(y, p)
    assert t["dias"].sum() == 500 and t["con_huaico"].sum() == y.sum()


def test_ficha_de_punta_a_punta_con_datos_sinteticos():
    X, y, ts, fam = _datos()
    Z, _ = pr.ajustar_estandar(X)
    r = pr.loso_anidado(Z, y, ts, fam, reducido=True, dispositivo="cpu")
    cal = pr.ajustar_calibrador(r.logit, y)
    p_oof = pr.calibrar_loso(r.logit, y, ts)
    bandas = pr.tabla_bandas(y, p_oof)
    mod = pr.ajustar_modelo(X, y, ts, fam, True, 0.03, False, None, cal, bandas, n_boot=40, dispositivo="cpu")
    seco = X.iloc[0].copy()
    seco["chosica_h_lluvia_3d"] = 0.0
    lluvioso = X.iloc[0].copy()
    lluvioso["chosica_h_lluvia_3d"] = 30.0
    a, b = pr.ficha(mod, seco), pr.ficha(mod, lluvioso)
    assert 0 <= a["probabilidad"] < b["probabilidad"] <= 1
    lo, hi = b["intervalo_80"]
    assert lo <= hi and "no es una alerta" in b["limites"].lower()
    assert b["factores_favorables"] and "lluvia de 3 días" in b["factores_favorables"][0]["texto"]
    assert b["banda_de_fiabilidad"]["dias_historicos"] >= 0


def test_describir_nombra_estacion_y_dia_anterior():
    assert pr.describir("chosica_h_lluvia_3d") == "lluvia de 3 días en Chosica"
    assert pr.describir("tic_temp_anom_prev") == "temperatura en Ticlio (del día anterior)"
    assert "Niño 1+2" in pr.describir("sst_nino12_alza_7d_prev")
    assert pr.describir("caudal_rimac-chosica_anom_prev").startswith("caudal del Rímac")
