import numpy as np
import pandas as pd
import pytest

from illapa_research import c3g_casero as K


def test_la_matriz_bilineal_reproduce_un_campo_lineal_y_sus_filas_suman_uno():
    lat_g, lon_g = np.array([-11.25, -11.5, -11.75]), np.array([-77.0, -76.75, -76.5, -76.25])
    lat_f, lon_f = np.array([-11.3, -11.42, -11.61]), np.array([-76.97, -76.6, -76.31])
    W = K.matriz_bilineal(lat_g, lon_g, lat_f, lon_f)
    assert W.sum(axis=1) == pytest.approx(np.ones(9))
    campo = 3 * lat_g[:, None] - 2 * lon_g[None, :]
    fino = (W @ campo.ravel()).reshape(3, 3)
    assert fino == pytest.approx(3 * lat_f[:, None] - 2 * lon_f[None, :])


def test_el_mapeo_lleva_la_distribucion_del_modelo_a_la_observada_y_es_monotono():
    rng = np.random.default_rng(0)
    obs = rng.gamma(0.6, 5, 3000)
    mod = 2.5 * rng.gamma(0.6, 5, 3000) + 0.3  # wet bias and drizzle
    x = 2.5 * rng.gamma(0.6, 5, 3000) + 0.3
    y = K.mapear(mod, obs, x)
    assert np.mean(y) == pytest.approx(np.mean(obs), rel=0.08)
    assert np.percentile(y, 95) == pytest.approx(np.percentile(obs, 95), rel=0.1)
    o = np.argsort(x)
    assert np.all(np.diff(y[o]) >= -1e-9)


def test_los_empates_secos_van_al_rango_medio_y_por_encima_del_maximo_se_escala():
    mod = np.r_[np.zeros(50), np.arange(1, 51, dtype=float)]
    obs = np.r_[np.zeros(70), np.arange(1, 31, dtype=float)]
    y = K.mapear(mod, obs, np.array([0.0, 100.0]))
    assert y[0] == 0  # half of the model is dry, 70 % of the observations: zero maps to zero
    assert y[1] == pytest.approx(100 * 30 / 50)


def test_fuera_de_temporada_no_usa_su_propia_temporada():
    dias = pd.DatetimeIndex([d for a in (2001, 2002, 2003) for d in pd.date_range(f"{a}-01-01", f"{a}-01-31")])
    mod = np.tile(np.arange(31, dtype=float), 3)[:, None]
    obs = mod.copy()
    obs[dias.year == 2003] *= 100  # only 2003 is different
    out = K.corregir_fuera_de_temporada(mod, obs, dias)
    assert out[dias.year == 2003] == pytest.approx(mod[dias.year == 2003], abs=1e-6)
    assert np.nanmax(out[dias.year == 2001]) > 100  # 2001 learns from 2003


def test_metricas_de_un_pronostico_perfecto():
    dias = pd.date_range("2001-01-01", periods=120)
    y = np.random.default_rng(1).gamma(0.5, 6, 120)
    m = K.metricas_celda(y, y, dias)
    assert m["sesgo"] == pytest.approx(1) and m["r_diaria"] == pytest.approx(1)
    assert m["csi_p90"] == 1 and m["falsas_p90"] == 0
