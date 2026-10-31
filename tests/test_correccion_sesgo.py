import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from illapa_research import correccion_sesgo as C


def _dias(inicio="2022-12-01", fin="2025-04-30"):
    idx = pd.date_range(inicio, fin)
    return idx[C.en_temporada(idx)]


def _par_sintetico(factor=3.0, semilla=0):
    """Observed rain and a model that marks `factor` times more, with the same order of days."""
    rng = np.random.default_rng(semilla)
    idx = _dias()
    obs = pd.Series(rng.gamma(0.5, 3.0, len(idx)), index=idx)
    return pd.Series(obs.to_numpy() * factor, index=idx), obs


def test_temporada_de_empieza_en_diciembre():
    assert C.temporada_de(date(2023, 12, 1)) == 2023
    assert C.temporada_de(date(2024, 4, 30)) == 2023
    assert C.temporada_de(pd.Timestamp("2025-01-15")) == 2024


def test_escala_recupera_el_factor():
    modelo, obs = _par_sintetico(factor=4.0)
    assert C.Escala.ajustar(modelo, obs).factor == pytest.approx(0.25)


def test_mapeo_de_cuantiles_quita_el_sesgo_y_no_cambia_el_orden():
    modelo, obs = _par_sintetico(factor=3.0)
    corregido = C.MapeoCuantiles.ajustar(modelo, obs).aplicar(modelo)
    assert corregido.sum() == pytest.approx(obs.sum(), rel=0.02)
    # A monotone correction never changes which day is bigger (ties aside)
    assert corregido.rank(method="min").corr(modelo.rank(method="min")) == pytest.approx(1.0, abs=1e-3)


def test_mapeo_de_cuantiles_sigue_creciendo_por_encima_del_maximo():
    modelo, obs = _par_sintetico()
    mapeo = C.MapeoCuantiles.ajustar(modelo, obs)
    arriba = np.array([modelo.max() + 1.0, modelo.max() + 5.0])
    salida = mapeo.aplicar(arriba)
    assert salida[1] - salida[0] == pytest.approx(4.0)
    assert (mapeo.aplicar(np.array([-1.0, 0.0])) >= 0).all()


def test_la_correccion_por_temporada_no_usa_la_temporada_que_corrige():
    modelo, obs = _par_sintetico(factor=2.0)
    # An outlier in the model, in the 2022-23 season
    modelo.loc["2023-02-10"] = 10_000.0
    corregido = C.corregir_por_temporada(modelo, obs, C.Escala)
    dias_2022 = [d for d in corregido.index if C.temporada_de(d) == 2022]
    dias_2023 = [d for d in corregido.index if C.temporada_de(d) == 2023]
    # The 2022-23 season is corrected with a fit from the other two, which do not have the outlier: factor 0.5
    assert corregido.loc[dias_2022].sum() == pytest.approx(0.5 * modelo.loc[dias_2022].sum(), rel=0.01)
    # The other seasons are corrected with a fit that has it, so their factor collapses
    assert corregido.loc[dias_2023].sum() < 0.1 * modelo.loc[dias_2023].sum()
    assert corregido.notna().all()


def test_metricas_cuenta_aciertos_falsas_alarmas_y_perdidos():
    idx = pd.date_range("2023-01-01", periods=6)
    obs = pd.Series([0, 5, 5, 0, 0, 1.0], index=idx)
    pred = pd.Series([0, 6, 1, 7, 0, 1.0], index=idx)
    m = C.metricas(obs, pred, umbral_mm=4.0)
    assert (m["aciertos"], m["falsas_alarmas"], m["perdidos"]) == (1, 1, 1)
    assert m["csi"] == pytest.approx(1 / 3)
    assert m["pod"] == pytest.approx(0.5) and m["far"] == pytest.approx(0.5)


def test_evaluar_dias_huaico_acepta_la_lluvia_del_dia_anterior():
    idx = pd.date_range("2023-03-01", "2023-03-31")
    pred = pd.Series(0.0, index=idx)
    pred.loc["2023-03-13"] = 9.0  # the rain; the press dates the huaico the 14th
    r = C.evaluar_dias_huaico(pred, [date(2023, 3, 14)], umbral_mm=5.0)
    assert r["huaicos"] == 1 and r["capturados"] == 1
    # Days next to the huaico are left out of the "other days" alarm rate
    assert r["tasa_alarma_otros"] == 0.0
    sin_aviso = C.evaluar_dias_huaico(pred, [date(2023, 3, 25)], umbral_mm=5.0)
    assert sin_aviso["capturados"] == 0 and sin_aviso["tasa_alarma_otros"] > 0.0


def test_dias_con_huaico_deja_solo_dia_exacto_dentro_de_las_temporadas():
    from illapa_research.catalogo import Evento

    def ev(d, precision="dia"):
        return Evento(d, precision, "Lurigancho-Chosica", (), "t", "alta", "")

    eventos = [ev(date(2023, 3, 14)), ev(date(2023, 3, 14)), ev(date(2023, 3, 1), "mes"), ev(date(2023, 8, 1)), ev(date(2020, 2, 1))]
    assert C.dias_con_huaico(eventos, date(2022, 12, 1), date(2025, 4, 30)) == [date(2023, 3, 14)]


def test_serie_modelo_suma_el_dia_de_las_7_a_las_7(tmp_path):
    # Two days of hourly data; 1 mm in the hour that ends at 13:00 UTC of day D belongs to the rain day D
    horas = pd.date_range("2023-03-01 00:00", periods=24 * 4, freq="h")
    lluvia = np.zeros(len(horas))
    lluvia[list(horas).index(pd.Timestamp("2023-03-02 13:00"))] = 1.0
    lluvia[list(horas).index(pd.Timestamp("2023-03-03 12:00"))] = 2.0
    punto = {"hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in horas], "precipitation": lluvia.tolist()}}
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps({"2022": [punto, punto]}))
    s = C.serie_modelo(ruta)
    assert s.loc["2023-03-02"] == pytest.approx(3.0)
    assert pd.isna(s.get(pd.Timestamp("2023-03-01"), np.nan)) or s.loc["2023-03-01"] == 0.0


def test_mejor_desfase_encuentra_el_dia_corrido():
    idx = _dias("2023-12-01", "2024-04-30")
    rng = np.random.default_rng(1)
    obs = pd.Series(rng.gamma(0.5, 3.0, len(idx)), index=idx)
    modelo = obs.shift(1).dropna()  # the model is one day behind: day D holds the rain of D-1
    assert C.mejor_desfase(modelo, obs) == -1


def test_a_igual_alarma_una_correccion_monotona_no_cambia_los_huaicos_capturados():
    rng = np.random.default_rng(3)
    idx = _dias()
    verdad = pd.Series(rng.gamma(0.5, 3.0, len(idx)), index=idx)
    modelo = verdad * 3.0 + rng.normal(0, 0.8, len(idx)).clip(-1, None)  # biased and noisy
    modelo = modelo.clip(lower=0)
    huaicos = [date(2023, 2, 10), date(2024, 3, 5), date(2025, 1, 20)]
    for d in huaicos:
        modelo.loc[pd.Timestamp(d)] = modelo.max()  # the model sees them
        verdad.loc[pd.Timestamp(d)] = verdad.max()
    tabla = C.comparar_a_igual_alarma(modelo, verdad, huaicos)
    capturados = tabla.pivot(index="tasa_alarma_otros", columns="correccion", values="capturados")
    assert (capturados["cuantiles"] == capturados["sin corregir"]).all()
    assert (capturados["escala"] == capturados["sin corregir"]).all()
