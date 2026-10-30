"""Gamma-Poisson model of huaico days per quebrada, with a reporting (exposure) term.

y0_i, y1_i = catalogued huaico days of quebrada i in non-Niño / Niño seasons of the window.

    lambda_i ~ Gamma(a, a / m_i),   m_i = mu0 * exp(gamma * z_i + delta * e_i)
    y0_i ~ Poisson(lambda_i * n0),  y1_i ~ Poisson(lambda_i * rho * n1)

z_i is the physical score (-1..1), e_i the standardised log number of buildings near the outlet.
The catalogue records what people saw and reported, so `delta` is not "danger": it measures how
much the record follows where people live. A model that wants to rank *propensity to activate*
must keep that term apart (`rangos(..., neutralizar_exposicion=True)`).

Everything is validated by predicting held-out quebradas (leave-one-quebrada-out) and held-out
Niño episodes, against simpler models.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.special import gammaln

SHAPE = 1.0
PRIORS = {"lm": (np.log(0.1), 1.5), "lr": (0.0, 1.0), "g": (0.0, 0.5), "d": (0.0, 0.5)}

MODELOS: dict[str, tuple[str, ...]] = {
    "nulo": (),
    "nino": ("lr",),
    "nino+fisica": ("lr", "g"),
    "nino+exposicion": ("lr", "d"),
    "nino+fisica+exposicion": ("lr", "g", "d"),
}


@dataclass
class Datos:
    slug: list[str]
    z: np.ndarray
    e: np.ndarray
    y0: np.ndarray
    y1: np.ndarray
    ubicada: np.ndarray
    n0: int
    n1: int
    s0: np.ndarray | None = None  # seasons with at least one day, non-Niño
    s1: np.ndarray | None = None  # same, Niño
    modo: str = "temporadas"  # "temporadas" (binomial, robust to clusters) or "dias" (Poisson)

    def tomar(self, mask: np.ndarray) -> Datos:
        return replace(self, slug=[s for s, k in zip(self.slug, mask, strict=True) if k],
                       z=self.z[mask], e=self.e[mask], y0=self.y0[mask], y1=self.y1[mask],
                       ubicada=self.ubicada[mask], s0=self.s0[mask], s1=self.s1[mask])


def preparar(
    ranking: pd.DataFrame, activaciones: pd.DataFrame, temporadas: pd.DataFrame, desde: int,
    hasta_temporadas: list[int] | None = None,
) -> Datos:
    """Counts per quebrada in the seasons from `desde` (optionally only `hasta_temporadas`)."""
    t = temporadas[temporadas.index >= desde]
    if hasta_temporadas is not None:
        t = t.loc[[s for s in t.index if s in set(hasta_temporadas)]]
    nino = set(t.index[t["nino"]])
    r = ranking.reset_index(drop=True)
    a = activaciones[activaciones["temporada"].isin(t.index)].drop_duplicates(["fecha", "slug"])
    y1 = np.zeros(len(r))
    y0 = np.zeros(len(r))
    s1 = np.zeros(len(r))
    s0 = np.zeros(len(r))
    for i, slug in enumerate(r["slug"]):
        d = a[a["slug"] == slug]
        y1[i] = d["temporada"].isin(nino).sum()
        y0[i] = (~d["temporada"].isin(nino)).sum()
        ts = set(d["temporada"])
        s1[i] = len(ts & nino)
        s0[i] = len(ts - nino)
    ubicada = r["evidencia"].eq("fisica+historial").to_numpy()
    le = np.log1p(r["edificios_1km"].to_numpy(dtype=float))
    ev = r["nivel"].to_numpy() < 6
    e = (le - le[ev].mean()) / le[ev].std()
    z = ((r["fisica"] - 50) / 50).fillna(0.0).to_numpy()
    return Datos(list(r["slug"]), z, e, y0 * ubicada, y1 * ubicada, ubicada, len(t) - len(nino), len(nino),
                 s0 * ubicada, s1 * ubicada)


def _theta(v: np.ndarray, libres: tuple[str, ...]) -> dict[str, float]:
    th = {"lm": v[0], "lr": 0.0, "g": 0.0, "d": 0.0}
    for k, x in zip(libres, v[1:], strict=True):
        th[k] = x
    return th


_K = 48
_Q = (np.arange(_K) + 0.5) / _K


def _loglik(d: Datos, th: dict[str, float], forma: float, solo_ubicadas: bool = True) -> np.ndarray:
    """Per-quebrada log marginal likelihood with lambda integrated out."""
    from scipy.stats import gamma as gam

    m = np.exp(th["lm"] + th["g"] * d.z + th["d"] * d.e)
    rho = np.exp(th["lr"])
    if d.modo == "dias":
        y = d.y0 + d.y1
        expo = d.n0 + rho * d.n1
        rate = forma / m
        ll = d.y0 * np.log(d.n0) + d.y1 * np.log(rho * d.n1)
        ll = ll + gammaln(forma + y) - gammaln(forma) + forma * np.log(rate) - (forma + y) * np.log(rate + expo)
        ll = ll - gammaln(d.y0 + 1) - gammaln(d.y1 + 1)
    else:
        # seasons with at least one catalogued day: P(active) = 1 - exp(-lambda * rho^Niño)
        lam = gam.ppf(_Q[None, :], forma, scale=(m / forma)[:, None])  # (quebradas, K)
        p0 = -np.expm1(-lam)
        p1 = -np.expm1(-lam * rho)
        s0, s1 = d.s0[:, None], d.s1[:, None]
        lk = (s0 * np.log(p0 + 1e-300) + (d.n0 - s0) * (-lam) + s1 * np.log(p1 + 1e-300) + (d.n1 - s1) * (-lam * rho))
        mx = lk.max(axis=1)
        ll = mx + np.log(np.exp(lk - mx[:, None]).mean(axis=1))
        ll = ll + (gammaln(d.n0 + 1) - gammaln(d.s0 + 1) - gammaln(d.n0 - d.s0 + 1)
                   + gammaln(d.n1 + 1) - gammaln(d.s1 + 1) - gammaln(d.n1 - d.s1 + 1))
    return ll[d.ubicada] if solo_ubicadas else ll


def _logpost(d: Datos, v: np.ndarray, libres: tuple[str, ...], forma: float) -> float:
    th = _theta(v, libres)
    lp = 0.0
    for k, x in th.items():
        if k == "lm" or k in libres:
            mu, sd = PRIORS[k]
            lp += -0.5 * ((x - mu) / sd) ** 2
    return lp + float(_loglik(d, th, forma).sum())


def muestrear(
    d: Datos, modelo: str = "nino+fisica+exposicion", forma: float = SHAPE, n: int = 3000, semilla: int = 0
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Posterior draws of the free parameters (columns: lm, then those of the model)."""
    libres = MODELOS[modelo]
    rng = np.random.default_rng(semilla)
    v = np.array([PRIORS["lm"][0]] + [0.0] * len(libres))
    lp = _logpost(d, v, libres, forma)
    paso = np.array([0.3] + [0.25] * len(libres))
    cadena = []
    for _ in range(1500 + n * 4):
        prop = v + rng.normal(0, paso)
        lp2 = _logpost(d, prop, libres, forma)
        if np.log(rng.uniform()) < lp2 - lp:
            v, lp = prop, lp2
        cadena.append(v.copy())
    return np.array(cadena[1500::4]), libres


