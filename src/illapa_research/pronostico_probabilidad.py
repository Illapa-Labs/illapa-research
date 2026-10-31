"""From a rain forecast to the probability of a huaico day, and its backtest.

Idea ("perfect prognosis"): fit the probability model of a huaico day on the long observed record (rain
grid, ERA5 antecedents, discharge, sea) and feed it, at forecast time, with the forecast rain in place of the
observed rain. The backtest replays that on the days for which an archive of past forecasts exists.

What a past forecast is here: Open-Meteo's *previous runs* archive keeps, for each hour, the rain forecast issued
``lead`` days before (``precipitation_previous_dayN``) and the latest one (``precipitation``, lead 0). The archive
of each model starts at a different date (see ``docs/17``), which is what limits the backtest.

No leak: at the issue time of day ``t - lead`` the model only gets (a) the forecast rain for day ``t`` and the days
before it at the same lead, and (b) observations up to the end of day ``t - lead - 1`` (the antecedent features
are shifted ``lead + 1`` days). It is a research prototype, not an alert.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.stats import rankdata

from . import correccion_sesgo as CS
from .evaluacion_diaria import temporadas_de

API_PREVIOUS = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODELOS = {
    "ukmo": "ukmo_global_deterministic_10km",
    "jma": "jma_gsm",
    "gfs": "gfs_global",
    "ecmwf": "ecmwf_ifs025",
}
VARIABLES_LEAD = {0: "precipitation", 1: "precipitation_previous_day1", 2: "precipitation_previous_day2",
                  3: "precipitation_previous_day3"}
# Rainy seasons (December to April) named as in the rest of the repo: by the year of their January.
TEMPORADAS_PRONOSTICO = {
    2023: ("2022-12-01", "2023-04-30"),
    2024: ("2023-12-01", "2024-04-30"),
    2025: ("2024-12-01", "2025-04-30"),
    2026: ("2025-12-01", "2026-04-30"),
}
ULTIMA_TEMPORADA_ENTRENAMIENTO = 2022  # the observed record up to April 2022 trains the model
AVISO = (
    "Prototipo de investigación: no es una alerta ni una predicción para decidir evacuaciones. Es la frecuencia "
    "histórica de días con huaico catalogado bajo condiciones parecidas. Ante una emergencia llama al 115 (INDECI)."
)


# ------------------------------------------------------------------------------------------ download


def descargar(destino: Path, modelos: tuple[str, ...] = ("ukmo", "jma", "gfs", "ecmwf"),
              temporadas: dict[int, tuple[str, str]] | None = None, pausa: float = 3.0) -> list[Path]:
    """Hourly forecasts at the six PISCOp cells, one JSON per model and season (cached; reruns skip them).

    One request per file, with a pause between requests: the free API caps calls per hour and per day.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    lats = ",".join(str(y) for y in CS.LATITUDES for _ in CS.LONGITUDES)
    lons = ",".join(str(x) for _ in CS.LATITUDES for x in CS.LONGITUDES)
    escritos = []
    for clave in modelos:
        for anio, (desde, hasta) in (temporadas or TEMPORADAS_PRONOSTICO).items():
            ruta = destino / f"{clave}_{anio}.json"
            if ruta.exists():
                escritos.append(ruta)
                continue
            fin = (date.fromisoformat(hasta) + timedelta(days=1)).isoformat()
            params = {"latitude": lats, "longitude": lons, "start_date": desde, "end_date": fin,
                      "hourly": ",".join(VARIABLES_LEAD.values()), "timezone": "GMT", "models": MODELOS[clave]}
            for intento in range(4):
                r = requests.get(API_PREVIOUS, params=params, timeout=180)
                if r.status_code == 200:
                    break
                time.sleep(15 * (intento + 1))
            r.raise_for_status()
            cuerpo = r.json()
            ruta.write_text(json.dumps(cuerpo if isinstance(cuerpo, list) else [cuerpo]), encoding="utf-8")
            escritos.append(ruta)
            time.sleep(pausa)
    return escritos


