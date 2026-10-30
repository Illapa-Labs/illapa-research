import numpy as np
import pandas as pd
import pytest

from illapa_research import lluvia_satelital as L
from illapa_research.fuentes import FUENTES, NO_POR_DEFECTO


def test_celda_mas_cercana_en_malla_regular():
    lon = np.arange(0.125, 360, 0.25)
    assert lon[L.celda_mas_cercana(lon, L.lon360(-76.70))] == pytest.approx(283.375)
    lat = np.arange(59.875, -60, -0.25)
    assert lat[L.celda_mas_cercana(lat, -11.93)] == pytest.approx(-11.875)


def test_extraer_persiann_lee_el_orden_lon_lat_y_los_rellenos():
    netCDF4 = pytest.importorskip("netCDF4")
    lat = np.arange(59.875, -60, -0.25)
    lon = np.arange(0.125, 360, 0.25)
    ds = netCDF4.Dataset("m.nc", mode="w", memory=1)
    ds.createDimension("time", 1)
    ds.createDimension("lon", len(lon))
    ds.createDimension("lat", len(lat))
    ds.createVariable("lat", "f4", ("lat",))[:] = lat
    ds.createVariable("lon", "f4", ("lon",))[:] = lon
    v = ds.createVariable("precipitation", "f4", ("time", "lon", "lat"), fill_value=-9999.0)
    campo = np.zeros((1, len(lon), len(lat)), dtype="f4")
    i = L.celda_mas_cercana(lon, L.lon360(-76.70))
    j = L.celda_mas_cercana(lat, -11.93)
    campo[0, i, j] = 12.5
    v[:] = campo
    contenido = ds.close()
    assert contenido is not None
    out = L.extraer_persiann(bytes(contenido))
    assert out["chosica"] == pytest.approx(12.5) and out["ticlio"] == pytest.approx(0.0)


def test_variables_suma_3_dias_y_7_previos():
    idx = pd.date_range("2020-02-01", periods=12)
    lluvia = pd.DataFrame({"chosica": np.arange(12, dtype=float)}, index=idx)
    v = L.variables(lluvia, idx, "psc")
    assert v.loc["2020-02-05", "psc_chosica_3d"] == 2 + 3 + 4
    assert v.loc["2020-02-10", "psc_chosica_7d_previa"] == sum(range(2, 9))


def test_fuentes_nuevas_son_opt_in_y_tienen_licencia():
    assert {"cpc-lluvia", "persiann-cdr"} <= set(FUENTES)
    assert {"chirps-v3", "persiann-cdr"} <= NO_POR_DEFECTO
    for i in ("cpc-lluvia", "persiann-cdr"):
        assert FUENTES[i].licencia and FUENTES[i].atribucion
