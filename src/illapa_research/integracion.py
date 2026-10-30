"""Putting the pieces together: how likely is a day, and which quebradas join when it happens.

    P(quebrada i active on day t)  =  P(huaico day t)  x  pi_i

`P(huaico day t)` comes from the daily model (`modelo_diario`). `pi_i` is the share of the
catalogued huaico days, among those that could be placed on a quebrada, in which quebrada i
appears; it is estimated with a Beta(1/2, 1/2) prior and kept separately for Niño and other
seasons. It inherits the reporting bias of the catalogue (people-rich quebradas appear more),
so it is a *relative* weight, not a hazard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import beta


def participacion(activaciones: pd.DataFrame, ubicadas: set[str], temporadas: pd.DataFrame) -> pd.DataFrame:
    """Share of placed huaico days in which each quebrada appears, overall and by season type."""
    a = activaciones[activaciones["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    nino = set(temporadas.index[temporadas["nino"]])
    a = a.assign(nino=a["temporada"].isin(nino))
    dias = a.drop_duplicates("fecha")
    n_total, n_nino, n_no = len(dias), int(dias["nino"].sum()), int((~dias["nino"]).sum())
    filas = []
    for slug in sorted(ubicadas):
        s = a[a["slug"] == slug]
        for etiqueta, k, n in (
            ("todas", len(s), n_total),
            ("nino", int(s["nino"].sum()), n_nino),
            ("no_nino", int((~s["nino"]).sum()), n_no),
        ):
            lo, hi = beta.ppf([0.1, 0.9], k + 0.5, n - k + 0.5)
            filas.append({"slug": slug, "temporadas": etiqueta, "dias_activa": k, "dias_con_evento": n,
                          "pi": (k + 0.5) / (n + 1.0), "pi_p10": lo, "pi_p90": hi})
    return pd.DataFrame(filas)


def activaciones_esperadas(p_dia: pd.Series, pi: pd.DataFrame, nino: pd.Series | None = None) -> pd.DataFrame:
    """Expected number of days each quebrada is active over the days of `p_dia`.

    `p_dia`: probability of a huaico day (index = dates). `pi`: output of `participacion`; when
    `nino` (bool by date) is given, the Niño / other-season shares are used day by day.
    """
    pivot = pi.pivot(index="slug", columns="temporadas", values="pi")
    out = {}
    for slug in pivot.index:
        if nino is None:
            w = pd.Series(pivot.loc[slug, "todas"], index=p_dia.index)
        else:
            w = pd.Series(np.where(nino.reindex(p_dia.index).fillna(False), pivot.loc[slug, "nino"],
                                   pivot.loc[slug, "no_nino"]), index=p_dia.index)
        out[slug] = float((p_dia * w).sum())
    return pd.Series(out, name="activaciones_esperadas").sort_values(ascending=False).to_frame()


def validar_pares(
    p_dia: pd.Series, activaciones: pd.DataFrame, ubicadas: list[str], temporada_por_dia: pd.Series,
    temporadas: pd.DataFrame,
) -> pd.DataFrame:
    """Leave-one-season-out score of "quebrada i is active on day t" for three weightings.

    `p_dia` are out-of-fold daily probabilities (index = rainy-season days). For every held-out
    season the participation `pi_i` is learned from the other seasons only. Models:

    * ``dia_y_quebrada``: p_t x pi_i (the product of the two parts);
    * ``solo_dia``: p_t x mean(pi) (every quebrada alike);
    * ``solo_quebrada``: base rate x pi_i (ignores the weather of the day).
    """
    from sklearn.metrics import average_precision_score, roc_auc_score

    a = activaciones[activaciones["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    filas = []
    base = float(p_dia.mean())
    for s in sorted(temporada_por_dia.unique()):
        test = temporada_por_dia[temporada_por_dia == s].index
        train_act = a[a["temporada"] != s]
        pi = participacion(train_act, set(ubicadas), temporadas[temporadas.index != s])
        pi_i = pi[pi["temporadas"] == "todas"].set_index("slug")["pi"].reindex(ubicadas)
        hoy = a[a["temporada"] == s]
        activos = set(zip(pd.to_datetime(hoy["fecha"]), hoy["slug"], strict=True))
        pt = p_dia.loc[test]
        for slug in ubicadas:
            y = np.array([(d, slug) in activos for d in test], dtype=int)
            filas.append(pd.DataFrame({
                "temporada": s, "slug": slug, "y": y,
                "dia_y_quebrada": (pt.to_numpy() * pi_i[slug]).clip(1e-6, 1 - 1e-6),
                "solo_dia": (pt.to_numpy() * pi_i.mean()).clip(1e-6, 1 - 1e-6),
                "solo_quebrada": np.full(len(pt), base * pi_i[slug]).clip(1e-6, 1 - 1e-6),
            }))
    d = pd.concat(filas, ignore_index=True)
    out = []
    for m in ("dia_y_quebrada", "solo_dia", "solo_quebrada"):
        p = d[m].to_numpy()
        out.append({"modelo": m, "ap": average_precision_score(d["y"], p), "ap_base": d["y"].mean(),
                    "auc": roc_auc_score(d["y"], p),
                    "logloss": float(-np.mean(d["y"] * np.log(p) + (1 - d["y"]) * np.log(1 - p)))})
    return pd.DataFrame(out)
