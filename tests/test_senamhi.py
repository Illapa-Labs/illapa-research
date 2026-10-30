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
    with pytest.raises(S.PideCredenciales):
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


def test_la_cita_lleva_la_leyenda_exacta_del_senamhi():
    assert S.LEYENDA in S.CITA and S.LEYENDA.startswith("Información recopilada y trabajada por el Servicio Nacional")


def test_senamhi_es_opt_in_y_no_entra_en_la_descarga_por_defecto():
    from illapa_research.fuentes import FUENTES
    from illapa_research.fuentes_opt_in import FUENTES_OPT_IN

    assert "senamhi" in FUENTES_OPT_IN and "senamhi" not in FUENTES


def test_senamhi_va_al_espejo_con_la_leyenda_en_la_tarjeta():
    from illapa_research.espejo_hf import ARCHIVOS, EXCLUIDAS_EN_PUBLICO, tarjeta

    assert ARCHIVOS["senamhi/tablas"] == "senamhi" and "senamhi" not in EXCLUIDAS_EN_PUBLICO
    man = {"senamhi": {"nombre": "SENAMHI", "licencia": "términos de uso", "atribucion": "SENAMHI", "descargado": "2026-10-30T00:00:00+00:00"}}
    t = tarjeta(man, publico=True)
    assert S.LEYENDA in t and "control de calidad" in t
    assert "comercializar" in t and "información oficial" in t


def test_la_tarjeta_sin_senamhi_no_lleva_su_leyenda():
    from illapa_research.espejo_hf import tarjeta

    man = {"noaa-oisst": {"nombre": "OISST", "licencia": "PD", "atribucion": "NOAA", "descargado": "2026-10-30T00:00:00+00:00"}}
    assert S.LEYENDA not in tarjeta(man, publico=True)


def test_lluvia_diaria_horaria_descarta_dias_incompletos():
    idx = pd.date_range("2020-01-01", periods=48, freq="h")
    s = pd.DataFrame({"N_LLUVIA": 1.0}, index=idx).iloc[:36]  # day 1 complete, day 2 has 12 hours
    d = S.lluvia_diaria_horaria(s, minimo_horas=20)
    assert d.iloc[0] == 24 and pd.isna(d.iloc[1])


def test_acuerdo_detecta_series_iguales_y_el_rezago():
    idx = pd.date_range("2020-01-01", periods=200, freq="D")
    import numpy as np

    x = pd.Series(np.random.default_rng(0).gamma(0.3, 5, 200), index=idx)
    perfecto = S.acuerdo(x, x)
    assert perfecto["pearson_log"] == pytest.approx(1.0) and perfecto["spearman"] == pytest.approx(1.0)
    assert S.acuerdo(x.shift(1), x, rezago=-1)["spearman"] > 0.99


def test_serie_diaria_de_avisos_toma_el_nivel_mas_alto_y_descarta_lluvia_solo_de_selva():
    av = pd.DataFrame({
        "fenomeno": ["PRECIPITACIONES EN SIERRA", "LLUVIA SELVA", "PP SIERRA Y COSTA NORTE", "INCREMENTO DE VIENTO"],
        "nivel_n": [2.0, 4.0, 3.0, 4.0],
        "fech_ini": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-01"]),
        "fech_fin": pd.to_datetime(["2020-01-03", "2020-01-03", "2020-01-02", "2020-01-03"]),
    })
    idx = pd.date_range("2020-01-01", "2020-01-04")
    s = S.serie_diaria_avisos(av, idx)
    assert list(s["nivel_max"]) == [2.0, 3.0, 2.0, 0.0] and list(s["aviso"]) == [True, True, True, False]


def test_alarma_por_umbral_usa_el_dia_o_los_tres_ultimos_dias():
    idx = pd.date_range("2020-01-01", periods=6)
    r = pd.Series([0, 0.5, 0.5, 0.5, 0, 3.0], index=idx)
    a = S.alarma_por_umbral(r, umbral=2.0, umb_acum=1.4, idx=idx)
    assert list(a.astype(bool)) == [False, False, False, True, False, True]


def test_centro_de_rango_y_dias_por_trimestre():
    from datetime import date

    assert S._centro_rango("60 - 120") == 90 and S._centro_rango("-120 - -60") == -90
    assert S._centro_rango(None) != S._centro_rango(None)  # NaN
    fechas = [date(2017, 1, 5), date(2017, 3, 20), date(2016, 12, 10), date(2017, 5, 1)]
    assert S.dias_huaico_por_trimestre(fechas, 2017, "DEF") == 2 and S.dias_huaico_por_trimestre(fechas, 2017, "FMA") == 1


def test_evalua_alarmas_cuenta_pod_y_falsas_alarmas_con_tolerancia():
    idx = pd.date_range("2020-01-01", periods=10)
    y = pd.Series([0, 0, 1, 0, 0, 0, 0, 0, 0, 0], index=idx)
    a = pd.Series([False, True, True, False, False, False, True, False, False, False], index=idx)
    m = pd.Series(True, index=idx)
    r = S.evalua_alarmas(a, y, m)
    assert r["POD"] == 1.0 and r["FAR_dias"] == pytest.approx(1 / 3)
