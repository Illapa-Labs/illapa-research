"""Daily predictors of a huaico day in Chosica-Chaclacayo, built only from past information.

Every feature at day t uses data up to day t (rain of the day included, flagged as `mismo_dia`) or
up to day t-1 (`previo`). Anomalies are taken against a smoothed day-of-year climatology of
1991-2020 so a feature means "unusual for the date", not "it is summer".

Sources (see `fuentes.py`): Open-Meteo/ERA5 at six points, GloFAS discharge, NOAA OISST sea
surface temperature, and the hourly Chosica / upper-basin rain of the first event study.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LAPSE_K_POR_M = 0.0065  # standard atmosphere, to turn a 2 m temperature into a 0 °C height
BASE_CLIMA = (1991, 2020)


def cargar_predictores(ruta: Path) -> dict[str, pd.DataFrame]:
    """Daily ERA5 summaries per point (`open_meteo_predictores_diarios.json`)."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    out = {}
    for punto, d in datos.items():
        df = pd.DataFrame(d["columnas"], index=pd.to_datetime(d["fecha"]))
        df.attrs["elevation"] = d["elevation"]
        out[punto] = df
    return out


def cargar_caudal(ruta: Path) -> pd.DataFrame:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return pd.DataFrame(
        {k: pd.Series(v["river_discharge"], index=pd.to_datetime(v["fecha"])) for k, v in datos.items()}
    )


def cargar_sst(ruta: Path) -> pd.DataFrame:
    return pd.read_csv(ruta, index_col="fecha", parse_dates=True)


def _ultimo_dia(pred, caudal, sst, lluvia_horaria) -> pd.Timestamp:
    fin = [d.index.max() for d in pred.values()]
    if caudal is not None:
        fin.append(caudal.index.max())
    if lluvia_horaria:
        fin += [h.index.max().normalize() for h in lluvia_horaria.values()]
    return min(fin) if fin else pd.Timestamp("2026-01-01")


def anomalia(serie: pd.Series, base: tuple[int, int] = BASE_CLIMA, suavizado: int = 15) -> pd.Series:
    """Departure from the smoothed day-of-year mean of the base period."""
    s = serie.dropna()
    ref = s[(s.index.year >= base[0]) & (s.index.year <= base[1])]
    doy = ref.groupby(ref.index.dayofyear).mean().reindex(range(1, 367))
    # circular smoothing so the new year has no seam
    ext = pd.concat([doy.iloc[-suavizado:], doy, doy.iloc[:suavizado]])
    suave = ext.rolling(2 * suavizado + 1, center=True, min_periods=1).mean().iloc[suavizado:-suavizado]
    suave.index = range(1, 367)
    return serie - serie.index.dayofyear.map(suave).to_numpy()


def altura_cero_grados(temp_c: pd.Series, elevacion_m: float) -> pd.Series:
    """Height of the 0 °C isotherm implied by the 2 m temperature and a standard lapse rate."""
    return elevacion_m + temp_c / LAPSE_K_POR_M


