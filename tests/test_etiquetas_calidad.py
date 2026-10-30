import numpy as np
import pandas as pd

from illapa_research import etiquetas_calidad as ec


def _fila(fecha, archivo, conf="media", q="Quirio", notas="", fuente="INDECI"):
    return {"fecha": fecha, "precision_fecha": "dia", "confianza": conf, "quebradas": q, "notas": notas,
            "fuente": fuente, "archivo": archivo}


def test_inundacion_solo_si_nunca_habla_de_huaico():
    assert ec.es_inundacion(_fila("1981-02-08", "a", q="(inundación)", notas="Inundación en Chosica"))
    assert not ec.es_inundacion(_fila("1983-03-22", "a", q="Cashahuacra", notas="desborde del Rímac"))
    assert not ec.es_inundacion(_fila("1983-03-22", "a", notas="Cashahuacra a las 16:45 con desborde del Rímac"))
    assert not ec.es_inundacion(_fila("2017-03-18", "a", notas="Huaico y desborde"))


def test_tabla_fechas_cuenta_archivos_y_tipos_de_fuente():
    filas = [
        _fila("2015-03-23", "a.csv", fuente="INDECI; El Comercio"),
        _fila("2015-03-23", "b.csv", fuente="IGP 2023; RPP", conf="alta"),
        _fila("2015-03-24", "a.csv", q="(inundación)", notas="Inundación", fuente="Valverde"),
        {**_fila("2015-03-25", "a.csv"), "confianza": "baja"},
        {**_fila("2015-03-26", "a.csv"), "precision_fecha": "mes"},
    ]
    t = ec.tabla_fechas(filas)
    assert list(t.index.strftime("%Y-%m-%d")) == ["2015-03-23", "2015-03-24"]
    a = t.loc["2015-03-23"]
    assert a["n_archivos"] == 2 and a["n_tipos_fuente"] == 4 and a["confianza_alta"]
    assert t.loc["2015-03-24", "solo_inundacion"] and not a["solo_inundacion"]


def test_etiquetas_alternativas_son_subconjuntos_o_ampliaciones_de_la_base():
    t = pd.DataFrame(
        {"n_archivos": [1, 2, 1], "confianza_alta": [False, False, True], "n_tipos_fuente": [1, 3, 0],
         "n_quebradas": [0, 2, 1], "solo_inundacion": [True, False, False],
         "menciona_inundacion": [True, False, False]},
        index=pd.to_datetime(["2015-03-01", "2015-03-10", "2015-03-20"]),
    )
    idx = pd.date_range("2015-02-25", "2015-03-25")
    L = ec.etiquetas_alternativas(t, idx)
    assert L["base"].sum() == 3 and L["A_corroborada"].sum() == 2 and L["B_severa"].sum() == 1
    assert L["C_prensa"].sum() == 1 and L["D_ampliada"].sum() == 6
    assert L["E_sin_inundacion"].sum() == 2 and L["E2_sin_mencion_inundacion"].sum() == 2
    assert (L["A_corroborada"] <= L["base"]).all() and (L["base"] <= L["D_ampliada"]).all()


def test_era_y_severidad():
    assert list(ec.era_de(np.array([1990, 2000, 2015]))) == ["1984-1998", "1999-2008", "2009-2026"]
    t = pd.DataFrame(index=pd.to_datetime(["2017-03-01", "2017-03-02"]))
    act = pd.DataFrame({"fecha": pd.to_datetime(["2017-03-01", "2017-03-01", "2017-03-01"]),
                        "slug": ["a", "b", "z"]})
    assert list(ec.agregar_severidad(t, act, {"a", "b"})["n_quebradas"]) == [2, 0]


def test_falsos_positivos_ignora_dias_cercanos_a_un_evento_y_agrupa():
    idx = pd.date_range("2000-01-01", periods=30)
    p = pd.Series(0.01, index=idx)
    p.iloc[5], p.iloc[6], p.iloc[20], p.iloc[12] = 0.9, 0.8, 0.5, 0.95
    y = pd.Series(0, index=idx)
    y.iloc[12] = 1  # the 0.95 day is a real event, so it is not a false positive
    fp = ec.falsos_positivos(p, y, k=2)
    assert list(fp.index) == [idx[5], idx[20]]


def test_metricas_sobre_da_lift_mayor_que_uno_si_el_modelo_ordena_bien():
    rng = np.random.default_rng(0)
    ts = np.repeat(np.arange(20), 50)
    y = (rng.uniform(size=1000) < 0.05).astype(int)
    p = np.where(y == 1, 0.6, 0.04) + rng.uniform(0, 0.02, 1000)
    m = ec.metricas_sobre(y, p, np.full(1000, y.mean()), ts, n=30)
    assert m["lift"] > 5 and m["ap_p5"] <= m["ap"] <= m["ap_p95"] + 1e-9 and m["eventos"] == int(y.sum())
