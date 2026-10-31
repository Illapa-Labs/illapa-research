"""Backtest of "forecast rain -> probability of a huaico day" with the GEFSv12 reforecast (2000-2019).

Pre-registered design (written before any score was looked at; see docs/19):

* **Test rows**: rainy-season days (December to April) of the seasons 2000 to 2019 whose reforecast
  exists. Always reported with and without 2017 (23 of the 56 catalogued huaico days).
* **PP, perfect prognosis**: the day model (ridge-logistic, C = 0.03, as in chapters 05 and 15) is
  trained on *ERA5-built* inputs of every other season (1984-2026, leave one season out) and applied
  to the held-out season with the rain of the day *replaced* by the forecast. Rain features that the
  reforecast cannot give (peak hour, 3-hour maximum) are left out of this model. Variants:
  ``pp_qm`` (forecast rain mapped to the ERA5 distribution by empirical quantiles, fitted on the
  other test seasons), ``pp_crudo`` (no mapping) and ``techo`` (the same model with ERA5 rain: the
  best a perfect rain forecast could do).
* **Lead k** (1, 2, 3 days): rain from the run issued k-1 days before the day (see
  `gefs_reforecast`). Antecedent features are the observed ones shifted by k days, so nothing that
  was not known at issue time is used.
* **MOS**: ridge-logistic trained *inside* 2000-2019 (leave one season out) on forecast
  statistics of the 5 boxes: ``mos_media`` (ensemble mean), ``mos_ens`` (+ maximum, spread and
  exceedance probabilities) and ``mos_ant`` (+ antecedents). Fixed regularisation (C = 0.3, 0.1,
  0.03), chosen before looking.
* **References**: raw forecast ranking (``gefs_media``: the ensemble mean of the valley box; a
  threshold only cuts this ranking), and the monthly climatology.
* **Nulls**: labels shifted cyclically inside each season (same events per season, same clustering),
  the whole pipeline refitted: thousands of worlds on the GPU.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import gefs_reforecast as G
from . import gpu

C_PP = 0.03
C_MOS = {"mos_media": 0.3, "mos_ens": 0.1, "mos_ant": 0.03, "mos_ens_conv": 0.1}
# ERA5 daily-rain column -> GEFS box (fixed in advance). The 3-day column is the rolling sum.
MAPEO_LLUVIA = {
    "ch_lluvia_1d": "chosica",
    "chosica_h_lluvia_1d": "chosica",
    "sea_lluvia_1d": "santa-eulalia-alta",
    "mat_lluvia_1d": "matucana",
    "cuenca-alta_h_lluvia_1d": "matucana",
    "tic_lluvia_1d": "ticlio",
}
COLS_1D = tuple(MAPEO_LLUVIA)
COLS_3D = tuple(c.replace("1d", "3d") for c in COLS_1D)
TEMPORADAS_PRUEBA = tuple(range(2000, 2020))


def temporada_de_fecha(idx: pd.DatetimeIndex) -> np.ndarray:
    """Rainy season of each date: November and December belong to the next year's season."""
    return np.where(idx.month >= 11, idx.year + 1, idx.year)


# ------------------------------------------------------------------ quantile mapping
def cuantiles(x_entrena: np.ndarray, y_entrena: np.ndarray, nuevos: np.ndarray) -> np.ndarray:
    """Empirical quantile mapping: the value of `nuevos` goes to the same quantile of `y_entrena`."""
    xs = np.sort(x_entrena)
    n = len(xs)
    u = (np.searchsorted(xs, nuevos, "left") + np.searchsorted(xs, nuevos, "right")) / (2 * n)
    return np.quantile(y_entrena, np.clip(u, 0, 1))


def mapear_fuera_de_temporada(gefs: pd.Series, obs: pd.Series, en_temporada: pd.Series) -> pd.Series:
    """Quantile-map the forecast of every season with a fit that never saw that season.

    `gefs` and `obs` are daily series; the fit uses only the days with `en_temporada` True and both
    values present. Days outside the rainy season (the 29-30 November needed for 3-day sums) use the
    fit of the season they belong to.
    """
    ts = pd.Series(temporada_de_fecha(gefs.index), index=gefs.index)
    ambos = pd.concat([gefs, obs], axis=1, keys=["g", "o"]).dropna()
    ambos = ambos[en_temporada.reindex(ambos.index).fillna(False).to_numpy(dtype=bool)]
    ts_ambos = pd.Series(temporada_de_fecha(ambos.index), index=ambos.index)
    out = pd.Series(np.nan, index=gefs.index)
    for s in np.unique(ts.dropna()):
        fit = ambos[ts_ambos != s]
        sel = ts == s
        if len(fit) >= 50:
            out[sel] = cuantiles(fit["g"].to_numpy(), fit["o"].to_numpy(), gefs[sel].to_numpy())
    return out


