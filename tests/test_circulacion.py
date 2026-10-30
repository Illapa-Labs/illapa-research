import numpy as np
import pandas as pd
import pytest

from illapa_research import circulacion as c


def test_soi_lee_columnas_pegadas_y_ignora_faltantes(tmp_path):
    texto = (
        "(STAND TAHITI - STAND DARWIN)  SEA LEVEL PRESS\n ANOMALY\n\nYEAR   JAN   FEB\n"
        "1951   2.5   1.5  -0.2  -0.5  -1.1   0.3  -1.7  -0.4  -1.8  -1.6  -1.3  -1.2\n"
        "(STAND TAHITI - STAND DARWIN)  SEA LEVEL PRESS\n STANDARDIZED    DATA\n\nYEAR   JAN   FEB\n"
        "2026   1.1   1.4   1.2  -0.6  -0.9  -1.4  -2.4  -1.1  -2.0-999.9-999.9-999.9\n"
    )
    f = tmp_path / "soi.txt"
    f.write_text(texto)
    s = c.cargar_soi(f)
    assert s[pd.Timestamp(2026, 1, 1)] == 1.1 and s[pd.Timestamp(2026, 9, 1)] == -2.0
    assert pd.Timestamp(2026, 10, 1) not in s.index
    assert pd.Timestamp(1951, 1, 1) not in s.index  # only the standardised table


def test_rmm_convierte_faltantes_en_nan(tmp_path):
    f = tmp_path / "rmm.txt"
    f.write_text(" cabecera\n year, month, day, RMM1, RMM2, phase, amplitude\n"
                 "  1974  6  1  1.6  1.2  5  2.0  WH\n  1974  6  2  1.0E36  1.0E36  999  1.0E36  WH\n")
    d = c.cargar_rmm(f)
    assert d.loc["1974-06-01", "rmm_amp"] == 2.0 and np.isnan(d.loc["1974-06-02", "rmm1"])


def test_con_circulacion_exige_desplazamiento_y_no_ve_el_futuro():
    idx = pd.date_range("2000-01-01", periods=6)
    C = pd.DataFrame({"x": np.arange(6.0)}, index=idx)
    X = pd.DataFrame({"a": 1.0}, index=idx)
    mask = np.ones(6, dtype=bool)
    out = c.con_circulacion(X, C, mask, desplazar=1)
    assert out["x_circ"].iloc[3] == 2.0 and np.isnan(out["x_circ"].iloc[0])
    with pytest.raises(ValueError):
        c.con_circulacion(X, C, mask, desplazar=0)
