"""Large-scale circulation predictors: 200 hPa wind, Amazon convection, moisture inflow, MJO, SOI.

The boxes and the lags were fixed before any analysis (docs/08-circulacion.md):

* ``u200_altiplano``: NCEP/NCAR R1 zonal wind at 200 hPa, 20S-12S, 75W-65W (Bolivian High; easterly
  wind = negative u = a wetter Altiplano).
* ``olr_amazonia``: NOAA interpolated OLR, 15S-5S, 70W-55W (low OLR = deep convection).
* ``u850_selva``, ``v850_selva``, ``q850_selva``: wind and specific humidity at 850 hPa over the
  central jungle, 14S-8S, 72W-66W.
* ``z500_chile_peru``: NCEP/NCAR R1 geopotential height at 500 hPa, 30S-15S, 85W-72W (trough or
  cut-off low off Chile-Peru), and ``z500_vaguada``: anomaly below the 10th percentile of the
  December-April climatology of 1991-2020.
* MJO: RMM (Australian Bureau of Meteorology) and OMI (NOAA PSL).
* SOI: monthly, Climate Prediction Center, always the previous month.

Every column returned by `construir` is the value of the day itself; the model uses it shifted by
at least one day (`modelo_con_circulacion`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import predictores as P

SERIES = ("u200_altiplano", "olr_amazonia", "u850_selva", "v850_selva", "q850_selva", "z500_chile_peru")


def cargar_ncep_olr(ruta: Path) -> pd.DataFrame:
    """Daily area means written by `descargar-datos --solo noaa-circulacion`."""
    return pd.read_csv(ruta, index_col="fecha", parse_dates=True)


def cargar_rmm(ruta: Path) -> pd.DataFrame:
    """RMM1, RMM2, amplitude and phase; the BoM missing values (1e36, 999) become NaN."""
    filas = []
    for linea in Path(ruta).read_text(encoding="utf-8", errors="replace").splitlines():
        t = linea.split()
        if len(t) < 7 or not t[0].isdigit():
            continue
        try:
            y, m, d = int(t[0]), int(t[1]), int(t[2])
            r1, r2, fase, amp = (float(x) for x in t[3:7])
        except ValueError:
            continue
        filas.append((pd.Timestamp(y, m, d), r1, r2, fase, amp))
    df = pd.DataFrame(filas, columns=["fecha", "rmm1", "rmm2", "rmm_fase", "rmm_amp"]).set_index("fecha")
    return df.where(df.abs() < 900)


def cargar_omi(ruta: Path) -> pd.DataFrame:
    """OMI PC1, PC2 and amplitude (NOAA PSL), daily."""
    df = pd.read_csv(ruta, sep=r"\s+", header=None, names=["y", "m", "d", "omi1", "omi2", "omi_amp"])
    df["fecha"] = pd.to_datetime(df[["y", "m", "d"]].rename(columns={"y": "year", "m": "month", "d": "day"}))
    return df.set_index("fecha")[["omi1", "omi2", "omi_amp"]].where(lambda x: x.abs() < 900)


def cargar_soi(ruta: Path) -> pd.Series:
    """Monthly standardised SOI (Tahiti - Darwin) from the CPC file; index = first day of the month."""
    texto = Path(ruta).read_text(encoding="utf-8", errors="replace").splitlines()
    # The file holds several tables; the standardised one follows the line "STANDARDIZED DATA".
    inicio = next((i for i, linea in enumerate(texto) if "STANDARDIZED" in linea.upper()), None)
    if inicio is None:
        raise ValueError("no encuentro la tabla estandarizada en el archivo del SOI")
    filas = {}
    for linea in texto[inicio:]:
        # fixed width: 4-character year, then twelve fields of six characters ("-999.9-999.9")
        if len(linea) >= 76 and linea[:4].isdigit():
            for mes in range(12):
                campo = linea[4 + 6 * mes : 10 + 6 * mes]
                try:
                    x = float(campo)
                except ValueError:
                    continue
                if abs(x) < 90:
                    filas[pd.Timestamp(int(linea[:4]), mes + 1, 1)] = x
    return pd.Series(filas, name="soi").sort_index()


def construir(datos: Path, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily circulation features for `idx` (anomalies against 1991-2020, plus short means).

    Columns are the value of the day; shift them before using them to look ahead.
    """
    datos = Path(datos) / "circulacion"
    f = pd.DataFrame(index=idx)
    base = cargar_ncep_olr(datos / "ncep_olr_diario.csv").reindex(idx)
    for c in SERIES:
        if c not in base:
            continue
        a = P.anomalia(base[c])
        f[f"{c}_anom"] = a
        f[f"{c}_anom_3d"] = a.rolling(3, min_periods=2).mean()
        f[f"{c}_anom_7d"] = a.rolling(7, min_periods=4).mean()
        if c == "olr_amazonia":
            f[f"{c}_anom_15d"] = a.rolling(15, min_periods=8).mean()
        if c == "z500_chile_peru":
            ref = a[(a.index.year >= 1991) & (a.index.year <= 2020) & ((a.index.month >= 12) | (a.index.month <= 4))]
            f["z500_vaguada"] = (a <= ref.quantile(0.10)).astype(float).where(a.notna())
    if {"q850_selva", "u850_selva"} <= set(base):
        flujo = base["q850_selva"] * base["u850_selva"]  # zonal moisture flux (g/kg m/s)
        f["flujo_q_u850_anom"] = P.anomalia(flujo)
        f["flujo_q_u850_anom_3d"] = f["flujo_q_u850_anom"].rolling(3, min_periods=2).mean()
    if (datos / "rmm.txt").exists():
        f = f.join(cargar_rmm(datos / "rmm.txt").drop(columns="rmm_fase").reindex(idx))
    if (datos / "omi.txt").exists():
        f = f.join(cargar_omi(datos / "omi.txt").reindex(idx))
    if (datos / "soi_cpc.txt").exists():
        soi = cargar_soi(datos / "soi_cpc.txt")
        # previous calendar month, known in full from the first day of the next month
        previo = soi.copy()
        previo.index = previo.index + pd.offsets.MonthBegin(1)
        f["soi_mes_previo"] = previo.reindex(idx.to_period("M").to_timestamp()).to_numpy()
    return f


