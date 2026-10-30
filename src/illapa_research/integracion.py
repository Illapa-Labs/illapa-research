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