# ------------------------------------------------------------------ inputs
def tabla_de_ensamble(corridas: pd.DataFrame) -> pd.DataFrame:
    """Ensemble summaries per (day, lead, box): mean, max, spread and exceedance probabilities."""
    ll = G.lluvia_por_dia_y_plazo(corridas)
    return G.resumen_de_ensamble(ll)


def serie_gefs(ens: pd.DataFrame, plazo: int, caja: str, col: str = "media") -> pd.Series:
    s = ens.xs((plazo, caja), level=("plazo", "caja"))[col]
    s.index = pd.DatetimeIndex(s.index)
    return s.sort_index()


def _estandarizar_ref(X: np.ndarray, n_ref: int) -> np.ndarray:
    """Median-impute and z-score with the statistics of the first `n_ref` rows (no labels)."""
    X = np.asarray(X, dtype=np.float64).copy()
    med = np.nanmedian(X[:n_ref], axis=0)
    idx = np.where(np.isnan(X))
    X[idx] = np.take(med, idx[1])
    sd = X[:n_ref].std(axis=0)
    sd[sd == 0] = 1.0
    return (X - X[:n_ref].mean(axis=0)) / sd


class Filas:
    """Rainy-season rows of the daily model (from `modelo_diario.cargar_datos`)."""

    def __init__(self, D):
        self.F = D.F
        self.mask = D.inventario["mask"]
        self.idx = D.F.index[self.mask]
        self.ts = np.asarray(D.temporada)[self.mask]
        self.y = D.y[self.mask].to_numpy().astype(float)
        self.mes = np.asarray(D.mes)[self.mask]
        self.todas = [c for c in D.F.columns if not c.startswith("icen_")]

    def antecedentes(self, k: int) -> pd.DataFrame:
        return self.F[self.todas].shift(k)[self.mask].add_suffix("_prev")


def entradas_pp(filas: Filas, ens: pd.DataFrame, plazo: int, dias_prueba: pd.DatetimeIndex):
    """ERA5 rows and forecast rows (quantile-mapped and raw) of the PP model for one lead."""
    F = filas.F
    en_temp = pd.Series(np.zeros(len(F), dtype=bool), index=F.index)
    en_temp[filas.idx] = True
    crudo, mapeado = {}, {}
    for c1, caja in MAPEO_LLUVIA.items():
        g = serie_gefs(ens, plazo, caja, "media").reindex(F.index)
        crudo[c1] = g
        mapeado[c1] = mapear_fuera_de_temporada(g, F[c1], en_temp)
    out = {}
    ant = filas.antecedentes(plazo)
    for nombre, d in (("fc_qm", mapeado), ("fc_crudo", crudo)):
        d1 = pd.DataFrame(d)
        d3 = d1.rolling(3).sum().rename(columns=lambda c: c.replace("1d", "3d"))
        out[nombre] = pd.concat([d1.loc[dias_prueba], d3.loc[dias_prueba], ant.loc[dias_prueba]], axis=1)
    era = pd.concat([F[list(COLS_1D) + list(COLS_3D)][filas.mask], ant], axis=1)
    return era, out["fc_qm"][era.columns], out["fc_crudo"][era.columns]


def ajustar_por_pliegue(
    X_grande: np.ndarray, y: np.ndarray, ts: np.ndarray, temporadas_prueba, n_era: int,
    quitar_de_entrenamiento: tuple[int, ...] = (), dispositivo: str | None = None,
) -> np.ndarray:
    """Probabilities of every row of `X_grande` from the leave-one-season-out fits (shape folds x rows)."""
    N = X_grande.shape[0]
    Y = np.zeros((len(temporadas_prueba), N))
    M = np.zeros((len(temporadas_prueba), N), dtype=bool)
    Y[:, :n_era] = y
    for f, s in enumerate(temporadas_prueba):
        M[f, :n_era] = (ts != s) & ~np.isin(ts, quitar_de_entrenamiento)
    return gpu.ajustar_logit_lote(X_grande, Y, M, C=C_PP, dispositivo_=dispositivo)


