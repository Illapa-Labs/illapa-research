"""Daily "huaico day" probability: seven competing theories, nested tuning, season-out validation.

Target: a catalogued huaico day in Chosica, Chaclacayo, Santa Eulalia or Ricardo Palma, on a
rainy-season day (December to April), 1984 on. Positives are rare (about 2 % of days) and come in
clusters, so the only fair test is to leave whole seasons (or whole Niño episodes) out.

Theories (written down before looking at any score):

* T1 ``fecha``: base rate by calendar month. The model to beat.
* T2 ``lluvia_dia``: rain of the day (Chosica, upper basin, Matucana...) and its peak hours.
* T3 ``antecedentes``: everything known up to *yesterday* (soil, 7/30-day rain, discharge, sea
  surface temperature, heat and 0 °C height upstream, Amazon-side moisture). A "favourable
  regime" model that never sees the rain of the day.
* T4 ``lluvia+antecedentes``: T2 and T3 together.
* T5 ``+nino``: T4 plus the causal ICEN (previous month and previous three-month mean).
  T5b adds the season's Niño flag, which is only known by hindsight (an upper bound).
* T6 ``no_lineal``: gradient boosting on the T5 columns with very small trees, to see whether
  there are real interactions that a logistic model misses.
* T7 ``dos_etapas``: P(strong-rain day | antecedents) x P(event | strong-rain day), the second
  term learned in the training seasons only.

Regularisation (L2 or L1 and its strength) is chosen *inside* each training set by an inner
season-grouped validation, never with the test fold.

This is research on how much of the catalogue is explained by the weather. It is not an alert
and not a forecast that can be used to decide an evacuation.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import evaluacion_diaria as E
from . import nino as N
from . import predictores as P
from .catalogo import cargar_todos
from .estudio_eventos import cargar_horario

TEORIAS = ("fecha", "lluvia_dia", "antecedentes", "lluvia+antecedentes", "+nino", "no_lineal", "dos_etapas")
REJILLA_LINEAL = (("l2", 0.003), ("l2", 0.01), ("l2", 0.03), ("l2", 0.1), ("l1", 0.05), ("l1", 0.15))
REJILLA_ARBOL = (40, 100, 200)  # boosting iterations


@dataclass
class Datos:
    """Daily table restricted to the rainy season, with labels and season ids."""

    F: pd.DataFrame
    y: pd.Series
    temporada: np.ndarray
    mes: np.ndarray
    temporadas: pd.DataFrame
    inventario: dict = field(default_factory=dict)


def _cargar_predictores(datos: Path) -> tuple[dict[str, pd.DataFrame], str]:
    pred, fuente = P.cargar_con_respaldo(datos)
    return pred, "; ".join(f"{k}: {v}" for k, v in sorted(fuente.items()))


def _cargar_sst(datos: Path) -> tuple[pd.DataFrame, str]:
    final = datos / "enso" / "oisst_diario.csv"
    if final.exists():
        sst = P.cargar_sst(final)
        return sst[~sst.index.duplicated(keep="last")], "consolidado"
    return P.cargar_sst_cache(datos / "enso" / "oisst_cache"), "cache parcial"


def _icen_causal(icen: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """ICEN of the previous month and mean of the previous three months, for every day."""
    fecha = pd.to_datetime({"year": icen["anio"], "month": icen["mes"], "day": 1})
    s = icen.assign(fecha=fecha).set_index("fecha")["icen"]
    mes = s.shift(1)  # known at the start of the month: value of the month before
    tres = s.shift(1).rolling(3).mean()
    inicio = idx.to_period("M").to_timestamp()
    return pd.DataFrame({"icen_mes_previo": mes.reindex(inicio).to_numpy(),
                         "icen_3m_previos": tres.reindex(inicio).to_numpy()}, index=idx)


def cargar_datos(raiz: Path = Path("."), dias_antes: int = 0, desde: int = 1984,
                 quitar_temporadas: tuple[int, ...] = ()) -> Datos:
    """Build the feature table and labels from `datos/` (whatever is already downloaded)."""
    datos = Path(raiz) / "datos"
    pred, fuente_pred = _cargar_predictores(datos)
    sst, fuente_sst = _cargar_sst(datos)
    caudal = P.cargar_caudal(datos / "open_meteo_caudal_glofas.json")
    horario = cargar_horario(datos / "open_meteo_horario_estudio.json")
    F = P.construir(pred, caudal, sst if len(sst.columns) else None, horario)
    temporadas = N.cargar_temporadas(datos)
    icen = N.cargar_icen(datos / "enso" / "igp_icen.txt")
    F = F.join(_icen_causal(icen, F.index))
    eventos = cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)
    y = E.etiquetas(eventos, F.index, dias_antes)
    ts_todas = E.temporadas_de(F.index)
    mask = P.temporada_mask(F.index) & (F.index.year >= desde) & ~np.isin(ts_todas, quitar_temporadas)
    inventario = {
        "puntos_era5": sorted(pred), "fuente_era5": fuente_pred,
        "cajas_sst": list(sst.columns), "fuente_sst": fuente_sst,
        "caudal": list(caudal.columns), "ultimo_dia": str(F.index.max().date()),
        "columnas": int(F.shape[1]),
    }
    inventario["mask"] = mask  # features are shifted on the full calendar, then masked (see `matrices`)
    return Datos(F, y, ts_todas, np.asarray(F.index.month), temporadas, inventario)


def matrices(D: Datos) -> tuple[dict[str, pd.DataFrame], pd.Series, np.ndarray, np.ndarray]:
    """Design matrix of every theory (rainy-season rows only), labels, season ids, months."""
    F = D.F
    mask = D.inventario["mask"]
    por_familia: dict[str, list[str]] = {}
    for c in F.columns:
        if c.startswith("icen_"):
            continue
        por_familia.setdefault(P.familia(c), []).append(c)
    lluvia_dia = por_familia.get("lluvia_mismo_dia", [])
    todas = [c for c in F.columns if not c.startswith("icen_")]
    previas = F[todas].shift(1).add_suffix("_prev")
    X = {
        "lluvia_dia": F[lluvia_dia],
        "antecedentes": previas,
        "lluvia+antecedentes": pd.concat([F[lluvia_dia], previas], axis=1),
    }
    nino = F[["icen_mes_previo", "icen_3m_previos"]]
    X["+nino"] = pd.concat([X["lluvia+antecedentes"], nino], axis=1)
    X["+nino_oraculo"] = X["+nino"].assign(
        nino_temporada=D.temporadas["nino"].reindex(D.temporada).astype(float).to_numpy())
    X["no_lineal"] = X["+nino"]
    X["dos_etapas"] = X["antecedentes"]
    X = {k: v[mask] for k, v in X.items()}
    X["_lluvia_fuerte_base"] = F[["chosica_h_lluvia_3d"]][mask]
    return X, D.y[mask], D.temporada[mask], D.mes[mask]


# ---------------------------------------------------------------- fitting
def _modelo_lineal(config: tuple[str, float]):
    pen, c = config
    if pen == "l1":
        modelo = LogisticRegression(l1_ratio=1.0, C=c, solver="liblinear", max_iter=2000)
    else:
        modelo = LogisticRegression(l1_ratio=0.0, C=c, solver="lbfgs", max_iter=2000)
    return make_pipeline(StandardScaler(), modelo)


def _modelo_arbol(iteraciones: int):
    return HistGradientBoostingClassifier(
        max_depth=2, max_leaf_nodes=4, learning_rate=0.05, max_iter=iteraciones, l2_regularization=10.0,
        min_samples_leaf=40, early_stopping=False, random_state=0)


def _interno(ts: np.ndarray, k: int = 4, semilla: int = 0) -> list[tuple[np.ndarray, np.ndarray]]:
    """Season-grouped inner folds."""
    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    grupo = dict(zip(seasons, rng.permutation(len(seasons)) % k, strict=True))
    g = np.array([grupo[s] for s in ts])
    return [(np.flatnonzero(g != i), np.flatnonzero(g == i)) for i in range(k)]


def _imputar(Xtr: pd.DataFrame, *otros: pd.DataFrame) -> list[pd.DataFrame]:
    med = Xtr.median().fillna(0.0)
    return [x.fillna(med) for x in (Xtr, *otros)]


def ajustar_anidado(Xtr: pd.DataFrame, ytr: np.ndarray, ts_tr: np.ndarray, arbol: bool = False):
    """Choose the regularisation by inner season-grouped log loss, refit on the whole training set."""
    rejilla = REJILLA_ARBOL if arbol else REJILLA_LINEAL
    Xi, = _imputar(Xtr)
    puntaje = {}
    for config in rejilla:
        perdidas = []
        for a, b in _interno(ts_tr):
            if ytr[a].sum() < 3:
                continue
            m = (_modelo_arbol if arbol else _modelo_lineal)(config).fit(Xi.iloc[a], ytr[a])
            p = np.clip(m.predict_proba(Xi.iloc[b])[:, 1], 1e-6, 1 - 1e-6)
            perdidas.append(log_loss(ytr[b], p, labels=[0, 1]))
        puntaje[config] = float(np.mean(perdidas)) if perdidas else np.inf
    mejor = min(puntaje, key=puntaje.get)
    modelo = (_modelo_arbol if arbol else _modelo_lineal)(mejor).fit(Xi, ytr)
    return modelo, mejor


def _pliegue(X: pd.DataFrame, y: np.ndarray, ts: np.ndarray, test: np.ndarray, arbol: bool):
    train = np.setdiff1d(np.arange(len(y)), test)
    _, Xte = _imputar(X.iloc[train], X.iloc[test])
    modelo, config = ajustar_anidado(X.iloc[train], y[train], ts[train], arbol)
    p = modelo.predict_proba(Xte)[:, 1]
    coef = None
    if not arbol:
        coef = modelo[-1].coef_[0]
    return test, p, config, coef


@dataclass
class Resultado:
    p: np.ndarray
    configs: list
    coef: np.ndarray | None
    columnas: list[str]


def validar_anidado(X: pd.DataFrame, y: pd.Series, ts: np.ndarray, folds: list[np.ndarray],
                    arbol: bool = False, n_jobs: int = 8) -> Resultado:
    """Out-of-fold probabilities, the configuration chosen in each fold and (linear) coefficients."""
    yv = y.to_numpy()
    folds = [f for f in folds if len(f)]  # an episode outside the data window leaves an empty fold
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = Parallel(n_jobs=n_jobs)(delayed(_pliegue)(X, yv, ts, t, arbol) for t in folds)
    p = np.full(len(yv), np.nan)
    configs, coefs = [], []
    for test, pt, config, coef in out:
        p[test] = pt
        configs.append(config)
        if coef is not None:
            coefs.append(coef)
    return Resultado(p, configs, np.array(coefs) if coefs else None, list(X.columns))


def dos_etapas(Xa: pd.DataFrame, lluvia: pd.Series, y: pd.Series, ts: np.ndarray, folds: list[np.ndarray],
               cuantil: float = 0.90, n_jobs: int = 8) -> Resultado:
    """T7. Strong-rain day = 3-day Chosica rain above the training `cuantil`.

    P(event) = P(strong | antecedents) * P(event | strong) + (1 - P(strong | antecedents)) * P(event | not strong),
    the two conditional rates taken from the training seasons only.
    """
    yv = y.to_numpy()
    lv = lluvia.to_numpy(dtype=float)
    folds = [f for f in folds if len(f)]

    def un_pliegue(test):
        train = np.setdiff1d(np.arange(len(yv)), test)
        corte = np.nanquantile(lv[train], cuantil)
        fuerte = (lv >= corte).astype(int)
        modelo, config = ajustar_anidado(Xa.iloc[train], fuerte[train], ts[train])
        _, Xte = _imputar(Xa.iloc[train], Xa.iloc[test])
        pa = modelo.predict_proba(Xte)[:, 1]
        r1 = (yv[train][fuerte[train] == 1].sum() + 0.5) / ((fuerte[train] == 1).sum() + 1)
        r0 = (yv[train][fuerte[train] == 0].sum() + 0.5) / ((fuerte[train] == 0).sum() + 1)
        return test, pa * r1 + (1 - pa) * r0, config

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = Parallel(n_jobs=n_jobs)(delayed(un_pliegue)(t) for t in folds)
    p = np.full(len(yv), np.nan)
    for test, pt, _ in out:
        p[test] = pt
    return Resultado(p, [o[2] for o in out], None, list(Xa.columns))


# ---------------------------------------------------------------- metrics
def metricas_completas(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray) -> dict[str, float]:
    """Skill scores against a reference, plus hit rate with 5 % and 10 % of days in alarm."""
    m = E.metricas(y, p, p_ref, 0.05)
    ok = ~np.isnan(p)
    corte10 = np.quantile(p[ok], 0.90)
    m["aciertos_con_10pc_alarmas"] = float(y[ok][p[ok] >= corte10].sum() / y[ok].sum())
    m["logloss"] = float(log_loss(y[ok], np.clip(p[ok], 1e-6, 1 - 1e-6)))
    return m


def intervalos_por_temporada(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray, ts: np.ndarray,
                             n: int = 300, semilla: int = 0) -> pd.DataFrame:
    """Bootstrap of whole seasons: 90 % interval of every metric."""
    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    idx = {s: np.flatnonzero(ts == s) for s in seasons}
    filas = []
    for _ in range(n):
        b = np.concatenate([idx[s] for s in rng.choice(seasons, len(seasons))])
        if y[b].sum() < 3:
            continue
        filas.append(metricas_completas(y[b], p[b], p_ref[b]))
    d = pd.DataFrame(filas)
    return d.quantile([0.05, 0.5, 0.95]).T.rename(columns={0.05: "p5", 0.5: "mediana", 0.95: "p95"})


def calibracion(y: np.ndarray, p: np.ndarray, bins: int = 8) -> pd.DataFrame:
    """Mean predicted vs observed frequency in quantile bins of the prediction."""
    ok = ~np.isnan(p)
    d = pd.DataFrame({"y": y[ok], "p": p[ok]})
    d["bin"] = pd.qcut(d["p"], bins, duplicates="drop")
    g = d.groupby("bin", observed=True).agg(p_media=("p", "mean"), observado=("y", "mean"),
                                           dias=("y", "size"), eventos=("y", "sum"))
    return g.reset_index(drop=True)


def razon_observado_predicho(y: np.ndarray, p: np.ndarray) -> float:
    ok = ~np.isnan(p)
    return float(y[ok].sum() / p[ok].sum())


def estabilidad_coeficientes(res: Resultado, minimo: float = 0.8) -> pd.DataFrame:
    """Median standardised coefficient, share of folds with a non-zero value and sign agreement."""
    if res.coef is None:
        return pd.DataFrame()
    c = res.coef
    activo = (np.abs(c) > 1e-9).mean(axis=0)
    signo = np.where(c > 0, 1, np.where(c < 0, -1, 0))
    nz = signo != 0
    concordancia = np.where(nz.sum(axis=0) > 0, np.abs(signo.sum(axis=0)) / np.maximum(nz.sum(axis=0), 1), 0)
    d = pd.DataFrame({"variable": res.columnas, "coef_mediana": np.median(c, axis=0), "pliegues_activo": activo,
                      "concordancia_signo": concordancia})
    d["estable"] = (d["pliegues_activo"] >= minimo) & (d["concordancia_signo"] >= minimo)
    return d.sort_values("coef_mediana", key=np.abs, ascending=False).reset_index(drop=True)


def ap_dentro(y: np.ndarray, p: np.ndarray, grupo: np.ndarray) -> dict[str, float]:
    """Average precision and AUC inside a subset of rows (for example Niño seasons)."""
    ok = ~np.isnan(p) & grupo
    if y[ok].sum() < 3:
        return {"ap": np.nan, "auc": np.nan, "base": float(y[ok].mean()) if ok.any() else np.nan}
    return {"ap": float(average_precision_score(y[ok], p[ok])), "auc": float(roc_auc_score(y[ok], p[ok])),
            "base": float(y[ok].mean())}


def sobreajuste(X: pd.DataFrame, y: pd.Series, ts: np.ndarray, res: Resultado) -> dict[str, float]:
    """In-sample average precision of the model refit on everything vs the out-of-fold one."""
    yv = y.to_numpy()
    modelo, _ = ajustar_anidado(X, yv, ts)
    p_in = modelo.predict_proba(_imputar(X)[0])[:, 1]
    ok = ~np.isnan(res.p)
    return {"ap_dentro_de_muestra": float(average_precision_score(yv, p_in)),
            "ap_fuera_de_muestra": float(average_precision_score(yv[ok], res.p[ok])),
            "variables": int(X.shape[1]), "positivos": int(yv.sum())}


def correr_teorias(D: Datos, folds_tipo: str = "temporada", n_jobs: int = 8,
                   teorias: tuple[str, ...] = TEORIAS, con_oraculo: bool = True) -> dict[str, Resultado]:
    """Out-of-fold predictions for every theory on the same folds."""
    X, y, ts, mes = matrices(D)
    eps = N.episodios(D.temporadas) if folds_tipo == "episodio" else None
    folds = [f for f in E.pliegues(ts, folds_tipo, eps) if len(f)]
    res: dict[str, Resultado] = {}
    p_fecha = E.p_climatologia(y, mes, folds)
    res["fecha"] = Resultado(p_fecha, [], None, [])
    if "lluvia_dia" in teorias:
        res["lluvia_dia"] = validar_anidado(X["lluvia_dia"], y, ts, folds, n_jobs=n_jobs)
    if "antecedentes" in teorias:
        res["antecedentes"] = validar_anidado(X["antecedentes"], y, ts, folds, n_jobs=n_jobs)
    if "lluvia+antecedentes" in teorias:
        res["lluvia+antecedentes"] = validar_anidado(X["lluvia+antecedentes"], y, ts, folds, n_jobs=n_jobs)
    if "+nino" in teorias:
        res["+nino"] = validar_anidado(X["+nino"], y, ts, folds, n_jobs=n_jobs)
        if con_oraculo:
            res["+nino_oraculo"] = validar_anidado(X["+nino_oraculo"], y, ts, folds, n_jobs=n_jobs)
    if "no_lineal" in teorias:
        res["no_lineal"] = validar_anidado(X["no_lineal"], y, ts, folds, arbol=True, n_jobs=n_jobs)
    if "dos_etapas" in teorias:
        res["dos_etapas"] = dos_etapas(X["dos_etapas"], X["_lluvia_fuerte_base"]["chosica_h_lluvia_3d"], y, ts,
                                       folds, n_jobs=n_jobs)
    return res


def tabla_metricas(res: dict[str, Resultado], y: pd.Series) -> pd.DataFrame:
    yv = y.to_numpy()
    ref = res["fecha"].p
    filas = []
    for nombre, r in res.items():
        m = metricas_completas(yv, r.p, ref)
        m["teoria"] = nombre
        filas.append(m)
    return pd.DataFrame(filas).set_index("teoria")


# ---------------------------------------------------------------- robustness
def pliegues_bloques(ts: np.ndarray, tamano: int = 5) -> list[np.ndarray]:
    """Blocks of `tamano` consecutive seasons left out together."""
    seasons = np.unique(ts)
    return [np.flatnonzero(np.isin(ts, seasons[i : i + tamano])) for i in range(0, len(seasons), tamano)]


def _base(columna: str) -> str:
    return columna.removesuffix("_prev")


def familia_de(columna: str) -> str:
    """Feature family of a (possibly shifted) column; the ICEN columns are their own family."""
    if columna.startswith("icen_"):
        return "nino_icen"
    return P.familia(_base(columna))


def ablacion(D: Datos, quitar: str, folds_tipo: str = "temporada", n_jobs: int = 8) -> Resultado:
    """The full '+nino' model without one family of columns."""
    X, y, ts, _ = matrices(D)
    cols = [c for c in X["+nino"].columns if familia_de(c) != quitar]
    eps = N.episodios(D.temporadas) if folds_tipo == "episodio" else None
    return validar_anidado(X["+nino"][cols], y, ts, E.pliegues(ts, folds_tipo, eps), n_jobs=n_jobs)


def por_regimen(y: pd.Series, res: Resultado, ts: np.ndarray, temporadas: pd.DataFrame) -> pd.DataFrame:
    """Skill inside Niño seasons and inside the others, plus observed/predicted calibration ratio."""
    yv = y.to_numpy()
    nino = temporadas["nino"].reindex(ts).fillna(False).to_numpy(dtype=bool)
    filas = []
    for nombre, g in (("Niño", nino), ("no Niño", ~nino)):
        m = ap_dentro(yv, res.p, g)
        ok = g & ~np.isnan(res.p)
        m.update(regimen=nombre, dias=int(ok.sum()), eventos=int(yv[ok].sum()),
                 observado_sobre_predicho=razon_observado_predicho(yv[ok], res.p[ok]))
        filas.append(m)
    return pd.DataFrame(filas).set_index("regimen")


def robustez(raiz: Path, teorias: tuple[str, ...] = ("lluvia_dia", "antecedentes", "lluvia+antecedentes", "+nino"),
             n_jobs: int = 8) -> pd.DataFrame:
    """Re-run the main theories under different labels, windows and exclusions."""
    escenarios = {
        "base (1984+, día exacto)": {},
        "etiqueta del día y del anterior": {"dias_antes": 1},
        "solo 2009 en adelante": {"desde": 2009},
        "sin 1983, 1998 y 2017": {"quitar_temporadas": (1983, 1998, 2017)},
    }
    filas = []
    for nombre, kw in escenarios.items():
        D = cargar_datos(raiz, **kw)
        _, y, _, _ = matrices(D)
        res = correr_teorias(D, "temporada", n_jobs, teorias=teorias, con_oraculo=False)
        t = tabla_metricas(res, y)
        t.insert(0, "escenario", nombre)
        t["dias_con_huaico"] = int(y.sum())
        filas.append(t.reset_index())
    return pd.concat(filas, ignore_index=True)
