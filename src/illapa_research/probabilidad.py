"""Probability sheet: how likely is a catalogued huaico day, given today's conditions.

The event is exactly "a huaico day that is in the catalogue for Chosica, Chaclacayo, Santa Eulalia or
Ricardo Palma" (rainy-season days, 1984 on). The number that comes out is the historical frequency of
such days under conditions like the ones given. It is not a hazard, not an annual probability, not a
forecast for one quebrada, and not an alert.

Pre-registered choices (fixed before any score was looked at; see notebook 12):

* Reduced model: inside every training set keep the 2 columns per family with the largest
  |AUC - 0.5| (families as in `modelo_diario.familia_de`); the ICEN family keeps both columns.
  The full model keeps all columns. The reduced one is the primary model if its out-of-fold log loss is
  at most 0.001 above the full one.
* Ridge-logistic penalty C chosen inside each training set from (0.003, 0.01, 0.03, 0.1, 0.3) by 4
  season-grouped inner folds.
* Recalibration (Platt, 2 parameters) fitted only on out-of-fold logits of the *other* seasons. The
  regime-adjusted version (adds "causal ICEN mean of the previous three months >= 0.4") is adopted only
  if it improves the out-of-fold log loss by at least 1 % and brings the observed/predicted ratio of
  both regimes closer to 1.
* Bands for the reliability table: 0.5, 1, 2, 5, 10 and 25 %.

All fits are batched ridge-logistic Newton steps (the same algorithm as `gpu.ajustar_logit_lote`, with
row weights and a per-fit column mask), on the GPU when there is one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist
from scipy.stats import rankdata

from . import gpu

K_POR_FAMILIA = 2
REJILLA_C = (0.003, 0.01, 0.03, 0.1, 0.3)
BANDAS = (0.0, 0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 1.0)
N_INTERNOS = 4
UMBRAL_ICEN = 0.4
FAMILIA_NINO = "nino_icen"

LIMITES = (
    "No es una alerta ni una predicción para decidir evacuaciones. Es la frecuencia histórica de días con "
    "huaico catalogado (Chosica, Chaclacayo, Santa Eulalia y Ricardo Palma) bajo condiciones parecidas a las "
    "dadas; el catálogo está incompleto y registra sobre todo donde hay gente. No es una probabilidad anual "
    "ni de una quebrada en particular. Ante una emergencia llama al 115 (INDECI)."
)

NOMBRES_FAMILIA = {
    "lluvia_mismo_dia": "lluvia del día",
    "lluvia_previa": "lluvia de los días previos",
    "suelo": "humedad del suelo",
    "caudal": "caudal de los ríos",
    "mar": "temperatura del mar",
    "calor_altura": "temperatura en altura",
    "humedad_y_circulacion": "humedad y nubes",
    FAMILIA_NINO: "régimen El Niño (ICEN)",
}


# ------------------------------------------------------------------ data helpers
@dataclass
class Estandar:
    """Label-free standardisation of a design matrix (median imputation, then z-score)."""

    columnas: list[str]
    mediana: np.ndarray
    media: np.ndarray
    desvio: np.ndarray
    referencia: np.ndarray  # sorted imputed values per column, to turn a value into a percentile

    def z(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        A = np.asarray(X[self.columnas] if isinstance(X, pd.DataFrame) else X, dtype=float).copy()
        idx = np.where(np.isnan(A))
        A[idx] = np.take(self.mediana, idx[1])
        return (A - self.media) / self.desvio

    def percentil(self, j: int, valor: float) -> float:
        ref = self.referencia[:, j]
        return float(100.0 * np.searchsorted(ref, valor, side="right") / len(ref))


def ajustar_estandar(X: pd.DataFrame) -> tuple[np.ndarray, Estandar]:
    A = X.to_numpy(dtype=float).copy()
    med = np.nanmedian(A, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    idx = np.where(np.isnan(A))
    A[idx] = np.take(med, idx[1])
    mu, sd = A.mean(axis=0), A.std(axis=0)
    sd[sd == 0] = 1.0
    est = Estandar(list(X.columns), med, mu, sd, np.sort(A, axis=0))
    return (A - mu) / sd, est


def auc_abs(Z: np.ndarray, y: np.ndarray) -> np.ndarray:
    """|AUC - 0.5| of every column of Z against y (rank formula, ties averaged)."""
    n1 = float(y.sum())
    n0 = float(len(y) - n1)
    if n1 < 2 or n0 < 2:
        return np.zeros(Z.shape[1])
    r = rankdata(Z, axis=0)
    auc = (r[y == 1].sum(axis=0) - n1 * (n1 + 1) / 2) / (n1 * n0)
    return np.abs(auc - 0.5)


def seleccionar(Z: np.ndarray, y: np.ndarray, familias: np.ndarray, k: int = K_POR_FAMILIA) -> np.ndarray:
    """Boolean mask keeping the top `k` columns of each family by |AUC - 0.5| on these rows."""
    fuerza = auc_abs(Z, y)
    mask = np.zeros(Z.shape[1], dtype=bool)
    for f in np.unique(familias):
        cols = np.flatnonzero(familias == f)
        mejores = cols[np.argsort(-fuerza[cols], kind="stable")[:k]]
        mask[mejores] = True
    return mask


# ------------------------------------------------------------------ batched ridge-logistic fits
def ajustar_lote(
    Z: np.ndarray, y: np.ndarray, W: np.ndarray, M: np.ndarray, lam: np.ndarray, iteraciones: int = 20,
    dispositivo: str | None = None, trozo: int = 192,
) -> np.ndarray:
    """B ridge-logistic fits in one pass; returns coefficients (B, d + 1) with the intercept last.

    W (B, n): row weights (0/1 for folds, counts for bootstraps). M (B, d): columns each fit may use.
    lam (B,): ridge strength 1 / C (the intercept is not penalised). Objective per fit:
    sum_i W_i logloss_i + lam / 2 |beta|^2, same as scikit-learn's `C = 1 / lam`.
    """
    torch = gpu.torch
    dev = gpu.dispositivo(dispositivo)
    dt = torch.float64 if dev == "cpu" else torch.float32
    n, d = Z.shape
    D = d + 1
    Xb = torch.cat([torch.as_tensor(Z, dtype=dt), torch.ones(n, 1, dtype=dt)], dim=1).to(dev)
    X2 = (Xb[:, :, None] * Xb[:, None, :]).reshape(n, D * D)
    yt = torch.as_tensor(y, dtype=dt, device=dev)
    out = np.empty((W.shape[0], D))
    for i in range(0, W.shape[0], trozo):
        w = torch.as_tensor(W[i : i + trozo], dtype=dt, device=dev)
        m = torch.cat([torch.as_tensor(M[i : i + trozo], dtype=dt, device=dev),
                       torch.ones(w.shape[0], 1, dtype=dt, device=dev)], dim=1)
        pen = torch.as_tensor(lam[i : i + trozo], dtype=dt, device=dev)[:, None] * torch.ones(1, D, dtype=dt, device=dev)
        pen[:, -1] = 0.0
        b = torch.zeros(w.shape[0], D, dtype=dt, device=dev)
        for _ in range(iteraciones):
            p = torch.sigmoid(b @ Xb.T).clamp(1e-7, 1 - 1e-7)
            g = (((p - yt) * w) @ Xb + b * pen) * m
            wt = w * p * (1 - p) + 1e-9 * w
            H = (wt @ X2).reshape(-1, D, D) * (m[:, :, None] * m[:, None, :])
            H = H + torch.diag_embed(pen * m + (1 - m) + 1e-8)
            b = b - torch.linalg.solve(H, g[:, :, None])[:, :, 0] * m
        out[i : i + trozo] = b.cpu().numpy()
    return out


def logits(Z: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Linear predictors of every fit (B, d + 1) on every row of Z: shape (B, n)."""
    return beta[:, :-1] @ Z.T + beta[:, -1:]