def serie_lead(rutas: list[Path], lead: int) -> pd.Series:
    """Daily rain (mm) of the forecast issued ``lead`` days before, mean of the six cells, over SENAMHI's rain day
    (7 a.m. to 7 a.m. Lima), indexed by the day the rain day starts. Days with a missing hour stay NaN."""
    col = VARIABLES_LEAD[lead]
    partes = []
    for ruta in rutas:
        puntos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        horas = pd.to_datetime(puntos[0]["hourly"]["time"])
        valores = np.array([[np.nan if v is None else v for v in p["hourly"][col]] for p in puntos], dtype=float)
        con_datos = ~np.isnan(valores).all(axis=0)
        media = np.full(valores.shape[1], np.nan)
        media[con_datos] = np.nanmean(valores[:, con_datos], axis=0)
        partes.append(pd.Series(media, index=horas))
    horas = pd.concat(partes).sort_index()
    horas = horas[~horas.index.duplicated()]
    horas.index = horas.index - pd.Timedelta(hours=CS.INICIO_DIA_UTC)
    por_dia = horas.resample("D").agg(["sum", "count"])
    s = por_dia["sum"].where(por_dia["count"] == 24)
    s.name = f"pp_lead{lead}"
    return s


# ------------------------------------------------------------------------------------------ correction


def corregir_fuera_de_temporada(pronostico: pd.Series, obs: pd.Series, temporadas_fit: list[int] | None = None) -> pd.Series:
    """Quantile mapping of the forecast onto the observed rain, each season with a fit that never saw it.

    The seasons of ``temporadas_fit`` (default: those with both series) are corrected leave-one-season-out; a
    season without observations (the recent one) is corrected with the fit of all the others, which is the
    honest out-of-time case.
    """
    comunes = pronostico.dropna().index.intersection(obs.dropna().index)
    comunes = comunes[CS.en_temporada(comunes)]
    temp_comunes = np.array([CS.temporada_de(d) for d in comunes])
    salida = pd.Series(np.nan, index=pronostico.index, name="corregido")
    en_temp = CS.en_temporada(pronostico.index)
    temp_todas = np.array([CS.temporada_de(d) if e else -1 for d, e in zip(pronostico.index, en_temp, strict=True)])
    for t in sorted(set(temp_todas) - {-1}):
        usa = temp_comunes != t
        if usa.sum() < 30:
            continue
        ajuste = CS.MapeoCuantiles.ajustar(pronostico.loc[comunes[usa]], obs.loc[comunes[usa]])
        mismo = temp_todas == t
        salida[mismo] = ajuste.aplicar(pronostico[mismo].fillna(0.0)).where(pronostico[mismo].notna())
    return salida


# ------------------------------------------------------------------------------------------ the model


@dataclass
class ModeloPP:
    """Ridge-logistic fitted on the observed record, with everything needed to score a forecast."""

    lead: int
    columnas: list[str]
    media: np.ndarray
    desv: np.ndarray
    mediana: np.ndarray
    beta: np.ndarray  # last element is the intercept
    c: float = 0.03
    info: dict = field(default_factory=dict)

    def logit(self, X: pd.DataFrame) -> np.ndarray:
        Z = X[self.columnas].to_numpy(dtype=float)
        Z = np.where(np.isnan(Z), self.mediana, Z)
        Z = (Z - self.media) / self.desv
        return Z @ self.beta[:-1] + self.beta[-1]

    def probabilidad(self, X: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0 / (1.0 + np.exp(-self.logit(X))), index=X.index, name="p")


