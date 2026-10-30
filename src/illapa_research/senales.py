"""Signals and lags: which conditions, how many days before, go with a huaico day?

Everything here is descriptive and tested against nulls. Positives are few and cluster, so:

* AUC of a feature at lag L is judged against labels cyclically shifted inside each season
  (same number of events and same clustering, no link with the weather);
* the many (variable x lag) tests are corrected with Benjamini-Hochberg and the expected number
  of chance hits is reported;
* event composites group consecutive days into one episode, so 2017 (23 days) counts once.

Lag 0 is the day itself: it describes the storm, it is not a precursor. Only lag >= 1 is
information available before the day.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from . import evaluacion_diaria as ev_d
from . import predictores as P
from .catalogo import Evento

# Pre-registered hypotheses: columns are selected by regular expression on the feature name.
HIPOTESIS: dict[str, dict[str, str]] = {
    "H1": {
        "texto": "La temperatura del mar (anomalía y alza de 3/7/14 días) sube días antes del huaico.",
        "patron": r"^sst_",
    },
    "H2": {
        "texto": "El calor aguas arriba (anomalía de temperatura y de la isoterma de 0 °C, nieve) precede "
        "al huaico o al aumento de caudal.",
        "patron": r"^(tic|sea|mat)_(temp_anom|cero_anom|temp_cambio|nieve)",
    },
    "H3": {
        "texto": "La humedad de la selva (punto de rocío, nubes) y el gradiente de presión selva-costa "
        "preceden al huaico.",
        "patron": r"^(selva_|costa_|gradiente_)",
    },
    "H4": {
        "texto": "El caudal de GloFAS y la humedad del suelo señalan condiciones previas.",
        "patron": r"^(caudal_|.*suelo)",
    },
    "H5": {
        "texto": "El efecto del mar es de régimen lento (interanual) y no un disparador diario: al quitar "
        "la media de cada temporada su señal desaparece.",
        "patron": r"^sst_",
    },
}
LLUVIA = r"(lluvia|_h_pico|_h_3h_max)"


def columnas_de(F: pd.DataFrame, hipotesis: str) -> list[str]:
    patron = re.compile(HIPOTESIS[hipotesis]["patron"])
    return [c for c in F.columns if patron.search(c) and not re.search(LLUVIA, c)]


def cargar_matriz(datos: Path, eventos: list[Evento], rellenar_con_power: bool = False) -> dict:
    """Daily feature matrix, labels and what was available.

    Reads the final ERA5 file when `descargar-datos` finished, or the per-point cache otherwise,
    and every OISST box whose yearly files are complete.
    """
    from . import estudio_eventos as ee

    pred, _fuente = P.cargar_con_respaldo(datos, rellenar_con_power=rellenar_con_power)
    diario = datos / "enso" / "oisst_diario.csv"
    sst = P.cargar_sst(diario) if diario.exists() else P.cargar_sst_cache(datos / "enso" / "oisst_cache")
    caudal = P.cargar_caudal(datos / "open_meteo_caudal_glofas.json")
    horario = ee.cargar_horario(datos / "open_meteo_horario_estudio.json")
    F = P.construir(pred, caudal, sst, horario)
    y = ev_d.etiquetas(eventos, F.index)
    ts = ev_d.temporadas_de(F.index)
    mask = P.temporada_mask(F.index) & (F.index.year >= 1984)
    return {
        "F": F, "y": y, "temporada": ts, "mask": mask,
        "puntos_era5": sorted(pred), "fuentes_era5": _fuente, "cajas_sst": list(sst.columns),
        "ultimo_dia": F.index.max(),
    }


# ---------------------------------------------------------------- fast AUC and permutation nulls
def _rangos_lag(F: pd.DataFrame, columnas: list[str], lag: int, mask: np.ndarray, temporada: np.ndarray,
                centrar: bool) -> tuple[np.ndarray, np.ndarray]:
    """(ranks with NaN -> 0, valid indicator) of lagged features over the masked rows."""
    X = F[columnas].shift(lag)
    X = X[mask]
    if centrar:
        X = ev_d.centrar_por_temporada(X, temporada[mask])
    V = X.notna().to_numpy()
    R = np.zeros(X.shape)
    for j in range(X.shape[1]):
        v = V[:, j]
        if v.sum() > 10:
            R[v, j] = rankdata(X.iloc[:, j].to_numpy()[v])
    return R, V.astype(float)


def _auc_desde_rangos(y: np.ndarray, R: np.ndarray, V: np.ndarray) -> np.ndarray:
    n1 = y @ V
    n0 = V.sum(axis=0) - n1
    s = y @ R
    with np.errstate(invalid="ignore", divide="ignore"):
        a = (s - n1 * (n1 + 1) / 2) / (n1 * n0)
    a[(n1 < 5) | (n0 < 5)] = np.nan
    return a


def _auc_lote(Y: np.ndarray, R: np.ndarray, V: np.ndarray, torch_: bool = False) -> np.ndarray:
    """AUC of every label row of `Y` (B, n) for every feature column: shape (B, features).

    One matrix product per call. With `torch_` (and PyTorch installed) it runs on the GPU when
    there is one; the result is the same as the NumPy path up to float rounding.
    """
    if torch_:
        try:
            import torch

            dev = "cuda" if torch.cuda.is_available() else "cpu"
            Yt = torch.as_tensor(Y, dtype=torch.float32, device=dev)
            Rt = torch.as_tensor(R, dtype=torch.float32, device=dev)
            Vt = torch.as_tensor(V, dtype=torch.float32, device=dev)
            n1, s = Yt @ Vt, Yt @ Rt
            n0 = Vt.sum(0)[None, :] - n1
            a = (s - n1 * (n1 + 1) / 2) / (n1 * n0)
            a[(n1 < 5) | (n0 < 5)] = float("nan")
            return a.cpu().numpy()
        except ImportError:
            pass
    n1 = Y @ V
    n0 = V.sum(axis=0)[None, :] - n1
    s = Y @ R
    with np.errstate(invalid="ignore", divide="ignore"):
        a = (s - n1 * (n1 + 1) / 2) / (n1 * n0)
    a[(n1 < 5) | (n0 < 5)] = np.nan
    return a


def _desplazar_etiquetas(
    y: np.ndarray, temporada: np.ndarray, rng: np.random.Generator, modo: str = "local"
) -> np.ndarray:
    """Labels moved inside each season, keeping the number of events and their clustering.

    `local` moves them 7 to 25 days either way (the seasonal phase is kept, so a feature that
    simply follows the calendar cannot pass); `estacion` moves them anywhere in the season.
    """
    ys = y.copy()
    for s in np.unique(temporada):
        i = np.flatnonzero(temporada == s)
        if modo == "local":
            k = int(rng.integers(7, 26)) * int(rng.choice([-1, 1]))
        else:
            k = int(rng.integers(5, max(6, len(i) - 5)))
        ys[i] = np.roll(y[i], k)
    return ys


def bh(p: np.ndarray, q: float = 0.10) -> np.ndarray:
    """Benjamini-Hochberg: True where the hypothesis is rejected at false-discovery rate q."""
    p = np.asarray(p, dtype=float)
    ok = ~np.isnan(p)
    sal = np.zeros(len(p), dtype=bool)
    idx = np.flatnonzero(ok)
    orden = idx[np.argsort(p[idx])]
    m = len(orden)
    pasa = p[orden] <= q * (np.arange(1, m + 1) / m)
    if pasa.any():
        sal[orden[: np.flatnonzero(pasa).max() + 1]] = True
    return sal


def rezagos_nula(
    F: pd.DataFrame, y: pd.Series, columnas: list[str], temporada: np.ndarray, mask: np.ndarray,
    lags: range = range(15), centrar: bool = False, n_null: int = 300, semilla: int = 0,
    q: float = 0.10, modo_nula: str = "local", usar_torch: bool = False, trozo: int = 2000,
) -> pd.DataFrame:
    """AUC per (variable, lag) with a two-sided p-value against season-shifted labels and BH.

    Returns one row per pair with `auc`, `p`, `senal` (passes BH at `q`) and, in `attrs`: the
    number of tests, the hits observed at BH, and the hits with nominal p < 0.05 against the
    `0.05 * n_tests` that chance alone would give. (Under a complete null BH rejects anything
    with probability at most `q`, so the nominal count is the useful chance benchmark.)
    """
    rng = np.random.default_rng(semilla)
    yv = y.to_numpy()[mask].astype(float)
    ts = temporada[mask]
    nulls = np.array([_desplazar_etiquetas(yv, ts, rng, modo_nula) for _ in range(n_null)], dtype=np.float32)
    filas = []
    for lag in lags:
        R, V = _rangos_lag(F, columnas, lag, mask, temporada, centrar)
        a = _auc_desde_rangos(yv, R, V)
        nul = np.concatenate([
            _auc_lote(nulls[i : i + trozo], R.astype(np.float32), V.astype(np.float32), usar_torch)
            for i in range(0, n_null, trozo)
        ])  # (n_null, vars)
        for j, c in enumerate(columnas):
            if np.isnan(a[j]):
                continue
            d = np.abs(nul[:, j] - 0.5)
            p = (1 + np.sum(d >= abs(a[j] - 0.5))) / (n_null + 1)
            filas.append({"variable": c, "lag": lag, "auc": a[j], "p": p})
    out = pd.DataFrame(filas)
    out["senal"] = bh(out["p"].to_numpy(), q)
    out.attrs["observados"] = int(out["senal"].sum())
    out.attrs["n_pruebas"] = len(out)
    out.attrs["observados_p05"] = int((out["p"] < 0.05).sum())
    out.attrs["esperados_p05_por_azar"] = 0.05 * len(out)
    return out


# ------------------------------------------------------------------------------- composites
def episodios_de_dias(dias: list, hueco: int = 3) -> list[pd.Timestamp]:
    """First day of every run of event days separated by at most `hueco` days."""
    ds = sorted({pd.Timestamp(d) for d in dias})
    out: list[pd.Timestamp] = []
    previo = None
    for d in ds:
        if previo is None or (d - previo).days > hueco:
            out.append(d)
        previo = d
    return out


def compuesto(
    serie: pd.Series, inicios: list[pd.Timestamp], temporada_de: Callable[[pd.Timestamp], int],
    dias: pd.DatetimeIndex, lags: range = range(-14, 4), n_null: int = 500, semilla: int = 0,
) -> pd.DataFrame:
    """Mean z-score of `serie` around the start of each episode, against shifted dates.

    A lag of -k is k days before the episode start. The null moves every episode to a random
    day of the same rainy season, so seasonality and persistence stay in the null.
    """
    rng = np.random.default_rng(semilla)
    s = serie.reindex(pd.date_range(dias.min() - timedelta(days=20), dias.max() + timedelta(days=20)))
    base = serie[dias[np.isin(dias.month, [12, 1, 2, 3, 4])]]
    z = (s - base.mean()) / base.std()
    lags_l = list(lags)

    def media(fechas: list[pd.Timestamp]) -> np.ndarray:
        m = np.array([[z.get(f + timedelta(days=k), np.nan) for k in lags_l] for f in fechas])
        return np.nanmean(m, axis=0)

    obs = media(inicios)
    por_temp: dict[int, list[pd.Timestamp]] = {}
    for d in dias:
        por_temp.setdefault(temporada_de(d), []).append(d)
    nul = np.empty((n_null, len(lags_l)))
    for i in range(n_null):
        nul[i] = media([por_temp[temporada_de(d)][int(rng.integers(len(por_temp[temporada_de(d)])))] for d in inicios])
    p = np.array([(1 + np.sum(np.abs(nul[:, j] - nul[:, j].mean()) >= abs(obs[j] - nul[:, j].mean()))) / (n_null + 1)
                  for j in range(len(lags_l))])
    return pd.DataFrame({"lag": lags_l, "z_medio": obs, "nula_p5": np.percentile(nul, 5, axis=0),
                         "nula_p95": np.percentile(nul, 95, axis=0), "p": p})


# --------------------------------------------------------------------- season-level regime
def regimen_temporada(
    F: pd.DataFrame, y: pd.Series, columnas: list[str], temporada: np.ndarray, mask: np.ndarray,
    n_perm: int = 2000, semilla: int = 0, q: float = 0.10,
) -> pd.DataFrame:
    """Spearman correlation between the season mean of each feature and the season's event days.

    One point per rainy season, so day clustering cannot inflate the evidence; the p-value
    permutes the seasons' event counts.
    """
    from scipy.stats import spearmanr

    rng = np.random.default_rng(semilla)
    ts = temporada[mask]
    medias = F[columnas][mask].groupby(ts).mean()
    n_ev = pd.Series(y.to_numpy()[mask], index=None).groupby(ts).sum()
    n_ev = n_ev.reindex(medias.index)
    filas = []
    for c in columnas:
        x = medias[c]
        ok = x.notna()
        if x.nunique() < 3:
            continue
        if ok.sum() < 12:
            continue
        rho = spearmanr(x[ok], n_ev[ok]).statistic
        perm = np.array([spearmanr(x[ok], rng.permutation(n_ev[ok].to_numpy())).statistic for _ in range(n_perm)])
        p = (1 + np.sum(np.abs(perm) >= abs(rho))) / (n_perm + 1)
        filas.append({"variable": c, "temporadas": int(ok.sum()), "spearman": rho, "p": p})
    out = pd.DataFrame(filas)
    out["senal"] = bh(out["p"].to_numpy(), q)
    out.attrs["observados_p05"] = int((out["p"] < 0.05).sum())
    out.attrs["esperados_p05_por_azar"] = 0.05 * len(out)
    return out


# ----------------------------------------------------------------------------- robustness
def mascaras_robustez(
    F: pd.DataFrame, temporada: np.ndarray, base: np.ndarray, temporadas_nino: pd.DataFrame | None = None
) -> dict[str, np.ndarray]:
    """Masks of rainy-season days for the coverage windows and subsets used as robustness checks."""
    anio = np.asarray(F.index.year)
    m = {
        "1984+": base,
        "2009+": base & (anio >= 2009),
        "sin 1983, 1998 y 2017": base & ~np.isin(temporada, [1983, 1998, 2017]),
    }
    if temporadas_nino is not None:
        nino = np.isin(temporada, temporadas_nino.index[temporadas_nino["nino"]])
        m["solo temporadas Niño"] = base & nino
        m["solo temporadas sin Niño"] = base & ~nino
    return m


def robustez(
    F: pd.DataFrame, y: pd.Series, columnas: list[str], temporada: np.ndarray,
    mascaras: dict[str, np.ndarray], lags: range = range(1, 15), centrar: bool = True,
    n_null: int = 1000, q: float = 0.10, p_nominal: float = 0.10, usar_torch: bool = False,
) -> pd.DataFrame:
    """AUC, p-value and verdict per (variable, lag) in each mask, and whether it is robust.

    `robusta`: passes Benjamini-Hochberg in the first mask (the widest coverage window) and, in
    each of the other coverage masks (2009+, without 1983/1998/2017), keeps the same sign with a
    nominal p below `p_nominal` (those subsets have only ~50 event days, so a corrected test would
    have no power). Niño / non-Niño rows are reported, not required.
    """
    partes = []
    for nombre, mask in mascaras.items():
        r = rezagos_nula(F, y, columnas, temporada, mask, lags, centrar=centrar, n_null=n_null, q=q,
                         usar_torch=usar_torch)
        r["ventana"] = nombre
        partes.append(r)
    t = pd.concat(partes)
    auc = t.pivot_table(index=["variable", "lag"], columns="ventana", values="auc")
    pv = t.pivot_table(index=["variable", "lag"], columns="ventana", values="p")
    sen = t.pivot_table(index=["variable", "lag"], columns="ventana", values="senal", aggfunc="max")
    nombres = list(mascaras)
    principal = nombres[0]
    cobertura = [v for v in ("2009+", "sin 1983, 1998 y 2017") if v in mascaras]
    signo = np.sign(auc[[principal, *cobertura]] - 0.5)
    ok = sen[principal].fillna(0).astype(bool) & (signo.nunique(axis=1) == 1)
    for v in cobertura:
        ok &= pv[v] < p_nominal
    out = auc.add_prefix("auc ").join(pv.add_prefix("p ")).join(sen.add_prefix("senal ").astype(bool))
    out["robusta"] = ok
    out.attrs["n_pruebas"] = len(out)
    out.attrs["esperadas_p05_por_azar"] = 0.05 * len(out)
    return out.reset_index()