def _logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _sigm(x):
    return 1.0 / (1.0 + np.exp(-x))


# ------------------------------------------------------------------ leave-one-season-out, nested
@dataclass
class ResultadoLOSO:
    logit: np.ndarray  # out-of-fold linear predictor, (n,)
    c_elegida: dict[int, float] = field(default_factory=dict)
    columnas_por_temporada: dict[int, np.ndarray] = field(default_factory=dict)


def loso_anidado(
    Z: np.ndarray, y: np.ndarray, ts: np.ndarray, familias: np.ndarray, reducido: bool, semilla: int = 0,
    dispositivo: str | None = None,
) -> ResultadoLOSO:
    """Out-of-fold linear predictor of every day, leaving each season out, with C chosen inside."""
    n, d = Z.shape
    temporadas = np.unique(ts)
    rng = np.random.default_rng(semilla)
    W, M, lam, info = [], [], [], []
    for s in temporadas:
        train = ts != s
        otras = temporadas[temporadas != s]
        grupo = dict(zip(otras, rng.permutation(len(otras)) % N_INTERNOS, strict=True))
        g = np.array([grupo.get(t, -1) for t in ts])
        for j in range(N_INTERNOS):
            fit = train & (g != j)
            test = train & (g == j)
            mask = seleccionar(Z[fit], y[fit], familias) if reducido else np.ones(d, dtype=bool)
            for c in REJILLA_C:
                W.append(fit.astype(float))
                M.append(mask)
                lam.append(1.0 / c)
                info.append((s, c, test))
    beta_i = ajustar_lote(Z, y, np.array(W), np.array(M), np.array(lam), dispositivo=dispositivo)
    perdidas: dict[tuple[int, float], list[float]] = {}
    for b, (s, c, test) in zip(beta_i, info, strict=True):
        p = _sigm(b[:-1] @ Z[test].T + b[-1])
        perdidas.setdefault((s, c), []).append(_logloss(y[test], p))
    res = ResultadoLOSO(np.full(n, np.nan))
    W2, M2, lam2 = [], [], []
    for s in temporadas:
        mejor = min(REJILLA_C, key=lambda c: float(np.mean(perdidas[(s, c)])))
        res.c_elegida[int(s)] = mejor
        train = ts != s
        mask = seleccionar(Z[train], y[train], familias) if reducido else np.ones(d, dtype=bool)
        res.columnas_por_temporada[int(s)] = mask
        W2.append(train.astype(float))
        M2.append(mask)
        lam2.append(1.0 / mejor)
    beta_o = ajustar_lote(Z, y, np.array(W2), np.array(M2), np.array(lam2), dispositivo=dispositivo)
    for s, b in zip(temporadas, beta_o, strict=True):
        i = ts == s
        res.logit[i] = Z[i] @ b[:-1] + b[-1]
    return res