def resumen_parametros(hiper: np.ndarray, libres: tuple[str, ...]) -> pd.DataFrame:
    nombres = ["mu0 (días por temporada, sin Niño)"] + list(libres)
    filas = []
    for j, k in enumerate(["lm", *libres]):
        x = hiper[:, j]
        if k == "lm":
            x, nombre = np.exp(x), "mu0"
        elif k == "lr":
            x, nombre = np.exp(x), "rho (razón de tasas Niño)"
        else:
            nombre = {"g": "gamma (física)", "d": "delta (exposición)"}[k]
        filas.append({"parametro": nombre, "mediana": np.median(x), "p10": np.percentile(x, 10),
                      "p90": np.percentile(x, 90), "p_positivo": float((hiper[:, j] > 0).mean())
                      if k != "lm" else np.nan})
    del nombres
    return pd.DataFrame(filas)


def _log_pred_nuevo(d: Datos, i: int, hiper: np.ndarray, libres: tuple[str, ...], forma: float) -> float:
    """log p(y0_i, y1_i) of a held-out quebrada: Gamma prior only, averaged over the posterior."""
    out = []
    dd = d.tomar(np.arange(len(d.slug)) == i)
    dd.ubicada = np.array([True])
    for v in hiper:
        out.append(float(_loglik(dd, _theta(v, libres), forma, solo_ubicadas=False)[0]))
    m = max(out)
    return float(m + np.log(np.mean(np.exp(np.array(out) - m))))


