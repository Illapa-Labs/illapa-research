import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from illapa_research import senales as S


def _serie(n_temp=30, dias=151, semilla=0, lag=3, fuerza=2.0):
    """Synthetic seasons: a noisy feature whose spike `lag` days earlier precedes each event."""
    rng = np.random.default_rng(semilla)
    idx, y, x, temporada = [], [], [], []
    for t in range(n_temp):
        inicio = pd.Timestamp(f"{1990 + t}-12-01")
        d = pd.date_range(inicio, periods=dias)
        xs = rng.normal(size=dias)
        ys = np.zeros(dias, dtype=int)
        for k in rng.choice(np.arange(10, dias - 5), 3, replace=False):
            ys[k] = 1
            xs[k - lag] += fuerza
        idx += list(d); y += list(ys); x += list(xs); temporada += [1991 + t] * dias
    F = pd.DataFrame({"senal": x, "ruido": rng.normal(size=len(x))}, index=pd.DatetimeIndex(idx))
    return F, pd.Series(y, index=F.index), np.array(temporada)


def test_auc_rapida_coincide_con_sklearn():
    rng = np.random.default_rng(1)
    x = rng.normal(size=300)
    x[rng.random(300) < 0.1] = np.nan
    y = (rng.random(300) < 0.2).astype(float)
    F = pd.DataFrame({"a": x})
    R, V = S._rangos_lag(F, ["a"], 0, np.ones(300, bool), np.zeros(300, int), False)
    ok = ~np.isnan(x)
    esperado = roc_auc_score(y[ok], x[ok])
    assert abs(S._auc_desde_rangos(y, R, V)[0] - esperado) < 1e-9


def test_bh_rechaza_solo_los_p_pequenos():
    p = np.array([0.001, 0.009, 0.04, 0.5, 0.9, np.nan])
    r = S.bh(p, q=0.10)
    assert list(r) == [True, True, True, False, False, False]


def test_episodios_agrupa_dias_cercanos():
    dias = ["2017-03-14", "2017-03-15", "2017-03-17", "2017-03-30", "2017-03-30"]
    assert S.episodios_de_dias(dias, hueco=3) == [pd.Timestamp("2017-03-14"), pd.Timestamp("2017-03-30")]


def test_rezagos_nula_encuentra_el_rezago_inyectado_y_no_el_ruido():
    F, y, ts = _serie()
    r = S.rezagos_nula(F, y, ["senal", "ruido"], ts, np.ones(len(F), bool), range(8), n_null=300)
    s = r[r.variable == "senal"].set_index("lag")
    assert s.loc[3, "senal"] and s.loc[3, "auc"] > 0.8
    assert not r[(r.variable == "ruido") & r.senal].shape[0] > 1  # at most a chance hit


def test_nula_local_y_de_estacion_conservan_el_numero_de_eventos():
    _F, y, ts = _serie()
    rng = np.random.default_rng(0)
    for modo in ("local", "estacion"):
        ys = S._desplazar_etiquetas(y.to_numpy(), ts, rng, modo)
        assert ys.sum() == y.sum()


def test_compuesto_ve_la_anomalia_antes_del_episodio():
    F, y, _ts = _serie(n_temp=40)
    inicios = S.episodios_de_dias(list(y.index[y == 1]), hueco=3)
    from illapa_research.nino import temporada_de

    c = S.compuesto(F["senal"], inicios, lambda d: temporada_de(d.date()), F.index, range(-6, 2), n_null=200)
    fila = c.set_index("lag").loc[-3]
    assert fila["z_medio"] > fila["nula_p95"] and fila["p"] < 0.05


def test_robustez_marca_la_senal_estable_y_no_el_ruido():
    F, y, ts = _serie(n_temp=45, fuerza=2.5)
    base = np.ones(len(F), bool)
    anio = np.asarray(F.index.year)
    masc = {"1984+": base, "2009+": base & (anio >= 2005), "sin 1983, 1998 y 2017": base & ~np.isin(ts, [1995, 2000])}
    r = S.robustez(F, y, ["senal", "ruido"], ts, masc, lags=range(1, 6), centrar=False, n_null=300)
    assert r[(r.variable == "senal") & (r.lag == 3)]["robusta"].iloc[0]
    assert not r[r.variable == "ruido"]["robusta"].any()
