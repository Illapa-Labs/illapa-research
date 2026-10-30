from illapa_research.espejo_hf import ARCHIVOS, tarjeta


def test_tarjeta_lista_cada_fuente_con_licencia_y_atribucion():
    man = {"noaa-oisst": {"nombre": "NOAA OISST", "licencia": "Dominio público", "atribucion": "NOAA",
                           "descargado": "2026-10-30T10:00:00+00:00"}}
    t = tarjeta(man)
    assert "noaa-oisst" in t and "Dominio público" in t and "No es un sistema de alerta" in t


def test_el_espejo_incluye_el_manifiesto():
    assert "MANIFIESTO.json" in ARCHIVOS


def test_la_tarjeta_pone_la_leyenda_del_senamhi_aunque_no_este_en_el_manifiesto():
    t = tarjeta({}, publico=True)
    assert "Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología" in t