def ajustar_pp(X: pd.DataFrame, y: pd.Series, lead: int, c: float = 0.03) -> ModeloPP:
    """Fit on the training days (no test information): median-impute, z-score, ridge logistic."""
    from sklearn.linear_model import LogisticRegression

    cols = list(X.columns)
    A = X.to_numpy(dtype=float)
    mediana = np.nanmedian(A, axis=0)
    A = np.where(np.isnan(A), mediana, A)
    media, desv = A.mean(axis=0), A.std(axis=0)
    desv[desv == 0] = 1.0
    modelo = LogisticRegression(C=c, max_iter=5000).fit((A - media) / desv, y.to_numpy())
    beta = np.concatenate([modelo.coef_[0], modelo.intercept_])
    return ModeloPP(lead, cols, media, desv, mediana, beta, c,
                    {"n_dias": len(y), "n_positivos": int(y.sum()), "n_columnas": len(cols)})


def entradas(F: pd.DataFrame, pp_valle: pd.Series, pisco: pd.Series, lead: int, compacto: bool = False) -> pd.DataFrame:
    """Design matrix for forecasting day ``t`` at issue time ``t - lead``.

    * rain of the day and of the last three days of the valley, from ``pp_valle`` (observed PISCOp to train, the
      forecast for the same lead to test);
    * (PISCOp ends in December 2025, so no PISCOp antecedent is used: the antecedent rain comes from ERA5, which
      is in ``F`` for the whole period);
    * every ERA5/discharge/sea/ICEN feature of ``F`` shifted ``lead + 1`` days (so only information up to the end
      of the day before the issue day).
    ``compacto`` keeps a short fixed list instead of every column (chosen before the backtest).
    """
    idx = F.index
    p = pp_valle.reindex(idx)
    base = pd.DataFrame({
        "pp_valle_1d": p,
        "pp_valle_3d": p.rolling(3, min_periods=3).sum(),
    }, index=idx)
    todas = [c for c in F.columns if not c.startswith("icen_")]
    previas = F[todas].shift(lead + 1).add_suffix("_prev")
    icen = F[[c for c in F.columns if c.startswith("icen_")]]
    if compacto:
        sel = [c for c in ("chosica_suelo_prev", "caudal_rimac-chosica_anom_prev", "sst_nino12_anom_30d_prev",
                           "sst_costa_lima_anom_7d_prev", "mat_lluvia_30d_previa_prev") if c in previas.columns]
        return pd.concat([base, previas[sel], icen[["icen_3m_previos"]]], axis=1)
    return pd.concat([base, previas, icen], axis=1)


# ------------------------------------------------------------------------------------------ measures


