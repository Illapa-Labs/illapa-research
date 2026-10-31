import numpy as np
import pandas as pd
import pytest

from illapa_research import ficha_pronostico as F


def _oof(n=6000, semilla=0, exceso=3.0):
    """A model that overstates: true logit = raw logit - shift."""
    rng = np.random.default_rng(semilla)
    ts = np.repeat(np.arange(2000, 2020), n // 20)
    x = rng.normal(-3.5, 1.2, n)
    p_crudo = 1 / (1 + np.exp(-x))
    y = (rng.random(n) < 1 / (1 + np.exp(-(x - exceso * 0.3)))).astype(int)
    filas = []
    for plazo in (1, 2, 3):
        filas.append(pd.DataFrame({"dia": pd.date_range("2000-01-01", periods=n), "plazo": plazo, "temporada": ts,
                                   "huaico": y, "climatologia": y.mean(), "pp_qm": p_crudo}))
    return pd.concat(filas, ignore_index=True)


def test_platt_corrige_un_modelo_que_exagera():
    oof = _oof()
    d = oof[oof.plazo == 1]
    cal = F.calibrar_fuera_de_temporada(d.pp_qm.to_numpy(), d.huaico.to_numpy(), d.temporada.to_numpy())
    antes = d.huaico.sum() / d.pp_qm.sum()
    despues = d.huaico.sum() / cal.sum()
    assert abs(despues - 1) < abs(antes - 1)


def test_bandas_cuentan_dias_y_huaicos():
    y = np.array([0, 0, 1, 0, 1, 1])
    p = np.array([0.005, 0.01, 0.05, 0.3, 0.4, 0.5])
    b = F.bandas(y, p)
    assert b["dias"].sum() == 6 and b["huaicos"].sum() == 3
    assert b.loc[b["desde"] == 0.25, "huaicos"].iloc[0] == 2


def test_ficha_devuelve_probabilidad_intervalo_y_limites():
    m = F.FichaPronostico(_oof(), n_boot=60)
    f = m.ficha(0.30, 1, condiciones={"lluvia": "fuerte"})
    assert 0 < f["probabilidad"] < 1 and f["intervalo_80"][0] <= f["probabilidad"] <= f["intervalo_80"][1]
    assert f["origen_de_la_cifra"].startswith("frecuencia observada") and "probabilidad_modelo_calibrada" in f
    assert "No es una alerta" in f["limites"] and f["condiciones"] == {"lluvia": "fuerte"}
    assert f["banda_de_fiabilidad"]["dias"] >= 0 and "probabilidad_sin_2017" in f


def test_ficha_avisa_a_48_y_72_horas():
    m = F.FichaPronostico(_oof(), n_boot=60)
    assert not any("48 h" in a for a in m.ficha(0.01, 1)["advertencias"])
    assert any("48 h" in a for a in m.ficha(0.01, 2)["advertencias"])


def test_plazo_desconocido_falla():
    with pytest.raises(ValueError):
        F.FichaPronostico(_oof(), n_boot=30).ficha(0.1, 5)