# ------------------------------------------------------------------ calibration
@dataclass
class Calibrador:
    a: float
    b: float
    c: float = 0.0  # regime coefficient (0 when not used)

    def __call__(self, logit: np.ndarray, regimen: np.ndarray | None = None) -> np.ndarray:
        r = 0.0 if regimen is None else self.c * np.asarray(regimen, dtype=float)
        return _sigm(self.a + self.b * np.asarray(logit) + r)


def ajustar_calibrador(logit: np.ndarray, y: np.ndarray, regimen: np.ndarray | None = None) -> Calibrador:
    from sklearn.linear_model import LogisticRegression

    X = logit[:, None] if regimen is None else np.column_stack([logit, regimen])
    m = LogisticRegression(C=1e4, max_iter=2000).fit(X, y)
    return Calibrador(float(m.intercept_[0]), float(m.coef_[0, 0]), float(m.coef_[0, 1]) if regimen is not None else 0.0)


def calibrar_loso(
    logit: np.ndarray, y: np.ndarray, ts: np.ndarray, regimen: np.ndarray | None = None
) -> np.ndarray:
    """Calibrated probability of every day, each season calibrated with the other seasons' logits only."""
    p = np.full(len(y), np.nan)
    for s in np.unique(ts):
        i = ts == s
        cal = ajustar_calibrador(logit[~i], y[~i], None if regimen is None else regimen[~i])
        p[i] = cal(logit[i], None if regimen is None else regimen[i])
    return p


# ------------------------------------------------------------------ metrics
def wilson(k: int, n: int, z: float = 1.2816) -> tuple[float, float]:
    """80 % Wilson interval of a binomial share."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    mitad = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(centro - mitad), float(centro + mitad)


def tabla_bandas(y: np.ndarray, p: np.ndarray, bandas: tuple[float, ...] = BANDAS) -> pd.DataFrame:
    """Resolution table: days in each probability band and the share that had a huaico."""
    filas = []
    for lo, hi in pairwise(bandas):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        k, n = int(y[m].sum()), int(m.sum())
        l80, h80 = wilson(k, n)
        filas.append({"banda": f"{lo:.1%} a {hi:.1%}", "desde": lo, "hasta": hi, "dias": n, "con_huaico": k,
                      "fraccion": k / n if n else float("nan"), "ic80_bajo": l80, "ic80_alto": h80,
                      "prob_media": float(p[m].mean()) if n else float("nan")})
    return pd.DataFrame(filas)


def curva_fiabilidad(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Reliability by quantile bins of the predicted probability."""
    q = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, len(q) - 2)
    filas = []
    for b in range(len(q) - 1):
        m = idx == b
        k, n = int(y[m].sum()), int(m.sum())
        lo, hi = wilson(k, n)
        filas.append({"bin": b, "prob_media": float(p[m].mean()), "frec_observada": k / n, "dias": n,
                      "con_huaico": k, "ic80_bajo": lo, "ic80_alto": hi})
    return pd.DataFrame(filas)


