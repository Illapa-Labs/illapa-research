from shapely.geometry import shape

from illapa_research.catalogo import cargar_cuencas, cargar_eventos


def test_eventos_tienen_precision_valida():
    eventos = cargar_eventos()
    assert len(eventos) == 13
    assert {e.precision_fecha for e in eventos} <= {"dia", "mes", "anio", "dia_por_confirmar"}


def test_solo_dia_exacto_filtra_las_fechas_aproximadas():
    exactos = cargar_eventos(solo_dia_exacto=True)
    assert exactos and all(e.precision_fecha == "dia" for e in exactos)
    assert len(exactos) < len(cargar_eventos())


def test_cuencas_son_poligonos_con_area_razonable():
    for ft in cargar_cuencas()["features"]:
        assert shape(ft["geometry"]).is_valid
        assert 5 < ft["properties"]["area_km2"] < 15
