from shapely.geometry import shape

from illapa_research.catalogo import cargar_cuencas, cargar_eventos, cargar_todos


def test_eventos_tienen_precision_valida():
    eventos = cargar_eventos()
    assert len(eventos) == 13
    assert {e.precision_fecha for e in eventos} <= {"dia", "mes", "anio", "dia_por_confirmar"}


def test_solo_dia_exacto_filtra_las_fechas_aproximadas():
    exactos = cargar_eventos(solo_dia_exacto=True)
    assert exactos and all(e.precision_fecha == "dia" for e in exactos)
    assert len(exactos) < len(cargar_eventos())


def test_cuencas_son_poligonos_con_area_razonable():
    nombradas = [f for f in cargar_cuencas()["features"] if f["properties"]["ubicacion"] == "referencia"]
    assert {f["properties"]["slug"] for f in nombradas} >= {"quirio", "pedregal", "los-laureles", "chacrasana", "la-ronda", "barba-blanca"}
    for ft in nombradas:
        assert shape(ft["geometry"]).is_valid
        if ft["properties"]["slug"] in {"quirio", "pedregal", "los-laureles", "chacrasana", "la-ronda", "barba-blanca"}:
            assert 3 < ft["properties"]["area_km2"] < 15


def test_cronica_igp_trae_1998_con_dia_exacto():
    igp = [e for e in cargar_todos(solo_dia_exacto=True) if e.fecha.year == 1998]
    assert {e.fecha.isoformat() for e in igp} >= {"1998-01-29", "1998-02-15", "1998-02-24"}
    chaclacayo = [e for e in igp if "Los Cóndores" in e.quebradas]
    assert chaclacayo and chaclacayo[0].distrito == "Chaclacayo"


def test_catalogo_completo_tiene_decadas_de_cobertura():
    fechas = {e.fecha for e in cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)}
    assert len(fechas) > 60
    assert {f.year for f in fechas} >= {1983, 1998, 2009, 2015, 2017, 2020, 2023, 2026}
    assert not any(e.confianza == "baja" for e in cargar_todos(sin_baja_confianza=True))
