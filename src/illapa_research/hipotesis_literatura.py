"""Hypotheses T23, T24, T25 and T28 of the literature review (docs/09).

* T23 rain timing: hour of the peak, share of the day's rain in the afternoon, wet hours, longest
  wet spell, from the hourly ERA5 rain of Chosica and the upper basin.
* T24 absolute sea surface temperature: degree-days above 25-28 °C and runs of days above them,
  from NOAA OISST (the convection over the eastern Pacific is non-linear in the absolute SST).
* T25 E and C indices (Takahashi et al. 2011) of the IGP, season by season and as monthly
  covariates, against the ICEN and the ONI.
* T28 CHIRPS v3 rain (IMERG-timed) as a rain source independent of ERA5.

Every new column is judged the same way as in chapter 05: added to the best model of that
chapter (rain of the day + yesterday's conditions), out-of-fold, season by season, with a paired
bootstrap of seasons for the change in average precision and a null in which the new block is
shifted cyclically inside each season (same distribution, no link with the labels).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import evaluacion_diaria as E
from . import modelo_diario as MD
from . import nino as N

# --- pre-registered choices (written down before looking at any result) -------------------------
TARDE = (12, 20)  # local hours that count as "afternoon"
UMBRAL_LLUVIA_HORA = 0.1  # mm per hour for a wet hour
UMBRALES_SST = (25.0, 26.0, 27.0, 28.0)
VENTANAS_SST = (7, 14, 30)
INDICES_EC = ("E", "C")


# ------------------------------------------------------------------------------------- T23 timing
def variables_horarias(horario: dict[str, pd.DataFrame], idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily timing features of the hourly rain, one set per point (`chosica`, `cuenca-alta`).

    Times are the local (America/Lima) hours of the Open-Meteo files. All columns describe the
    day itself, so they are nowcast variables (lag 0) unless shifted.
    """
    out = {}
    for punto, h in horario.items():
        p = h["precipitation"].astype(float)
        dia = p.index.normalize()
        hora = p.index.hour
        total = p.groupby(dia).sum()
        tarde = p[(hora >= TARDE[0]) & (hora < TARDE[1])].groupby(dia[(hora >= TARDE[0]) & (hora < TARDE[1])]).sum()
        horas_humedas = (p >= UMBRAL_LLUVIA_HORA).groupby(dia).sum()
        r3 = p.rolling(3).sum()
        r3max = r3.groupby(dia).max()
        # hour of the peak (first hour of the maximum), NaN on dry days
        pico = p.groupby(dia).apply(lambda s: s.index[int(np.argmax(s.to_numpy()))].hour if s.max() > 0 else np.nan)
        # longest run of consecutive wet hours inside the day
        racha = (p >= UMBRAL_LLUVIA_HORA).groupby(dia).apply(_racha_maxima)
        pref = punto.replace("-", "_")
        d = pd.DataFrame(
            {
                f"{pref}_hora_pico": pico,
                f"{pref}_frac_tarde": (tarde.reindex(total.index).fillna(0) / total.where(total > 0)),
                f"{pref}_horas_humedas": horas_humedas,
                f"{pref}_frac_3h_max": r3max / total.where(total > 0),
                f"{pref}_racha_max_h": racha,
                f"{pref}_lluvia_tarde": tarde.reindex(total.index).fillna(0),
                f"{pref}_lluvia_dia": total,
            }
        )
        out[punto] = d
    return pd.concat(out.values(), axis=1).reindex(idx)


def _racha_maxima(s: pd.Series) -> int:
    mejor = actual = 0
    for v in s.to_numpy():
        actual = actual + 1 if v else 0
        mejor = max(mejor, actual)
    return mejor