def metricas_prob(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    p = np.clip(p, 1e-6, 1 - 1e-6)
    n5 = max(1, round(0.05 * len(p)))
    n10 = max(1, round(0.10 * len(p)))
    orden = np.argsort(-p)
    return {
        "ap": float(average_precision_score(y, p)), "auc": float(roc_auc_score(y, p)),
        "brier": float(np.mean((p - y) ** 2)),
        "logloss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        "huaicos_en_5pc": int(y[orden[:n5]].sum()), "huaicos_en_10pc": int(y[orden[:n10]].sum()),
        "positivos": int(y.sum()), "dias": len(y), "base": float(y.mean()),
    }


def bootstrap_bloques(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray | None = None, bloque: int = 14,
                      n: int = 2000, semilla: int = 0) -> dict[str, tuple[float, float]]:
    """Interval of AP (and of the AP difference a - b) by resampling blocks of ``bloque`` consecutive days.

    With only four seasons the season bootstrap has almost no resolution, so blocks are used instead; a block
    keeps the clustering of consecutive huaico days.
    """
    from .gpu import auc_ap_lote

    rng = np.random.default_rng(semilla)
    nb = int(np.ceil(len(y) / bloque))
    bloques = [np.arange(i * bloque, min((i + 1) * bloque, len(y))) for i in range(nb)]
    Y, A, B = [], [], []
    for _ in range(n):
        elegido: list[np.ndarray] = []
        total = 0
        while total < len(y):
            b = bloques[int(rng.integers(0, nb))]
            elegido.append(b)
            total += len(b)
        idx = np.concatenate(elegido)[: len(y)]
        Y.append(y[idx]); A.append(p_a[idx]); B.append(p_b[idx] if p_b is not None else p_a[idx])
    Y, A, B = np.array(Y, float), np.array(A), np.array(B)
    _, ap_a = auc_ap_lote(Y, A, dispositivo_="cpu")
    out = {"ap_a": (float(np.percentile(ap_a, 10)), float(np.percentile(ap_a, 90)))}
    if p_b is not None:
        _, ap_b = auc_ap_lote(Y, B, dispositivo_="cpu")
        d = ap_a - ap_b
        out["ap_diferencia"] = (float(np.percentile(d, 10)), float(np.percentile(d, 90)))
        out["p_a_mejor"] = (float((d > 0).mean()), float((d > 0).mean()))
    return out


def nula_desplazada(y: np.ndarray, p: np.ndarray, temporada: np.ndarray, n: int = 2000, semilla: int = 0,
                    dispositivo: str | None = None) -> dict[str, float]:
    """AP of fixed predictions against labels shifted cyclically inside each season (n null worlds).

    The predictions do not change, so this asks: how often would the same forecasts look this good against
    the same number of huaicos, with the same clustering, placed on the wrong days?
    """
    from .gpu import auc_ap_lote

    rng = np.random.default_rng(semilla)
    mundos = np.empty((n, len(y)))
    por_temp = {s: np.flatnonzero(temporada == s) for s in np.unique(temporada)}
    for b in range(n):
        ys = y.astype(float).copy()
        for i in por_temp.values():
            ys[i] = np.roll(y[i], int(rng.integers(3, max(4, len(i) - 3))))
        mundos[b] = ys
    P = np.tile(p, (n, 1))
    _, ap = auc_ap_lote(mundos, P, dispositivo_=dispositivo)
    _, ap_real = auc_ap_lote(y[None, :].astype(float), p[None, :], dispositivo_=dispositivo)
    return {"ap_real": float(ap_real[0]), "ap_nula_media": float(ap.mean()), "ap_nula_p95": float(np.percentile(ap, 95)),
            "p": float((1 + (ap >= ap_real[0]).sum()) / (1 + n))}


# ------------------------------------------------------------------------------------------ public function


def probabilidad_desde_pronostico(fecha_emision: date | pd.Timestamp, lead: int, pronostico: pd.Series,
                                  observaciones: pd.DataFrame, modelo: ModeloPP, pisco: pd.Series) -> dict:
    """Probability of a huaico day for ``fecha_emision + lead`` using only what exists at the issue time.

    ``pronostico``: daily forecast rain (mm) of the valley for the days up to the target day, same lead.
    ``observaciones``: the feature table ``F`` (any rows after the issue day are ignored and never used).
    Returns the probability and the dates it relied on; raises if an input would need data after the issue day.
    """
    emision = pd.Timestamp(fecha_emision)
    objetivo = emision + pd.Timedelta(days=lead)
    if pronostico.reindex([objetivo]).isna().all():
        raise ValueError("falta el pronóstico para el día objetivo")
    F = observaciones.loc[: emision - pd.Timedelta(days=1)]  # nothing from the issue day on
    F = F.reindex(pd.date_range(F.index.min(), objetivo, freq="D"))  # target rows are empty on purpose
    obs = pisco.loc[: emision - pd.Timedelta(days=1)].reindex(F.index)
    pp = pronostico.reindex(F.index)
    X = entradas(F, pp, obs, lead).loc[[objetivo]]
    p = float(modelo.probabilidad(X).iloc[0])
    return {"probabilidad": p, "fecha_emision": emision.date(), "dia_objetivo": objetivo.date(), "lead": lead,
            "pronostico_mm": float(pp.loc[objetivo]), "ultimo_dato_observado": F.dropna(how="all").index.max().date(),
            "aviso": AVISO}


def temporada_de_dias(idx: pd.DatetimeIndex) -> np.ndarray:
    return temporadas_de(idx)


# ------------------------------------------------------------------------------------------ backtest driver


def _climatologia_mensual(y: pd.Series, entrenamiento: np.ndarray, idx: pd.DatetimeIndex) -> pd.Series:
    tasa = y[entrenamiento].groupby(y.index[entrenamiento].month).mean()
    return pd.Series(idx.month.map(tasa).to_numpy(dtype=float), index=idx)


def correr_backtest(raiz: Path = Path("."), leads: tuple[int, ...] = (0, 1, 2, 3), modelos: tuple[str, ...] = ("ukmo", "jma", "gfs", "ecmwf"),
                    compacto: bool = False, c: float = 0.03) -> dict:
    """Train on the observed record up to April 2022, replay the forecasts of every archive and lead.

    Returns the per-day predictions of each scenario plus the metric tables. Scenarios per (model, lead):
    ``pron``: probability model fed with the quantile-corrected forecast; ``mm_crudo``: ranking by the raw
    forecast mm of the day. Common references: ``techo`` (observed PISCOp rain in place of the forecast, lead 0
    only through December 2025) and ``clima`` (month base rate learned on the training years).
    """
    from . import modelo_diario as MD

    raiz = Path(raiz)
    D = MD.cargar_datos(raiz)
    F, y_all = D.F, D.y
    ts_all = D.temporada
    pisco = CS.serie_pisco(None, cache=raiz / "datos" / "pisco" / "rimac_diario.csv")
    en_t = CS.en_temporada(F.index)
    entrena = en_t & (F.index.year >= 1984) & (ts_all <= ULTIMA_TEMPORADA_ENTRENAMIENTO)
    prueba = en_t & (ts_all > ULTIMA_TEMPORADA_ENTRENAMIENTO) & (F.index <= pd.Timestamp("2026-04-30"))
    clima = _climatologia_mensual(y_all, entrena, F.index)
    carpeta = raiz / "datos" / "pronosticos"
    modelos_pp: dict[int, ModeloPP] = {}
    predicciones: dict[str, pd.Series] = {}
    desfases: dict[str, int] = {}
    for lead in leads:
        X_obs = entradas(F, pisco, pisco, lead, compacto)
        ok = entrena & X_obs[["pp_valle_1d", "pp_valle_3d"]].notna().all(axis=1).to_numpy()
        modelos_pp[lead] = ajustar_pp(X_obs[ok], y_all[ok], lead, c)
        techo = modelos_pp[lead].probabilidad(X_obs)
        techo = techo.where(pisco.reindex(F.index).notna())
        predicciones[f"techo_lead{lead}"] = techo
        for clave in modelos:
            rutas = sorted(carpeta.glob(f"{clave}_*.json"))
            if not rutas:
                continue
            raw = serie_lead(rutas, lead)
            if clave not in desfases:  # alignment with PISCOp, measured once on lead 0 and reused for every lead
                desfases[clave] = int(CS.mejor_desfase(serie_lead(rutas, 0), pisco))
            raw.index = raw.index + pd.Timedelta(days=desfases[clave])
            cor = corregir_fuera_de_temporada(raw, pisco)
            raw_f, cor_f = raw.reindex(F.index), cor.reindex(F.index)
            X = entradas(F, cor_f.fillna(0.0).where(cor_f.notna()), pisco, lead, compacto)
            p = modelos_pp[lead].probabilidad(X).where(cor_f.notna() & X["pp_valle_3d"].notna())
            predicciones[f"{clave}_lead{lead}_pron"] = p
            predicciones[f"{clave}_lead{lead}_mm"] = raw_f
            predicciones[f"{clave}_lead{lead}_mm3d"] = raw_f.rolling(3, min_periods=3).sum()
    return {"D": D, "pisco": pisco, "predicciones": predicciones, "modelos": modelos_pp, "entrena": entrena,
            "prueba": prueba, "y": y_all, "temporada": ts_all, "clima": clima, "desfases": desfases}


def tabla_backtest(R: dict, n_boot: int = 2000, n_nulas: int = 2000, dispositivo: str | None = None) -> pd.DataFrame:
    """One row per (archive, lead): the probability model against its references on the same days.

    Days used: rainy-season test days with a forecast for that archive and lead (and, for the ``techo``
    columns, with observed PISCOp rain: through December 2025).
    """
    y_all, prueba, clima, ts = R["y"], R["prueba"], R["clima"], R["temporada"]
    filas = []
    claves = sorted({k.split("_lead")[0] for k in R["predicciones"] if "_lead" in k and k.endswith("_pron")})
    leads = sorted({int(k.split("_lead")[1].split("_")[0]) for k in R["predicciones"] if k.endswith("_pron")})
    for clave in claves:
        for lead in leads:
            p = R["predicciones"].get(f"{clave}_lead{lead}_pron")
            if p is None:
                continue
            ok = prueba & p.notna().to_numpy()
            if ok.sum() < 60 or y_all[ok].sum() < 2:
                continue
            y = y_all[ok].to_numpy().astype(float)
            m = metricas_prob(y, p[ok].to_numpy())
            fila = {"archivo": clave, "lead": lead, "dias": m["dias"], "huaicos": m["positivos"], "base": round(m["base"], 4),
                    "AP_pron": m["ap"], "AUC_pron": m["auc"], "Brier_pron": m["brier"], "logloss_pron": m["logloss"],
                    "huaicos_en_5pc": m["huaicos_en_5pc"], "huaicos_en_10pc": m["huaicos_en_10pc"]}
            for nombre, serie in (("mm", R["predicciones"][f"{clave}_lead{lead}_mm"]), ("mm3d", R["predicciones"][f"{clave}_lead{lead}_mm3d"])):
                s = serie[ok].fillna(0.0).to_numpy()
                # only the order of the mm matters for AP and AUC: use ranks in (0, 1) so nothing is clipped
                r = (rankdata(s, method="average") - 0.5) / len(s)
                mm = metricas_prob(y, r)
                fila[f"AP_{nombre}_crudo"] = mm["ap"]
                fila[f"AUC_{nombre}_crudo"] = mm["auc"]
            cl = clima[ok].to_numpy()
            fila["AP_clima"] = metricas_prob(y, cl)["ap"]
            t = R["predicciones"][f"techo_lead{lead}"]
            ok_t = ok & t.notna().to_numpy()
            if ok_t.sum() >= 60 and y_all[ok_t].sum() >= 2:
                yt = y_all[ok_t].to_numpy().astype(float)
                fila["AP_techo"] = metricas_prob(yt, t[ok_t].to_numpy())["ap"]
                fila["AP_pron_mismos_dias_techo"] = metricas_prob(yt, p[ok_t].to_numpy())["ap"]
                fila["huaicos_techo"] = int(yt.sum())
            nula = nula_desplazada(y, p[ok].to_numpy(), ts[ok], n_nulas, dispositivo=dispositivo)
            fila["p_nula"] = nula["p"]
            fila["AP_nula_p95"] = nula["ap_nula_p95"]
            b = bootstrap_bloques(y, p[ok].to_numpy(), (rankdata(R["predicciones"][f"{clave}_lead{lead}_mm3d"][ok].fillna(0.0).to_numpy()) - 0.5) / ok.sum(), n=n_boot)
            fila["AP_lo"], fila["AP_hi"] = b["ap_a"]
            fila["dAP_lo"], fila["dAP_hi"] = b["ap_diferencia"]
            fila["AP_ic80"] = f"{b['ap_a'][0]:.3f} a {b['ap_a'][1]:.3f}"
            fila["dAP_vs_mm3d_ic80"] = f"{b['ap_diferencia'][0]:+.3f} a {b['ap_diferencia'][1]:+.3f}"
            fila["P(pron mejor que mm3d)"] = b["p_a_mejor"][0]
            filas.append(fila)
    return pd.DataFrame(filas)


def mos_platt_por_temporada(y: np.ndarray, p: np.ndarray, temporada: np.ndarray) -> np.ndarray:
    """Light MOS: Platt scaling of the logit, each season recalibrated with a fit on the other seasons only.

    There are only three or four test seasons and 12 to 14 huaico days, so this is a sanity check of the
    calibration, not a tuned layer.
    """
    from sklearn.linear_model import LogisticRegression

    z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))[:, None]
    salida = np.full(len(y), np.nan)
    for t in np.unique(temporada):
        fuera = temporada == t
        if y[~fuera].sum() < 2:
            continue
        m = LogisticRegression(C=1.0, max_iter=2000).fit(z[~fuera], y[~fuera])
        salida[fuera] = m.predict_proba(z[fuera])[:, 1]
    return salida


