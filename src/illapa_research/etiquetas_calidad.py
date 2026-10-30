"""How good is the label? Corroboration, severity, era and flood contamination of the catalogue.

The daily model of `modelo_diario` is trained on "a catalogued huaico day". Not every catalogued
day is equally certain, and the catalogue does not describe every era equally well. This module
builds the alternative labels and the diagnostics that chapter 07 uses to ask whether the model's
skill, and the sources of its errors, depend on how the label was made.

Alternative labels (all on the same calendar, rainy-season rows are cut by the caller):

* ``base``: every catalogued day with exact date and confidence above `baja` (what chapter 05 uses);
* ``A_corroborada``: dates that appear in two or more catalogue files or whose best confidence is `alta`;
* ``B_severa``: dates on which two or more placed quebradas were active;
* ``C_prensa``: dates cited by three or more distinct kinds of source (institutions, press, studies);
* ``D_ampliada``: base plus the day before each date (night events filed late);
* ``E_sin_inundacion``: base without the dates whose every row describes a flood, not a debris flow;
* ``E2_sin_mencion_inundacion``: base without any date whose rows mention a flood or overflow at all.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .catalogo import CATALOGO

PALABRAS_INUNDACION = re.compile(r"inundaci|desborde|crecida|rebalse|aniego|anegaci", re.IGNORECASE)
PALABRAS_HUAICO = re.compile(r"huayco|huaico|aluvi|\balud|flujo de detritos|flujos de detritos|activ", re.IGNORECASE)

# Kinds of source named in the `fuente` column. A date cited by three kinds is "well documented".
TIPOS_FUENTE = {
    "indeci_coen": re.compile(r"INDECI|COEN|SINPAD|Defensa Civil|CENEPRED", re.IGNORECASE),
    "cientifica": re.compile(r"IGP|INGEMMET|Valverde|UNFV|S[aá]nchez Meza|PREDES|CIP", re.IGNORECASE),
    "desinventar": re.compile(r"DesInventar", re.IGNORECASE),
    "prensa_lima": re.compile(r"El Comercio|La Rep[uú]blica|Per[uú]21|Correo|Trome|Andina|El Peruano|Infobae", re.IGNORECASE),
    "prensa_tv": re.compile(r"RPP|Am[eé]rica|Panamericana|Canal N|ATV|Latina", re.IGNORECASE),
}


@dataclass
class Fecha:
    fecha: date
    archivos: set[str]
    tipos: set[str]
    confianza_alta: bool
    solo_inundacion: bool
    filas: int


def leer_filas(carpeta: Path = CATALOGO) -> list[dict]:
    """Every row of every `eventos*.csv`, with the file it came from."""
    filas = []
    for ruta in sorted(Path(carpeta).glob("eventos*.csv")):
        with open(ruta, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                r["archivo"] = ruta.name
                filas.append(r)
    return filas


def es_inundacion(fila: dict) -> bool:
    """A row that talks about a flood or overflow, never about a huaico, and names no quebrada.

    A named quebrada with an overflow of the Rímac (1983-03-22) is a debris flow with a flood,
    not a flood: only rows without a named quebrada can be read as plain floods.
    """
    q = fila.get("quebradas", "")
    con_nombre = any(t.strip() and not t.strip().startswith("(") for t in q.split(";"))
    texto = f"{q} {fila.get('notas', '')}"
    return (
        bool(PALABRAS_INUNDACION.search(texto)) and not PALABRAS_HUAICO.search(texto) and not con_nombre
    )


def tipos_de_fuente(texto: str) -> set[str]:
    return {k for k, rx in TIPOS_FUENTE.items() if rx.search(texto)}


def tabla_fechas(filas: list[dict]) -> pd.DataFrame:
    """One row per exact date (confidence above `baja`) with corroboration columns."""
    por_fecha: dict[date, list[dict]] = {}
    for r in filas:
        if r["precision_fecha"] != "dia" or r["confianza"] == "baja":
            continue
        por_fecha.setdefault(date.fromisoformat(r["fecha"]), []).append(r)
    out = []
    for f, rs in sorted(por_fecha.items()):
        tipos = set()
        for r in rs:
            tipos |= tipos_de_fuente(r["fuente"])
        out.append(
            {
                "fecha": pd.Timestamp(f),
                "filas": len(rs),
                "n_archivos": len({r["archivo"] for r in rs}),
                "n_tipos_fuente": len(tipos),
                "confianza_alta": any(r["confianza"] == "alta" for r in rs),
                "solo_inundacion": all(es_inundacion(r) for r in rs),
                "menciona_inundacion": any(
                    PALABRAS_INUNDACION.search(f"{r.get('quebradas', '')} {r.get('notas', '')}") for r in rs
                ),
            }
        )
    return pd.DataFrame(out).set_index("fecha")


def agregar_severidad(tabla: pd.DataFrame, activaciones: pd.DataFrame, ubicadas: set[str]) -> pd.DataFrame:
    """Number of placed quebradas active on each date (``n_quebradas``)."""
    a = activaciones[activaciones["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    n = a.groupby(pd.to_datetime(a["fecha"]))["slug"].nunique()
    return tabla.assign(n_quebradas=n.reindex(tabla.index).fillna(0).astype(int))


def etiqueta_de_fechas(fechas, idx: pd.DatetimeIndex, dias_antes: int = 0) -> pd.Series:
    y = pd.Series(0, index=idx, dtype=int)
    for f in fechas:
        for k in range(dias_antes + 1):
            d = pd.Timestamp(f) - timedelta(days=k)
            if d in y.index:
                y.loc[d] = 1
    return y


def etiquetas_alternativas(tabla: pd.DataFrame, idx: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """All the labels of the module docstring on the calendar `idx`."""
    t = tabla
    return {
        "base": etiqueta_de_fechas(t.index, idx),
        "A_corroborada": etiqueta_de_fechas(t.index[(t["n_archivos"] >= 2) | t["confianza_alta"]], idx),
        "B_severa": etiqueta_de_fechas(t.index[t["n_quebradas"] >= 2], idx),
        "C_prensa": etiqueta_de_fechas(t.index[t["n_tipos_fuente"] >= 3], idx),
        "D_ampliada": etiqueta_de_fechas(t.index, idx, dias_antes=1),
        "E_sin_inundacion": etiqueta_de_fechas(t.index[~t["solo_inundacion"]], idx),
        "E2_sin_mencion_inundacion": etiqueta_de_fechas(t.index[~t["menciona_inundacion"]], idx),
    }


def era_de(temporada: np.ndarray) -> np.ndarray:
    """Era of a season: documentation changed with the archives (see chapter 07)."""
    t = np.asarray(temporada)
    return np.where(t <= 1998, "1984-1998", np.where(t <= 2008, "1999-2008", "2009-2026"))


def fuentes_por_temporada(filas: list[dict]) -> pd.DataFrame:
    """Catalogue files and kinds of source that contribute to each rainy season."""
    from .nino import temporada_de

    acc: dict[int, dict[str, set]] = {}
    for r in filas:
        if r["precision_fecha"] != "dia" or r["confianza"] == "baja":
            continue
        s = temporada_de(date.fromisoformat(r["fecha"]))
        a = acc.setdefault(s, {"archivos": set(), "tipos": set(), "fechas": set()})
        a["archivos"].add(r["archivo"])
        a["tipos"] |= tipos_de_fuente(r["fuente"])
        a["fechas"].add(r["fecha"])
    return pd.DataFrame(
        {s: {"n_archivos": len(a["archivos"]), "n_tipos": len(a["tipos"]), "n_fechas": len(a["fechas"])}
         for s, a in sorted(acc.items())}
    ).T


def indice_deteccion(F: pd.DataFrame, y: pd.Series, columna: str = "chosica_h_lluvia_1d", q: float = 0.99) -> pd.DataFrame:
    """Catalogued dates per season divided by the days of extreme rain (``q`` of the whole series).

    The reanalysis rain is the same for every year, so a falling ratio in a period means the
    catalogue knows fewer huaicos for the same weather: a measure of under-reporting, not of hazard.
    """
    from .evaluacion_diaria import temporadas_de
    from .predictores import temporada_mask

    m = temporada_mask(F.index) & (F.index.year >= 1984)
    r = F.loc[m, columna]
    umbral = r.quantile(q)
    ts = temporadas_de(r.index)
    extremos = pd.Series((r > umbral).to_numpy(), index=ts).groupby(level=0).sum()
    fechas = pd.Series(y.loc[m].to_numpy(), index=ts).groupby(level=0).sum()
    d = pd.DataFrame({"dias_extremos": extremos, "fechas": fechas})
    d["indice"] = d["fechas"] / d["dias_extremos"].clip(lower=1)
    d["umbral_mm"] = umbral
    return d


def metricas_sobre(y: np.ndarray, p: np.ndarray, p_ref: np.ndarray, ts: np.ndarray, n: int = 300,
                   semilla: int = 0, mascara: np.ndarray | None = None) -> dict[str, float]:
    """AP, lift over the base rate, AUC, Brier skill and hits at 5 % alarms, with a 90 % interval
    from a bootstrap over whole seasons. `mascara` keeps only some rows (an era, or the rows
    left after dropping uncertain dates)."""
    from .modelo_diario import metricas_completas

    mascara = np.ones(len(y), dtype=bool) if mascara is None else mascara
    y, p, p_ref, ts = y[mascara], p[mascara], p_ref[mascara], ts[mascara]
    out = metricas_completas(y, p, p_ref)
    out["lift"] = out["ap"] / out["ap_base"] if out["ap_base"] > 0 else float("nan")
    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    idx = {s: np.flatnonzero(ts == s) for s in seasons}
    aps, lifts = [], []
    for _ in range(n):
        b = np.concatenate([idx[s] for s in rng.choice(seasons, len(seasons))])
        if y[b].sum() < 3:
            continue
        m = metricas_completas(y[b], p[b], p_ref[b])
        aps.append(m["ap"])
        lifts.append(m["ap"] / m["ap_base"])
    out["ap_p5"], out["ap_p95"] = (float(np.percentile(aps, 5)), float(np.percentile(aps, 95))) if aps else (np.nan, np.nan)
    out["lift_p5"], out["lift_p95"] = (
        (float(np.percentile(lifts, 5)), float(np.percentile(lifts, 95))) if lifts else (np.nan, np.nan)
    )
    out["eventos"] = int(y.sum())
    out["dias"] = len(y)
    return out


def falsos_positivos(p: pd.Series, y: pd.Series, k: int = 20, separacion_dias: int = 3) -> pd.DataFrame:
    """The ``k`` highest out-of-fold probabilities on days with no catalogued date within one day,
    keeping one day per cluster (days closer than ``separacion_dias``)."""
    cerca = y.rolling(3, center=True, min_periods=1).max().astype(bool)
    cand = p[~cerca & p.notna()].sort_values(ascending=False)
    elegidos: list[pd.Timestamp] = []
    for d in cand.index:
        if all(abs((d - e).days) > separacion_dias for e in elegidos):
            elegidos.append(d)
        if len(elegidos) == k:
            break
    return pd.DataFrame({"p": p.loc[elegidos]})


def bootstrap_gpu(
    etiquetas: dict[str, np.ndarray], p: np.ndarray, p_ref: np.ndarray, ts: np.ndarray, B: int = 3000,
    semilla: int = 0, mascara: np.ndarray | None = None, referencia: str = "base",
    dispositivo_: str | None = None,
) -> pd.DataFrame:
    """Season bootstrap of AP, lift, AUC and hits at 5 % alarms for several labels at once.

    Every label is scored with the same `B` resamples of whole seasons (`gpu.auc_ap_lote`), so the
    difference to the reference label is paired. Returns, per label and metric, the point value,
    the 5th / 95th percentiles of the resamples and, for AUC and lift, the 5th / 95th percentile of
    the difference to `referencia` (an interval that excludes 0 means a real difference).
    """
    from . import gpu

    mascara = np.ones(len(p), dtype=bool) if mascara is None else mascara
    ts_m = ts[mascara]
    seasons = np.unique(ts_m)
    filas_de = {s: np.flatnonzero(mascara & (ts == s)) for s in seasons}
    rng = np.random.default_rng(semilla)
    largo = max(len(v) for v in filas_de.values())
    indices = []
    for _ in range(B):
        idx = np.concatenate([filas_de[s] for s in rng.choice(seasons, len(seasons))])
        indices.append(idx)
    nmax = max(len(i) for i in indices)
    I = np.zeros((B, nmax), dtype=np.int64)
    M = np.zeros((B, nmax))
    for b, idx in enumerate(indices):
        I[b, : len(idx)] = idx
        M[b, : len(idx)] = 1.0
    del largo
    P = p[I]
    out: dict[str, dict[str, np.ndarray]] = {}
    for nombre, y in etiquetas.items():
        Y = y[I].astype(float)
        auc, ap = gpu.auc_ap_lote(Y, P, M, dispositivo_)
        tasa = (Y * M).sum(axis=1) / M.sum(axis=1)
        # hits with 5 % of the scored days in alarm
        hits = np.empty(B)
        for b in range(B):
            k = int(M[b].sum())
            pb, yb = P[b, :k], Y[b, :k]
            corte = np.quantile(pb, 0.95)
            hits[b] = yb[pb >= corte].sum() / max(yb.sum(), 1)
        out[nombre] = {"ap": ap, "lift": ap / np.clip(tasa, 1e-9, None), "auc": auc, "hits5": hits}
    filas = []
    ref = out[referencia]
    yv = {k: v[mascara] for k, v in etiquetas.items()}
    from .modelo_diario import metricas_completas

    for nombre, m in out.items():
        punto = metricas_completas(yv[nombre], p[mascara], p_ref[mascara])
        fila = {"etiqueta": nombre, "eventos": int(yv[nombre].sum()), "ap": punto["ap"],
                "lift": punto["ap"] / punto["ap_base"], "auc": punto["auc"],
                "hits5": punto["aciertos_con_5pc_alarmas"]}
        for k in ("ap", "lift", "auc", "hits5"):
            lo, hi = np.percentile(m[k], [5, 95])
            fila[f"{k}_p5"], fila[f"{k}_p95"] = float(lo), float(hi)
        if nombre != referencia:
            for k in ("lift", "auc"):
                lo, hi = np.percentile(m[k] - ref[k], [5, 95])
                fila[f"d_{k}_p5"], fila[f"d_{k}_p95"] = float(lo), float(hi)
        filas.append(fila)
    return pd.DataFrame(filas).set_index("etiqueta")


def nulas_por_etiqueta(
    X: pd.DataFrame, etiquetas: dict[str, np.ndarray], ts: np.ndarray, n_nulas: int = 2000, C: float = 0.03,
    dispositivo_: str | None = None,
) -> pd.DataFrame:
    """Out-of-fold AP of every label against `n_nulas` worlds with the labels shifted inside each
    season (same events per season and clustering, no link to the weather)."""
    from . import gpu

    filas = {}
    for nombre, y in etiquetas.items():
        r = gpu.ap_real_y_nulas(X.to_numpy(), y.astype(int), ts, C=C, n_nulas=n_nulas, dispositivo_=dispositivo_)
        filas[nombre] = r
    return pd.DataFrame(filas).T