def comparar_dias_lluviosos(
    T: pd.DataFrame, y: pd.Series, temporada: np.ndarray, mask: np.ndarray, punto: str,
    minimo_mm: float = 1.0, n_boot: int = 300, semilla: int = 0,
) -> pd.DataFrame:
    """Among rainy days of `punto` (daily rain >= `minimo_mm`), how different are the event days?

    Reports, per timing variable, the median of event and non-event days, the AUC (0.5 = no
    difference) and its 90 % interval from a bootstrap of whole seasons, plus the same AUC inside
    the days above the 90th percentile of daily rain (so that the contrast is not just intensity).
    """
    pref = punto.replace("-", "_")
    cols = [c for c in T.columns if c.startswith(pref + "_") and not c.endswith(("_lluvia_dia", "_lluvia_tarde"))]
    lluvia = T[f"{pref}_lluvia_dia"].to_numpy()
    yv = y.to_numpy()
    rng = np.random.default_rng(semilla)
    base = mask & (lluvia >= minimo_mm)
    fuerte = base & (lluvia >= np.nanpercentile(lluvia[base], 90))
    filas = []
    seasons = np.unique(temporada[base])
    por_temp = {s: np.flatnonzero(base & (temporada == s)) for s in seasons}
    boots = [np.concatenate([por_temp[s] for s in rng.choice(seasons, len(seasons))]) for _ in range(n_boot)]
    for c in cols:
        x = T[c].to_numpy(dtype=float)
        a = E.auc_rangos(x[base], yv[base])
        bs = np.array([E.auc_rangos(x[b], yv[b]) for b in boots])
        lo, hi = np.nanpercentile(bs, [5, 95]) if np.isfinite(bs).any() else (np.nan, np.nan)
        filas.append({
            "variable": c, "dias_lluviosos": int(base.sum()), "eventos": int(yv[base].sum()),
            "mediana_evento": float(np.nanmedian(x[base & (yv == 1)])) if (base & (yv == 1)).any() else np.nan,
            "mediana_sin_evento": float(np.nanmedian(x[base & (yv == 0)])),
            "auc": a, "auc_p5": lo, "auc_p95": hi, "separa": bool(lo > 0.5 or hi < 0.5),
            "auc_dias_fuertes": E.auc_rangos(x[fuerte], yv[fuerte]), "eventos_fuertes": int(yv[fuerte].sum()),
        })
    return pd.DataFrame(filas)


def auc_estratificado(x: np.ndarray, y: np.ndarray, estrato: np.ndarray) -> float:
    """AUC computed inside each stratum (for example each calendar month) and averaged with the
    number of event/non-event pairs as weights. It removes anything that is only the seasonal cycle."""
    from sklearn.metrics import roc_auc_score

    num = den = 0.0
    for e in np.unique(estrato):
        m = (estrato == e) & ~np.isnan(x)
        npos, nneg = int(y[m].sum()), int((1 - y[m]).sum())
        if npos < 2 or nneg < 2:
            continue
        w = npos * nneg
        num += w * roc_auc_score(y[m], x[m])
        den += w
    return float(num / den) if den else float("nan")