def bandas_fiabilidad(y: np.ndarray, p: np.ndarray, cortes: tuple[float, ...] = (0.0, 0.02, 0.10, 0.25, 1.01)) -> pd.DataFrame:
    """Days and huaicos by probability band (Wilson 80 % interval of the observed share)."""
    from .probabilidad import wilson

    filas = []
    for a, b in pairwise(cortes):
        m = (p >= a) & (p < b)
        n, k = int(m.sum()), int(y[m].sum())
        lo, hi = wilson(k, n) if n else (np.nan, np.nan)
        filas.append({"banda": f"{a:.0%} a {min(b, 1):.0%}", "dias": n, "huaicos": k,
                      "observado": k / n if n else np.nan, "ic80": f"{lo:.2f} a {hi:.2f}",
                      "predicho_medio": float(p[m].mean()) if n else np.nan})
    return pd.DataFrame(filas)


def pares_pronostico(R: dict, clave: str, lead: int, activaciones: pd.DataFrame, ubicadas: list[str],
                     temporadas: pd.DataFrame) -> dict:
    """Quebrada level for the backtest days: P(day) x participation learned on the training seasons only.

    Compares the product with the day alone and the quebrada alone over every (quebrada, day) pair, and counts
    how many of the quebradas that were active on a huaico day fall in the top 5 of the participation.
    """
    from sklearn.metrics import average_precision_score, roc_auc_score

    from .integracion import participacion

    p = R["predicciones"][f"{clave}_lead{lead}_pron"]
    ok = R["prueba"] & p.notna().to_numpy()
    dias = p.index[ok]
    entren = activaciones[activaciones["temporada"] <= ULTIMA_TEMPORADA_ENTRENAMIENTO]
    pi = participacion(entren, set(ubicadas), temporadas[temporadas.index <= ULTIMA_TEMPORADA_ENTRENAMIENTO])
    pi = pi[pi["temporadas"] == "todas"].set_index("slug")["pi"].reindex(ubicadas)
    prueba = activaciones[activaciones["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    prueba = prueba[pd.to_datetime(prueba["fecha"]).isin(dias)]
    activos = set(zip(pd.to_datetime(prueba["fecha"]), prueba["slug"], strict=True))
    y, s_prod, s_dia, s_q = [], [], [], []
    base = float(p[ok].mean())
    for d in dias:
        for q in ubicadas:
            y.append(int((d, q) in activos))
            s_prod.append(p[d] * pi[q]); s_dia.append(p[d] * pi.mean()); s_q.append(base * pi[q])
    y = np.array(y)
    top5 = set(pi.sort_values(ascending=False).index[:5])
    n_act = len(prueba)
    en_top5 = int(prueba["slug"].isin(top5).sum())
    res = {"pares": len(y), "pares_activos": int(y.sum()), "dias_con_quebrada_ubicada": int(prueba["fecha"].nunique()),
           "top5_participacion": sorted(top5), "activaciones_en_top5": en_top5, "activaciones_totales": n_act,
           "esperado_al_azar": n_act * 5 / len(ubicadas)}
    if y.sum() >= 2:
        for nombre, s in (("producto", s_prod), ("solo_dia", s_dia), ("solo_quebrada", s_q)):
            res[f"AP_{nombre}"] = float(average_precision_score(y, s))
            res[f"AUC_{nombre}"] = float(roc_auc_score(y, s))
    res["base_pares"] = float(y.mean())
    return res
