import numpy as np
import pandas as pd
import pytest

from illapa_research import correccion_malla as M
from illapa_research.correccion_sesgo import Escala, MapeoCuantiles

Z = {"id": "z", "west": -77.0, "north": -11.5, "step": 0.1, "cols": 3, "rows": 3, "cells": list(range(9))}


def _datos(semilla=0, factor=2.6):
    rng = np.random.default_rng(semilla)
    dias = pd.date_range("2021-07-01", "2025-06-30")
    obs = pd.DataFrame(rng.gamma(0.4, 3, (len(dias), 9)), index=dias, columns=range(9))
    mod = obs * factor + rng.normal(0, 0.1, obs.shape).clip(0)
    return mod, obs


def test_los_nodos_siguen_la_formula_del_engine():
    nd = M.nodos(Z)
    assert nd.loc[0, ["lat", "lon"]].tolist() == [-11.5, -77.0]
    assert nd.loc[5, ["fila", "col", "lat", "lon"]].tolist() == [1, 2, -11.6, -76.8]


def test_vecinos_en_una_ventana_de_3x3():
    v = M.vecinos(M.nodos(Z))
    assert sorted(v[4]) == list(range(9)) and sorted(v[0]) == [0, 1, 3, 4]


def test_dia_de_lluvia_de_12_a_12_utc_y_solo_dias_completos():
    h = pd.DataFrame({0: 1.0}, index=pd.date_range("2024-01-01 12:00", "2024-01-03 11:00", freq="h"))
    d = M.diario_desde_horas(h)
    assert d.loc["2024-01-01", 0] == 24 and d.loc["2024-01-02", 0] == 24
    assert np.isnan(M.diario_desde_horas(h.iloc[:-1]).loc["2024-01-02", 0])


def test_escala_y_cuantiles_quitan_el_sesgo_fuera_de_anio():
    mod, obs = _datos()
    nd = M.nodos(Z)
    crudo = M.evaluar(obs, mod)
    esc = M.evaluar(obs, M.corregir_fuera_de_anio(mod, obs, nd, Escala))
    qm = M.evaluar(obs, M.corregir_fuera_de_anio(mod, obs, nd, MapeoCuantiles, n=20))
    assert crudo["sesgo"].median() == pytest.approx(2.6, rel=0.05)
    assert esc["sesgo"].median() == pytest.approx(1, rel=0.05)
    assert qm["sesgo"].median() == pytest.approx(1, rel=0.1)


def test_la_correccion_de_un_anio_no_usa_sus_propios_dias():
    mod, obs = _datos()
    nd = M.nodos(Z)
    a = M.corregir_fuera_de_anio(mod, obs, nd, Escala)
    obs2 = obs.copy()
    obs2.loc["2023-07-01":"2024-06-30"] *= 10
    b = M.corregir_fuera_de_anio(mod, obs2, nd, Escala)
    anio = slice("2023-07-01", "2024-06-30")
    assert np.allclose(a.loc[anio], b.loc[anio])
    assert not np.allclose(a.loc["2022-07-01":"2023-06-30"], b.loc["2022-07-01":"2023-06-30"])


def test_regimenes_se_ajustan_por_separado():
    mod, obs = _datos()
    mod.loc[~np.isin(mod.index.month, M.MESES_LLUVIAS)] = obs * 0.5
    aj = M.ajustar(mod, obs, M.nodos(Z), Escala)
    assert aj[("lluvias", 4)].factor == pytest.approx(1 / 2.6, rel=0.05)
    assert aj[("seca", 4)].factor == pytest.approx(2, rel=0.01)


def test_tabla_json_trae_cuantiles_por_regimen_y_celda():
    mod, obs = _datos()
    t = M.a_json(M.ajustar(mod, obs, M.nodos(Z), MapeoCuantiles, n=20), Z, "cuantiles", "PISCOp")
    q = t["regimenes"]["lluvias"]["4"]
    assert len(q["q_modelo"]) == 21 and q["q_modelo"] == sorted(q["q_modelo"]) and q["q_obs"] == sorted(q["q_obs"])


def test_pisco_en_nodos_promedia_las_cuatro_celdas(tmp_path):
    import netCDF4

    ruta = tmp_path / "p.nc"
    with netCDF4.Dataset(ruta, "w") as d:
        d.createDimension("time", 2)
        d.createDimension("latitude", 4)
        d.createDimension("longitude", 4)
        t = d.createVariable("time", "f8", ("time",))
        t.units = "days since 1981-01-01"
        t[:] = [0, 1]
        d.createVariable("latitude", "f8", ("latitude",))[:] = [-11.45, -11.55, -11.65, -11.75]
        d.createVariable("longitude", "f8", ("longitude",))[:] = [-77.05, -76.95, -76.85, -76.75]
        p = d.createVariable("precipitation", "f4", ("time", "latitude", "longitude"))
        p[:] = np.arange(32, dtype="float32").reshape(2, 4, 4)
    nd = M.nodos({**Z, "cells": [0]})  # node at (-11.5, -77.0): cells (0,0), (0,1), (1,0), (1,1)
    s = M.pisco_en_nodos(ruta, nd)
    assert s.loc["1981-01-01", 0] == pytest.approx(np.mean([0, 1, 4, 5]))
    assert s.index[1] == pd.Timestamp("1981-01-02")


def test_pisco_con_el_contador_z1_del_archivo_real(tmp_path):
    import netCDF4

    ruta = tmp_path / "z1.nc"
    with netCDF4.Dataset(ruta, "w") as d:
        for k, n in (("Z1", 3), ("latitude", 2), ("longitude", 2)):
            d.createDimension(k, n)
        z = d.createVariable("Z1", "i4", ("Z1",))
        z.units = "unknown"
        z[:] = [1, 2, 3]
        d.createVariable("latitude", "f8", ("latitude",))[:] = [-11.45, -11.55]
        d.createVariable("longitude", "f8", ("longitude",))[:] = [-77.05, -76.95]
        d.createVariable("precipitation", "f4", ("Z1", "latitude", "longitude"))[:] = np.ones((3, 2, 2))
    s = M.pisco_en_nodos(ruta, M.nodos({**Z, "cells": [0]}))
    assert list(s.index) == list(pd.date_range("1981-01-01", periods=3)) and (s[0] == 1).all()


def test_indice_ukmo_devuelve_la_celda_del_centro_que_da_la_api():
    # centres returned by the API in chapter 14
    assert M.indice_ukmo(-11.90625, -76.78125) == (833, 734)
    assert M.indice_ukmo(-12.0, -76.640625) == (832, 735)
