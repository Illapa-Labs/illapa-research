from datetime import UTC, datetime

import numpy as np
import pandas as pd

from illapa_research import era5_alterno as ea


def test_indice_de_celda_coincide_con_la_malla_de_open_meteo():
    # Matucana sits at row 313, column 414 of the 0.25 degree grid (checked against the API values)
    assert ea.indice_celda(-11.84, -76.38) == (313, 414)
    assert ea.indice_celda(-11.84, -76.38, "land")[0] == round((-11.84 + 90) / 0.1)


def test_archivo_de_usa_year_hasta_2021_y_chunks_despues():
    assert ea.archivo_de(datetime(1983, 1, 1, 5, tzinfo=UTC)) == ("year_1983.om", 0, 5)
    nombre, _, k = ea.archivo_de(datetime(2021, 12, 31, 23, tzinfo=UTC))
    assert nombre == "year_2021.om" and k == 8759
    nombre, primera, k = ea.archivo_de(datetime(2022, 1, 1, tzinfo=UTC))
    assert nombre.startswith("chunk_") and 0 <= k < 504
    assert primera + k == int((datetime(2022, 1, 1, tzinfo=UTC) - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() // 3600)


def test_segmentos_cubren_todas_las_horas_sin_huecos_ni_solapes():
    ini, fin = datetime(2021, 12, 20, tzinfo=UTC), datetime(2022, 2, 3, 12, tzinfo=UTC)
    total = 0
    for nombre, a, b, h0 in ea.segmentos(ini, fin):
        total += b - a
        assert b > a and (nombre.startswith("year_") or b <= 504)
    assert total == int((fin - ini).total_seconds() // 3600) + 1


def test_correccion_de_altura_enfria_al_subir_el_punto():
    s = pd.Series([10.0, 12.0])
    assert ea.corregir_altura(s, 1000.0, 1500.0, 0.0065).iloc[0] == 10.0 - 3.25  # point above the cell
    assert ea.corregir_altura(s, 1500.0, 1000.0, 0.0065).iloc[0] == 10.0 + 3.25


def test_humedad_y_deficit_de_presion_de_vapor():
    t, td = np.array([20.0, 20.0]), np.array([20.0, 10.0])
    rh = ea.humedad_relativa(t, td)
    assert rh[0] == 100.0 and 45 < rh[1] < 55
    d = ea.deficit_presion_vapor_kpa(t, td)
    assert d[0] == 0.0 and 1.0 < d[1] < 1.4  # ~2.3 kPa saturation - ~1.2 kPa actual


def test_escribir_cache_tiene_el_formato_de_open_meteo(tmp_path):
    idx = pd.date_range("1999-12-31 22:00", periods=6, freq="h")
    df = pd.DataFrame({"temperature_2m": np.arange(6.0), "dew_point_2m": np.arange(6.0) - 2}, index=idx)
    rutas = ea.escribir_cache(df, "punto", 1234.0, tmp_path, "2026-10-30")
    import json

    a = json.loads(rutas[0].read_text())
    b = json.loads(rutas[1].read_text())
    assert a["elevation"] == 1234.0 and a["hourly"]["time"][-1] == "1999-12-31T23:00"
    assert b["hourly"]["time"][0] == "2000-01-01T00:00" and set(b["hourly"]) == {"time", "temperature_2m", "dew_point_2m"}


def test_el_corte_entre_year_y_chunk_puede_variar_por_variable():
    # cloud cover has year files up to 2023: January 2023 is still a year file there
    assert ea.archivo_de(datetime(2023, 1, 1, tzinfo=UTC), 2023)[0] == "year_2023.om"
    assert ea.archivo_de(datetime(2023, 1, 1, tzinfo=UTC), 2021)[0].startswith("chunk_")
    segs = ea.segmentos(datetime(2023, 12, 20, tzinfo=UTC), datetime(2024, 1, 10, tzinfo=UTC), 2023)
    assert segs[0][0] == "year_2023.om" and segs[-1][0].startswith("chunk_")
    assert sum(b - a for _, a, b, _ in segs) == 22 * 24 + 1
