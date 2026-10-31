import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from illapa_research import pronostico_probabilidad as PP


def _json_sintetico(tmp_path, lead_col="precipitation", horas=72, valor=1.0):
    t = pd.date_range("2023-02-01", periods=horas, freq="h")
    punto = {"hourly": {"time": [x.strftime("%Y-%m-%dT%H:%M") for x in t], lead_col: [valor] * horas}}
    ruta = tmp_path / "m_2023.json"
    ruta.write_text(json.dumps([punto] * 6), encoding="utf-8")
    return ruta


def test_serie_lead_suma_el_dia_de_lluvia_de_24_horas(tmp_path):
    s = PP.serie_lead([_json_sintetico(tmp_path)], 0)
    completos = s.dropna()
    assert len(completos) >= 1 and np.allclose(completos, 24.0)  # 24 h x 1 mm


def test_serie_lead_usa_la_columna_del_lead(tmp_path):
    ruta = _json_sintetico(tmp_path, lead_col="precipitation_previous_day2", valor=2.0)
    assert np.allclose(PP.serie_lead([ruta], 2).dropna(), 48.0)


def _datos(n=2500, semilla=0):
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2000-01-01", periods=n, freq="D")
    F = pd.DataFrame({"suelo": rng.normal(size=n), "caudal": rng.normal(size=n), "icen_3m_previos": rng.normal(size=n)}, index=idx)
    pisco = pd.Series(rng.gamma(0.4, 3.0, n), index=idx)
    return F, pisco


def test_entradas_no_ven_nada_posterior_a_la_emision():
    F, pisco = _datos()
    lead = 2
    X = PP.entradas(F, pisco, pisco, lead)
    dia = pd.Timestamp("2005-02-10")
    fila = X.loc[dia].copy()
    F2, p2 = F.copy(), pisco.copy()
    emision = dia - pd.Timedelta(days=lead)
    F2.loc[emision:, ["suelo", "caudal"]] = 999.0  # change everything from the issue day on
    p2.loc[emision:] = 999.0
    # forecast rain of the day is allowed to differ, so keep it from the original series
    X2 = PP.entradas(F2, pisco.where(pisco.index <= dia, pisco), p2, lead)
    cambiadas = [c for c in fila.index if not np.isclose(fila[c], X2.loc[dia, c], equal_nan=True)]
    assert cambiadas == []  # antecedent features and PISCOp antecedents ignore the issue day onward


def test_ajustar_pp_y_probabilidad_son_coherentes():
    F, pisco = _datos()
    y = (pisco.rolling(3).sum().fillna(0) > pisco.rolling(3).sum().quantile(0.97)).astype(int)
    X = PP.entradas(F, pisco, pisco, 0)
    ok = X.dropna(how="all").index
    m = PP.ajustar_pp(X.loc[ok], y.loc[ok], 0)
    p = m.probabilidad(X.loc[ok])
    assert ((p > 0) & (p < 1)).all() and p[y.loc[ok] == 1].mean() > p[y.loc[ok] == 0].mean()


def test_probabilidad_desde_pronostico_ignora_el_futuro_y_exige_pronostico():
    F, pisco = _datos()
    y = (pisco.rolling(3).sum().fillna(0) > pisco.rolling(3).sum().quantile(0.97)).astype(int)
    X = PP.entradas(F, pisco, pisco, 1)
    ok = X.dropna(how="all").index
    m = PP.ajustar_pp(X.loc[ok], y.loc[ok], 1)
    emision = date(2005, 3, 1)
    objetivo = pd.Timestamp(emision) + pd.Timedelta(days=1)
    pron = pisco.copy()
    a = PP.probabilidad_desde_pronostico(emision, 1, pron, F, m, pisco)
    F2 = F.copy()
    F2.loc[pd.Timestamp(emision):, :] = 1e6  # future observations must not matter
    b = PP.probabilidad_desde_pronostico(emision, 1, pron, F2, m, pisco.copy())
    assert a["probabilidad"] == pytest.approx(b["probabilidad"]) and a["dia_objetivo"] == objetivo.date()
    assert "no es una alerta" in a["aviso"]
    with pytest.raises(ValueError):
        PP.probabilidad_desde_pronostico(emision, 1, pron.iloc[:0], F, m, pisco)


def test_nula_y_bootstrap_dan_valores_razonables():
    rng = np.random.default_rng(1)
    n = 300
    y = np.zeros(n); y[[40, 41, 120, 200, 250]] = 1
    p = np.clip(rng.random(n) * 0.1 + 0.6 * y, 0, 1)
    temporada = np.repeat([1, 2, 3], 100)
    r = PP.nula_desplazada(y, p, temporada, n=200, dispositivo="cpu")
    assert r["ap_real"] > r["ap_nula_p95"] and 0 < r["p"] <= 1
    b = PP.bootstrap_bloques(y, p, p * 0 + 0.1, bloque=10, n=200)
    assert b["ap_a"][0] <= b["ap_a"][1] and "ap_diferencia" in b


def test_corregir_fuera_de_temporada_reduce_el_sesgo():
    idx = pd.date_range("2022-12-01", "2025-04-30", freq="D")
    rng = np.random.default_rng(3)
    obs = pd.Series(rng.gamma(0.3, 3.0, len(idx)), index=idx)
    mod = obs * 2.5
    cor = PP.corregir_fuera_de_temporada(mod, obs)
    en_t = cor.dropna()
    assert en_t.mean() < mod.loc[en_t.index].mean() and abs(en_t.mean() / obs.loc[en_t.index].mean() - 1) < 0.2