def dejar_una_quebrada_fuera(d: Datos, modelos: list[str] | None = None, n: int = 800) -> pd.DataFrame:
    """Leave-one-quebrada-out predictive log score of the observed counts of each located quebrada."""
    filas = []
    for i in np.flatnonzero(d.ubicada):
        entrena = d.tomar(np.arange(len(d.slug)) != i)
        for nombre in modelos or list(MODELOS):
            hiper, libres = muestrear(entrena, nombre, n=n)
            filas.append({"slug": d.slug[i], "modelo": nombre, "y0": d.y0[i], "y1": d.y1[i],
                          "log_pred": _log_pred_nuevo(d, i, hiper, libres, SHAPE)})
    return pd.DataFrame(filas)


def rangos(
    d: Datos, hiper: np.ndarray, libres: tuple[str, ...], neutralizar_exposicion: bool = False,
    top: int = 5, semilla: int = 1,
) -> pd.DataFrame:
    """Posterior rank (1 = highest rate in a Niño season) of every quebrada.

    With `neutralizar_exposicion` the reporting term is set to the average quebrada, so the
    ranking reflects physical score and observed history without the "more buildings, more
    reports" effect.
    """
    rng = np.random.default_rng(semilla)
    lam = np.empty((len(hiper), len(d.slug)))
    for k, v in enumerate(hiper):
        th = _theta(v, libres)
        e = np.zeros_like(d.e) if neutralizar_exposicion else d.e
        m = np.exp(th["lm"] + th["g"] * d.z + th["d"] * e)
        rho = np.exp(th["lr"])
        expo = d.n0 + rho * d.n1
        y = d.y0 + d.y1
        lam[k] = rng.gamma(SHAPE + y, 1.0 / (SHAPE / m + expo)) * rho
    orden = (-lam).argsort(axis=1).argsort(axis=1) + 1
    q = np.percentile(lam, [10, 50, 90], axis=0)
    return pd.DataFrame(
        {"slug": d.slug, "dias_nino": d.y1, "dias_no_nino": d.y0, "ubicada": d.ubicada,
         "tasa_nino_p10": q[0], "tasa_nino_mediana": q[1], "tasa_nino_p90": q[2],
         f"p_top{top}": (orden <= top).mean(axis=0), "rango_mediano": np.median(orden, axis=0),
         "rango_p10": np.percentile(orden, 10, axis=0), "rango_p90": np.percentile(orden, 90, axis=0)}
    )


def _p_activa(d: Datos, hiper: np.ndarray, libres: tuple[str, ...], nino: bool, semilla: int = 3) -> np.ndarray:
    """Posterior predictive P(at least one day in a season) per quebrada, shape (quebradas,)."""
    rng = np.random.default_rng(semilla)
    acc = np.zeros(len(d.slug))
    for v in hiper:
        th = _theta(v, libres)
        m = np.exp(th["lm"] + th["g"] * d.z + th["d"] * d.e)
        rho = np.exp(th["lr"])
        y = d.s0 + d.s1
        expo = d.n0 + rho * d.n1
        lam = rng.gamma(SHAPE + 0 * y, m / SHAPE)  # prior draw; refined below for located ones
        # located quebradas: posterior of lambda given their seasons (approximate, Poisson on seasons)
        post = rng.gamma(SHAPE + y, 1.0 / (SHAPE / m + expo))
        lam = np.where(d.ubicada, post, lam)
        acc += -np.expm1(-lam * (rho if nino else 1.0))
    return acc / len(hiper)


def dejar_un_episodio_fuera(
    ranking: pd.DataFrame, activaciones: pd.DataFrame, temporadas: pd.DataFrame, desde: int,
    modelos: list[str] | None = None, n: int = 600,
) -> pd.DataFrame:
    """Leave-one-Niño-episode-out: predict which located quebradas are active in the held-out seasons.

    A fold removes every season of one Niño episode (or a block of three non-Niño seasons),
    fits on the rest and scores P(active) for each (quebrada, held-out season) with the log
    score and the Brier score. `climatologia` ignores the Niño flag and the covariates.
    """
    from .modelo import episodios

    t = temporadas[temporadas.index >= desde]
    eps = episodios(t)
    usados = {s for ep in eps for s in ep}
    resto = [s for s in t.index if s not in usados]
    bloques = eps + [resto[i : i + 3] for i in range(0, len(resto), 3)]
    act = activaciones.drop_duplicates(["fecha", "slug"])
    filas = []
    for bloque in bloques:
        d = preparar(ranking, activaciones, temporadas, desde, [s for s in t.index if s not in bloque])
        for nombre in modelos or list(MODELOS):
            hiper, libres = muestrear(d, nombre, n=n)
            for s in bloque:
                es_nino = bool(t.loc[s, "nino"])
                p = _p_activa(d, hiper, libres, es_nino)
                activos = set(act.loc[act["temporada"] == s, "slug"])
                for i in np.flatnonzero(d.ubicada):
                    y = int(d.slug[i] in activos)
                    pi = float(np.clip(p[i], 1e-4, 1 - 1e-4))
                    filas.append({"bloque": f"{bloque[0]}-{bloque[-1]}" if len(bloque) > 1 else str(bloque[0]),
                                  "temporada": s, "nino": es_nino, "slug": d.slug[i], "modelo": nombre,
                                  "activa": y, "p": pi,
                                  "log_score": y * np.log(pi) + (1 - y) * np.log(1 - pi),
                                  "brier": (pi - y) ** 2})
    return pd.DataFrame(filas)


