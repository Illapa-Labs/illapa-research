import numpy as np
import pandas as pd

from illapa_research import modelo_quebradas as mq


def _datos(s0, s1, n0=20, n1=10, modo="temporadas"):
    k = len(s0)
    return mq.Datos(
        slug=[f"q{i}" for i in range(k)], z=np.zeros(k), e=np.zeros(k), y0=np.array(s0, float),
        y1=np.array(s1, float), ubicada=np.ones(k, bool), n0=n0, n1=n1,
        s0=np.array(s0, float), s1=np.array(s1, float), modo=modo,
    )


def test_razon_de_tasas_recupera_un_efecto_nino_claro():
    d = _datos([1, 2, 1, 2, 1, 2], [6, 7, 8, 6, 7, 8])
    hiper, libres = mq.muestrear(d, "nino", n=600)
    rho = np.exp(hiper[:, 1])
    assert libres == ("lr",) and 2.0 < np.median(rho) < 12.0


def test_sin_datos_la_razon_queda_ancha():
    d = _datos([0, 0, 0], [0, 0, 0])
    hiper, _ = mq.muestrear(d, "nino", n=600)
    rho = np.exp(hiper[:, 1])
    assert np.percentile(rho, 97.5) / np.percentile(rho, 2.5) > 5


def test_verosimilitud_es_finita_en_ambos_modos():
    for modo in ("temporadas", "dias"):
        d = _datos([1, 0], [3, 0], modo=modo)
        ll = mq._loglik(d, {"lm": -2.0, "lr": 0.5, "g": 0.0, "d": 0.0}, 1.0)
        assert np.isfinite(ll).all()


def test_rangos_ponen_arriba_la_quebrada_con_historial():
    d = _datos([0, 0, 0], [0, 0, 0])
    d.ubicada = np.array([True, False, False])
    d.s1 = d.y1 = np.array([6.0, 0, 0])
    hiper, libres = mq.muestrear(d, "nino", n=600)
    r = mq.rangos(d, hiper, libres)
    assert r.loc[0, "rango_mediano"] <= r.loc[1, "rango_mediano"]
    assert (r["rango_p10"] <= r["rango_p90"]).all()


def test_dejar_una_quebrada_fuera_devuelve_un_puntaje_por_modelo():
    d = _datos([1, 0, 2, 1], [5, 3, 6, 4])
    out = mq.dejar_una_quebrada_fuera(d, ["nulo", "nino"], n=200)
    assert set(out["modelo"]) == {"nulo", "nino"} and len(out) == 8 and np.isfinite(out["log_pred"]).all()


def test_contraste_cuenta_quebradas_activas_por_temporada():
    t = pd.DataFrame({"nino": [True, True, False, False]}, index=pd.Index([2001, 2002, 2003, 2004]))
    act = pd.DataFrame({"fecha": pd.to_datetime(["2001-03-01", "2001-03-02", "2002-03-01", "2003-03-01"]),
                        "slug": ["a", "b", "a", "a"], "temporada": [2001, 2001, 2002, 2003]})
    r = mq.contraste_temporadas(act, {"a", "b"}, t, 2001)
    assert r["media_activas_nino"] == 1.5 and r["media_activas_no_nino"] == 0.5
