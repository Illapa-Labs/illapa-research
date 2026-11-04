"""Probability of heavy rain at every node of the alert map, from the GEFS ensemble (docs/26, stage 3).

Stage 1 showed that the deterministic UK Met Office rain, even with the right totals, catches few
heavy days (daily r about 0.38 at a 10 km node). This stage turns an ensemble into a calibrated
probability of "today's rain passes the node's 95th percentile of PISCOp".

* **Forecasts.** GEFSv12 reforecast 2000-2019 (NOAA, public domain; one 00 UTC run a day, members
  c00 and p01-p04, 0.25°), read by byte ranges as in `gefs_reforecast`, but keeping a rectangle of
  cells over the zone instead of box means. The operational GEFS is the same model and has the same
  first five members, so a calibration fitted here can be applied in real time to those members.
* **Day.** PISCOp's day runs from 12 UTC to 12 UTC (7 a.m. to 7 a.m. in Lima). Hours 12-36 of run
  `d` cover exactly that day (lead 1) and are issued at 19:00 of the day before; hours 36-60 of run
  `d-1` give lead 2. Nothing after the issue time is used.
* **Node value.** Bilinear interpolation of each member's 0.25° field to the node.
* **Event.** PISCOp at the node (mean of the four cells around it, `correccion_malla.pisco_en_nodos`)
  above its 95th percentile of the rainy months (December to April), computed on the training seasons.
* **Calibration.** Per node, logistic regression on two ensemble summaries: square root of the
  ensemble mean, and the fraction of members above the model's own 95th percentile at that node
  (training seasons). Validated leaving one rainy season out.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import gefs_reforecast as G

VENTANAS = tuple((h, h + 6) for h in range(12, 60, 6))  # 12-18 ... 54-60
LEADS = {1: (0, 12), 2: (1, 36)}  # lead -> (days before the rain day the run is issued, first hour)
PERCENTIL = 95
MESES = (12, 1, 2, 3, 4)


def rectangulo(caja: tuple[float, float, float, float], margen: float = 0.25):
    """Rows and columns of the 0.25° GEFS cells around a box (one cell of margin for interpolation)."""
    w, s, e, n = caja
    return G.celdas_de_caja(G.LAT, G.LON, (w - margen, s - margen, e + margen, n + margen))


def procesar_corrida(fecha_run: date, filas: np.ndarray, cols: np.ndarray,
                     miembros=G.MIEMBROS) -> np.ndarray:
    """6-hour rain of every member over the rectangle: array (member, window, row, col), NaN if missing."""
    s = requests.Session()
    out = np.full((len(miembros), len(VENTANAS), len(filas), len(cols)), np.nan, dtype="float32")
    for k, m in enumerate(miembros):
        url = G.url_archivo(fecha_run, m, "apcp_sfc")
        idx = G.leer_idx(G._get(s, url + ".idx").decode())
        msgs = [x for x in G.ventanas_6h(idx, hasta=VENTANAS[-1][1]) if (x.h_ini, x.h_fin) in VENTANAS]
        if not msgs:
            continue
        ini, fin = msgs[0].inicio, msgs[-1].fin
        bloque = G._get(s, url, (ini, fin))
        for x in msgs:
            trozo = bloque[x.inicio - ini : (x.fin + 1 - ini) if x.fin is not None else None]
            campo = G.decodificar(trozo)
            out[k, VENTANAS.index((x.h_ini, x.h_fin))] = campo[np.ix_(filas, cols)]
    return out


def _trabajo(args) -> str:
    d, carpeta, filas, cols = args
    try:
        a = procesar_corrida(d, filas, cols)
    except FileNotFoundError:
        return f"falta {d}"
    np.save(Path(carpeta) / f"{d:%Y%m%d}.npy", a)
    return ""


def descargar(destino: Path, caja, desde: int = 2000, hasta: int = 2019, procesos: int = 12) -> int:
    """Every run of the rainy seasons `desde`..`hasta` over the rectangle, one `.npy` per run; resumable."""
    filas, cols = rectangulo(caja)
    carpeta = Path(destino) / "runs"
    carpeta.mkdir(parents=True, exist_ok=True)
    np.savez(Path(destino) / "rejilla.npz", lat=G.LAT[filas], lon=np.where(G.LON[cols] > 180, G.LON[cols] - 360, G.LON[cols]))
    pend = [d for d in G.fechas_de_corridas(desde, hasta) if not (carpeta / f"{d:%Y%m%d}.npy").exists()]
    hechos = 0
    with ProcessPoolExecutor(procesos) as pool:
        for r in pool.map(_trabajo, [(d, str(carpeta), filas, cols) for d in pend], chunksize=2):
            hechos += 1
            if r:
                print(r, flush=True)
            if hechos % 200 == 0:
                print(f"{hechos}/{len(pend)} corridas", flush=True)
    return hechos


def pesos_bilineales(lat_g: np.ndarray, lon_g: np.ndarray, lat: float, lon: float) -> list[tuple[int, int, float]]:
    """(row, col, weight) of the four grid points around (lat, lon); `lat_g` descending, `lon_g` ascending."""
    i = int(np.searchsorted(-lat_g, -lat) - 1)
    j = int(np.searchsorted(lon_g, lon) - 1)
    i, j = min(max(i, 0), len(lat_g) - 2), min(max(j, 0), len(lon_g) - 2)
    ty = (lat_g[i] - lat) / (lat_g[i] - lat_g[i + 1])
    tx = (lon - lon_g[j]) / (lon_g[j + 1] - lon_g[j])
    return [(i, j, (1 - ty) * (1 - tx)), (i, j + 1, (1 - ty) * tx), (i + 1, j, ty * (1 - tx)), (i + 1, j + 1, ty * tx)]


def lluvia_en_nodos(destino: Path, nd: pd.DataFrame) -> pd.DataFrame:
    """Daily rain per (rain day, lead, member, node) from the saved runs, as a long table."""
    rej = np.load(Path(destino) / "rejilla.npz")
    pesos = {c: pesos_bilineales(rej["lat"], rej["lon"], r["lat"], r["lon"]) for c, r in nd.iterrows()}
    filas = []
    for f in sorted((Path(destino) / "runs").glob("*.npy")):
        run = pd.Timestamp(f.stem)
        a = np.load(f)  # member, window, row, col
        for lead, (atras, h0) in LEADS.items():
            w = [VENTANAS.index((h, h + 6)) for h in range(h0, h0 + 24, 6)]
            diario = a[:, w].sum(axis=1)  # member, row, col
            dia = run + pd.Timedelta(days=atras)
            for c, ps in pesos.items():
                v = sum(p * diario[:, i, j] for i, j, p in ps)
                for m, x in enumerate(v):
                    filas.append((dia, lead, m, c, float(x)))
    return pd.DataFrame(filas, columns=["dia", "lead", "miembro", "celda", "mm"])


def temporada(d: pd.DatetimeIndex) -> np.ndarray:
    return np.where(d.month == 12, d.year + 1, d.year)


def resumen_ensamble(ll: pd.DataFrame, lead: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(ensemble mean, members) per rain day and node for one lead; members as a 3-D-like wide table."""
    x = ll[ll["lead"] == lead]
    miembros = x.pivot_table(index=["dia", "celda"], columns="miembro", values="mm")
    return miembros.mean(axis=1).unstack("celda"), miembros