def ensamblar(P: np.ndarray, temporadas_prueba, ts_prueba: np.ndarray, pos_era_prueba: np.ndarray,
              n_era: int) -> dict[str, np.ndarray]:
    """Out-of-fold probability of every test row, read from the fold of its own season.

    Row layout of the big design matrix: ERA5 rows (n_era), quantile-mapped forecast rows (nt),
    raw forecast rows (nt). Returns the ERA5 ceiling (``techo``), ``pp_qm`` and ``pp_crudo``.
    """
    nt = len(ts_prueba)
    out = {k: np.empty(nt) for k in ("techo", "pp_qm", "pp_crudo")}
    for f, s in enumerate(temporadas_prueba):
        j = np.flatnonzero(ts_prueba == s)
        out["techo"][j] = P[f, pos_era_prueba[j]]
        out["pp_qm"][j] = P[f, n_era + j]
        out["pp_crudo"][j] = P[f, n_era + nt + j]
    return out


# ------------------------------------------------------------------ metrics
def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def metricas(y: np.ndarray, p: np.ndarray, p_clim: np.ndarray | None = None, es_prob: bool = True) -> dict[str, float]:
    from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

    out = {"n": len(y), "eventos": int(y.sum()), "ap": float(average_precision_score(y, p)),
           "ap_base": float(y.mean()), "auc": float(roc_auc_score(y, p))}
    for presup in (0.05, 0.10):
        corte = np.quantile(p, 1 - presup)
        out[f"aciertos_{int(presup * 100)}pc"] = float(y[p >= corte].sum() / max(1, y.sum()))
    if es_prob:
        pp = np.clip(p, 1e-6, 1 - 1e-6)
        out["brier"] = brier(y, pp)
        out["logloss"] = float(log_loss(y, pp))
        out["obs_sobre_pred"] = float(y.sum() / pp.sum())
        if p_clim is not None:
            out["brier_skill"] = float(1 - brier(y, pp) / brier(y, np.clip(p_clim, 1e-6, 1 - 1e-6)))
    return out


def valor_costo_perdida(y: np.ndarray, p: np.ndarray, razones=(0.02, 0.05, 0.1, 0.2, 0.3, 0.5)) -> pd.DataFrame:
    """Relative economic value (cost-loss): alarm when p >= C/L; 1 = perfect forecast, 0 = climatology."""
    base = y.mean()
    filas = []
    for c in razones:
        alarma = p >= c
        gasto = (c * alarma.sum() + ((y == 1) & ~alarma).sum()) / len(y)
        clima = min(c, base)
        perfecto = base * c
        filas.append({"coste_sobre_perdida": c, "alarmas_pc": float(alarma.mean()),
                      "valor": float((clima - gasto) / (clima - perfecto)) if clima > perfecto else np.nan})
    return pd.DataFrame(filas)


