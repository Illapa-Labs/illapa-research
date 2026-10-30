import pandas as pd

from illapa_research import integracion as ig


def _act():
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2017-03-01", "2017-03-01", "2017-03-02", "2018-03-01"]),
            "slug": ["a", "b", "a", "a"],
            "temporada": [2017, 2017, 2017, 2018],
        }
    )


def test_participacion_cuenta_dias_con_evento_y_separa_nino():
    t = pd.DataFrame({"nino": [True, False]}, index=pd.Index([2017, 2018]))
    pi = ig.participacion(_act(), {"a", "b"}, t)
    a = pi[(pi.slug == "a") & (pi.temporadas == "todas")].iloc[0]
    assert a["dias_activa"] == 3 and a["dias_con_evento"] == 3
    b = pi[(pi.slug == "b") & (pi.temporadas == "nino")].iloc[0]
    assert b["dias_activa"] == 1 and b["dias_con_evento"] == 2
    assert (pi["pi_p10"] <= pi["pi"]).all() and (pi["pi"] <= pi["pi_p90"]).all()


def test_activaciones_esperadas_pondera_por_participacion():
    t = pd.DataFrame({"nino": [True, False]}, index=pd.Index([2017, 2018]))
    pi = ig.participacion(_act(), {"a", "b"}, t)
    p = pd.Series([0.1, 0.3], index=pd.to_datetime(["2017-03-05", "2017-03-06"]))
    out = ig.activaciones_esperadas(p, pi)
    assert out.loc["a", "activaciones_esperadas"] > out.loc["b", "activaciones_esperadas"]