def calibrar(media: pd.DataFrame, miembros: pd.DataFrame, obs: pd.DataFrame, C: float = 1.0) -> dict[str, pd.DataFrame]:
    """Out-of-season probabilities per node: calibrated, raw ensemble fraction and climatology.

    For every left-out season and node, the thresholds (PISCOp and model 95th percentiles), the
    logistic fit and the climatological rate use the other seasons only.
    """
    from sklearn.linear_model import LogisticRegression

    dias = media.index.intersection(obs.index)
    dias = dias[np.isin(dias.month, MESES)]
    ts = temporada(dias)
    out = {k: pd.DataFrame(np.nan, index=dias, columns=media.columns) for k in ("calibrada", "fraccion_cruda", "clima")}
    y_tab = pd.DataFrame(np.nan, index=dias, columns=media.columns)
    for c in media.columns:
        o = obs.loc[dias, c].to_numpy()
        mu = media.loc[dias, c].to_numpy()
        mm = miembros.xs(c, level="celda").reindex(dias).to_numpy()  # days x members
        ok = ~np.isnan(o) & ~np.isnan(mu)
        for s in np.unique(ts):
            tr, te = ok & (ts != s), ok & (ts == s)
            if te.sum() == 0 or tr.sum() < 100:
                continue
            u_obs = np.percentile(o[tr], PERCENTIL)
            u_mod = np.percentile(mm[tr].ravel(), PERCENTIL)
            y = (o > u_obs).astype(int)
            X = np.column_stack([np.sqrt(mu), (mm > u_mod).mean(axis=1)])
            if y[tr].sum() < 5:
                continue
            m = LogisticRegression(C=C).fit(X[tr], y[tr])
            out["calibrada"].loc[dias[te], c] = m.predict_proba(X[te])[:, 1]
            out["fraccion_cruda"].loc[dias[te], c] = (mm[te] > u_obs).mean(axis=1)
            out["clima"].loc[dias[te], c] = y[tr].mean()
            y_tab.loc[dias[te], c] = y[te]
    out["y"] = y_tab
    return out


