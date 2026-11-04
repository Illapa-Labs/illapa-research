"""A home-made CHIRPS3-GEFS for one zone, from the GEFS reforecast and the CHIRPS grid (docs/26).

CHIRPS3-GEFS (Harrison et al. 2022) is the GEFSv12 ensemble-mean rain, quantile-matched to CHIRPS and put on
its 0.05° grid. The CHC data server stopped answering the remote PC, and there is no mirror, so this rebuilds
the same idea from data already on the PC:

* **Forecast.** The stage 3 rectangle of the GEFSv12 reforecast 2000-2019 (00 UTC, members c00 and p01-p04,
  0.25°), with the same two leads: hours 12-36 of run `d` (lead 1) and 36-60 of run `d-1` (lead 2). The
  official product uses UTC days; here the day is SENAMHI's (7 a.m. to 7 a.m.), which is the map's day and,
  per stage 0, the day CHIRPS v3 `rnl` agrees with best (lag 0 against 12 rain gauges).
* **Grid.** Bilinear interpolation of the five-member mean to the centres of the CHIRPS cells.
* **Matching.** Empirical quantile mapping per CHIRPS cell and calendar month (December to April), with
  mid-ranks for ties (dry days) and a constant ratio above the training maximum. Fitted leaving one rainy
  season out, so every value of the hindcast comes from a mapping that did not see its season.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import probabilidad_malla as P

MESES = P.MESES


def matriz_bilineal(lat_g: np.ndarray, lon_g: np.ndarray, lat_f: np.ndarray, lon_f: np.ndarray) -> np.ndarray:
    """Weights (fine cells, coarse cells) that interpolate a coarse field (lat_g x lon_g, raveled) to every
    fine cell centre (lat_f x lon_f, raveled)."""
    W = np.zeros((len(lat_f) * len(lon_f), len(lat_g) * len(lon_g)))
    for a, la in enumerate(lat_f):
        for b, lo in enumerate(lon_f):
            for i, j, p in P.pesos_bilineales(lat_g, lon_g, float(la), float(lo)):
                W[a * len(lon_f) + b, i * len(lon_g) + j] += p
    return W


def media_gefs(destino: Path, lead: int) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Five-member mean of the rain day for one lead, from the saved runs: (days, array day x row x col)."""
    atras, h0 = P.LEADS[lead]
    w = [P.VENTANAS.index((h, h + 6)) for h in range(h0, h0 + 24, 6)]
    dias, campos = [], []
    for f in sorted((Path(destino) / "runs").glob("*.npy")):
        a = np.load(f)  # member, window, row, col
        diario = a[:, w].sum(axis=1)  # NaN if a window is missing
        with np.errstate(invalid="ignore"):
            campos.append(np.nanmean(diario, axis=0) if np.isfinite(diario).any() else diario[0])
        dias.append(pd.Timestamp(f.stem) + pd.Timedelta(days=atras))
    return pd.DatetimeIndex(dias), np.stack(campos).astype("float32")


