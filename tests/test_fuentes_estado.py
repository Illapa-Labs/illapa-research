import json
from datetime import date

import pandas as pd
import pytest

from illapa_research import fuentes_estado as FE


class _Falso(FE.ClienteEstado):
    """Client that answers from a dict instead of the network."""

    def __init__(self, tmp_path, respuestas):
        super().__init__(tmp_path, pausa=0)
        self.respuestas = respuestas

    def get(self, url, params=None, cache=None, **kw):
        r = pytest.importorskip("requests").Response()
        r.status_code = 200
        r._content = self.respuestas[url] if isinstance(self.respuestas[url], bytes) else json.dumps(self.respuestas[url]).encode()
        return r


def test_arcgis_json_se_detiene_ante_un_token(tmp_path):
    c = _Falso(tmp_path, {"u": {"error": {"code": 499, "message": "Token Required"}}})
    with pytest.raises(PermissionError):
        FE.arcgis_json(c, "u")


def test_arcgis_consulta_pide_ids_y_luego_por_lotes(tmp_path):
    base = f"{FE.INGEMMET}/SERV/MapServer/0/query"
    c = _Falso(tmp_path, {base: {"objectIds": [1, 2, 3], "features": [{"attributes": {"a": 1}, "geometry": {"x": -76.7, "y": -11.9}}]}})
    f = FE.arcgis_consulta(c, "SERV", 0, lote=2)
    assert len(f) == 2  # two batches of ids, one fake feature each
    g = FE.a_geojson(f)
    assert g["features"][0]["geometry"]["coordinates"] == [-76.7, -11.9]


def test_fecha_arcgis_acepta_milisegundos_y_texto():
    assert FE.fecha_arcgis(1049173200000) == "2003-04-01"
    assert FE.fecha_arcgis("25/02/2019") == "2019-02-25"
    assert FE.fecha_arcgis(None) is None


def test_ambito_sigrid_lee_los_poligonos_de_la_pagina(tmp_path):
    html = b"<script>wkt='POLYGON((-76.7 -11.9,-76.6 -11.9,-76.6 -11.8,-76.7 -11.9))';</script>"
    c = _Falso(tmp_path, {f"{FE.SIGRID}/documento/7": html})
    assert FE.ambito_sigrid(c, 7)[0].startswith("POLYGON((-76.7 -11.9")


def _cuencas():
    def cuadro(x0, y0, x1, y1):
        return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}

    return {"features": [
        {"geometry": cuadro(-76.80, -11.99, -76.70, -11.90), "properties": {"slug": "grande", "area_km2": 50.0}},
        {"geometry": cuadro(-76.75, -11.95, -76.72, -11.92), "properties": {"slug": "chica", "area_km2": 2.0}},
    ]}


def test_indice_de_cuencas_prefiere_la_mas_pequena_que_contiene_el_punto():
    i = FE.IndiceCuencas(_cuencas())
    assert i.de_punto(-76.735, -11.935) == ("chica", True, 0.0)
    assert i.de_punto(-76.78, -11.97)[:2] == ("grande", True)
    assert i.de_punto(-76.0, -11.0)[0] is None


def _sinpad():
    return pd.DataFrame({
        "codigoSinpad": [1, 2, 3, 4],
        "peligroPrincipal": ["HUAICO", "HUAICO", "LLUVIAS INTENSAS", "INCENDIOS URBANOS"],
        "fechaHoraEvento": ["19/02/2025 09:17", "12/02/2025 18:41", "08/02/2024 05:30", "01/01/2024 10:00"],
        "nivel": [1, 1, 1, 1], "distrito": ["CALLAHUANCA", "CALLAHUANCA", "CHACLACAYO", "ATE"],
    })


def test_emergencias_de_lluvia_filtra_incendios_y_pone_fecha_iso():
    e = FE.emergencias_de_lluvia(_sinpad())
    assert list(e["fecha"]) == ["2024-02-08", "2025-02-12", "2025-02-19"]


def test_huaicos_sinpad_nuevos_omite_los_dias_ya_catalogados():
    nuevos = FE.huaicos_sinpad_nuevos(_sinpad(), {date(2025, 2, 12)})
    assert list(nuevos["fecha"]) == ["2025-02-19"]
    assert nuevos.loc[0, "confianza"] == "alta" and "SINPAD" in nuevos.loc[0, "fuente"]
    assert list(nuevos.columns) == ["fecha", "precision_fecha", "hora_local", "distrito", "quebradas", "fuente", "confianza", "notas"]


def test_comparar_priorizadas_une_los_nombres_oficiales_con_nuestro_rango():
    refs = [{"nombre": "Quirio", "alias": ("Quiro",), "cuenca_slug": "", "lon": -76.7, "lat": -11.9},
            {"nombre": "Corrales", "alias": ("Rayito de Sol",), "cuenca_slug": "", "lon": None, "lat": None}]
    rk = pd.DataFrame({"slug": ["quirio", "corrales"], "rango_mediano": [3.0, 9.0], "p_top5": [0.8, 0.2]})
    out = FE.comparar_priorizadas(refs, rk)
    q = out[(out.entidad == "ANIN") & (out.quebrada_oficial == "Quirio")].iloc[0]
    assert q["rango_mediano"] == 3.0
    r = out[(out.entidad == "ANIN") & (out.quebrada_oficial == "Rayito de Sol")].iloc[0]
    assert r["slug"] == "corrales" and r["rango_mediano"] == 9.0


def test_geoquebradas_historico_pagina_por_offset(tmp_path):
    pag1 = {"features": [{"attributes": {"fecha": 1769904000000, "nivel": 3}}, {"attributes": {"fecha": 1769990400000, "nivel": 2}}],
            "exceededTransferLimit": True}
    pag2 = {"features": [{"attributes": {"fecha": 1770076800000, "nivel": 1}}]}

    class Pagina(FE.ClienteEstado):
        def __init__(self):
            super().__init__(tmp_path, pausa=0)
            self.pedidos = []

        def get(self, url, params=None, cache=None, **kw):
            self.pedidos.append(params["resultOffset"])
            r = pytest.importorskip("requests").Response()
            r.status_code = 200
            r._content = json.dumps(pag1 if params["resultOffset"] == 0 else pag2).encode()
            return r

    c = Pagina()
    filas = FE.geoquebradas_historico(c, "nombdep='LIMA'", pagina=2)
    assert [f["nivel"] for f in filas] == [3, 2, 1] and c.pedidos == [0, 2]
    assert FE.fecha_arcgis(filas[0]["fecha"]) == "2026-02-01"


def test_geoquebradas_resumen_agrupa_por_dia_y_provincia():
    filas = [{"fecha": 1769904000000, "nombprov": "A", "nivel": 3, "pob_exp": 10.4, "nombdist": "X"},
             {"fecha": 1769904000000, "nombprov": "A", "nivel": 1, "pob_exp": 2.0, "nombdist": "Y"},
             {"fecha": 1769904000000, "nombprov": "B", "nivel": 2, "pob_exp": 0.0, "nombdist": "Z"}]
    r = FE.geoquebradas_resumen(filas).set_index("nombprov")
    assert r.loc["A", "avisos"] == 2 and r.loc["A", "nivel_max"] == 3 and r.loc["A", "distritos"] == 2
    assert r.loc["A", "pob_exp_max"] == 10 and r.loc["B", "fecha"] == "2026-02-01"