def bootstrap_temporadas(y, ts, columnas: dict[str, np.ndarray], n: int = 1000, semilla: int = 0,
                         funcion=None) -> pd.DataFrame:
    """Season-block bootstrap: 5-95 % intervals of `funcion(y, p)` for each column of predictions."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    funcion = funcion or {"ap": average_precision_score, "auc": roc_auc_score}
    res = {k: {f: [] for f in funcion} for k in columnas}
    for _ in range(n):
        ii = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        if y[ii].sum() == 0:
            continue
        for k, p in columnas.items():
            for f, fn in funcion.items():
                res[k][f].append(fn(y[ii], p[ii]))
    filas = []
    for k in columnas:
        fila = {"modelo": k}
        for f in funcion:
            lo, hi = np.percentile(res[k][f], [5, 95])
            fila[f"{f}_p5"], fila[f"{f}_p95"] = lo, hi
        filas.append(fila)
    return pd.DataFrame(filas)


def diferencia_pareada(y, ts, p_a, p_b, n: int = 2000, semilla: int = 0) -> dict[str, float]:
    """AP(a) - AP(b) on the same season resamples: mean and 90 % interval."""
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    d = []
    for _ in range(n):
        ii = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        if y[ii].sum() == 0:
            continue
        d.append(average_precision_score(y[ii], p_a[ii]) - average_precision_score(y[ii], p_b[ii]))
    lo, hi = np.percentile(d, [5, 95])
    return {"delta_ap": float(np.mean(d)), "p5": float(lo), "p95": float(hi), "p_positivo": float(np.mean(np.array(d) > 0))}


# ------------------------------------------------------------------ MOS (trained inside 2000-2019)
def caracteristicas_mos(ens: pd.DataFrame, plazo: int, dias: pd.DatetimeIndex, nivel: str = "ens",
                        conv: pd.DataFrame | None = None) -> pd.DataFrame:
    """Forecast statistics per box for the test days. `nivel`: 'media' or 'ens' (+ max, spread, probabilities)."""
    cols = {}
    for caja in G.CAJAS:
        e = ens.xs((plazo, caja), level=("plazo", "caja"))
        e.index = pd.DatetimeIndex(e.index)
        e = e.sort_index()
        media = e["media"]
        cols[f"{caja}_media"] = np.log1p(media.reindex(dias))
        cols[f"{caja}_3d"] = np.log1p(media.rolling(3).sum().reindex(dias))
        if nivel in ("ens", "ens_conv"):
            cols[f"{caja}_max"] = np.log1p(e["maximo"].reindex(dias))
            cols[f"{caja}_disp"] = np.log1p(e["dispersion"].reindex(dias))
            for u in ("1", "5", "10"):
                cols[f"{caja}_p{u}"] = e[f"p_gt{u}"].reindex(dias)
    if conv is not None and nivel == "ens_conv":
        for caja in G.CAJAS:
            c = conv.xs((plazo, caja), level=("plazo", "caja"))
            c.index = pd.DatetimeIndex(c.index)
            for v in ("cape", "pwat"):
                if v in c:
                    cols[f"{caja}_{v}"] = c[v].reindex(dias)
    return pd.DataFrame(cols, index=dias)


def _ajuste_pliegues_prueba(X: np.ndarray, y: np.ndarray, ts: np.ndarray, C: float, dispositivo=None) -> np.ndarray:
    """Out-of-fold probabilities, leave one season out, rows = test rows only."""
    seasons = np.unique(ts)
    Y = np.tile(y, (len(seasons), 1))
    M = np.stack([ts != s for s in seasons])
    P = gpu.ajustar_logit_lote(X, Y, M, C=C, dispositivo_=dispositivo)
    out = np.empty(len(y))
    for f, s in enumerate(seasons):
        j = ts == s
        out[j] = P[f, j]
    return out


def mos_oof(X: pd.DataFrame, y: np.ndarray, ts: np.ndarray, C: float, dispositivo=None) -> np.ndarray:
    Z = _estandarizar_ref(X.to_numpy(), len(X))
    return _ajuste_pliegues_prueba(Z, y, ts, C, dispositivo)


def nulas_mos(X: pd.DataFrame, y: np.ndarray, ts: np.ndarray, C: float, n: int = 2000, semilla: int = 0,
              dispositivo=None, trozo: int = 400) -> np.ndarray:
    """Average precision of `n` null worlds for a MOS model (labels shifted inside each season)."""
    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    Z = _estandarizar_ref(X.to_numpy(), len(X))
    mundos = np.empty((n, len(y)))
    for b in range(n):
        ys = y.copy()
        for s, i in por.items():
            ys[i] = np.roll(y[i], int(rng.integers(5, max(6, len(i) - 5))))
        mundos[b] = ys
    P = np.empty((n, len(y)))
    for f, s in enumerate(seasons):
        m = np.tile(ts != s, (min(trozo, n), 1))
        for i in range(0, n, trozo):
            Yc = mundos[i : i + trozo]
            Pc = gpu.ajustar_logit_lote(Z, Yc, m[: len(Yc)], C=C, dispositivo_=dispositivo)
            P[i : i + trozo, por[s]] = Pc[:, por[s]]
    return gpu.auc_ap_lote(mundos, P, dispositivo_=dispositivo)[1]


def nulas_pp(X_grande: np.ndarray, y_era: np.ndarray, ts_era: np.ndarray, temporadas_prueba, pos_era_prueba: np.ndarray,
             ts_prueba: np.ndarray, n_era: int, n: int = 2000, semilla: int = 0, dispositivo=None,
             trozo: int = 256) -> np.ndarray:
    """Average precision of `n` null worlds of the PP-QM pipeline (labels shifted on the ERA5 rows,
    every leave-one-season-out model refitted, predictions read from the quantile-mapped forecast rows)."""
    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts_era)
    por = {s: np.flatnonzero(ts_era == s) for s in seasons}
    mundos = np.empty((n, n_era))
    for b in range(n):
        ys = y_era.copy()
        for s, i in por.items():
            ys[i] = np.roll(y_era[i], int(rng.integers(5, max(6, len(i) - 5))))
        mundos[b] = ys
    nt = len(ts_prueba)
    N = X_grande.shape[0]
    P = np.empty((n, nt))
    for f, s in enumerate(temporadas_prueba):
        j = np.flatnonzero(ts_prueba == s)
        for i in range(0, n, trozo):
            Yc = np.zeros((min(trozo, n - i), N))
            Yc[:, :n_era] = mundos[i : i + trozo]
            Mc = np.zeros(Yc.shape, dtype=bool)
            Mc[:, :n_era] = ts_era != s
            Pc = gpu.ajustar_logit_lote(X_grande, Yc, Mc, C=C_PP, dispositivo_=dispositivo)
            P[i : i + trozo, j] = Pc[:, n_era + j]
    Yt = mundos[:, pos_era_prueba]
    return gpu.auc_ap_lote(Yt, P, dispositivo_=dispositivo)[1]


# ------------------------------------------------------------------ pipeline
def climatologia_oof(filas: Filas, ts_prueba: np.ndarray, pos_era_prueba: np.ndarray) -> np.ndarray:
    """Monthly base rate of each test row from the seasons other than its own (all ERA-period rows)."""
    out = np.empty(len(ts_prueba))
    for s in np.unique(ts_prueba):
        entrena = filas.ts != s
        tasa = pd.Series(filas.y[entrena]).groupby(filas.mes[entrena]).mean()
        j = np.flatnonzero(ts_prueba == s)
        out[j] = pd.Series(filas.mes[pos_era_prueba[j]]).map(tasa).to_numpy()
    return out


def dias_con_pronostico(filas: Filas, ens: pd.DataFrame, plazos=(1, 2, 3)) -> pd.DatetimeIndex:
    """Test days (seasons 2000-2019) with a complete forecast (all boxes, 3 consecutive days) at every lead."""
    ok = None
    for k in plazos:
        for caja in set(MAPEO_LLUVIA.values()):
            s = serie_gefs(ens, k, caja, "media").reindex(filas.F.index)
            tres = s.rolling(3).sum().notna()
            ok = tres if ok is None else (ok & tres)
    en_prueba = np.isin(filas.ts, TEMPORADAS_PRUEBA)
    dias = filas.idx[en_prueba]
    return dias[ok.reindex(dias).to_numpy(dtype=bool)]


def correr(D, corridas: pd.DataFrame, plazos=(1, 2, 3), n_nulas: int = 2000, dispositivo=None,
           con_nulas: bool = True) -> dict:
    """Run the whole backtest. Returns a dict with the test rows and, per lead, the probabilities of every model."""
    filas = Filas(D)
    ens = tabla_de_ensamble(corridas)
    conv = G.convectivas_por_dia(corridas)
    dias = dias_con_pronostico(filas, ens, plazos)
    pos = filas.idx.get_indexer(dias)
    ts_t, y_t = filas.ts[pos], filas.y[pos]
    temporadas = sorted(set(ts_t))
    R = {"dias": dias, "ts": ts_t, "y": y_t, "mes": filas.mes[pos], "plazos": {}, "nulas": {}}
    R["clim"] = climatologia_oof(filas, ts_t, pos)
    n_era = len(filas.idx)
    for k in plazos:
        era, fq, fc = entradas_pp(filas, ens, k, dias)
        X_grande = _estandarizar_ref(np.vstack([era.to_numpy(), fq.to_numpy(), fc.to_numpy()]), n_era)
        P = ajustar_por_pliegue(X_grande, filas.y, filas.ts, temporadas, n_era, dispositivo=dispositivo)
        mod = ensamblar(P, temporadas, ts_t, pos, n_era)
        P17 = ajustar_por_pliegue(X_grande, filas.y, filas.ts, temporadas, n_era, quitar_de_entrenamiento=(2017,),
                                  dispositivo=dispositivo)
        mod["pp_qm_sin2017_ent"] = ensamblar(P17, temporadas, ts_t, pos, n_era)["pp_qm"]
        # MOS models
        ant = filas.antecedentes(k).loc[dias]
        for nombre, nivel in (("mos_media", "media"), ("mos_ens", "ens")):
            X = caracteristicas_mos(ens, k, dias, nivel)
            mod[nombre] = mos_oof(X, y_t, ts_t, C_MOS[nombre], dispositivo)
        X_ens = caracteristicas_mos(ens, k, dias, "ens")
        mod["mos_ant"] = mos_oof(pd.concat([X_ens, ant], axis=1), y_t, ts_t, C_MOS["mos_ant"], dispositivo)
        if len(conv):
            X_conv = caracteristicas_mos(ens, k, dias, "ens_conv", conv)
            mod["mos_ens_conv"] = mos_oof(X_conv, y_t, ts_t, C_MOS["mos_ens_conv"], dispositivo)
        mod["gefs_media"] = serie_gefs(ens, k, "valle", "media").reindex(dias).to_numpy()
        mod["gefs_max_ens"] = serie_gefs(ens, k, "valle", "maximo").reindex(dias).to_numpy()
        R["plazos"][k] = mod
        if con_nulas:
            R["nulas"][k] = {
                "pp_qm": nulas_pp(X_grande, filas.y, filas.ts, temporadas, pos, ts_t, n_era, n_nulas, dispositivo=dispositivo),
                "mos_ens": nulas_mos(X_ens, y_t, ts_t, C_MOS["mos_ens"], n_nulas, dispositivo=dispositivo),
            }
            if "mos_ens_conv" in mod:
                R["nulas"][k]["mos_ens_conv"] = nulas_mos(X_conv, y_t, ts_t, C_MOS["mos_ens_conv"], n_nulas,
                                                          dispositivo=dispositivo)
    R["ens"], R["conv"] = ens, conv
    return R


SUBCONJUNTOS = {
    "todo": lambda ts: np.ones(len(ts), dtype=bool),
    "sin_2017": lambda ts: ts != 2017,
    "2000-2008": lambda ts: ts <= 2008,
    "2009-2019": lambda ts: ts >= 2009,
}
ES_PROBABILIDAD = {"techo", "pp_qm", "pp_crudo", "pp_qm_sin2017_ent", "mos_media", "mos_ens", "mos_ant", "mos_ens_conv"}


def tabla_metricas(R: dict, subconjuntos=SUBCONJUNTOS) -> pd.DataFrame:
    filas = []
    for k, mod in R["plazos"].items():
        for sub, fn in subconjuntos.items():
            m = fn(R["ts"])
            y = R["y"][m]
            if y.sum() == 0:
                continue
            clim = R["clim"][m]
            filas.append({"plazo": k, "subconjunto": sub, "modelo": "climatologia", **metricas(y, clim, clim, True)})
            for nombre, p in mod.items():
                filas.append({"plazo": k, "subconjunto": sub, "modelo": nombre,
                              **metricas(y, p[m], clim, nombre in ES_PROBABILIDAD)})
    return pd.DataFrame(filas)


def tabla_nulas(R: dict) -> pd.DataFrame:
    """Real AP against the null worlds, per lead and model (all test rows)."""
    from sklearn.metrics import average_precision_score

    filas = []
    for k, nul in R["nulas"].items():
        for nombre, ap in nul.items():
            real = average_precision_score(R["y"], R["plazos"][k][nombre])
            filas.append({"plazo": k, "modelo": nombre, "ap_real": real, "ap_nula_media": float(ap.mean()),
                          "ap_nula_p95": float(np.percentile(ap, 95)), "ap_nula_max": float(ap.max()),
                          "p": float((1 + (ap >= real).sum()) / (1 + len(ap))), "mundos": len(ap)})
    return pd.DataFrame(filas)


def cobertura_top_k(activaciones: pd.DataFrame, ubicadas: list[str], temporadas: pd.DataFrame, k: int = 5,
                    temporadas_prueba=TEMPORADAS_PRUEBA) -> dict[str, float]:
    """On huaico days, how many of the quebradas that were active fall in the `k` highest-participation ones.

    The participation of each quebrada (`integracion.participacion`) is learned without the season
    of the day. It is compared with the share a random choice of `k` quebradas would give.
    """
    from . import integracion as ig

    a = activaciones[activaciones["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    total = cubiertas = dias = 0
    for s in temporadas_prueba:
        hoy = a[a["temporada"] == s]
        if hoy.empty:
            continue
        pi = ig.participacion(a[a["temporada"] != s], set(ubicadas), temporadas[temporadas.index != s])
        top = set(pi[pi["temporadas"] == "todas"].nlargest(k, "pi")["slug"])
        for _, g in hoy.groupby("fecha"):
            dias += 1
            total += len(g)
            cubiertas += int(g["slug"].isin(top).sum())
    return {"dias_con_huaico_ubicado": dias, "pares_activos": total, "en_top_k": cubiertas,
            "fraccion": cubiertas / max(1, total), "esperada_al_azar": k / len(ubicadas)}
