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