def contraste_temporadas(act: pd.DataFrame, ubicadas: set[str], temporadas: pd.DataFrame, desde: int) -> dict[str, float]:
    """Season-level contrast: quebradas (of those placed) active in Niño vs other seasons.

    One number per season, so the strong dependence between quebradas that activate together
    does not inflate the evidence. Mann-Whitney one-sided p-value.
    """
    from scipy.stats import mannwhitneyu

    t = temporadas[temporadas.index >= desde]
    a = act[act["slug"].isin(ubicadas)].drop_duplicates(["fecha", "slug"])
    k = a.groupby("temporada")["slug"].nunique().reindex(t.index, fill_value=0)
    n, m = k[t["nino"]], k[~t["nino"]]
    return {"desde": desde, "temporadas_nino": len(n), "temporadas_no_nino": len(m),
            "media_activas_nino": float(n.mean()), "media_activas_no_nino": float(m.mean()),
            "p_mannwhitney": float(mannwhitneyu(n, m, alternative="greater").pvalue)}


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from . import filtro
    from . import nino as _nino
    from .catalogo import CATALOGO, cargar_cuencas, cargar_todos
    from .quebradas import cargar_referencias

    ap = argparse.ArgumentParser(description="Modelo Gamma-Poisson por quebrada con término de exposición")
    ap.add_argument("--datos", type=Path, default=Path("datos"))
    ap.add_argument("--catalogo", type=Path, default=CATALOGO)
    args = ap.parse_args(argv)
    cuencas = filtro.cuencas_a_tabla(cargar_cuencas(args.catalogo / "cuencas.geojson"))
    refs = cargar_referencias(args.catalogo / "quebradas_referencias.csv")
    eventos = cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)
    temporadas = _nino.temporadas(
        _nino.cargar_oni(args.datos / "enso" / "noaa_oni.txt"),
        _nino.cargar_nino12(args.datos / "enso" / "noaa_nino12.txt"),
    )
    hist = filtro.asignar_historial(eventos, refs, cuencas)
    ranking = filtro.tabla(cuencas, hist, temporadas)
    ubic = set(ranking.loc[ranking["evidencia"] == "fisica+historial", "slug"])
    par, cont = [], []
    for desde in (2009, 1983):
        d = preparar(ranking, hist.activaciones, temporadas, desde)
        hiper, libres = muestrear(d, "nino+fisica+exposicion")
        p = resumen_parametros(hiper, libres)
        p.insert(0, "desde", desde)
        par.append(p)
        cont.append(contraste_temporadas(hist.activaciones, ubic, temporadas, desde))
        if desde == 2009:
            rangos(d, hiper, libres).round(4).to_csv(args.catalogo / "ranking_bayes_quebradas_nino.csv", index=False)
            rangos(d, hiper, libres, neutralizar_exposicion=True).round(4).to_csv(
                args.catalogo / "ranking_bayes_quebradas_nino_sin_exposicion.csv", index=False
            )
            dejar_una_quebrada_fuera(d).round(4).to_csv(args.catalogo / "validacion_dejar_una_quebrada_fuera.csv", index=False)
            dejar_un_episodio_fuera(ranking, hist.activaciones, temporadas, desde).round(4).to_csv(
                args.catalogo / "validacion_dejar_un_episodio_fuera.csv", index=False
            )
    pd.concat(par).round(3).to_csv(args.catalogo / "parametros_modelo_quebradas.csv", index=False)
    pd.DataFrame(cont).round(4).to_csv(args.catalogo / "contraste_temporadas_nino.csv", index=False)
    print(pd.concat(par).round(2).to_string(index=False))
    print(pd.DataFrame(cont).round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
