"""Does knowing the quebrada add anything to knowing the day? Pair-level validation.

A pair is (quebrada i, rainy-season day t); it is positive when quebrada i appears in the catalogue
on day t. Four ways to score a pair, all built leaving the season of the day out (the participation
`pi_i` of every quebrada is learned in the other seasons only):

* ``solo_dia``: P(day t) x mean(pi): every quebrada alike.
* ``solo_quebrada``: base rate x pi_i: ignores the weather of the day.
* ``producto``: P(day t) x pi_i.
* ``producto_regimen``: P(day t) x pi_i of the Niño / other-season share that matches day t.

`P(day t)` is any out-of-sample daily probability: the observed-rain model (chapter 15) or the
GEFS forecast-driven one (chapter 19). The pairs only exist for quebradas with a placed history, and
the catalogue records what people report, so `pi_i` follows exposure; this module measures whether
that is worth anything beyond the day, it does not turn it into hazard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from .integracion import participacion

MODELOS = ("solo_dia", "solo_quebrada", "producto", "producto_regimen")


def pares(
    p_dia: pd.Series, activaciones: pd.DataFrame, ubicadas: list[str], temporadas: pd.DataFrame,
    temporada_por_dia: pd.Series,
) -> pd.DataFrame:
    """Pair table with the four scores. `p_dia`: out-of-sample probability of each rainy-season day."""
    a = activaciones[activaciones["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    activos = set(zip(pd.to_datetime(a["fecha"]), a["slug"], strict=True))
    nino = set(temporadas.index[temporadas["nino"]])
    base = float(p_dia.mean())
    filas = []
    for s in sorted(temporada_por_dia.unique()):
        dias = temporada_por_dia[temporada_por_dia == s].index
        pi = participacion(a[a["temporada"] != s], set(ubicadas), temporadas[temporadas.index != s])
        tabla = pi.pivot(index="slug", columns="temporadas", values="pi").reindex(ubicadas)
        reg = "nino" if s in nino else "no_nino"
        pt = p_dia.loc[dias].to_numpy()
        for slug in ubicadas:
            y = np.array([(d, slug) in activos for d in dias], dtype=int)
            pi_i, pi_r = float(tabla.loc[slug, "todas"]), float(tabla.loc[slug, reg])
            filas.append(pd.DataFrame({
                "temporada": s, "slug": slug, "y": y,
                "solo_dia": pt * float(tabla["todas"].mean()), "solo_quebrada": np.full(len(pt), base * pi_i),
                "producto": pt * pi_i, "producto_regimen": pt * pi_r,
            }))
    d = pd.concat(filas, ignore_index=True)
    for m in MODELOS:
        d[m] = d[m].clip(1e-7, 1 - 1e-7)
    return d


def metricas(d: pd.DataFrame, modelos: tuple[str, ...] = MODELOS) -> pd.DataFrame:
    filas = []
    for m in modelos:
        p, y = d[m].to_numpy(), d["y"].to_numpy()
        filas.append({"modelo": m, "pares": len(d), "positivos": int(y.sum()), "ap": average_precision_score(y, p),
                      "ap_base": float(y.mean()), "auc": roc_auc_score(y, p),
                      "logloss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))})
    return pd.DataFrame(filas)


def diferencia_ap(d: pd.DataFrame, a: str, b: str, n: int = 500, semilla: int = 0) -> dict[str, float]:
    """AP(a) - AP(b) with a season bootstrap (90 % interval): paired by resampling whole seasons."""
    d = d.reset_index(drop=True)  # positional indices below
    rng = np.random.default_rng(semilla)
    seasons = d["temporada"].unique()
    por = {s: d.index[d["temporada"] == s].to_numpy() for s in seasons}
    obs = average_precision_score(d["y"], d[a]) - average_precision_score(d["y"], d[b])
    difs = []
    for _ in range(n):
        idx = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        y = d["y"].to_numpy()[idx]
        if y.sum() == 0:
            continue
        difs.append(average_precision_score(y, d[a].to_numpy()[idx]) - average_precision_score(y, d[b].to_numpy()[idx]))
    lo, hi = np.percentile(difs, [5, 95])
    return {"a": a, "b": b, "dif_ap": float(obs), "p5": float(lo), "p95": float(hi), "excluye_cero": bool(lo > 0 or hi < 0)}


def cobertura_top_k(d: pd.DataFrame, k: int = 5) -> dict[str, float]:
    """Share of the active (quebrada, day) pairs whose quebrada is in the top-k of participation.

    The top-k of each season uses the participation learned in the *other* seasons (the column
    `solo_quebrada` is constant inside a season), so the quebrada never helps pick itself. The
    random expectation is k / number of quebradas.
    """
    n_q = d["slug"].nunique()
    dentro = total = 0
    for _, g in d.groupby("temporada"):
        top = g.groupby("slug")["solo_quebrada"].first().sort_values(ascending=False).index[:k]
        act = g[g["y"] == 1]
        dentro += int(act["slug"].isin(top).sum())
        total += len(act)
    return {"activaciones": total, "en_top_k": dentro, "cobertura": dentro / total if total else float("nan"),
            "al_azar": k / n_q, "k": k, "quebradas": n_q}


def por_subconjunto(d: pd.DataFrame, excluir: dict[str, list[int]]) -> pd.DataFrame:
    """Metrics on all seasons and with each cluster of seasons removed."""
    filas = [metricas(d).assign(subconjunto="todo")]
    for nombre, temporadas in excluir.items():
        filas.append(metricas(d[~d["temporada"].isin(temporadas)]).assign(subconjunto=nombre))
    return pd.concat(filas, ignore_index=True)


def correr(raiz=".", guardar: bool = True) -> dict[str, pd.DataFrame]:
    """Pair validation with observed rain (1984-2026) and with the GEFS forecast at 24, 48 and 72 h."""
    from pathlib import Path

    from . import ficha_pronostico as FP
    from . import filtro
    from . import modelo_diario as md
    from . import quebradas as q
    from .catalogo import CATALOGO, cargar_cuencas, cargar_todos

    raiz = Path(raiz)
    cuencas = filtro.cuencas_a_tabla(cargar_cuencas())
    refs = q.cargar_referencias(CATALOGO / "quebradas_referencias.csv")
    eventos = cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)
    D = md.cargar_datos(raiz)
    T = D.temporadas
    hist = filtro.asignar_historial(eventos, refs, cuencas)
    ranking = filtro.tabla(cuencas, hist, T)
    ubic = sorted(ranking.loc[ranking["evidencia"] == "fisica+historial", "slug"])
    res = md.correr_teorias(D, "temporada", n_jobs=-1, teorias=("lluvia+antecedentes",), con_oraculo=False)
    _, y, ts, _ = md.matrices(D)
    p_dia = pd.Series(res["lluvia+antecedentes"].p, index=y.index)
    tsd = pd.Series(ts, index=y.index)
    excluir = {"sin 2017": [2017], "sin 1983/1998/2017": [1983, 1998, 2017], "desde 2009": list(range(1984, 2009))}
    d_obs = pares(p_dia, hist.activaciones, ubic, T, tsd)
    metr = [por_subconjunto(d_obs, excluir).assign(entrada="lluvia observada (ERA5), 1984-2026")]
    difs = [pd.DataFrame([diferencia_ap(d_obs, "producto", "solo_dia"), diferencia_ap(d_obs, "producto_regimen", "producto"),
                          diferencia_ap(d_obs, "producto", "solo_quebrada")]).assign(entrada="observada"),
            pd.DataFrame([diferencia_ap(d_obs[d_obs["temporada"] != 2017], "producto", "solo_dia")]).assign(entrada="observada sin 2017")]
    oof = FP.cargar_oof(CATALOGO / "gefs_probabilidades_fuera_de_muestra.csv.gz")
    for plazo in (1, 2, 3):
        g = oof[oof["plazo"] == plazo]
        pg = pd.Series(g["pp_qm"].to_numpy(), index=pd.DatetimeIndex(g["dia"]))
        tg = pd.Series(g["temporada"].to_numpy(), index=pg.index)
        d = pares(pg, hist.activaciones, ubic, T, tg)
        metr.append(por_subconjunto(d, {"sin 2017": [2017]}).assign(entrada=f"GEFS {plazo * 24} h, 2000-2019"))
        difs.append(pd.DataFrame([diferencia_ap(d, "producto", "solo_dia")]).assign(entrada=f"GEFS {plazo * 24} h"))
        difs.append(pd.DataFrame([diferencia_ap(d[d["temporada"] != 2017], "producto", "solo_dia")]).assign(entrada=f"GEFS {plazo * 24} h sin 2017"))
    cob = pd.DataFrame([{**cobertura_top_k(d_obs), "entrada": "observada"},
                        {**cobertura_top_k(d_obs[d_obs["temporada"] != 2017]), "entrada": "observada sin 2017"}])
    out = {"metricas": pd.concat(metr, ignore_index=True), "diferencias": pd.concat(difs, ignore_index=True), "cobertura": cob}
    if guardar:
        for k, v in out.items():
            v.round(5).to_csv(raiz / "catalogo" / f"quebradas_dia_{k}.csv", index=False)
    return out


def main(argv: list[str] | None = None) -> int:
    out = correr()
    for v in out.values():
        print(v.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
