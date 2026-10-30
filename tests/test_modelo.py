import numpy as np
import pandas as pd

from illapa_research import modelo


def _temporadas():
    idx = range(2000, 2012)
    return pd.DataFrame({"nino": [a in {2002, 2003, 2007, 2010} for a in idx]}, index=pd.Index(idx))


def test_episodios_une_temporadas_consecutivas():
    assert modelo.episodios(_temporadas()) == [[2002, 2003], [2007], [2010]]


def _datos(y0, y1, n0=40, n1=20):
    k = len(y0)
    return modelo.Datos(
        slug=[f"q{i}" for i in range(k)], z=np.zeros(k), y0=np.array(y0, float),
        y1=np.array(y1, float), ubicada=np.ones(k, bool), n0=n0, n1=n1,
    )


def test_razon_de_tasas_recupera_un_efecto_nino_claro():
    # About 0.1 days per non-Niño season and 0.4 per Niño season: ratio near 4.
    d = _datos([4, 4, 4], [8, 8, 8])
    r = modelo.razon_de_tasas(modelo.muestrear(d, n=800))
    assert 2.0 < r["mediana"] < 7.0 and r["ic95_bajo"] < r["mediana"] < r["ic95_alto"]


def test_sin_datos_la_razon_queda_ancha_cerca_de_uno():
    d = _datos([0, 0], [0, 0])
    r = modelo.razon_de_tasas(modelo.muestrear(d, n=800))
    assert r["ic95_alto"] / r["ic95_bajo"] > 5


def test_rangos_ponen_arriba_a_la_quebrada_con_eventos():
    d = _datos([0, 0, 0], [0, 0, 0])
    d.ubicada = np.array([True, False, False])
    d.y1 = np.array([6.0, 0, 0])
    r = modelo.rangos(d, modelo.muestrear(d, n=800))
    assert r.loc[0, "p_top5"] >= r.loc[1, "p_top5"]
    assert r.loc[0, "rango_mediano"] <= r.loc[1, "rango_mediano"]
    assert (r["rango_p10"] <= r["rango_p90"]).all()