def cribado_estratificado(
    F: pd.DataFrame, y: pd.Series, estrato: np.ndarray, temporada: np.ndarray, n_boot: int = 200, semilla: int = 0
) -> pd.DataFrame:
    """Stratified AUC of every column with a 90 % interval from a bootstrap of whole seasons."""
    rng = np.random.default_rng(semilla)
    yv = y.to_numpy()
    seasons = np.unique(temporada)
    por_temp = {s: np.flatnonzero(temporada == s) for s in seasons}
    boots = [np.concatenate([por_temp[s] for s in rng.choice(seasons, len(seasons))]) for _ in range(n_boot)]
    filas = []
    for c in F.columns:
        x = F[c].to_numpy(dtype=float)
        a = auc_estratificado(x, yv, estrato)
        bs = np.array([auc_estratificado(x[b], yv[b], estrato[b]) for b in boots])
        lo, hi = np.nanpercentile(bs, [5, 95]) if np.isfinite(bs).any() else (np.nan, np.nan)
        filas.append({"variable": c, "auc_por_mes": a, "p5": lo, "p95": hi, "separa": bool(lo > 0.5 or hi < 0.5)})
    out = pd.DataFrame(filas)
    out["fuerza"] = (out["auc_por_mes"] - 0.5).abs()
    return out.sort_values("fuerza", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------------------------ T24 abs SST
def variables_sst_absoluta(sst: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Degree-days above each threshold in the `ventana` days up to yesterday, and the run of
    consecutive days above it ending yesterday, for every OISST box.

    `sst` holds absolute temperatures in °C. The first day of the window is yesterday, so nothing
    uses the day itself.
    """
    s = sst.reindex(idx).interpolate(limit=5)
    cols = {}
    for caja in s.columns:
        t = s[caja].shift(1)
        cols[f"sstabs_{caja}_nivel"] = t
        for u in UMBRALES_SST:
            exceso = (t - u).clip(lower=0)
            sobre = (t > u).astype(float).where(t.notna())
            racha = sobre.groupby((sobre != sobre.shift()).cumsum()).cumsum() * sobre
            cols[f"sstabs_{caja}_racha_{int(u)}"] = racha
            for v in VENTANAS_SST:
                cols[f"sstabs_{caja}_gd{int(u)}_{v}d"] = exceso.rolling(v, min_periods=max(1, v // 2)).sum()
    return pd.DataFrame(cols, index=idx)


# ------------------------------------------------------------------------------------ T25 E and C
def cargar_ec(ruta: Path) -> pd.DataFrame:
    """Monthly E and C indices of the IGP (`igp_ec_ersstv5.txt`), indexed by month start."""
    df = pd.read_csv(ruta, sep=r"\s+", comment="%", header=0, names=["anio", "mes", "E", "C"])
    df.index = pd.to_datetime({"year": df["anio"], "month": df["mes"], "day": 1})
    return df[["E", "C"]]


def ec_por_temporada(ec: pd.DataFrame, icen: pd.DataFrame, oni: pd.DataFrame) -> pd.DataFrame:
    """Season table with the January-April mean of E, C, ICEN and the ONI (DJF-JFM-FMA)."""
    filas = []
    for anio in sorted(set(ec.index.year)):
        e = ec[(ec.index.year == anio) & (ec.index.month <= 4)]
        if len(e) < 4:
            continue
        i = icen[(icen["anio"] == anio) & icen["mes"].between(1, 4)]["icen"]
        o = oni[(oni["anio"] == anio) & oni["trimestre"].isin(["DJF", "JFM", "FMA"])]["oni"]
        if len(i) < 4 or len(o) < 3:
            continue
        filas.append({"temporada": anio, "E": e["E"].mean(), "C": e["C"].mean(), "ICEN": i.mean(), "ONI": o.mean()})
    return pd.DataFrame(filas).set_index("temporada")


def correlacion_con_temporadas(
    indices: pd.DataFrame, resultado: pd.Series, n_perm: int = 5000, semilla: int = 0
) -> pd.DataFrame:
    """Spearman correlation of every index with a season-level outcome, with a permutation p-value.

    `resultado` is the number of placed quebradas active, or of huaico days, in each season.
    """
    rng = np.random.default_rng(semilla)
    r = resultado.reindex(indices.index).fillna(0).to_numpy(dtype=float)
    filas = []
    for c in indices.columns:
        x = indices[c].to_numpy(dtype=float)
        rho = spearmanr(x, r)[0]
        perm = np.array([spearmanr(x, rng.permutation(r))[0] for _ in range(n_perm)])
        filas.append({"indice": c, "rho": rho, "p_permutacion": float((np.abs(perm) >= abs(rho)).mean()),
                      "temporadas": len(r)})
    return pd.DataFrame(filas)


def validacion_poisson(indices: pd.DataFrame, resultado: pd.Series, conjuntos: dict[str, list[str]]) -> pd.DataFrame:
    """Leave-one-season-out Poisson deviance of season counts for sets of indices (lower is better).

    Each model is a penalised Poisson regression on the standardised indices; the empty set is the
    mean of the other seasons. The deviance is summed over the seasons left out.
    """
    from sklearn.linear_model import PoissonRegressor
    from sklearn.preprocessing import StandardScaler

    y = resultado.reindex(indices.index).fillna(0).to_numpy(dtype=float)
    filas = []
    for nombre, cols in conjuntos.items():
        mu = np.empty(len(y))
        for i in range(len(y)):
            tr = np.arange(len(y)) != i
            if cols:
                X = indices[cols].to_numpy(dtype=float)
                esc = StandardScaler().fit(X[tr])
                m = PoissonRegressor(alpha=1.0, max_iter=1000).fit(esc.transform(X[tr]), y[tr])
                mu[i] = m.predict(esc.transform(X[[i]]))[0]
            else:
                mu[i] = y[tr].mean()
        mu = np.clip(mu, 1e-6, None)
        dev = 2 * np.sum(np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0) - (y - mu))
        filas.append({"modelo": nombre, "deviance_dejando_una_fuera": float(dev)})
    return pd.DataFrame(filas)


def variables_ec_mensuales(ec: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """E and C as known on each day: the previous complete month and the change from the one before."""
    mes_previo = (idx.to_period("M") - 1).to_timestamp()
    dos_antes = (idx.to_period("M") - 2).to_timestamp()
    out = {}
    for c in ec.columns:
        out[f"ec_{c}_mes_previo"] = ec[c].reindex(mes_previo).to_numpy()
        out[f"ec_{c}_cambio"] = ec[c].reindex(mes_previo).to_numpy() - ec[c].reindex(dos_antes).to_numpy()
    return pd.DataFrame(out, index=idx)


# ------------------------------------------------------------------------------------ T28 CHIRPS
def cargar_chirps(ruta: Path) -> pd.DataFrame:
    return pd.read_csv(ruta, parse_dates=["fecha"], index_col="fecha")


def variables_chirps(chirps: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Rain of the day, of 3 days and of the previous 7 days, per box (`chirps_<caja>_...`)."""
    c = chirps.reindex(idx)
    out = {}
    for caja in c.columns:
        r = c[caja]
        pref = f"chirps_{caja.replace('-', '_')}"
        out[f"{pref}_1d"] = r
        out[f"{pref}_3d"] = r.rolling(3, min_periods=2).sum()
        out[f"{pref}_7d_previa"] = r.shift(1).rolling(7, min_periods=4).sum()
    return pd.DataFrame(out, index=idx)


def comparar_con_era5(chirps: pd.DataFrame, F: pd.DataFrame, correspondencia: dict[str, str]) -> pd.DataFrame:
    """Daily correlation and bias of CHIRPS against the ERA5 rain of the same point.

    `correspondencia`: CHIRPS box -> ERA5 daily-rain column of `F` (for example
    `"matucana": "mat_lluvia_1d"`). Also reports the bias on the wettest 5 % of ERA5 days.
    """
    filas = []
    for caja, col in correspondencia.items():
        if caja not in chirps or col not in F:
            continue
        j = pd.concat([chirps[caja].rename("chirps"), F[col].rename("era5")], axis=1).dropna()
        j = j[(j.index.month >= 12) | (j.index.month <= 4)]
        cola = j[j["era5"] >= j["era5"].quantile(0.95)]
        filas.append({
            "caja": caja, "dias": len(j),
            "corr_pearson": float(j.corr().iloc[0, 1]), "corr_spearman": float(j.corr(method="spearman").iloc[0, 1]),
            "media_chirps_mm": float(j["chirps"].mean()), "media_era5_mm": float(j["era5"].mean()),
            "media_chirps_5pc_era5": float(cola["chirps"].mean()), "media_era5_5pc_era5": float(cola["era5"].mean()),
        })
    return pd.DataFrame(filas)


# ------------------------------------------------------------------- adding a block to the model
def contexto_modelo(raiz: Path = Path("."), folds_tipo: str = "temporada", **kw):
    """Data, base design matrix (rain + yesterday's conditions), labels, seasons and folds."""
    D = MD.cargar_datos(raiz, **kw)
    X, y, ts, mes = MD.matrices(D)
    eps = N.episodios(D.temporadas) if folds_tipo == "episodio" else None
    folds = [f for f in E.pliegues(ts, folds_tipo, eps) if len(f)]
    return D, X, y, ts, mes, folds


def alinear(extra: pd.DataFrame, D: MD.Datos) -> pd.DataFrame:
    """Rainy-season rows of a full-calendar frame, in the order of the design matrices."""
    return extra.reindex(D.F.index)[D.inventario["mask"]]


def correr_bloque(
    X_base: pd.DataFrame, extra: pd.DataFrame, y: pd.Series, ts: np.ndarray, folds: list[np.ndarray],
    n_jobs: int = 8,
) -> MD.Resultado:
    """Out-of-fold probabilities of the base columns plus `extra` (same nested tuning as chapter 05)."""
    X = pd.concat([X_base.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)
    X.index = X_base.index
    return MD.validar_anidado(X, y, ts, folds, n_jobs=n_jobs)


def ap_pareado(y: np.ndarray, p_nuevo: np.ndarray, p_base: np.ndarray, ts: np.ndarray, n: int = 400,
               semilla: int = 0) -> dict[str, float]:
    """Change in average precision (new - base) with a 90 % interval from a bootstrap of seasons."""
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    idx = {s: np.flatnonzero(ts == s) for s in seasons}
    ok = ~np.isnan(p_nuevo) & ~np.isnan(p_base)
    d = []
    for _ in range(n):
        b = np.concatenate([idx[s] for s in rng.choice(seasons, len(seasons))])
        b = b[ok[b]]
        if y[b].sum() < 3:
            continue
        d.append(average_precision_score(y[b], p_nuevo[b]) - average_precision_score(y[b], p_base[b]))
    d = np.array(d)
    return {"delta_ap": float(average_precision_score(y[ok], p_nuevo[ok]) - average_precision_score(y[ok], p_base[ok])),
            "p5": float(np.percentile(d, 5)), "p95": float(np.percentile(d, 95)),
            "prob_mejora": float((d > 0).mean())}


def nula_bloque(
    X_base: pd.DataFrame, extra: pd.DataFrame, y: pd.Series, ts: np.ndarray, folds: list[np.ndarray],
    n: int = 12, semilla: int = 0, n_jobs: int = 8,
) -> np.ndarray:
    """Change in average precision when the new columns are shifted cyclically inside each season.

    The shifted block keeps its values and its autocorrelation but loses its link with the day, so
    this is the "no information" distribution for the real change.
    """
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(semilla)
    yv = y.to_numpy()
    base = MD.validar_anidado(X_base, y, ts, folds, n_jobs=n_jobs).p
    ok = ~np.isnan(base)
    out = []
    for _ in range(n):
        ex = extra.copy()
        for s in np.unique(ts):
            i = np.flatnonzero(ts == s)
            ex.iloc[i] = np.roll(extra.iloc[i].to_numpy(), int(rng.integers(5, max(6, len(i) - 5))), axis=0)
        p = correr_bloque(X_base, ex, y, ts, folds, n_jobs).p
        out.append(average_precision_score(yv[ok], p[ok]) - average_precision_score(yv[ok], base[ok]))
    return np.array(out)


# ---------------------------------------------------------------- T28: complement or replace ERA5
def columnas_lluvia_era5(columnas: list[str], puntos: tuple[str, ...] = ("mat", "sea", "tic")) -> list[str]:
    """ERA5 rain columns of the upper-basin points (same day and shifted), the ones CHIRPS can replace."""
    base = tuple(f"{p}_lluvia_" for p in puntos)
    return [c for c in columnas if c.removesuffix("_prev").startswith(base)]


def evaluar_chirps(
    X_base: pd.DataFrame, chirps_cols: pd.DataFrame, y: pd.Series, ts: np.ndarray, desde: int = 1998,
    n_jobs: int = 8,
) -> pd.DataFrame:
    """Complement and substitution tests on the seasons that have CHIRPS (`desde` on).

    Three models, all fitted and scored on the same rows and the same season-out folds:
    ``era5`` (the base design), ``era5+chirps`` (the CHIRPS columns added) and ``chirps en vez de
    era5`` (the upper-basin ERA5 rain columns replaced by their CHIRPS counterparts). The change
    in average precision is paired with a bootstrap of seasons.
    """
    dentro = (ts >= desde) & chirps_cols.notna().any(axis=1).to_numpy()
    Xb = X_base[dentro]
    Cx = chirps_cols[dentro]
    ys, tss = y[dentro], ts[dentro]
    folds = [f for f in E.pliegues(tss, "temporada") if len(f)]
    ref = MD.validar_anidado(Xb, ys, tss, folds, n_jobs=n_jobs)
    sust = Xb.drop(columns=columnas_lluvia_era5(list(Xb.columns)))
    modelos = {
        "era5": ref,
        "era5+chirps": correr_bloque(Xb, Cx, ys, tss, folds, n_jobs),
        "chirps en vez de era5": correr_bloque(sust, Cx, ys, tss, folds, n_jobs),
    }
    yv = ys.to_numpy()
    pf = E.p_climatologia(ys, np.asarray(ys.index.month), folds)
    filas = []
    for nombre, r in modelos.items():
        m = MD.metricas_completas(yv, r.p, pf)
        d = ap_pareado(yv, r.p, ref.p, tss)
        filas.append({"modelo": nombre, "dias": len(ys), "eventos": int(yv.sum()), "ap": m["ap"], "ap_base": m["ap_base"],
                      "auc": m["auc"], "aciertos_con_5pc_alarmas": m["aciertos_con_5pc_alarmas"],
                      "delta_ap_vs_era5": d["delta_ap"], "p5": d["p5"], "p95": d["p95"]})
    return pd.DataFrame(filas)
