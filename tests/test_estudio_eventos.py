from datetime import date

import numpy as np
import pandas as pd

from illapa_research.estudio_eventos import (
    diario,
    percentil_evento,
    puntaje,
    tasa_aciertos,
    temporada,
)


def serie():
    idx = pd.date_range("2001-01-01", "2003-12-31 23:00", freq="h")
    rng = np.random.default_rng(1)
    p = pd.Series(rng.exponential(0.05, len(idx)), index=idx)
    p.loc["2002-02-10 14:00"] = 30.0  # one extreme hour
    return pd.DataFrame({"precipitation": p, "soil_moisture_0_to_7cm": 0.3}, index=idx)


def test_el_dia_extremo_sale_en_el_percentil_mas_alto():
    d = diario(serie(), "x")
    temp = temporada(d, 2003)
    assert percentil_evento(d, temp, date(2002, 2, 10), "x_p1d") > 99


def test_antecedente_excluye_el_propio_dia():
    d = diario(serie(), "x")
    assert d.loc["2002-02-10", "x_p7d"] < 15  # the 30 mm fall on the day itself, not before
    assert d.loc["2002-02-11", "x_p7d"] > 30


def test_aciertos_y_alarmas_por_anio():
    d = diario(serie(), "x")
    temp = temporada(d, 2003)
    score = puntaje(temp, ["x_p1d"])
    aciertos, alarmas = tasa_aciertos(score, [date(2002, 2, 10)], 99)
    assert aciertos == 1
    assert 0 < alarmas < 10