def metricas(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray | None = None) -> dict[str, float]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    out = {"brier": float(np.mean((p - y) ** 2)), "logloss": _logloss(y, p), "ap": float(average_precision_score(y, p)),
           "auc": float(roc_auc_score(y, p)), "base": float(y.mean()), "obs_sobre_pred": float(y.sum() / p.sum())}
    if p_ref is not None:
        out["brier_skill"] = float(1 - out["brier"] / np.mean((p_ref - y) ** 2))
    return out


def metricas_por_grupo(y: np.ndarray, p: np.ndarray, grupos: dict[str, np.ndarray]) -> pd.DataFrame:
    filas = []
    for nombre, m in grupos.items():
        if m.sum() == 0 or y[m].sum() == 0:
            continue
        r = metricas(y[m], p[m])
        r.update(grupo=nombre, dias=int(m.sum()), con_huaico=int(y[m].sum()))
        filas.append(r)
    return pd.DataFrame(filas).set_index("grupo")


# ------------------------------------------------------------------ bootstrap ensemble
@dataclass
class Ensamble:
    beta: np.ndarray  # (B, d + 1)
    cuentas: np.ndarray  # (B, n_temporadas) times each season was drawn
    temporadas: np.ndarray


def bootstrap_temporadas(
    Z: np.ndarray, y: np.ndarray, ts: np.ndarray, familias: np.ndarray, c: float, reducido: bool, n: int = 500,
    semilla: int = 0, dispositivo: str | None = None,
) -> Ensamble:
    """Models refitted on `n` resamples of whole seasons (the resampling unit that keeps clusters intact)."""
    rng = np.random.default_rng(semilla)
    temporadas = np.unique(ts)
    cuentas = np.stack([np.bincount(rng.integers(0, len(temporadas), len(temporadas)), minlength=len(temporadas))
                        for _ in range(n)])
    idx_t = np.searchsorted(temporadas, ts)
    W = cuentas[:, idx_t].astype(float)
    M = np.stack([seleccionar(Z[w > 0], y[w > 0], familias) if reducido else np.ones(Z.shape[1], dtype=bool)
                  for w in W])
    beta = ajustar_lote(Z, y, W, M, np.full(n, 1.0 / c), dispositivo=dispositivo)
    return Ensamble(beta, cuentas, temporadas)


def intervalo_fuera_de_bolsa(
    ens: Ensamble, Z: np.ndarray, ts: np.ndarray, cal: Calibrador, regimen: np.ndarray | None = None,
    nivel: tuple[float, float] = (10, 90),
) -> tuple[np.ndarray, np.ndarray]:
    """80 % interval of each day's calibrated probability from the replicates that did not see its season."""
    lo = np.full(len(ts), np.nan)
    hi = np.full(len(ts), np.nan)
    for k, s in enumerate(ens.temporadas):
        fuera = ens.cuentas[:, k] == 0
        i = ts == s
        if fuera.sum() < 20 or not i.any():
            continue
        lg = logits(Z[i], ens.beta[fuera])  # (replicates, days)
        pr = cal(lg, None if regimen is None else regimen[i][None, :])
        lo[i], hi[i] = np.percentile(pr, nivel, axis=0)
    return lo, hi


# ------------------------------------------------------------------ plain-language factors
_ESTACION = {"ch": "Chosica", "chosica": "Chosica", "sea": "Santa Eulalia alta", "mat": "Matucana", "tic": "Ticlio",
             "cuenca-alta": "la cuenca alta", "selva": "la selva de Tarma", "costa": "la costa de Lima",
             "gradiente": "el gradiente de presión Chosica-selva"}
