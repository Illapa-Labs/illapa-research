import json

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

from illapa_research import chirps_malla as C


def _tif(ruta, oeste=-78.0, norte=-11.0, ancho=60, alto=50):
    """A small CHIRPS-like GeoTIFF: 0.05° cells, value = 100*row + col, sea (-9999) in the first column."""
    v = (100 * np.arange(alto)[:, None] + np.arange(ancho)[None, :]).astype("float32")
    v[:, 0] = -9999
    with rasterio.open(ruta, "w", driver="GTiff", width=ancho, height=alto, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(oeste, norte, 0.05, 0.05)) as d:
        d.write(v, 1)
    return v


def test_ventana_da_celdas_enteras_y_siempre_la_misma_forma():
    assert C.ventana((-77.4, -12.9, -75.6, -11.3)) == (2052, 1426, 36, 32)
    # a box that does not fall on cell edges still covers whole cells
    _, _, w, h = C.ventana((-77.41, -12.91, -75.59, -11.29))
    assert (w, h) == (38, 34)


def test_cajas_de_las_zonas_con_margen(tmp_path):
    ruta = tmp_path / "z.json"
    ruta.write_text(json.dumps({"zonas": [{"id": "a", "west": -77.2, "north": -11.5, "step": 0.1, "cols": 14, "rows": 12}]}))
    assert C.cajas_zonas(ruta) == {"a": (-77.4, -12.9, -75.6, -11.3)}


def test_leer_coincide_con_una_lectura_directa_y_marca_el_mar(tmp_path):
    v = _tif(tmp_path / "d.tif")
    caja = (-77.9, -13.0, -77.5, -11.6)
    with rasterio.open(tmp_path / "d.tif") as src:
        a = C.leer(src, {"z": caja})["z"]
        b = src.read(1, window=from_bounds(*caja, src.transform))
    assert a.shape == b.shape
    assert np.array_equal(np.nan_to_num(a, nan=-9999), b)
    c0, r0, _, _ = C.ventana(caja, -78.0, -11.0)
    assert c0 == 2 and r0 == 12 and np.isnan(C.leer(rasterio.open(tmp_path / "d.tif"), {"z": (-78.0, -13.0, -77.9, -11.6)})["z"][:, 0]).all()
    assert v[12, 2] == a[0, 0]


def test_coordenadas_son_centros_de_celda():
    lat, lon = C.coordenadas((-77.4, -12.9, -75.6, -11.3))
    assert lat[0] == pytest.approx(-11.325) and lon[0] == pytest.approx(-77.375)
    assert len(lat) == 32 and len(lon) == 36 and np.all(np.diff(lat) < 0)


def test_descargar_cachea_meses_completos_y_para_en_el_que_falta(tmp_path, monkeypatch):
    zonas = tmp_path / "z.json"
    zonas.write_text(json.dumps({"zonas": [{"id": "a", "west": -77.2, "north": -11.5, "step": 0.1, "cols": 2, "rows": 2}]}))
    cajas = C.cajas_zonas(zonas)
    forma = C.ventana(cajas["a"])[2:][::-1]
    publicado_hasta = pd.Timestamp("2024-02-10")

    def falso(fecha, cajas_, producto="rnl"):
        if fecha > publicado_hasta:
            return None
        return {"a": np.full(forma, float(fecha.day), dtype="float32")}

    monkeypatch.setattr(C, "leer_dia", falso)
    rutas = C.descargar(tmp_path / "m", desde="2024-01-01", hasta="2024-03-31", hilos=2, zonas=zonas)
    assert (tmp_path / "m" / "cache" / "rnl_2024_01.npz").exists()
    assert not (tmp_path / "m" / "cache" / "rnl_2024_02.npz").exists()  # partial month is not cached as complete
    import xarray as xr

    ds = xr.open_dataset(rutas[0])
    assert ds.sizes["time"] == 31 + 10 and ds["precip"].isel(time=-1).mean() == 10
    assert pd.Timestamp(ds.time.values[-1]) == publicado_hasta


def test_media_de_caja_y_pentadas():
    import xarray as xr

    t = pd.date_range("2024-01-01", "2024-01-31")
    da = xr.DataArray(np.ones((31, 4, 4)), coords={"time": t, "lat": [-11.325, -11.375, -11.425, -11.475],
                                                   "lon": [-77.375, -77.325, -77.275, -77.225]}, dims=("time", "lat", "lon"))
    assert np.allclose(C.media_caja(da, (-77.35, -11.45, -77.25, -11.35)), 1)
    p = C.pentadas(da)
    assert p.sizes["pentada"] == 6  # 6 pentads in January
    assert float(p.isel(pentada=0).mean()) == 5 and float(p.isel(pentada=5).mean()) == 6  # days 26-31
