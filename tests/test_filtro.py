from datetime import date

import pandas as pd
import pytest

from illapa_research import filtro, nino
from illapa_research.catalogo import Evento


def _temporadas(anios_nino, desde=2000, hasta=2009):
    idx = range(desde, hasta + 1)
    return pd.DataFrame({"nino": [a in anios_nino for a in idx]}, index=pd.Index(idx, name="temporada"))


def test_temporada_cuenta_noviembre_y_diciembre_en_la_siguiente():
    assert nino.temporada_de(date(2016, 12, 20)) == 2017
    assert nino.temporada_de(date(2017, 3, 15)) == 2017


def test_temporadas_marca_el_nino_con_umbrales_fijos():
    oni = pd.DataFrame(
        [(s, 2017, v) for s, v in (("DJF", -0.3), ("JFM", 0.0), ("FMA", 0.1))]
        + [(s, 2016, v) for s, v in (("DJF", 2.2), ("JFM", 2.0), ("FMA", 1.6))],
        columns=["trimestre", "anio", "oni"],
    )
    n12 = pd.DataFrame(
        [(2017, m, v) for m, v in ((1, 0.8), (2, 1.4), (3, 1.7), (4, 1.5))]
        + [(2016, m, 0.3) for m in (1, 2, 3, 4)],
        columns=["anio", "mes", "nino12"],
    )
    t = nino.temporadas(oni, n12)
    assert bool(t.loc[2017, "nino_costero"]) and not bool(t.loc[2017, "nino_global"])
    assert bool(t.loc[2016, "nino_global"]) and not bool(t.loc[2016, "nino_costero"])
    assert t["nino"].all()


@pytest.mark.parametrize(
    "fisica, k, evaluable, nivel",
    [(10, 2, True, 1), (10, 1, True, 2), (90, 0, True, 3), (50, 0, True, 4), (10, 0, True, 5), (99, 0, False, 6)],
)
def test_clasificar(fisica, k, evaluable, nivel):
    assert filtro.clasificar(fisica, k, evaluable) == nivel


def test_nombres_genericos_no_son_quebradas():
    for t in ("(sin quebrada)", "(varias", " ver tabla de la fuente)", "(huaycos)", "(inundación)"):
        assert filtro.es_generico(t)
    assert not filtro.es_generico("Quirio")
    assert not filtro.es_generico("La Ronda (río Seco)")


def test_intervalo_jeffreys_es_ancho_con_pocos_datos():
    _, lo, hi = filtro.intervalo_jeffreys(1, 3)
    assert hi - lo > 0.4
    p, lo2, hi2 = filtro.intervalo_jeffreys(30, 90)
    assert hi2 - lo2 < 0.2 and lo2 < p < hi2


def _cuencas():
    return pd.DataFrame(
        {
            "slug": ["quirio", "q1", "q2", "chica"],
            "nombre": ["Quebrada Quirio", "", "", ""],
            "ubicacion": ["referencia", "sin_nombre", "sin_nombre", "sin_nombre"],
            "area_km2": [10.0, 5.0, 6.0, 1.2],
            "melton": [0.4, 0.8, 0.2, 1.0],
            "pendiente_cauce_1085_pct": [15, 30, 8, 40],
            "pendiente_media_pct": [55, 70, 30, 80],
            "edificios_1km": [1000, 10, 0, 0],
            "salida_lon": [-76.7] * 4,
            "salida_lat": [-11.9] * 4,
        }
    )


def test_asignar_historial_cuenta_ubicadas_sin_ubicar_y_genericas():
    refs = [
        {"nombre": "Quirio", "alias": ("Quiro",), "lon": -76.7, "lat": -11.9},
        {"nombre": "Chacrasana", "alias": (), "lon": None, "lat": None},
    ]
    ev = [
        Evento(date(2017, 3, 15), "dia", "Chosica", ("Quiro", "Chacrasana"), "x", "alta", ""),
        Evento(date(2017, 3, 16), "dia", "Chosica", ("Chacrasana",), "x", "alta", ""),
        Evento(date(2017, 3, 17), "dia", "Chosica", ("(sin quebrada)",), "x", "alta", ""),
    ]
    h = filtro.asignar_historial(ev, refs, _cuencas())
    assert h.resumen == {
        "fechas": 3, "con_quebrada_ubicada": 1, "con_nombre_sin_ubicar": 1, "sin_quebrada": 1,
    }
    assert list(h.activaciones["slug"]) == ["quirio"]
    assert h.sin_ubicar == {"Chacrasana": 1}


def test_tabla_pone_primero_lo_documentado_y_deja_fuera_lo_muy_chico():
    temporadas = _temporadas({2002, 2005})
    act = pd.DataFrame(
        {"fecha": [date(2002, 3, 1), date(2005, 3, 1)], "slug": ["quirio", "quirio"], "temporada": [2002, 2005]}
    )
    t = filtro._tabla(_cuencas(), act, temporadas)
    assert t.iloc[0]["slug"] == "quirio" and t.iloc[0]["nivel"] == 1
    assert t.set_index("slug").loc["chica", "nivel"] == 6
    assert t.set_index("slug").loc["q1", "nivel"] < t.set_index("slug").loc["q2", "nivel"]


def test_dejar_un_nino_fuera_no_usa_la_temporada_retenida():
    temporadas = _temporadas({2002, 2005})
    act = pd.DataFrame({"fecha": [date(2002, 3, 1)], "slug": ["quirio"], "temporada": [2002]})
    hist = filtro.Historial(act)
    v = filtro.dejar_un_nino_fuera(_cuencas(), hist, temporadas)
    # Without 2002 the quebrada has no Niño season left: it falls to a physical-only level.
    assert len(v) == 1 and v["nivel"].iloc[0] > 2
