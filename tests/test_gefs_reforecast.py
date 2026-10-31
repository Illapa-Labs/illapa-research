from datetime import date

import numpy as np
import pandas as pd
import pytest

from illapa_research import gefs_backtest as B
from illapa_research import gefs_reforecast as G

IDX = """1:0:d=2017031600:APCP:surface:0-3 hour acc fcst:ENS=low-res ctl
2:458200:d=2017031600:APCP:surface:0-6 hour acc fcst:ENS=low-res ctl
3:1018782:d=2017031600:APCP:surface:6-9 hour acc fcst:ENS=low-res ctl
4:1459797:d=2017031600:APCP:surface:6-12 hour acc fcst:ENS=low-res ctl
5:1746065:d=2017031600:APCP:surface:12-15 hour acc fcst:ENS=low-res ctl
6:2202269:d=2017031600:APCP:surface:12-18 hour acc fcst:ENS=low-res ctl
7:2496711:d=2017031600:APCP:surface:18-21 hour acc fcst:ENS=low-res ctl
"""
IDX_CAPE = """1:0:d=2017031600:CAPE:surface:3 hour fcst:ENS=low-res ctl
2:444555:d=2017031600:CAPE:surface:6 hour fcst:ENS=low-res ctl
3:908762:d=2017031600:CAPE:surface:9 hour fcst:ENS=low-res ctl
"""


def test_leer_idx_y_ventanas_de_6_horas():
    msgs = G.leer_idx(IDX)
    assert len(msgs) == 7 and msgs[3].inicio == 1459797 and msgs[3].fin == 1746064
    v = G.ventanas_6h(msgs)
    assert [(m.h_ini, m.h_fin) for m in v] == [(6, 12), (12, 18)]  # 0-6 is not a "6 h window from 6", 3 h ones are dropped


def test_pasos_instantaneos():
    msgs = G.leer_idx(IDX_CAPE)
    assert [m.h_fin for m in G.pasos(msgs, (6, 9, 12))] == [6, 9]


def test_url_del_bucket():
    u = G.url_archivo(date(2017, 3, 16), "p02", "apcp_sfc")
    assert u.endswith("/2017/2017031600/p02/Days:1-10/apcp_sfc_2017031600_p02.grib2")


def test_celdas_de_la_caja_del_valle_son_cuatro():
    f, c = G.celdas_de_caja(G.LAT, G.LON, G.CAJAS["valle"])
    assert len(f) == 2 and len(c) == 2


def test_medias_por_caja_promedia_las_celdas_de_cada_caja():
    campo = np.zeros((721, 1440))
    f, c = G._CELDAS["chosica"]
    campo[np.ix_(f, c)] = 7.0
    m = G.medias_por_caja(campo)
    assert m["chosica"] == pytest.approx(7.0)
    assert m["ticlio"] == pytest.approx(0.0)


def test_corridas_necesarias_cubren_noviembre_29_hasta_abril_30():
    d = G.fechas_de_corridas(2000, 2001)
    assert d[0] == date(1999, 11, 29) and d[-1] == date(2001, 4, 30)
    assert len(G.fechas_de_corridas(2001, 2001)) == 153  # 2 + 31 + 31 + 28 + 31 + 30


def _corridas():
    filas = []
    for run in pd.to_datetime(["2000-01-10", "2000-01-11", "2000-01-12"]):
        for m in ("c00", "p01"):
            for h in range(6, 78, 6):
                filas.append({"run": run, "miembro": m, "variable": "apcp", "h_ini": h, "h_fin": h + 6,
                              "caja": "valle", "valor": 1.0 if m == "c00" else 3.0})
    return pd.DataFrame(filas)


def test_lluvia_por_dia_y_plazo_alinea_la_corrida_con_el_dia():
    ll = G.lluvia_por_dia_y_plazo(_corridas())
    # lead 1: run d, hours 6-30; lead 2: run d-1; lead 3: run d-2. Four 6 h windows each.
    d = pd.Timestamp("2000-01-12")
    for plazo in (1, 2, 3):
        x = ll[(ll["dia"] == d) & (ll["plazo"] == plazo) & (ll["miembro"] == "c00")]
        assert len(x) == 1 and x["mm"].iloc[0] == pytest.approx(4.0)
    # a run issued the same day (lead 1) never feeds an earlier day
    assert ll[(ll["plazo"] == 1)]["dia"].min() == pd.Timestamp("2000-01-10")
    assert ll[(ll["plazo"] == 3)]["dia"].min() == pd.Timestamp("2000-01-12")


def test_resumen_de_ensamble_tiene_media_maximo_y_probabilidades():
    ens = G.resumen_de_ensamble(G.lluvia_por_dia_y_plazo(_corridas()))
    fila = ens.loc[(pd.Timestamp("2000-01-12"), 1, "valle")]
    assert fila["media"] == pytest.approx(8.0) and fila["maximo"] == pytest.approx(12.0)
    assert fila["p_gt10"] == pytest.approx(0.5) and fila["miembros"] == 2


def test_cuantiles_conserva_el_orden_y_lleva_la_mediana_a_la_mediana():
    rng = np.random.default_rng(0)
    g = rng.gamma(2, 1.0, 500)
    o = rng.gamma(2, 3.0, 500)
    nuevos = np.sort(rng.gamma(2, 1.0, 50))
    m = B.cuantiles(g, o, nuevos)
    assert (np.diff(m) >= -1e-9).all()
    assert B.cuantiles(g, o, np.array([np.median(g)]))[0] == pytest.approx(np.median(o), rel=0.1)


def test_valor_costo_perdida_es_uno_con_pronostico_perfecto_y_cero_con_climatologia():
    y = np.array([0] * 90 + [1] * 10)
    perfecto = B.valor_costo_perdida(y, y.astype(float), razones=(0.2,))
    assert perfecto["valor"].iloc[0] == pytest.approx(1.0)
    clim = B.valor_costo_perdida(y, np.full(100, 0.1), razones=(0.2,))
    assert clim["valor"].iloc[0] == pytest.approx(0.0, abs=1e-9) or np.isnan(clim["valor"].iloc[0])


def test_metricas_y_ensamblado_de_pliegues_en_cpu():
    pytest.importorskip("torch")
    rng = np.random.default_rng(1)
    n, nt = 300, 60
    ts = np.repeat(np.arange(10), n // 10)
    X = rng.normal(size=(n + 2 * nt, 4))
    y = (X[:n, 0] + rng.normal(size=n) > 1.5).astype(float)
    P = B.ajustar_por_pliegue(X, y, ts, [0, 1], n, dispositivo="cpu")
    ts_t = np.array([0] * 30 + [1] * 30)
    pos = np.arange(60)
    out = B.ensamblar(P, [0, 1], ts_t, pos, n)
    assert set(out) == {"techo", "pp_qm", "pp_crudo"} and all(len(v) == 60 for v in out.values())
    m = B.metricas(y[:60], out["techo"], np.full(60, y.mean()))
    assert 0 <= m["auc"] <= 1 and "brier_skill" in m


def test_cargar_corridas_lee_el_archivo_unico_del_espejo(tmp_path):
    t = pd.DataFrame({"run": ["2000-01-01"], "miembro": ["c00"], "variable": ["apcp"], "h_ini": [6.0], "h_fin": [12],
                      "caja": ["valle"], "valor": [0.0]})
    t.to_csv(tmp_path / "gefs_corridas.csv.gz", index=False)
    c = G.cargar_corridas(tmp_path)
    assert len(c) == 1 and c["run"].iloc[0] == pd.Timestamp("2000-01-01")
    assert G.cargar_corridas(tmp_path / "vacio").empty