def con_circulacion(X: pd.DataFrame, C: pd.DataFrame, mask: np.ndarray, desplazar: int = 1) -> pd.DataFrame:
    """Add the circulation columns, shifted `desplazar` days (at least 1), to a design matrix.

    `X` is already masked to the rainy-season rows; `C` covers the whole calendar so the shift is
    taken before the mask.
    """
    if desplazar < 1:
        raise ValueError("las variables de circulación deben ir desplazadas al menos un día")
    nuevas = C.shift(desplazar).add_suffix("_circ")[mask]
    nuevas.index = X.index
    return pd.concat([X, nuevas], axis=1)


# ------------------------------------------------------------------ does it add to the daily model?
def ganancia_ap(
    D, C: pd.DataFrame, folds_tipo: str = "temporada", n_jobs: int = 4, etiquetas: pd.Series | None = None,
    solo: list[str] | None = None,
) -> dict[str, float]:
    """Out-of-fold average precision of `lluvia+antecedentes` with and without the circulation.

    `D` comes from `modelo_diario.cargar_datos`; `C` from `construir`. `etiquetas` replaces the real
    labels (used for the shifted-label null). `solo` keeps a subset of the circulation columns.
    The circulation enters shifted by one day or more (`con_circulacion`).
    """
    from sklearn.metrics import average_precision_score

    from . import evaluacion_diaria as E
    from . import modelo_diario as md
    from . import nino as N

    X, y, ts, _ = md.matrices(D)
    if etiquetas is not None:
        y = etiquetas
    base = X["lluvia+antecedentes"]
    cols = C if solo is None else C[solo]
    mas = con_circulacion(base, cols, D.inventario["mask"])
    eps = N.episodios(D.temporadas) if folds_tipo == "episodio" else None
    folds = [f for f in E.pliegues(ts, folds_tipo, eps) if len(f)]
    p0 = md.validar_anidado(base, y, ts, folds, n_jobs=n_jobs).p
    p1 = md.validar_anidado(mas, y, ts, folds, n_jobs=n_jobs).p
    ok = ~np.isnan(p0) & ~np.isnan(p1)
    yv = y.to_numpy()
    ap0 = float(average_precision_score(yv[ok], p0[ok]))
    ap1 = float(average_precision_score(yv[ok], p1[ok]))
    return {"ap_sin": ap0, "ap_con": ap1, "ganancia": ap1 - ap0, "columnas": int(mas.shape[1] - base.shape[1])}