_VARIABLE = [
    (r"lluvia_1d", "lluvia del día"), (r"lluvia_3d", "lluvia de 3 días"), (r"lluvia_hmax|h_pico", "pico horario de lluvia"),
    (r"h_3h_max", "máximo de lluvia en 3 horas"), (r"lluvia_7d_previa", "lluvia de los 7 días previos"),
    (r"lluvia_30d_previa", "lluvia de los 30 días previos"), (r"suelo", "humedad del suelo"),
    (r"temp_cambio_3d", "cambio de temperatura en 3 días"), (r"temp_anom", "temperatura"),
    (r"cero_anom", "altura de la isoterma de 0 °C"), (r"nieve_7d", "nieve de los 7 días previos"),
    (r"radiacion_anom", "radiación solar"), (r"punto_rocio", "punto de rocío"), (r"nubes", "nubosidad"),
    (r"hum_rel", "humedad relativa"), (r"vpd", "déficit de presión de vapor"), (r"viento", "viento"),
    (r"caudal_.*_anom", "caudal"), (r"caudal_.*_alza_3d", "alza de caudal en 3 días"),
    (r"caudal_.*_max_7d", "máximo de caudal en 7 días"),
    (r"sst_(.*)_alza_(\d+)d", "alza de la temperatura del mar"), (r"sst_.*_anom_30d", "temperatura del mar (media de 30 días)"),
    (r"sst_.*_anom_7d", "temperatura del mar (media de 7 días)"), (r"sst_.*_anom", "temperatura del mar"),
    (r"icen_3m", "ICEN medio de los 3 meses previos"), (r"icen_mes", "ICEN del mes previo"),
]
_MAR = {"nino12": "región Niño 1+2", "costa_peru": "costa de Perú", "costa_lima": "costa de Lima"}


def describir(columna: str) -> str:
    """Short Spanish name of a feature column (with the station and, for lags, 'del día anterior')."""
    base = columna.removesuffix("_prev")
    previo = columna.endswith("_prev")
    nombre = None
    for patron, texto in _VARIABLE:
        if re.search(patron, base):
            nombre = texto
            break
    nombre = nombre or base.replace("_", " ")
    lugar = ""
    if base.startswith("sst_"):
        for k, v in _MAR.items():
            if base.startswith(f"sst_{k}"):
                lugar = f" ({v})"
    elif base.startswith("caudal_"):
        lugar = " del Rímac" if "rimac" in base else " de Santa Eulalia"
    elif not base.startswith("icen"):
        for pref, v in _ESTACION.items():
            if base.startswith(pref + "_") or base == pref:
                lugar = f" en {v}" if not v.startswith("el ") else f" ({v})"
                break
    return f"{nombre}{lugar}" + (" (del día anterior)" if previo else "")


# ------------------------------------------------------------------ the fitted sheet
@dataclass
class ModeloProbabilidad:
    estandar: Estandar
    familias: np.ndarray
    beta: np.ndarray  # final model (d + 1)
    ensamble: Ensamble
    calibrador: Calibrador
    usa_regimen: bool
    reducido: bool
    c: float
    bandas: pd.DataFrame  # reliability / resolution table from out-of-fold probabilities
    pi: pd.DataFrame | None = None  # integracion.participacion output
    ubicadas: dict[str, int] = field(default_factory=dict)  # slug -> located activation days
    nombres: dict[str, str] = field(default_factory=dict)
    datos: str = ""

    def _regimen(self, features: pd.Series) -> float | None:
        if not self.usa_regimen:
            return None
        v = features.get("icen_3m_previos", np.nan)
        return float(v >= UMBRAL_ICEN) if not pd.isna(v) else 0.0


def ajustar_modelo(
    X: pd.DataFrame, y: np.ndarray, ts: np.ndarray, familias: np.ndarray, reducido: bool, c: float,
    usa_regimen: bool, regimen: np.ndarray | None, cal: Calibrador, bandas: pd.DataFrame, n_boot: int = 500,
    dispositivo: str | None = None, datos: str = "",
) -> ModeloProbabilidad:
    Z, est = ajustar_estandar(X)
    mask = seleccionar(Z, y, familias) if reducido else np.ones(Z.shape[1], dtype=bool)
    beta = ajustar_lote(Z, y, np.ones((1, len(y))), mask[None, :], np.array([1.0 / c]), dispositivo=dispositivo)[0]
    ens = bootstrap_temporadas(Z, y, ts, familias, c, reducido, n_boot, dispositivo=dispositivo)
    return ModeloProbabilidad(est, familias, beta, ens, cal, usa_regimen, reducido, c, bandas, datos=datos)


def _banda(modelo: ModeloProbabilidad, p: float) -> dict:
    b = modelo.bandas
    fila = b[(b["desde"] <= p) & ((b["hasta"] > p) | (b["hasta"] >= 1.0))].iloc[0]
    return {"banda": fila["banda"], "dias_historicos": int(fila["dias"]), "con_huaico": int(fila["con_huaico"]),
            "fraccion_observada": float(fila["fraccion"]), "ic80": (float(fila["ic80_bajo"]), float(fila["ic80_alto"]))}


