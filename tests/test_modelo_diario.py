import numpy as np
import pandas as pd

from illapa_research import modelo_diario as M


def _sintetico(n_temp=12, dias=60, semilla=0):
    """Rare events that follow a noisy 'rain' feature; a second feature is pure noise."""
    rng = np.random.default_rng(semilla)
    ts = np.repeat(np.arange(2000, 2000 + n_temp), dias)
    lluvia = rng.gamma(1.0, 1.0, len(ts))
    ruido = rng.normal(size=len(ts))
    p = 1 / (1 + np.exp(-(1.4 * (lluvia - 3.5) - 2.0)))
    y = pd.Series((rng.uniform(size=len(ts)) < p).astype(int))
    X = pd.DataFrame({"lluvia": lluvia, "ruido": ruido, "faltante": np.where(rng.uniform(size=len(ts)) < 0.1, np.nan, ruido)})
    return X, y, ts


def test_ajuste_anidado_elige_una_configuracion_de_la_rejilla_y_predice_mejor_que_el_azar():
    X, y, ts = _sintetico()
    modelo, config = M.ajustar_anidado(X, y.to_numpy(), ts)
    assert config in M.REJILLA_LINEAL
    p = modelo.predict_proba(X.fillna(X.median()))[:, 1]
    assert p[y.to_numpy() == 1].mean() > p[y.to_numpy() == 0].mean()


def test_validacion_anidada_deja_fuera_las_temporadas_y_da_probabilidades():
    X, y, ts = _sintetico()
    folds = [np.flatnonzero(ts == s) for s in np.unique(ts)]
    res = M.validar_anidado(X, y, ts, folds, n_jobs=1)
    assert not np.isnan(res.p).any() and ((res.p >= 0) & (res.p <= 1)).all()
    assert len(res.configs) == len(folds) and res.coef.shape == (len(folds), 3)
    m = M.metricas_completas(y.to_numpy(), res.p, np.full(len(y), y.mean()))
    assert m["auc"] > 0.7 and m["ap"] > y.mean()


def test_dos_etapas_devuelve_probabilidades_por_pliegue():
    X, y, ts = _sintetico()
    folds = [np.flatnonzero(ts == s) for s in np.unique(ts)]
    res = M.dos_etapas(X[["ruido"]], X["lluvia"], y, ts, folds, n_jobs=1)
    assert not np.isnan(res.p).any() and (res.p > 0).all() and (res.p < 1).all()


def test_estabilidad_marca_la_variable_con_signo_constante():
    rng = np.random.default_rng(1)
    coef = np.column_stack([0.5 + 0.05 * rng.normal(size=20), rng.normal(size=20)])
    d = M.estabilidad_coeficientes(M.Resultado(np.zeros(1), [], coef, ["buena", "mala"])).set_index("variable")
    assert bool(d.loc["buena", "estable"]) and not bool(d.loc["mala", "estable"])


def test_calibracion_cuenta_todos_los_dias_y_eventos():
    rng = np.random.default_rng(2)
    p = rng.uniform(0, 0.3, 800)
    y = (rng.uniform(size=800) < p).astype(int)
    c = M.calibracion(y, p, bins=5)
    assert c["dias"].sum() == 800 and c["eventos"].sum() == y.sum()
    assert c["p_media"].is_monotonic_increasing
    assert abs(M.razon_observado_predicho(y, p) - 1) < 0.35


def test_bloques_y_familias():
    ts = np.repeat(np.arange(1990, 2002), 3)
    b = M.pliegues_bloques(ts, 5)
    assert sum(len(x) for x in b) == len(ts) and len(b) == 3
    assert M.familia_de("sst_nino12_anom_30d_prev") == "mar"
    assert M.familia_de("chosica_h_lluvia_7d_previa_prev") == "lluvia_previa"
    assert M.familia_de("icen_mes_previo") == "nino_icen"


def test_intervalos_por_temporada_traen_los_tres_cuantiles():
    X, y, ts = _sintetico()
    p = 1 / (1 + np.exp(-(1.2 * (X["lluvia"].to_numpy() - 3.5) - 2.0)))
    d = M.intervalos_por_temporada(y.to_numpy(), p, np.full(len(y), y.mean()), ts, n=30)
    assert list(d.columns) == ["p5", "mediana", "p95"] and (d["p5"] <= d["p95"]).all()


def test_nulas_gpu_comparan_el_ap_real_con_mundos_desplazados():
    import pytest

    pytest.importorskip("torch")
    X, y, ts = _sintetico()
    r = M.nulas_gpu(X[["lluvia", "ruido"]], y, ts, c=0.1, n_nulas=20)
    assert r["ap_real"] > r["ap_nula_p95"] and 0 < r["p"] <= 1 and r["n_nulas"] == 20
