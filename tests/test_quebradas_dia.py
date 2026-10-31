import numpy as np
import pandas as pd

from illapa_research import quebradas_dia as QD


def _datos():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2001-01-01", periods=300)
    ts = pd.Series(np.repeat(np.arange(2001, 2011), 30), index=idx)
    p = pd.Series(rng.uniform(0.001, 0.2, len(idx)), index=idx)
    filas = []
    for i, d in enumerate(idx):
        if rng.random() < p.iloc[i]:
            filas.append({"fecha": d, "slug": "a" if rng.random() < 0.7 else "b", "temporada": int(ts.iloc[i])})
    act = pd.DataFrame(filas)
    t = pd.DataFrame({"nino": [s % 2 == 0 for s in range(2001, 2011)]}, index=pd.Index(range(2001, 2011)))
    return p, act, ["a", "b", "c"], t, ts


def test_pares_tiene_un_puntaje_por_modelo_y_par():
    p, act, ub, t, ts = _datos()
    d = QD.pares(p, act, ub, t, ts)
    assert len(d) == len(p) * 3 and set(QD.MODELOS) <= set(d.columns)
    assert ((d[list(QD.MODELOS)] > 0) & (d[list(QD.MODELOS)] < 1)).all().all()


def test_metricas_y_diferencia_con_intervalo():
    p, act, ub, t, ts = _datos()
    d = QD.pares(p, act, ub, t, ts)
    m = QD.metricas(d)
    assert set(m["modelo"]) == set(QD.MODELOS) and (m["auc"] > 0.4).all()
    r = QD.diferencia_ap(d[d["temporada"] != 2005], "producto", "solo_dia", n=50)
    assert r["p5"] <= r["p95"]


def test_cobertura_top_k_usa_la_participacion_de_otras_temporadas():
    p, act, ub, t, ts = _datos()
    d = QD.pares(p, act, ub, t, ts)
    c = QD.cobertura_top_k(d, k=1)
    assert c["quebradas"] == 3 and abs(c["al_azar"] - 1 / 3) < 1e-9 and 0 <= c["cobertura"] <= 1