def _factores(modelo: ModeloProbabilidad, z: np.ndarray, X: pd.Series, top: int = 5) -> list[dict]:
    """Largest upward pushes on the logit relative to an average rainy-season day, grouped by family."""
    est = modelo.estandar
    b = modelo.beta[:-1]
    aporte = b * z
    cols = est.columnas
    fams = [f for f in np.unique(modelo.familias)]
    reps = {f: int(np.flatnonzero(modelo.familias == f)[np.argmax(aporte[modelo.familias == f])]) for f in fams}
    # stability: how often each family is the top family among the bootstrap models
    filas = []
    for f in fams:
        suma = float(aporte[modelo.familias == f].sum())
        j = reps[f]
        valor = X.get(cols[j], np.nan)
        pct = est.percentil(j, est.mediana[j] if pd.isna(valor) else valor)
        bs = modelo.ensamble.beta[:, :-1]
        aportes_b = (bs[:, modelo.familias == f] * z[modelo.familias == f]).sum(axis=1)
        filas.append({"familia": f, "familia_texto": NOMBRES_FAMILIA.get(f, f), "aporte_logit": suma,
                      "variable": cols[j], "texto": f"{describir(cols[j])}: percentil {pct:.0f} de los días de temporada",
                      "estabilidad": float((aportes_b > 0).mean())})
    filas.sort(key=lambda r: -r["aporte_logit"])
    return [r for r in filas if r["aporte_logit"] > 0][:top]


def ficha(
    modelo: ModeloProbabilidad, features: pd.Series, regimen_nino: bool | None = None, top: int = 5,
) -> dict:
    """Probability sheet for one day. `features` holds the model's columns (as built by `matrices`)."""
    est = modelo.estandar
    z = est.z(features.reindex(est.columnas).to_numpy(dtype=float)[None, :])[0]
    m = modelo.beta[:-1] != 0
    lg = float(z[m] @ modelo.beta[:-1][m] + modelo.beta[-1])
    reg = modelo._regimen(features)
    p = float(modelo.calibrador(np.array([lg]), None if reg is None else np.array([reg]))[0])
    lgb = logits(z[None, :], modelo.ensamble.beta)[:, 0]
    pb = modelo.calibrador(lgb, None if reg is None else np.full(len(lgb), reg))
    lo, hi = (float(v) for v in np.percentile(pb, [10, 90]))
    es_nino = (reg == 1.0) if regimen_nino is None else regimen_nino
    out = {"probabilidad": p, "intervalo_80": (lo, hi), "banda_de_fiabilidad": _banda(modelo, p),
           "factores_favorables": _factores(modelo, z, features, top), "regimen_nino": bool(es_nino),
           "limites": LIMITES, "evento": "día con huaico catalogado en Chosica, Chaclacayo, Santa Eulalia o Ricardo Palma"}
    if modelo.pi is not None:
        t = modelo.pi
        etiqueta = "nino" if es_nino else "no_nino"
        filas = []
        for slug, n_dias in modelo.ubicadas.items():
            a = t[(t["slug"] == slug) & (t["temporadas"] == etiqueta)].iloc[0]
            filas.append({"slug": slug, "nombre": modelo.nombres.get(slug, slug), "probabilidad": p * float(a["pi"]),
                          "intervalo_80": (lo * float(a["pi_p10"]), hi * float(a["pi_p90"])),
                          "participacion": float(a["pi"]), "dias_historicos": n_dias,
                          "evidencia": "historial" if n_dias >= 3 else "solo reparto genérico"})
        out["quebradas"] = sorted(filas, key=lambda r: -r["probabilidad"])
        out["nota_quebradas"] = ("Probabilidad de que la quebrada aparezca en el catálogo ese día = P(día) × participación "
                                 "histórica. La participación sigue a la exposición y al reporte, no solo al terreno; las "
                                 "cuencas sin historial ubicado no se estiman.")
    return out


def beta_interval(k: int, n: int, nivel: float = 0.8) -> tuple[float, float]:
    lo, hi = beta_dist.ppf([(1 - nivel) / 2, 1 - (1 - nivel) / 2], k + 0.5, n - k + 0.5)
    return float(lo), float(hi)


