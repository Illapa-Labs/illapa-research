import json

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

from illapa_research import chirps_malla as C


def _tif(ruta, oeste=-78.0, norte=-11.0, ancho=60, alto=50, res=0.05):
    """A small CHIRPS-like GeoTIFF: 0.05° cells, value = 100*row + col, sea (-9999) in the first column."""
    v = (100 * np.arange(alto)[:, None] + np.arange(ancho)[None, :]).astype("float32")
    v[:, 0] = -9999
    with rasterio.open(ruta, "w", driver="GTiff", width=ancho, height=alto, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(oeste, norte, res, res)) as d:
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


def test_la_resolucion_en_float32_del_servidor_no_cambia_la_forma(tmp_path):
    # CHIRPS v3 files store 0.05000000074505806; the window must still match `coordenadas`
    _tif(tmp_path / "f32.tif", oeste=-78.0, norte=-11.0, ancho=60, alto=50, res=0.05000000074505806)
    caja = (-77.9, -13.0, -77.5, -11.6)
    with rasterio.open(tmp_path / "f32.tif") as src:
        a = C.leer(src, {"z": caja})["z"]
    lat, lon = C.coordenadas(caja, -78.0, -11.0)
    assert a.shape == (len(lat), len(lon))


def test_comparar_encuentra_el_rezago_y_la_razon():
    idx = pd.date_range("2000-01-01", "2003-12-31")
    rng = np.random.default_rng(0)
    obs = pd.Series(rng.gamma(0.5, 4, len(idx)), index=idx)
    chirps = 2 * obs.shift(-1)  # CHIRPS a day early and twice as wet
    r = C.comparar(chirps, obs)
    assert r["r_diaria_rezago+1"] > 0.99 and r["r_diaria_rezago+0"] < 0.3
    assert r["razon_medias"] == pytest.approx(2, rel=0.05) and r["r_mensual"] > 0.9


def test_serie_punto_toma_la_celda_que_contiene_la_estacion():
    import xarray as xr

    t = pd.date_range("2024-01-01", periods=3)
    v = np.arange(3 * 2 * 2, dtype=float).reshape(3, 2, 2)
    da = xr.DataArray(v, coords={"time": t, "lat": [-11.325, -11.375], "lon": [-77.375, -77.325]}, dims=("time", "lat", "lon"))
    s = C.serie_punto(da, -77.33, -11.37)
    assert list(s.values) == [3.0, 7.0, 11.0]


def test_un_dia_que_sigue_fallando_queda_en_nan_y_en_la_lista(tmp_path, monkeypatch):
    zonas = tmp_path / "z.json"
    zonas.write_text(json.dumps({"zonas": [{"id": "a", "west": -77.2, "north": -11.5, "step": 0.1, "cols": 2, "rows": 2}]}))
    cajas = C.cajas_zonas(zonas)
    forma = C.ventana(cajas["a"])[2:][::-1]

    def falso(fecha, cajas_, producto="rnl"):
        if fecha == pd.Timestamp("2024-01-07"):
            raise RuntimeError("sin respuesta")
        return {"a": np.ones(forma, dtype="float32")}

    monkeypatch.setattr(C, "leer_dia", falso)
    rutas = C.descargar(tmp_path / "m", desde="2024-01-01", hasta="2024-01-31", hilos=2, zonas=zonas)
    import xarray as xr

    ds = xr.open_dataset(rutas[0])
    assert ds.sizes["time"] == 31 and np.isnan(ds["precip"].sel(time="2024-01-07")).all()
    assert (tmp_path / "m" / "rnl_dias_fallidos.txt").read_text().split() == ["2024-01-07"]


def test_url_de_chirps3_gefs_por_emision_y_plazo():
    u = C.url_c3g(pd.Timestamp("2026-11-03"), 1)
    assert u.endswith("/v3/daily/global/2026/11/03/c3g_2026.11.04.tif")
    assert C.url_c3g(pd.Timestamp("2016-12-31"), 2).endswith("/2016/12/31/c3g_2017.01.02.tif")


def test_descargar_c3g_arma_emision_por_plazo_con_nan_donde_falta(tmp_path, monkeypatch):
    zonas = tmp_path / "z.json"
    zonas.write_text(json.dumps({"zonas": [{"id": "a", "west": -77.2, "north": -11.5, "step": 0.1, "cols": 2, "rows": 2}]}))
    cajas = C.cajas_zonas(zonas)
    forma = C.ventana(cajas["a"])[2:][::-1]

    def falso(url, cajas_, intentos=8, etiqueta=""):
        if url.endswith("c3g_2010.03.02.tif"):
            return None  # not published
        dia = int(url[-6:-4])
        return {"a": np.full(forma, float(dia), dtype="float32")}

    monkeypatch.setattr(C, "leer_url", falso)
    rutas = C.descargar_c3g(tmp_path / "g", leads=(0, 1), desde=2010, hasta=2010, hilos=2, zonas=zonas)
    import xarray as xr

    ds = xr.open_dataset(rutas[0])
    assert ds.sizes["lead"] == 2 and pd.Timestamp(ds.emision.values[0]) == pd.Timestamp("2009-11-28")
    v = ds["precip"].sel(emision="2010-03-01")
    assert float(v.sel(lead=0).mean()) == 1 and np.isnan(v.sel(lead=1)).all()  # 2 March was not published


def test_indices_anuales_de_temporada():
    idx = pd.date_range("2000-12-01", "2001-04-30")
    v = np.zeros(len(idx))
    v[:3] = [12, 25, 2]  # 1-3 Dec: three wet days in a row, one >= 20, two >= 10
    v[50] = 0.5
    r = C.indices_anuales(pd.Series(v, index=idx)).loc[2001]
    assert r["prctot"] == pytest.approx(39.5) and r["r10mm"] == 2 and r["r20mm"] == 1
    assert r["sdii"] == pytest.approx(13) and r["cdw"] == 3
