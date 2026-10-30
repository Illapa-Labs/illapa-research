import numpy as np
import pytest
from shapely.geometry import shape

from illapa_research.catalogo import cargar_cuencas
from illapa_research.quebradas import (
    RESOLUCION_M,
    Terreno,
    nombrar,
    slug,
)


@pytest.fixture(scope="module")
def cuencas():
    return {f["properties"]["slug"]: f for f in cargar_cuencas()["features"]}


def test_cuencas_coinciden_con_las_areas_publicadas(cuencas):
    # Quirio ~9-10 km², Pedregal ~9.6-10, Los Laureles ~9 (IGP 2020 and the earlier pilot).
    assert 9.0 <= cuencas["quirio"]["properties"]["area_km2"] <= 10.5
    assert 9.0 <= cuencas["pedregal"]["properties"]["area_km2"] <= 10.5
    assert 8.5 <= cuencas["los-laureles"]["properties"]["area_km2"] <= 9.5
    # IGP 2020 (Cuadro 01), placed with its UTM points: Chacrasana 4,7, La Ronda 8,9, Barba Blanca 3,5.
    for nombre, ref in ("chacrasana", 4.7), ("la-ronda", 8.9), ("barba-blanca", 3.5):
        assert abs(cuencas[nombre]["properties"]["area_km2"] / ref - 1) < 0.15


def test_cuencas_tienen_atributos_fisicos_consistentes(cuencas):
    assert len(cuencas) > 100
    for f in cuencas.values():
        p = f["properties"]
        assert shape(f["geometry"]).is_valid
        assert p["relieve_m"] == pytest.approx(p["z_max_m"] - p["z_min_m"], abs=0.1)
        assert p["area_km2"] >= 0.4
        assert p["longitud_cauce_km"] > 0
        assert p["melton"] == pytest.approx(p["relieve_m"] / (p["area_km2"] * 1e6) ** 0.5, rel=0.01)


def test_slug_quita_acentos():
    assert slug("Río Seco") == "rio-seco"
    assert slug("Los Cóndores") == "los-condores"


def test_referencias_sin_coordenadas_no_nombran():
    cuencas = [{"_poligono_utm": shape({"type": "Point", "coordinates": (0, 0)}).buffer(1), "area_km2": 1.0,
                "salida_lon": -76.7, "salida_lat": -11.9}]
    nombrar(cuencas, [{"nombre": "X", "alias": (), "lon": None, "lat": None}])
    assert cuencas[0]["ubicacion"] == "sin_nombre"
    assert cuencas[0]["slug"].startswith("q")


def test_cauce_principal_recorre_la_celda_mas_lejana():
    from illapa_research.quebradas import cauce_principal

    # A 1 x 6 channel flowing east (D8 code 1) to the outlet in the last column.
    fdir = np.full((1, 6), 1, dtype=np.int64)
    acc = np.arange(1, 7)[None, :]
    t = Terreno(z=np.zeros((1, 6)), z_lleno=np.zeros((1, 6)), fdir=fdir, acc=acc, transform=None)
    ruta, dist = cauce_principal(t, np.ones((1, 6), dtype=bool), (0, 5))
    assert ruta[0] == (0, 0) and ruta[-1] == (0, 5)
    assert dist[0] == pytest.approx(5 * RESOLUCION_M)


def test_delimitar_separa_afluentes_de_un_valle_sintetico(monkeypatch):
    from rasterio import Affine

    from illapa_research import quebradas as qb

    h, w = 70, 90
    filas, cols = np.mgrid[0:h, 0:w]
    # Valley floor along row 60 falling to the east; two side valleys (columns 20 and 60) feed it
    # from the north. The floor is the "river"; the side valleys are the quebradas.
    z = 1000.0 + 8.0 * np.abs(filas - 60) - 1.0 * cols
    for c0 in (20, 60):
        z -= 12.0 * np.exp(-((cols - c0) ** 2) / 8.0) * (filas < 60)
    tr = Affine(30.0, 0.0, 300000.0, 0.0, -30.0, 8680000.0)
    monkeypatch.setattr(qb, "AREA_RIO_KM2", 0.5)
    monkeypatch.setattr(qb, "AREA_MIN_KM2", 0.05)
    t = qb.acondicionar(z.astype("float32"), tr, [])
    etiqueta, salidas = qb.delimitar(t, ventana=(-180, -90, 180, 90))
    assert len(salidas) >= 2
    assert etiqueta.max() == len(salidas) and (etiqueta > 0).sum() > 0
    a = qb.atributos(t, etiqueta, salidas[0], 1)
    assert a["area_km2"] > 0.04 and a["longitud_cauce_km"] > 0 and np.isfinite(a["melton"])
    assert a["relieve_m"] == pytest.approx(a["z_max_m"] - a["z_min_m"], abs=0.1)
