from datetime import date

from illapa_research import avisos_senamhi as V


def _aviso(i, ini, fin, nivel="2", prov="LIMA"):
    return {"id": i, "number": i, "provincia": prov, "title": "t", "level": nivel, "publishedDate": ini,
            "activeStartDate": ini, "activeEndDate": fin}


def test_tabla_y_dias_con_aviso():
    t = V.tabla_avisos([_aviso(1, "2024-02-10T00:00:00", "2024-02-12T23:59:59"), _aviso(1, "2024-02-10T00:00:00", "2024-02-12T23:59:59"),
                        _aviso(2, "2024-02-20T00:00:00", "2024-02-20T23:59:59", nivel="1")])
    assert len(t) == 2
    assert V.dias_con_aviso(t, "LIMA") == {date(2024, 2, 10), date(2024, 2, 11), date(2024, 2, 12), date(2024, 2, 20)}
    assert V.dias_con_aviso(t, "LIMA", nivel_min=2) == {date(2024, 2, 10), date(2024, 2, 11), date(2024, 2, 12)}


def test_cobertura_pod_y_far():
    t = V.tabla_avisos([_aviso(1, "2024-02-10T00:00:00", "2024-02-11T23:59:59")])
    r = V.cobertura(t, [date(2024, 2, 11), date(2024, 2, 25), date(2023, 1, 1)], "LIMA")
    assert r["huaicos"] == 2 and r["con_aviso"] == 1 and r["pod"] == 0.5
    assert r["dias_aviso"] == 2 and abs(r["far"] - 0.5) < 1e-9


def test_solo_avisos_de_lluvia_descarta_viento_y_temperatura():
    assert V.es_de_lluvia("Precipitaciones en la sierra centro y sur")
    assert V.es_de_lluvia("Lluvia en la costa")
    assert not V.es_de_lluvia("Incremento de viento en la costa")
    assert not V.es_de_lluvia("Descenso de temperatura nocturna en la sierra")
    a = _aviso(1, "2024-02-10T00:00:00", "2024-02-11T23:59:59")
    b = {**_aviso(2, "2024-02-15T00:00:00", "2024-02-15T23:59:59"), "title": "Incremento de viento en la costa"}
    a["title"] = "Precipitaciones en la sierra"
    t = V.tabla_avisos([a, b])
    assert len(V.dias_con_aviso(t, "LIMA")) == 3 and len(V.dias_con_aviso(t, "LIMA", solo_lluvia=True)) == 2
