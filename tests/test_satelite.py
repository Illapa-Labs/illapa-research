import numpy as np
from rasterio.transform import from_origin

from illapa_research import satelite as S


def test_indices_de_vegetacion_y_suelo():
    uno = np.full((2, 2), 0.2, dtype=np.float32)
    ind = S.indices(b04=uno, b08=uno * 2, b11=uno, b12=uno)
    assert np.allclose(ind["ndvi"], (0.4 - 0.2) / (0.4 + 0.2), atol=1e-4)
    assert np.allclose(ind["nbr"], (0.4 - 0.2) / (0.4 + 0.2), atol=1e-4)


def test_cambio_y_resumen_ignoran_pixeles_no_validos():
    antes = {"nbr": np.zeros((8, 8))}
    despues = {"nbr": np.full((8, 8), -0.3)}
    validos = np.ones((8, 8), dtype=bool)
    validos[:4] = False
    d = S.cambio(antes, despues, validos)
    assert np.isnan(d["nbr"][:4]).all() and np.allclose(d["nbr"][4:], -0.3)
    r = S.resumen_cuenca(d, np.ones((8, 8), dtype=bool), minimo_valido=0.4)
    assert np.isclose(r["nbr_media"], -0.3) and np.isclose(r["validos_nbr"], 0.5)
    r2 = S.resumen_cuenca(d, np.ones((8, 8), dtype=bool), minimo_valido=0.9)
    assert np.isnan(r2["nbr_media"])


def test_mascara_salida_es_un_disco_alrededor_del_punto():
    tr = from_origin(300000.0, 8660000.0, 20.0, 20.0)
    m = S.mascara_salida(-76.7, -11.95, 100.0, tr, "EPSG:32718", (100, 100))
    assert m.shape == (100, 100) and m.dtype == bool


def test_auc_dentro_de_temporada_detecta_una_senal_y_ninguna():
    import pandas as pd

    rng = np.random.default_rng(0)
    filas = []
    for t in range(2019, 2025):
        for k in range(20):
            activa = k < 6
            filas.append({"temporada": t, "activa": activa, "nbr_media": rng.normal(-0.2 if activa else 0.0, 0.1)})
    tabla = pd.DataFrame(filas)
    con = S.auc_dentro_de_temporada(tabla, "nbr_media", -1, n_perm=200)
    assert con["auc"] > 0.85 and con["p"] < 0.05
    tabla["nbr_media"] = rng.normal(size=len(tabla))
    sin = S.auc_dentro_de_temporada(tabla, "nbr_media", -1, n_perm=200)
    assert 0.3 < sin["auc"] < 0.7


def test_mascara_en_rejilla_quema_y_dilata_los_puntos():
    tr = from_origin(300000.0, 8660000.0, 10.0, 10.0)
    pts = np.array([[300055.0, 8659945.0]])
    m = S.mascara_en_rejilla(pts, tr, (20, 20), radio_m=20.0)
    assert m[5, 5] and m.sum() > 1 and not m[0, 0]
    assert S.mascara_en_rejilla(np.empty((0, 2)), tr, (20, 20)).sum() == 0


def test_dos_vias_quita_efectos_de_cuenca_y_temporada():
    import pandas as pd

    filas = [{"slug": s, "temporada": t, "v": 2.0 * i + 3.0 * j, "activa": False}
             for i, s in enumerate("abcde") for j, t in enumerate(range(2019, 2024))]
    z = S.dos_vias(pd.DataFrame(filas), "v")
    assert np.allclose(z["v"], 0.0, atol=1e-6)
