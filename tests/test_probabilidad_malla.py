import numpy as np
import pandas as pd
import pytest

from illapa_research import probabilidad_malla as P


def test_pesos_bilineales_suman_uno_y_son_exactos_en_la_malla():
    lat = np.array([-11.0, -11.25, -11.5])
    lon = np.array([-77.0, -76.75, -76.5])
    ps = P.pesos_bilineales(lat, lon, -11.25, -76.75)
    assert sum(p for *_, p in ps) == pytest.approx(1)
    assert max(ps, key=lambda t: t[2])[:2] in [(1, 1)] and max(p for *_, p in ps) == pytest.approx(1)
    campo = lat[:, None] * 2 + lon[None, :]  # linear field: bilinear is exact
    v = sum(p * campo[i, j] for i, j, p in P.pesos_bilineales(lat, lon, -11.1, -76.9))
    assert v == pytest.approx(-11.1 * 2 - 76.9)


def test_las_ventanas_del_dia_de_lluvia_van_de_12_a_36_y_de_36_a_60():
    assert [w for w in P.VENTANAS[:4]] == [(12, 18), (18, 24), (24, 30), (30, 36)]
    assert P.LEADS == {1: (0, 12), 2: (1, 36)}


def _sintetico(semilla=0, n_temp=8):
    rng = np.random.default_rng(semilla)
    dias = pd.DatetimeIndex([d for a in range(2001, 2001 + n_temp) for d in pd.date_range(f"{a - 1}-12-01", f"{a}-04-30")])
    senal = rng.gamma(0.5, 4, (len(dias), 2))
    obs = pd.DataFrame(senal + rng.gamma(0.3, 1, senal.shape), index=dias, columns=[0, 1])
    miembros = {}
    for c in (0, 1):
        m = senal[:, c][:, None] * rng.lognormal(0, 0.4, (len(dias), 5))
        miembros[c] = pd.DataFrame(m, index=dias)
    mi = pd.concat(miembros, names=["celda", "dia"]).swaplevel().sort_index()
    media = mi.mean(axis=1).unstack("celda")
    return media, mi, obs


def test_la_calibrada_gana_a_la_climatologia_y_esta_bien_calibrada():
    media, mi, obs = _sintetico()
    res = P.calibrar(media, mi, obs)
    t, _ = P.metricas(res)
    assert t.loc["calibrada", "bss_vs_clima"] > 0.2 and t.loc["calibrada", "auc"] > 0.85
    assert abs(t.loc["calibrada", "p_media"] - t.loc["calibrada", "frecuencia"]) < 0.01
    assert t.loc["clima", "bss_vs_clima"] == pytest.approx(0)


def test_una_temporada_se_predice_sin_sus_propias_etiquetas():
    media, mi, obs = _sintetico()
    a = P.calibrar(media, mi, obs)["calibrada"]
    obs2 = obs.copy()
    sel = P.temporada(obs.index) == 2003
    obs2.loc[sel] = obs.loc[sel] * 50
    b = P.calibrar(media, mi, obs2)["calibrada"]
    t = P.temporada(a.index) == 2003
    assert np.allclose(a[t], b[t]) and not np.allclose(a[~t], b[~t])


def test_tabla_operativa_reproduce_la_probabilidad():
    media, mi, obs = _sintetico()
    tab = P.tabla_operativa(media, mi, obs, {"id": "z"}, 1)
    n = tab["nodos"]["0"]
    mu, mm = media[0].iloc[10], mi.xs(0, level="celda").iloc[10].to_numpy()
    z = n["intercepto"] + n["coef_raiz_media"] * np.sqrt(mu) + n["coef_fraccion"] * (mm > n["umbral_modelo_mm"]).mean()
    assert 0 < 1 / (1 + np.exp(-z)) < 1 and n["umbral_pisco_mm"] > 0