def ganancia_nula(
    D, C: pd.DataFrame, n: int = 12, folds_tipo: str = "temporada", n_jobs: int = 4, semilla: int = 0,
    solo: list[str] | None = None,
) -> np.ndarray:
    """Gain in average precision when the huaico labels are shifted inside each season.

    The shift keeps the number of events and their clustering in every season but breaks their
    link with the weather, so it shows how much AP the extra columns "earn" by chance.
    """
    from . import modelo_diario as md
    from . import senales as S

    _, y, ts, _ = md.matrices(D)
    rng = np.random.default_rng(semilla)
    out = []
    for _ in range(n):
        ys = pd.Series(S._desplazar_etiquetas(y.to_numpy(), ts, rng, "local"), index=y.index)
        out.append(ganancia_ap(D, C, folds_tipo, n_jobs, ys, solo)["ganancia"])
    return np.array(out)


# ------------------------------------------------------------- many null worlds on the GPU
def _oof_logit(Z: np.ndarray, y: np.ndarray, folds: list[np.ndarray], C: float, dispositivo_: str | None = None) -> np.ndarray:
    """Out-of-fold probabilities of one ridge-logistic design `Z` over the given test folds."""
    from . import gpu

    n = len(y)
    Y = np.tile(y.astype(float), (len(folds), 1))
    M = np.ones((len(folds), n), dtype=bool)
    for k, f in enumerate(folds):
        M[k, f] = False
    Pl = gpu.ajustar_logit_lote(Z, Y, M, C=C, dispositivo_=dispositivo_)
    p = np.full(n, np.nan)
    for k, f in enumerate(folds):
        p[f] = Pl[k, f]
    return p


def mover_filas_en_temporada(B: np.ndarray, temporada: np.ndarray, rng: np.random.Generator, minimo: int = 5) -> np.ndarray:
    """Rows of `B` cyclically shifted inside every season (the block keeps its own persistence and
    its seasonal cycle, but loses the day-to-day link with the labels)."""
    out = B.copy()
    for s in np.unique(temporada):
        i = np.flatnonzero(temporada == s)
        if len(i) > 2 * minimo:
            out[i] = np.roll(B[i], int(rng.integers(minimo, len(i) - minimo)), axis=0)
    return out


def ganancia_bloque(
    Xbase: np.ndarray, Bloque: np.ndarray, y: np.ndarray, temporada: np.ndarray, folds: list[np.ndarray],
    C: float = 0.03, n_nulas: int = 1000, semilla: int = 0, dispositivo_: str | None = None,
    trozo_mundos: int = 25,
) -> dict[str, float]:
    """Average-precision gain of adding `Bloque` to `Xbase`, against null worlds, all on the GPU.

    Both models are the same ridge-logistic fit (fixed `C`) over the same test folds
    (`folds`: leave-one-season-out or leave-one-episode-out). A null world moves the rows of the
    block cyclically inside each season and refits every fold; its gain is AP(base + moved block)
    minus AP(base). `p` is the share of null worlds whose gain reaches the real one (plus one).
    Missing values are median-imputed and everything standardised before (no labels used).
    """
    from . import gpu

    rng = np.random.default_rng(semilla)
    yv = np.asarray(y, dtype=float)
    Zb = gpu.estandarizar(Xbase)
    Zk = gpu.estandarizar(Bloque)
    p0 = _oof_logit(Zb, yv, folds, C, dispositivo_)
    p1 = _oof_logit(np.hstack([Zb, Zk]), yv, folds, C, dispositivo_)
    ok = ~np.isnan(p0) & ~np.isnan(p1)
    _, ap0 = gpu.auc_ap_lote(yv[None], p0[None], ok[None], dispositivo_)
    _, ap1 = gpu.auc_ap_lote(yv[None], p1[None], ok[None], dispositivo_)
    ganancias = []
    for _ in range(0, n_nulas, trozo_mundos):
        P = []
        for _ in range(min(trozo_mundos, n_nulas - len(ganancias))):
            Zm = mover_filas_en_temporada(Zk, temporada, rng)
            P.append(_oof_logit(np.hstack([Zb, Zm]), yv, folds, C, dispositivo_))
        P = np.array(P)
        _, ap = gpu.auc_ap_lote(np.tile(yv, (len(P), 1)), np.nan_to_num(P), np.tile(ok, (len(P), 1)), dispositivo_)
        ganancias.extend((ap - ap0[0]).tolist())
    g = np.array(ganancias)
    real = float(ap1[0] - ap0[0])
    return {
        "ap_base": float(ap0[0]), "ap_con": float(ap1[0]), "ganancia": real, "columnas": int(Bloque.shape[1]),
        "nula_media": float(g.mean()), "nula_p95": float(np.percentile(g, 95)), "nula_p99": float(np.percentile(g, 99)),
        "nula_max": float(g.max()), "p": float((1 + (g >= real).sum()) / (1 + len(g))), "n_nulas": len(g),
    }


