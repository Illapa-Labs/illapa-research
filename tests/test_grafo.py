import math

from illapa_research.grafo import aguas_abajo, desde_elementos, propagar_riesgo


def way(id_, nodes, coords, **tags):
    return {
        "type": "way",
        "id": id_,
        "nodes": nodes,
        "geometry": [{"lon": x, "lat": y} for x, y in coords],
        "tags": tags,
    }


# Two creeks (1-2-3 and 4-3) join at node 3 and flow on to node 5.
ELEMENTOS = [
    way(10, [1, 2, 3], [(-76.60, -11.90), (-76.62, -11.91), (-76.64, -11.92)], waterway="stream"),
    way(11, [4, 3], [(-76.64, -11.90), (-76.64, -11.92)], waterway="stream"),
    way(12, [3, 5], [(-76.64, -11.92), (-76.70, -11.93)], waterway="river", name="Rímac"),
]


def test_aguas_abajo_sigue_la_corriente():
    g = desde_elementos(ELEMENTOS)
    assert aguas_abajo(g, 1) == {2, 3, 5}
    assert aguas_abajo(g, 4) == {3, 5}
    assert aguas_abajo(g, 5) == set()


def test_el_riesgo_solo_baja_y_decae():
    g = desde_elementos(ELEMENTOS)
    r = propagar_riesgo(g, {1: 1.0}, decaimiento_km=5)
    assert r[1] == 1.0
    assert r[2] < r[1] and r[3] < r[2] and r[5] < r[3]
    assert r[4] == 0.0  # the other creek is not downstream of node 1


def test_dos_origenes_toman_el_maximo():
    g = desde_elementos(ELEMENTOS)
    r = propagar_riesgo(g, {1: 1.0, 4: 0.5})
    assert math.isclose(r[4], 0.5)
    assert r[3] >= 0.5 * math.exp(-2.2 / 10) - 1e-9