def _rezago_media(s: pd.Series, ventana: int, desde: int = 1) -> pd.Series:
    """Mean of the `ventana` days ending `desde` days before t (desde=1: up to yesterday)."""
    return s.shift(desde).rolling(ventana, min_periods=max(1, ventana // 2)).mean()


def construir(
    pred: dict[str, pd.DataFrame],
    caudal: pd.DataFrame | None,
    sst: pd.DataFrame | None,
    lluvia_horaria: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Daily feature table, one row per day, columns tagged by family in `FAMILIAS`."""
    idx = pd.date_range("1983-01-01", _ultimo_dia(pred, caudal, sst, lluvia_horaria), freq="D")
    f = pd.DataFrame(index=idx)

    # --- rain: same day (trigger) and antecedent (conditions)
    for p, nombre in (("chosica", "ch"), ("santa-eulalia-alta", "sea"), ("matucana", "mat"), ("ticlio", "tic")):
        if p not in pred:
            continue
        d = pred[p].reindex(idx)
        r = d["precipitation_sum"]
        f[f"{nombre}_lluvia_1d"] = r
        f[f"{nombre}_lluvia_3d"] = r.rolling(3).sum()
        f[f"{nombre}_lluvia_7d_previa"] = r.shift(1).rolling(7).sum()
        f[f"{nombre}_lluvia_30d_previa"] = r.shift(1).rolling(30).sum()
        f[f"{nombre}_lluvia_hmax"] = d["precipitation_max"]
    # the first study's hourly rain (Chosica and upper basin) keeps the peak-hour feature
    if lluvia_horaria:
        for nombre, h in lluvia_horaria.items():
            p = h["precipitation"]
            dia = p.resample("D").sum().reindex(idx)
            f[f"{nombre}_h_lluvia_1d"] = dia
            f[f"{nombre}_h_lluvia_3d"] = dia.rolling(3).sum()
            f[f"{nombre}_h_lluvia_7d_previa"] = dia.shift(1).rolling(7).sum()
            f[f"{nombre}_h_lluvia_30d_previa"] = dia.shift(1).rolling(30).sum()
            f[f"{nombre}_h_pico"] = p.resample("D").max().reindex(idx)
            f[f"{nombre}_h_3h_max"] = p.rolling(3).sum().resample("D").max().reindex(idx)
            f[f"{nombre}_suelo"] = h["soil_moisture_0_to_7cm"].resample("D").mean().reindex(idx).shift(1)

    # --- soil wetness and humidity (state of the basin)
    for p, nombre in (("chosica", "ch"), ("santa-eulalia-alta", "sea"), ("matucana", "mat")):
        if p not in pred:
            continue
        d = pred[p].reindex(idx)
        if "soil_moisture_0_to_7cm" not in d:
            continue
        f[f"{nombre}_suelo_era5"] = d["soil_moisture_0_to_7cm"].shift(1)

    # --- heat and 0 °C height upstream: warm spells melt snow and raise the rain-snow line
    for p, nombre in (("ticlio", "tic"), ("santa-eulalia-alta", "sea"), ("matucana", "mat")):
        if p not in pred:
            continue
        d = pred[p].reindex(idx)
        t = d["temperature_2m"]
        elev = pred[p].attrs["elevation"]
        z0 = altura_cero_grados(t, elev)
        f[f"{nombre}_temp_anom"] = anomalia(t)
        f[f"{nombre}_temp_anom_3d"] = _rezago_media(f[f"{nombre}_temp_anom"], 3)
        f[f"{nombre}_temp_anom_7d"] = _rezago_media(f[f"{nombre}_temp_anom"], 7)
        f[f"{nombre}_cero_anom"] = anomalia(z0)
        f[f"{nombre}_cero_anom_3d"] = _rezago_media(f[f"{nombre}_cero_anom"], 3)
        f[f"{nombre}_temp_cambio_3d"] = t.shift(1) - t.shift(4)
        f[f"{nombre}_nieve_7d"] = d["snowfall_sum"].shift(1).rolling(7).sum()
        f[f"{nombre}_radiacion_anom"] = anomalia(d["shortwave_radiation_sum"])

    # --- moisture inflow from the Amazon side and the coast
    if {"selva-tarma", "costa-lima", "chosica", "ticlio"} <= set(pred):
        sel = pred["selva-tarma"].reindex(idx)
        cos = pred["costa-lima"].reindex(idx)
        f["selva_punto_rocio_anom"] = anomalia(sel["dew_point_2m"])
        f["selva_punto_rocio_anom_3d"] = _rezago_media(f["selva_punto_rocio_anom"], 3)
        f["selva_nubes"] = sel["cloud_cover"]
        f["selva_lluvia_3d"] = sel["precipitation_sum"].rolling(3).sum()
        f["costa_punto_rocio_anom_3d"] = _rezago_media(anomalia(cos["dew_point_2m"]), 3)
        f["costa_nubes"] = cos["cloud_cover"]
        dp = (pred["chosica"].reindex(idx)["pressure_msl"] - sel["pressure_msl"])
        f["gradiente_presion_chosica_selva"] = anomalia(dp)
        f["chosica_hum_rel"] = pred["chosica"].reindex(idx)["relative_humidity_2m"]
        f["chosica_nubes"] = pred["chosica"].reindex(idx)["cloud_cover"]
        f["chosica_vpd_anom_3d"] = _rezago_media(anomalia(pred["chosica"].reindex(idx)["vapour_pressure_deficit"]), 3)
        f["tic_viento"] = pred["ticlio"].reindex(idx)["wind_speed_10m"]


    # --- sea surface temperature: level, weekly mean and recent rise
    if sst is not None:
        s = sst.reindex(idx).interpolate(limit=5)
        for caja in s.columns:
            a = anomalia(s[caja])
            f[f"sst_{caja}_anom"] = a.shift(1)
            f[f"sst_{caja}_anom_7d"] = _rezago_media(a, 7)
            f[f"sst_{caja}_anom_30d"] = _rezago_media(a, 30)
            f[f"sst_{caja}_alza_7d"] = a.shift(1) - a.shift(8)
            f[f"sst_{caja}_alza_14d"] = a.shift(1) - a.shift(15)

    # --- river: discharge relative to the date and recent rise
    if caudal is not None:
        for c in caudal.columns:
            q = caudal[c].reindex(idx)
            lq = np.log(q.clip(lower=0.1))
            f[f"caudal_{c}_anom"] = anomalia(lq).shift(1)
            f[f"caudal_{c}_alza_3d"] = lq.shift(1) - lq.shift(4)
            f[f"caudal_{c}_max_7d"] = lq.shift(1).rolling(7).max()

    return f


def familia(c: str) -> str:
    """Feature family, used to compare model blocks."""
    if c.startswith("sst_"):
        return "mar"
    if c.startswith("caudal_"):
        return "caudal"
    if "suelo" in c:
        return "suelo"
    if c.endswith(("_7d_previa", "_30d_previa")):
        return "lluvia_previa"
    if c.endswith(("_lluvia_1d", "_lluvia_3d", "_lluvia_hmax", "_h_pico", "_h_3h_max")):
        return "lluvia_mismo_dia"
    if any(k in c for k in ("temp_", "cero_", "nieve", "radiacion")):
        return "calor_altura"
    return "humedad_y_circulacion"


def temporada_mask(idx: pd.DatetimeIndex) -> np.ndarray:
    """Rainy-season days (December to April)."""
    return np.asarray((idx.month >= 12) | (idx.month <= 4))


def _resumen_diario(js: dict) -> pd.DataFrame:
    from .fuentes import _agregar_diario

    df = pd.DataFrame(js["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return _agregar_diario(df)


def cargar_predictores_cache(cache: Path) -> dict[str, pd.DataFrame]:
    """Points already downloaded in `predictores_cache/` (both periods present), so analyses can
    start before `descargar-datos` has finished every point."""
    cache = Path(cache)
    out = {}
    for p1 in sorted(cache.glob("*_1983.json")):
        nombre = p1.stem[: -len("_1983")]
        p2 = cache / f"{nombre}_2000.json"
        if not p2.exists():
            continue
        js1, js2 = (json.loads(p.read_text(encoding="utf-8")) for p in (p1, p2))
        df = pd.concat([_resumen_diario(js1), _resumen_diario(js2)])
        df = df[~df.index.duplicated(keep="last")]
        df.attrs["elevation"] = js1["elevation"]
        out[nombre] = df
    return out


def cargar_sst_cache(cache: Path) -> pd.DataFrame:
    """Daily SST of the boxes whose yearly files are all in `oisst_cache/`."""
    cache = Path(cache)
    cajas = sorted({p.stem.rsplit("_", 1)[0] for p in cache.glob("*.csv")})
    anio = pd.Timestamp.today().year
    series = {}
    for caja in cajas:
        archivos = [cache / f"{caja}_{a}.csv" for a in range(1982, anio + 1)]
        if all(a.exists() for a in archivos):
            series[caja] = pd.concat([pd.read_csv(a, index_col=0, parse_dates=True)["sst"] for a in archivos])
    out = pd.DataFrame({k: v[~v.index.duplicated(keep="last")] for k, v in series.items()})
    out.index.name = "fecha"
    return out


def cargar_power(ruta: Path) -> dict[str, pd.DataFrame]:
    """NASA POWER (MERRA-2) daily values with the column names of the ERA5 summaries.

    Units differ a little (pressure is at the grid-cell surface, not sea level; cloud is a
    fraction scale), which is harmless for anomalies and differences of anomalies, the only
    way the features use them.
    """
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    out = {}
    for punto, d in datos.items():
        c = pd.DataFrame(d["columnas"], index=pd.to_datetime(d["fecha"]), dtype=float)
        df = pd.DataFrame(
            {
                "temperature_2m": c["T2M"],
                "temperature_2m_max": c["T2M_MAX"],
                "temperature_2m_min": c["T2M_MIN"],
                "dew_point_2m": c["T2MDEW"],
                "relative_humidity_2m": c["RH2M"],
                "pressure_msl": c["PS"] * 10.0,
                "cloud_cover": c["CLOUD_AMT"],
                "precipitation_sum": c["PRECTOTCORR"],
                "wind_speed_10m": c["WS10M"],
                "shortwave_radiation_sum": c["ALLSKY_SFC_SW_DWN"],
            }
        )
        df.attrs["elevation"] = d["elevation"]
        out[punto] = df
    return out


def cargar_con_respaldo(datos: Path, rellenar_con_power: bool = True) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Daily point data: ERA5 (consolidated file, or the cache of what is downloaded) and, for
    the points ERA5 does not have yet, NASA POWER (MERRA-2, a much coarser grid).

    Returns the data and the source of each point, so every result can say which one it used.
    """
    datos = Path(datos)
    final = datos / "open_meteo_predictores_diarios.json"
    pred = cargar_predictores(final) if final.exists() else cargar_predictores_cache(datos / "predictores_cache")
    fuente = {k: "ERA5 (Open-Meteo)" for k in pred}
    power = datos / "nasa_power_diario.json"
    if rellenar_con_power and power.exists():
        for k, df in cargar_power(power).items():
            if k not in pred:
                pred[k] = df
                fuente[k] = "MERRA-2 (NASA POWER, malla gruesa)"
    return pred, fuente