def matrices_para_bloques(D, C: pd.DataFrame, desplazar: int = 1, hasta_temporada: int | None = None):
    """Design pieces for `ganancia_bloque`: base matrix, shifted circulation block, labels, seasons.

    `hasta_temporada` drops later seasons entirely (for the OLR, which ends in 2022, so that no
    median has to be imputed).
    """
    from . import modelo_diario as md

    X, y, ts, _ = md.matrices(D)
    base = X["lluvia+antecedentes"]
    bloque = C.shift(desplazar).add_suffix("_circ")[D.inventario["mask"]]
    bloque.index = base.index
    if hasta_temporada is not None:
        k = ts <= hasta_temporada
        base, bloque, y, ts = base[k], bloque[k], y[k], ts[k]
    return base, bloque, y, ts


def grupos(columnas: list[str]) -> dict[str, list[str]]:
    """The hypothesis blocks of docs/08-circulacion.md, by column name."""
    g = {
        "T16 u200": [c for c in columnas if c.startswith("u200")],
        "T17 OLR y MJO": [c for c in columnas if c.startswith(("olr", "rmm", "omi"))],
        "T18 SOI": [c for c in columnas if c.startswith("soi")],
        "T19 850 hPa": [c for c in columnas if c.startswith(("u850", "v850", "q850", "flujo"))],
        "T20 z500": [c for c in columnas if c.startswith("z500")],
        "todas": list(columnas),
    }
    return {k: v for k, v in g.items() if v}


def grupos_t19(columnas: list[str]) -> dict[str, list[str]]:
    """Ablation of the 850 hPa block: one variable at a time and in pairs."""
    u = [c for c in columnas if c.startswith("u850")]
    v = [c for c in columnas if c.startswith("v850")]
    q = [c for c in columnas if c.startswith("q850")]
    f = [c for c in columnas if c.startswith("flujo")]
    g = {"u850": u, "v850": v, "q850": q, "flujo q·u": f, "u850 + v850": u + v, "u850 + v850 + flujo": u + v + f,
         "T19 completo": u + v + q + f}
    return {k: x for k, x in g.items() if x}


def correr_gpu(
    raiz: Path, especificaciones: list[dict], n_nulas: int = 1000, C: float = 0.03, dias_antes: int = 0,
    desde: int = 1984, quitar: tuple[int, ...] = (), hasta_temporada: int | None = None, semilla: int = 0,
    dispositivo_: str | None = None, verbose: bool = True,
) -> pd.DataFrame:
    """Gain of each block against `n_nulas` null worlds, with leave-season-out and leave-episode-out folds.

    `especificaciones`: list of {"prueba": name, "columnas": [...]}. The scenario (label with the
    day before, window, dropped seasons, last season) is set by the other arguments and written
    in every row, so tables of different scenarios can be stacked.
    """
    from . import evaluacion_diaria as E
    from . import modelo_diario as md
    from . import nino as N

    D = md.cargar_datos(Path(raiz), dias_antes=dias_antes, desde=desde, quitar_temporadas=quitar)
    Cir = construir(Path(raiz) / "datos", D.F.index)
    base, bloque, y, ts = matrices_para_bloques(D, Cir, 1, hasta_temporada)
    eps = [e for e in N.episodios(D.temporadas) if any(s in set(ts) for s in e)]
    out = []
    for esp in especificaciones:
        cols = [c + "_circ" for c in esp["columnas"] if c + "_circ" in bloque.columns]
        if not cols:
            continue
        for tipo in ("temporada", "episodio"):
            folds = [f for f in E.pliegues(ts, tipo, eps if tipo == "episodio" else None) if len(f)]
            r = ganancia_bloque(base.to_numpy(), bloque[cols].to_numpy(), y.to_numpy(), ts, folds, C=C,
                                n_nulas=n_nulas, semilla=semilla, dispositivo_=dispositivo_)
            r.update(prueba=esp["prueba"], pliegues=tipo, dias_antes=dias_antes, desde=desde,
                     quitar=",".join(map(str, quitar)), hasta_temporada=hasta_temporada or 9999,
                     filas=len(y), positivos=int(y.sum()))
            out.append(r)
            if verbose:
                print(f"{esp['prueba']:24s} {tipo:9s} ganancia={r['ganancia']:+.4f} p95={r['nula_p95']:.4f} p={r['p']:.4f}", flush=True)
    return pd.DataFrame(out)