def mapear(mod_tr: np.ndarray, obs_tr: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Empirical quantile mapping of `x` for one cell: the value's mid-rank among the training model values
    gives a probability, read off the training observations. Above the model's maximum the ratio of the two
    maxima is kept instead of clipping."""
    m = np.sort(mod_tr[np.isfinite(mod_tr)])
    o = np.sort(obs_tr[np.isfinite(obs_tr)])
    out = np.full(x.shape, np.nan)
    if len(m) < 10 or len(o) < 10:
        return out
    ok = np.isfinite(x)
    xv = x[ok]
    rango = (np.searchsorted(m, xv, "left") + np.searchsorted(m, xv, "right")) / 2  # mid-rank, 0..n
    p = np.clip((rango - 0.5) / (len(m) - 1), 0, 1)
    y = np.interp(p * (len(o) - 1), np.arange(len(o)), o)
    arriba = xv > m[-1]
    if arriba.any() and m[-1] > 0:
        y[arriba] = xv[arriba] * o[-1] / m[-1]
    out[ok] = y
    return out


def temporada(d: pd.DatetimeIndex) -> np.ndarray:
    return P.temporada(d)


def corregir_fuera_de_temporada(mod: np.ndarray, obs: np.ndarray, dias: pd.DatetimeIndex) -> np.ndarray:
    """Hindcast (day x cell): each rainy season mapped with the other seasons, per cell and calendar month."""
    ts, ms = temporada(dias), dias.month.to_numpy()
    out = np.full(mod.shape, np.nan)
    for s in np.unique(ts):
        for mes in MESES:
            te = (ts == s) & (ms == mes)
            tr = (ts != s) & (ms == mes)
            if not te.any():
                continue
            for c in range(mod.shape[1]):
                out[te, c] = mapear(mod[tr, c], obs[tr, c], mod[te, c])
    return out


def tablas_operativas(mod: np.ndarray, obs: np.ndarray, dias: pd.DatetimeIndex, n: int = 101) -> dict[int, np.ndarray]:
    """Fit on all seasons: per calendar month, the model and CHIRPS quantiles of every cell (2, n, cells)."""
    p = np.linspace(0, 1, n)
    out = {}
    for mes in MESES:
        s = dias.month == mes
        with np.errstate(invalid="ignore"):
            out[mes] = np.stack([np.nanquantile(mod[s], p, axis=0), np.nanquantile(obs[s], p, axis=0)]).astype("float32")
    return out


def _pentada(d: pd.DatetimeIndex) -> np.ndarray:
    return (d.year * 100 + d.month) * 10 + np.minimum((d.day - 1) // 5, 5)


def metricas_celda(pred: np.ndarray, obs: np.ndarray, dias: pd.DatetimeIndex, percentiles=(90, 95)) -> dict[str, float]:
    """How one cell's forecast series agrees with CHIRPS (or a gauge) on the rainy-season days of both."""
    ok = np.isfinite(pred) & np.isfinite(obs)
    x, y, d = pred[ok], obs[ok], dias[ok]
    if len(x) < 60 or y.mean() <= 0:
        return {"dias": float(len(x))}
    out = {"dias": float(len(x)), "sesgo": float(x.mean() / y.mean()), "error_medio": float(np.abs(x - y).mean()),
           "r_diaria": float(np.corrcoef(x, y)[0, 1])}
    pent = pd.DataFrame({"x": x, "y": y}).groupby(_pentada(d)).sum()
    out["r_pentada"] = float(pent["x"].corr(pent["y"]))
    for q in percentiles:
        u = np.percentile(y, q)
        a, o = x > u, y > u
        h = int((a & o).sum())
        out[f"aciertos_p{q}"] = h / max(int(o.sum()), 1)
        out[f"falsas_p{q}"] = int((a & ~o).sum()) / max(int(a.sum()), 1)
        out[f"csi_p{q}"] = h / max(int((a | o).sum()), 1)
        out[f"dias_sobre_p{q}_pred"] = float(a.mean())
    return out


def pluviometros(raiz: Path):
    """(name, lon, lat, daily series) of the historical SENAMHI gauges of the Rímac used in stage 0."""
    from .senamhi import HISTORICAS_NOMBRES

    tablas = Path(raiz) / "datos" / "senamhi" / "tablas"
    est = pd.read_csv(tablas / "estaciones.csv", dtype={"legacyStationId": str})
    est = {r["legacyStationId"]: r for _, r in est.iterrows()}
    for k, n in HISTORICAS_NOMBRES.items():
        r = est[str(k)]
        s = pd.read_csv(tablas / f"diaria_historica_{n}.csv", index_col=0, parse_dates=True)["lluvia_mm"]
        yield r["name"], float(r["longitude"]), float(r["latitude"]), s


def principal(zona_id: str = "lima-este", raiz: Path = Path(".")) -> pd.DataFrame:
    """Rebuild, validate against CHIRPS cell by cell, and write the hindcast, the tables and the metrics."""
    import xarray as xr

    raiz = Path(raiz)
    gefs = raiz / "datos" / "gefs_malla" / zona_id
    ch = xr.open_dataset(raiz / "datos" / "chirps_malla" / f"{zona_id}_rnl.nc")["precip"]
    lat_f, lon_f = ch["lat"].to_numpy(), ch["lon"].to_numpy()
    rej = np.load(gefs / "rejilla.npz")
    W = matriz_bilineal(rej["lat"], rej["lon"], lat_f, lon_f)
    tierra = np.isfinite(ch.isel(time=0).to_numpy()).ravel()
    t_ch = pd.DatetimeIndex(ch["time"].to_numpy())
    salida = raiz / "datos" / "c3g_casero"
    salida.mkdir(parents=True, exist_ok=True)

    filas, crudo_l, casero_l, dias_l = [], {}, {}, {}
    for lead in P.LEADS:
        dias, g = media_gefs(gefs, lead)
        sel = np.isin(dias.month, MESES) & dias.isin(t_ch)
        dias, g = dias[sel], g[sel]
        crudo = g.reshape(len(dias), -1) @ W.T  # day x fine cell
        obs = ch.sel(time=dias).to_numpy().reshape(len(dias), -1)
        crudo[:, ~tierra] = np.nan
        casero = corregir_fuera_de_temporada(crudo, obs, dias)
        for nombre, pred in (("gefs_crudo", crudo), ("c3g_casero", casero)):
            for c in np.flatnonzero(tierra):
                m = metricas_celda(pred[:, c], obs[:, c], dias)
                filas.append({"lead": lead, "version": nombre, "celda": int(c), **m})
        crudo_l[lead], casero_l[lead], dias_l[lead] = crudo, casero, dias
        tab = tablas_operativas(crudo, obs, dias)
        np.savez_compressed(salida / f"{zona_id}_tablas_lead{lead}.npz", lat=lat_f, lon=lon_f,
                            probabilidades=np.linspace(0, 1, 101), **{f"mes_{m:02d}": v for m, v in tab.items()})
    comunes = dias_l[1].union(dias_l[2])
    forma = (len(lat_f), len(lon_f))

    # hindcast on disk: one variable per version, dims (lead, dia, lat, lon); NaN where a lead has no run
    ds = {}
    for nombre, d in (("gefs_crudo", crudo_l), ("c3g_casero", casero_l)):
        partes = [pd.DataFrame(d[lead], index=dias_l[lead]).reindex(comunes).to_numpy().reshape(len(comunes), *forma)
                  for lead in P.LEADS]
        ds[nombre] = (("lead", "dia", "lat", "lon"), np.stack(partes).astype("float32"), {"units": "mm/day"})
    xr.Dataset(ds, coords={"lead": list(P.LEADS), "dia": comunes, "lat": lat_f, "lon": lon_f},
               attrs={"product": "home-made CHIRPS3-GEFS: GEFSv12 reforecast 5-member mean, bilinear to the CHIRPS v3 "
                                 "0.05 grid, quantile-mapped per cell and month to CHIRPS v3 rnl, leaving one season out",
                      "day": "SENAMHI day, 12 UTC to 12 UTC; lead 1 = hours 12-36 of the run of that day, lead 2 = hours 36-60 of the run before",
                      "zone": zona_id,
                      "sources": "GEFSv12 reforecast (NOAA, public domain); CHIRPS v3 (Climate Hazards Center, CC BY 4.0)"}
               ).to_netcdf(salida / f"{zona_id}_c3g_casero.nc",
                           encoding={k: {"zlib": True, "complevel": 4} for k in ds})
    # SENAMHI rain gauges (to 2014): the forecast at the gauge's CHIRPS cell, against the gauge, with CHIRPS itself
    est = []
    for nom, lon, lat, serie in pluviometros(raiz):
        a, b = int(np.abs(lat_f - lat).argmin()), int(np.abs(lon_f - lon).argmin())
        c = a * len(lon_f) + b
        for lead in P.LEADS:
            d = dias_l[lead]
            o = serie.reindex(d).to_numpy()
            versiones = {"gefs_crudo": crudo_l[lead][:, c], "c3g_casero": casero_l[lead][:, c],
                         "chirps": ch.sel(time=d).to_numpy()[:, a, b]}
            for v, x in versiones.items():
                est.append({"estacion": nom, "lead": lead, "version": v, **metricas_celda(x, o, d)})
    pd.DataFrame(est).round(4).to_csv(raiz / "catalogo" / f"c3g_casero_{zona_id}_pluviometros.csv", index=False)

    t = pd.DataFrame(filas)
    t.to_csv(raiz / "catalogo" / f"c3g_casero_{zona_id}_celdas.csv.gz", index=False, float_format="%.4f")
    res = t.groupby(["lead", "version"]).median(numeric_only=True).drop(columns="celda")
    res.round(4).to_csv(raiz / "catalogo" / f"c3g_casero_{zona_id}_resumen.csv")
    return res