# ------------------------------------------------------------------ season bootstrap of a band table
def bandas_bootstrap(
    y: np.ndarray, p: np.ndarray, ts: np.ndarray, n: int = 1000, semilla: int = 0, bandas: tuple[float, ...] = BANDAS
) -> pd.DataFrame:
    """Observed share per band with a 80 % interval that resamples whole seasons (days are not independent)."""
    rng = np.random.default_rng(semilla)
    temporadas = np.unique(ts)
    idx = {s: np.flatnonzero(ts == s) for s in temporadas}
    base = tabla_bandas(y, p, bandas)
    fr = np.full((n, len(base)), np.nan)
    for b in range(n):
        sel = np.concatenate([idx[s] for s in rng.choice(temporadas, len(temporadas))])
        t = tabla_bandas(y[sel], p[sel], bandas)
        fr[b] = t["fraccion"].to_numpy()
    base["ic80_temporadas_bajo"] = np.nanpercentile(fr, 10, axis=0)
    base["ic80_temporadas_alto"] = np.nanpercentile(fr, 90, axis=0)
    return base


def aportes_por_familia(modelo: ModeloProbabilidad, Z: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """Mean logit contribution of each family on event days and on the other days, with stability.

    Stability = share of the bootstrap models in which the family pushes event days higher than other days.
    """
    filas = []
    for f in np.unique(modelo.familias):
        cols = modelo.familias == f
        a_final = Z[:, cols] @ modelo.beta[:-1][cols]
        ab = Z[:, cols] @ modelo.ensamble.beta[:, :-1][:, cols].T  # (days, replicates)
        dif_b = ab[y == 1].mean(axis=0) - ab[y == 0].mean(axis=0)
        filas.append({"familia": f, "texto": NOMBRES_FAMILIA.get(f, f), "aporte_dias_huaico": float(a_final[y == 1].mean()),
                      "aporte_otros_dias": float(a_final[y == 0].mean()),
                      "diferencia": float(a_final[y == 1].mean() - a_final[y == 0].mean()),
                      "estabilidad": float((dif_b > 0).mean())})
    return pd.DataFrame(filas).sort_values("diferencia", ascending=False).set_index("familia")


# ------------------------------------------------------------------ the whole analysis
def correr(raiz=".", n_boot: int = 500, dispositivo: str | None = None, verboso: bool = True) -> dict:
    """Run the full pre-registered analysis on the data in `raiz/datos` and `raiz/catalogo`."""
    from pathlib import Path

    from . import evaluacion_diaria as E
    from . import filtro, integracion, quebradas
    from . import modelo_diario as md
    from .catalogo import CATALOGO, cargar_cuencas, cargar_todos

    def say(*a):
        if verboso:
            print(*a, flush=True)

    raiz = Path(raiz)
    D = md.cargar_datos(raiz)
    X, y_s, ts, mes = md.matrices(D)
    Xa = X["+nino"]
    y = y_s.to_numpy(dtype=float)
    fam = np.array([md.familia_de(c) for c in Xa.columns])
    reg = (Xa["icen_3m_previos"].to_numpy(dtype=float) >= UMBRAL_ICEN).astype(float)
    reg = np.nan_to_num(reg)
    Z, est = ajustar_estandar(Xa)
    say("datos:", Xa.shape, int(y.sum()), "positivos;", D.inventario["fuente_era5"][:120])
    temporadas = D.temporadas
    nino_s = temporadas["nino"].reindex(ts).fillna(False).to_numpy(dtype=bool)

    res = {"completo": loso_anidado(Z, y, ts, fam, False, dispositivo=dispositivo),
           "reducido": loso_anidado(Z, y, ts, fam, True, dispositivo=dispositivo)}
    plata = {k: calibrar_loso(r.logit, y, ts) for k, r in res.items()}
    tabla_modelos = pd.DataFrame({k: metricas(y, plata[k]) for k in res}).T
    tabla_modelos["logloss_sin_calibrar"] = [_logloss(y, _sigm(res[k].logit)) for k in res]
    primario = "reducido" if tabla_modelos.loc["reducido", "logloss"] <= tabla_modelos.loc["completo", "logloss"] + 0.001 else "completo"
    say("modelo primario:", primario)
    r = res[primario]
    p_plano = plata[primario]
    p_reg = calibrar_loso(r.logit, y, ts, reg)
    mejora = 1 - _logloss(y, p_reg) / _logloss(y, p_plano)

    def razones(p):
        return {"Niño": float(y[nino_s].sum() / p[nino_s].sum()), "no Niño": float(y[~nino_s].sum() / p[~nino_s].sum()),
                "régimen causal (ICEN>=0,4)": float(y[reg == 1].sum() / p[reg == 1].sum()),
                "régimen causal (ICEN<0,4)": float(y[reg == 0].sum() / p[reg == 0].sum())}

    rz_plano, rz_reg = razones(p_plano), razones(p_reg)
    mas_cerca = all(abs(np.log(rz_reg[k])) < abs(np.log(rz_plano[k])) for k in ("Niño", "no Niño"))
    usa_regimen = bool(mejora >= 0.01 and mas_cerca)
    p_oof = p_reg if usa_regimen else p_plano
    say(f"regimen: mejora logloss {mejora:.3%}, razones {rz_plano} -> {rz_reg}, adoptado={usa_regimen}")
    c_mod = float(pd.Series(list(r.c_elegida.values())).mode().iloc[0])
    cal = ajustar_calibrador(r.logit, y, reg if usa_regimen else None)
    bandas = bandas_bootstrap(y, p_oof, ts)
    modelo = ajustar_modelo(Xa, y, ts, fam, primario == "reducido", c_mod, usa_regimen, reg, cal, bandas.copy(),
                            n_boot=n_boot, dispositivo=dispositivo,
                            datos=f"ERA5 6 puntos, ICEN, catálogo; {int(y.sum())} días con huaico en {len(y)} días")
    lo, hi = intervalo_fuera_de_bolsa(modelo.ensamble, Z, ts, cal, reg if usa_regimen else None)
    say("modelo final ajustado; C =", c_mod, "columnas usadas:", int((modelo.beta[:-1] != 0).sum()))

    folds = E.pliegues(ts, "temporada")
    p_clim = E.p_climatologia(pd.Series(y), mes, folds)
    glob = metricas(y, p_oof, p_clim)
    era = np.where(ts <= 1998, "1984-1998", np.where(ts <= 2008, "1999-2008", "2009-2026"))
    grupos = {"todas": np.ones(len(y), dtype=bool), "Niño (temporada)": nino_s, "no Niño (temporada)": ~nino_s,
              "1984-1998": era == "1984-1998", "1999-2008": era == "1999-2008", "2009-2026": era == "2009-2026",
              "sin 1983, 1998 y 2017 (mismos modelos)": ~np.isin(ts, (1983, 1998, 2017))}
    por_grupo = metricas_por_grupo(y, p_oof, grupos)
    # retrained without the three biggest clusters
    keep = ~np.isin(ts, (1983, 1998, 2017))
    r2 = loso_anidado(Z[keep], y[keep], ts[keep], fam, primario == "reducido", dispositivo=dispositivo)
    p2 = calibrar_loso(r2.logit, y[keep], ts[keep], reg[keep] if usa_regimen else None)
    sin_racimos = metricas(y[keep], p2)
    say("métricas globales:", {k: round(v, 4) for k, v in glob.items()})

    # quebradas
    cuencas = filtro.cuencas_a_tabla(cargar_cuencas())
    refs = quebradas.cargar_referencias(CATALOGO / "quebradas_referencias.csv")
    eventos = cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)
    hist = filtro.asignar_historial(eventos, refs, cuencas)
    ranking = filtro.tabla(cuencas, hist, temporadas)
    ubic = sorted(ranking.loc[ranking.evidencia == "fisica+historial", "slug"])
    pi = integracion.participacion(hist.activaciones, set(ubic), temporadas)
    todas = pi[pi.temporadas == "todas"].set_index("slug")
    modelo.pi = pi
    modelo.ubicadas = {s: int(todas.loc[s, "dias_activa"]) for s in ubic}
    modelo.nombres = {c.slug: (c.nombre or c.slug) for c in cuencas.itertuples()}
    p_dia = pd.Series(p_oof, index=y_s.index)
    pares = integracion.validar_pares(p_dia, hist.activaciones, ubic, pd.Series(ts, index=y_s.index), temporadas)

    return {"D": D, "X": Xa, "y": y, "ts": ts, "mes": mes, "Z": Z, "familias": fam, "modelo": modelo, "primario": primario,
            "tabla_modelos": tabla_modelos, "c_elegidas": pd.Series(r.c_elegida), "p_oof": p_oof, "p_plano": p_plano, "p_reg": p_reg,
            "razones_plano": rz_plano, "razones_regimen": rz_reg, "mejora_regimen": mejora, "usa_regimen": usa_regimen,
            "intervalo": (lo, hi), "global": glob, "por_grupo": por_grupo, "sin_racimos_reentrenado": sin_racimos,
            "bandas": bandas, "fiabilidad": curva_fiabilidad(y, p_oof), "aportes": aportes_por_familia(modelo, Z, y),
            "pi": pi, "pares": pares, "ranking": ranking, "ubicadas": ubic, "nino_temporada": nino_s, "regimen_causal": reg,
            "p_clim": p_clim, "calibrador": cal, "est": est}