def metricas(res: dict[str, pd.DataFrame], bandas=(0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0001)) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pooled Brier score, skill against climatology and AUC per version; reliability table."""
    from sklearn.metrics import roc_auc_score

    y = res["y"].to_numpy().ravel()
    ok = ~np.isnan(y)
    clima = res["clima"].to_numpy().ravel()[ok]
    bs_clima = float(np.mean((clima - y[ok]) ** 2))
    filas, fiab = [], []
    for k in ("calibrada", "fraccion_cruda", "clima"):
        p = res[k].to_numpy().ravel()[ok]
        bs = float(np.mean((p - y[ok]) ** 2))
        filas.append({"version": k, "brier": bs, "bss_vs_clima": 1 - bs / bs_clima,
                      "auc": float(roc_auc_score(y[ok], p)) if k != "clima" else 0.5,
                      "p_media": float(p.mean()), "frecuencia": float(y[ok].mean()), "n": int(ok.sum())})
        b = pd.cut(p, bandas, right=False)
        t = pd.DataFrame({"p": p, "y": y[ok], "banda": b}).groupby("banda", observed=True).agg(
            p_media=("p", "mean"), frecuencia=("y", "mean"), n=("y", "size")).reset_index()
        t.insert(0, "version", k)
        fiab.append(t)
    return pd.DataFrame(filas).set_index("version"), pd.concat(fiab)


def tabla_operativa(media: pd.DataFrame, miembros: pd.DataFrame, obs: pd.DataFrame, z: dict, lead: int,
                    C: float = 1.0) -> dict:
    """Fit on all seasons, per node: PISCOp and model thresholds and the logistic coefficients."""
    from sklearn.linear_model import LogisticRegression

    dias = media.index.intersection(obs.index)
    dias = dias[np.isin(dias.month, MESES)]
    nodos = {}
    for c in media.columns:
        o, mu = obs.loc[dias, c].to_numpy(), media.loc[dias, c].to_numpy()
        mm = miembros.xs(c, level="celda").reindex(dias).to_numpy()
        ok = ~np.isnan(o) & ~np.isnan(mu)
        u_obs, u_mod = np.percentile(o[ok], PERCENTIL), np.percentile(mm[ok].ravel(), PERCENTIL)
        y = (o[ok] > u_obs).astype(int)
        X = np.column_stack([np.sqrt(mu[ok]), (mm[ok] > u_mod).mean(axis=1)])
        m = LogisticRegression(C=C).fit(X, y)
        nodos[str(c)] = {"umbral_pisco_mm": round(float(u_obs), 2), "umbral_modelo_mm": round(float(u_mod), 2),
                         "intercepto": round(float(m.intercept_[0]), 4),
                         "coef_raiz_media": round(float(m.coef_[0, 0]), 4), "coef_fraccion": round(float(m.coef_[0, 1]), 4)}
    return {"zona": z["id"], "lead_dias": lead, "evento": f"lluvia del día (7 a. m. a 7 a. m.) sobre el percentil {PERCENTIL} de PISCOp",
            "miembros": list(G.MIEMBROS), "formula": "p = 1/(1+exp(-(intercepto + coef_raiz_media*sqrt(media) + coef_fraccion*fraccion)))",
            "fraccion": "miembros con lluvia del día > umbral_modelo_mm", "nodos": nodos,
            "fuente": "GEFSv12 reforecast 2000-2019 (NOAA) calibrado con PISCOp v3.0 (SENAMHI, GPL-3.0)"}


def principal(zona_id: str = "lima-este", raiz: Path = Path("."), procesos: int = 12) -> pd.DataFrame:
    """Stage 3 for one zone: download the rectangle, validate leads 1 and 2, write tables in `catalogo/`."""
    from . import correccion_malla as CM
    from .chirps_malla import cajas_zonas

    raiz = Path(raiz)
    destino = raiz / "datos" / "gefs_malla" / zona_id
    descargar(destino, cajas_zonas(margen=0.0)[zona_id], procesos=procesos)
    z = CM.zona(zona_id)
    nd = CM.nodos(z)
    r_ll = destino / "lluvia_nodos.csv.gz"
    if not r_ll.exists():
        lluvia_en_nodos(destino, nd).to_csv(r_ll, index=False)
    ll = pd.read_csv(r_ll, parse_dates=["dia"])
    obs = pd.read_csv(raiz / "datos" / "correccion_malla" / f"{zona_id}_pisco_diario.csv.gz", index_col=0, parse_dates=True)
    obs.columns = obs.columns.astype(int)
    tablas, fiabs = [], []
    for lead in LEADS:
        media, miembros = resumen_ensamble(ll, lead)
        res = calibrar(media, miembros, obs)
        t, f = metricas(res)
        t.insert(0, "lead", lead)
        f.insert(0, "lead", lead)
        tablas.append(t)
        fiabs.append(f)
        tab = tabla_operativa(media, miembros, obs, z, lead)
        (raiz / "catalogo" / f"probabilidad_{zona_id}_lead{lead}.json").write_text(json.dumps(tab), encoding="utf-8")
    t = pd.concat(tablas)
    t.round(4).to_csv(raiz / "catalogo" / f"probabilidad_{zona_id}_metricas.csv")
    pd.concat(fiabs).round(4).to_csv(raiz / "catalogo" / f"probabilidad_{zona_id}_fiabilidad.csv", index=False)
    return t
