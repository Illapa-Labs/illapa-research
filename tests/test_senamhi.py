import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from illapa_research import senamhi as S

FIX = Path(__file__).parent / "fixtures" / "senamhi_estaciones_muestra.json"


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._p = status, payload or {"status": True, "data": []}

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            e = requests.HTTPError(str(self.status_code))
            e.response = self
            raise e


@pytest.fixture()
def cliente(tmp_path):
    return S.Cliente(tmp_path, pausa=0)


def test_catalogo_y_estaciones_cercanas(cliente, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(payload=json.loads(FIX.read_text())))
    est = cliente.estaciones()
    cerca = S.cercanas(est, -76.70, -11.93, 40)
    assert list(cerca["name"][:2]) == ["CHOSICA", "CHOSICA"] and "LEJOS" not in set(cerca["name"])
    assert set(S.cercanas(est, -76.70, -11.93, 40, tipo="H")["stationId"]) == {"47278214"}


def test_la_cache_evita_repetir_la_llamada(cliente, monkeypatch):
    llamadas = []

    def falso(*a, **k):
        llamadas.append(a)
        return _Resp(payload={"status": True, "data": [{"id": "202610", "label": "10/2026"}]})

    monkeypatch.setattr(requests, "get", falso)
    assert cliente.periodos("111060") == ["202610"]
    assert cliente.periodos("111060") == ["202610"]
    assert len(llamadas) == 1


def test_un_endpoint_con_credenciales_detiene_el_cliente(cliente, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(status=401))
    with pytest.raises(S.AccesoRestringido):
        cliente.get("algo/privado")


def test_estacion_sin_serie_publicada_da_lista_vacia(cliente, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(status=422))
    assert cliente.periodos("212603") == []


def test_lecturas_de_estacion_automatica_leen_fecha_dia_primero(cliente, monkeypatch):
    payload = {"status": True, "data": {"readings": [
        {"date": "01/09/2026", "time": "00:00", "values": [{"column": "N_LLUVIA", "value": 0.0}]},
        {"date": "01/09/2026", "time": "01:00", "values": [{"column": "N_LLUVIA", "value": 1.2}]},
    ]}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(payload=payload))
    s = cliente.serie("111290", ["202609"])
    assert list(s.index[:2]) == [pd.Timestamp("2026-09-01 00:00"), pd.Timestamp("2026-09-01 01:00")]
    assert s["N_LLUVIA"].sum() == pytest.approx(1.2)


def test_completitud_cuenta_dias_con_valor():
    s = pd.Series([1.0, None, 2.0], index=pd.to_datetime(["2000-01-01", "2000-01-02", "2000-01-04"]))
    assert S.completitud(s, "2000-01-01", "2000-01-04") == pytest.approx(0.5)


def test_la_cita_nombra_al_senamhi():
    assert "SENAMHI" in S.CITA and "Información recopilada y trabajada" in S.CITA


def test_senamhi_es_opt_in_y_no_entra_en_la_descarga_por_defecto():
    from illapa_research.fuentes import FUENTES
    from illapa_research.fuentes_restringidas import FUENTES_OPT_IN

    assert "senamhi" in FUENTES_OPT_IN and "senamhi" not in FUENTES


def test_senamhi_no_esta_en_el_espejo_de_huggingface():
    from illapa_research.espejo_hf import ARCHIVOS

    assert not any("senamhi" in k or "senamhi" in v for k, v in ARCHIVOS.items())
