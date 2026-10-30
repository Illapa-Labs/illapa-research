import numpy as np
import pandas as pd

from illapa_research import hipotesis_literatura as H


def _horario():
    idx = pd.date_range("2020-02-01", periods=48, freq="h")
    p = np.zeros(48)
    p[14:17] = [1.0, 3.0, 1.0]  # day 1: afternoon burst 14-16 h, peak at 15 h
    p[24 + 2 : 24 + 8] = 0.5  # day 2: six wet hours at night
    return {"chosica": pd.DataFrame({"precipitation": p}, index=idx)}


def test_variables_horarias_hora_pico_tarde_y_racha():
    idx = pd.date_range("2020-02-01", periods=2, freq="D")
    T = H.variables_horarias(_horario(), idx)
    assert T.loc["2020-02-01", "chosica_hora_pico"] == 15
    assert T.loc["2020-02-01", "chosica_frac_tarde"] == 1.0
    assert T.loc["2020-02-01", "chosica_horas_humedas"] == 3
    assert T.loc["2020-02-02", "chosica_racha_max_h"] == 6
    assert T.loc["2020-02-02", "chosica_frac_tarde"] == 0.0
    assert T.loc["2020-02-01", "chosica_frac_3h_max"] == 1.0


def test_sst_absoluta_no_usa_el_dia_y_cuenta_grados_dia_y_racha():
    idx = pd.date_range("2020-02-01", periods=6, freq="D")
    sst = pd.DataFrame({"nino12": [24.0, 26.5, 27.0, 25.0, 28.0, 20.0]}, index=idx)
    S = H.variables_sst_absoluta(sst, idx)
    # day 4 sees days 1-3: 26.5 and 27.0 are above 26 (run of 2), degree-days 0.5 + 1.0
    d = idx[3]
    assert S.loc[d, "sstabs_nino12_racha_26"] == 2
    assert abs(S.loc[d, "sstabs_nino12_gd26_7d"] - 1.5) < 1e-9
    # the day itself (25.0 on day 4, 28.0 on day 5) never enters its own features
    assert S.loc[idx[4], "sstabs_nino12_nivel"] == 25.0
    assert S.loc[idx[0], "sstabs_nino12_nivel"] != S.loc[idx[0], "sstabs_nino12_nivel"]  # NaN: no yesterday


def test_auc_estratificado_ignora_el_ciclo_estacional():
    # x only separates months, never events inside a month: stratified AUC must be 0.5
    mes = np.array([1] * 20 + [2] * 20)
    x = np.array([0.0] * 20 + [1.0] * 20)
    y = np.array([0, 0, 1, 1] * 5 + [0, 1, 0, 1] * 5)
    assert abs(H.auc_estratificado(x, y, mes) - 0.5) < 1e-9
    x2 = np.arange(40, dtype=float)
    y2 = (x2 % 20 >= 15).astype(int)
    assert H.auc_estratificado(x2, y2, mes) > 0.9


def test_cargar_ec_y_variables_mensuales_usan_el_mes_previo(tmp_path):
    ruta = tmp_path / "ec.txt"
    ruta.write_text("year month E_index C_index\n2020 01 1.0 0.1\n2020 02 2.0 0.2\n2020 03 4.0 0.3\n", encoding="utf-8")
    ec = H.cargar_ec(ruta)
    idx = pd.date_range("2020-03-10", periods=2, freq="D")
    V = H.variables_ec_mensuales(ec, idx)
    assert V["ec_E_mes_previo"].iloc[0] == 2.0  # in March only February is known
    assert V["ec_E_cambio"].iloc[0] == 1.0  # February minus January


def test_correlacion_con_temporadas_detecta_una_relacion_monotona():
    ind = pd.DataFrame({"x": np.arange(20.0), "ruido": np.tile([1.0, -1.0], 10)}, index=range(2000, 2020))
    res = pd.Series(np.arange(20.0), index=range(2000, 2020))
    out = H.correlacion_con_temporadas(ind, res, n_perm=300).set_index("indice")
    assert out.loc["x", "rho"] > 0.99 and out.loc["x", "p_permutacion"] < 0.01
    assert out.loc["ruido", "p_permutacion"] > 0.05


def test_ap_pareado_mejora_si_el_modelo_nuevo_es_perfecto():
    rng = np.random.default_rng(0)
    ts = np.repeat(np.arange(10), 30)
    y = (rng.random(300) < 0.1).astype(int)
    perfecto = y.astype(float) * 0.9 + 0.05
    azar = rng.random(300)
    r = H.ap_pareado(y, perfecto, azar, ts, n=100)
    assert r["delta_ap"] > 0.5 and r["prob_mejora"] > 0.95


def test_comparar_con_era5_separa_cola_y_correlacion():
    idx = pd.date_range("2020-01-01", periods=60, freq="D")
    era = pd.Series(np.arange(60.0), index=idx)
    chirps = pd.DataFrame({"mat": era * 2.0})
    F = pd.DataFrame({"mat_lluvia_1d": era})
    r = H.comparar_con_era5(chirps, F, {"mat": "mat_lluvia_1d"})
    assert r.loc[0, "corr_pearson"] > 0.99 and r.loc[0, "media_chirps_5pc_era5"] > r.loc[0, "media_era5_5pc_era5"]
