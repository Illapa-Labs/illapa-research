"""Hierarchical Gamma-Poisson model of huaico days per quebrada and rainy season.

For quebrada i and season s: y_is ~ Poisson(lambda_i * rho^N_s), with N_s = 1 in a Niño season.
lambda_i ~ Gamma(a, a / m_i) and m_i = mu0 * exp(gamma * z_i), where z_i in [-1, 1] is the
physical score of `filtro.py` (an uncalibrated prior: there are too few located quebradas to
recalibrate it). mu0 and rho are estimated together for all quebradas, with wide priors, so
the Niño effect is one rate ratio shared by everybody and the no-Niño base is kept.

lambda_i is integrated out, so only (log mu0, log rho) are sampled (random-walk Metropolis).
Quebradas without located history keep their prior: their rank is wide, not "low".

Results are relative ranks with posterior ranges, never absolute annual probabilities: the
level of the rate is confounded with how well each quebrada is reported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import gammaln

SHAPE = 1.0  # Gamma shape: how much quebradas differ beyond the physical prior
GAMMA_FISICA = 0.35  # log-rate change per unit of z: top vs bottom physical score = x2
PRIOR_LOG_MU0 = (np.log(0.1), 1.5)
PRIOR_LOG_RHO = (0.0, 1.0)  # rho in about 0.14 to 7.4 at 95 %


@dataclass
class Datos:
    slug: list[str]
    z: np.ndarray  # physical prior in [-1, 1]
    y0: np.ndarray  # huaico days in non-Niño seasons (0 where not located)
    y1: np.ndarray  # huaico days in Niño seasons
    ubicada: np.ndarray  # bool: has located history
    n0: int  # non-Niño seasons in the window
    n1: int


def preparar(
    ranking: pd.DataFrame, activaciones: pd.DataFrame, temporadas: pd.DataFrame, desde: int
) -> Datos:
    """Counts per quebrada for the seasons from `desde` on. `ranking` comes from `filtro.tabla`."""
    t = temporadas[temporadas.index >= desde]
    nino = set(t.index[t["nino"]])
    r = ranking[ranking["nivel"] < 6].reset_index(drop=True)
    a = activaciones[activaciones["temporada"].isin(t.index)].drop_duplicates(["fecha", "slug"])
    y1 = np.zeros(len(r))
    y0 = np.zeros(len(r))
    for i, slug in enumerate(r["slug"]):
        d = a[a["slug"] == slug]
        y1[i] = d["temporada"].isin(nino).sum()
        y0[i] = (~d["temporada"].isin(nino)).sum()
    ubicada = r["evidencia"].eq("fisica+historial").to_numpy()
    return Datos(
        slug=list(r["slug"]),
        z=((r["fisica"] - 50) / 50).to_numpy(),
        y0=y0 * ubicada,
        y1=y1 * ubicada,
        ubicada=ubicada,
        n0=len(t) - len(nino),
        n1=len(nino),
    )


def _log_marginal(d: Datos, log_mu0: float, log_rho: float, forma: float, gamma: float) -> float:
    """log p(data | mu0, rho) with lambda_i integrated out, located quebradas only."""
    m = np.exp(log_mu0 + gamma * d.z[d.ubicada])
    y0, y1 = d.y0[d.ubicada], d.y1[d.ubicada]
    rho = np.exp(log_rho)
    y = y0 + y1
    expo = d.n0 + rho * d.n1
    rate = forma / m
    ll = y0 * np.log(d.n0) + y1 * np.log(rho * d.n1)
    ll += gammaln(forma + y) - gammaln(forma) + forma * np.log(rate) - (forma + y) * np.log(rate + expo)
    return float(ll.sum())


def _log_post(d, lm, lr, forma, gamma):
    lp = -0.5 * ((lm - PRIOR_LOG_MU0[0]) / PRIOR_LOG_MU0[1]) ** 2
    lp += -0.5 * ((lr - PRIOR_LOG_RHO[0]) / PRIOR_LOG_RHO[1]) ** 2
    return lp + _log_marginal(d, lm, lr, forma, gamma)


def muestrear(
    d: Datos,
    forma: float = SHAPE,
    gamma: float = GAMMA_FISICA,
    n: int = 6000,
    semilla: int = 0,
    fijar_rho: bool = False,
) -> np.ndarray:
    """Posterior draws of (log mu0, log rho), after burn-in and thinning."""
    rng = np.random.default_rng(semilla)
    estado = np.array([PRIOR_LOG_MU0[0], 0.0])
    lp = _log_post(d, *estado, forma, gamma)
    cadena = []
    for _ in range(n * 5 + 2000):
        prop = estado + rng.normal(0, [0.35, 0.0 if fijar_rho else 0.35])
        lp2 = _log_post(d, *prop, forma, gamma)
        if np.log(rng.uniform()) < lp2 - lp:
            estado, lp = prop, lp2
        cadena.append(estado.copy())
    return np.array(cadena[2000::5])


def lambdas(d: Datos, hiper: np.ndarray, forma: float = SHAPE, gamma: float = GAMMA_FISICA, semilla: int = 1):
    """Posterior draws of lambda_i (rate in a non-Niño season), shape (draws, quebradas)."""
    rng = np.random.default_rng(semilla)
    lm, lr = hiper[:, [0]], hiper[:, [1]]
    m = np.exp(lm + gamma * d.z[None, :])
    rho = np.exp(lr)
    expo = d.n0 + rho * d.n1
    y = d.y0 + d.y1
    return rng.gamma(forma + y[None, :], 1.0 / (forma / m + expo))


def rangos(d: Datos, hiper: np.ndarray, top: int = 5, **kw) -> pd.DataFrame:
    """Rank summary in a Niño season: P(top-k), median rank and 10-90 % range of the rank."""
    lam = lambdas(d, hiper, **kw) * np.exp(hiper[:, [1]])
    orden = (-lam).argsort(axis=1).argsort(axis=1) + 1  # 1 = highest rate
    q = np.percentile(lam, [10, 50, 90], axis=0)
    return pd.DataFrame(
        {
            "slug": d.slug,
            "dias_nino": d.y1,
            "dias_no_nino": d.y0,
            "tasa_nino_p10": q[0],
            "tasa_nino_mediana": q[1],
            "tasa_nino_p90": q[2],
            "p_top5": (orden <= top).mean(axis=0),
            "rango_mediano": np.median(orden, axis=0),
            "rango_p10": np.percentile(orden, 10, axis=0),
            "rango_p90": np.percentile(orden, 90, axis=0),
        }
    )


def razon_de_tasas(hiper: np.ndarray) -> dict[str, float]:
    rho = np.exp(hiper[:, 1])
    return {
        "mediana": float(np.median(rho)),
        "ic80_bajo": float(np.percentile(rho, 10)),
        "ic80_alto": float(np.percentile(rho, 90)),
        "ic95_bajo": float(np.percentile(rho, 2.5)),
        "ic95_alto": float(np.percentile(rho, 97.5)),
        "p_mayor_que_1": float((rho > 1).mean()),
    }


def episodios(temporadas: pd.DataFrame) -> list[list[int]]:
    """Runs of consecutive Niño seasons (2015-2016, 2019-2020...) are one episode."""
    anios = sorted(temporadas.index[temporadas["nino"]])
    out: list[list[int]] = []
    for a in anios:
        if out and a - out[-1][-1] == 1:
            out[-1].append(a)
        else:
            out.append([a])
    return out


def _predictivo(d: Datos, hiper, forma, gamma, nino: bool, semilla=2) -> np.ndarray:
    """Posterior predictive mean rate and P(at least one day), per quebrada, in one season."""
    lam = lambdas(d, hiper, forma, gamma, semilla)
    if nino:
        lam = lam * np.exp(hiper[:, [1]])
    return lam


def validar(
    ranking: pd.DataFrame,
    activaciones: pd.DataFrame,
    temporadas: pd.DataFrame,
    desde: int,
    n: int = 1500,
) -> pd.DataFrame:
    """Leave-one-Niño-episode-out scores for three models on the located quebradas.

    nulo: no Niño effect (rho = 1) but quebradas differ; solo_nino: one rate for everybody with a
    Niño ratio; completo: both. Scores are per (quebrada, held-out season): the Poisson log score
    of the observed count and the Brier score of "any day". Higher log score and lower Brier win.
    """
    t = temporadas[temporadas.index >= desde]
    filas = []
    for ep in episodios(t):
        entrena = t.drop(index=ep)
        act = activaciones[~activaciones["temporada"].isin(ep)]
        d = preparar(ranking, act, entrena, desde)
        prueba = activaciones[activaciones["temporada"].isin(ep)].drop_duplicates(["fecha", "slug"])
        for nombre, forma, gamma, fijar_rho in (
            ("nulo", SHAPE, GAMMA_FISICA, True),
            ("solo_nino", 1e4, 0.0, False),
            ("completo", SHAPE, GAMMA_FISICA, False),
        ):
            hiper = muestrear(d, forma, gamma, n=n, fijar_rho=fijar_rho)
            for s in ep:
                lam = _predictivo(d, hiper, forma, gamma, nino=True)
                for i, slug in enumerate(d.slug):
                    if not d.ubicada[i]:
                        continue
                    y = int((prueba[(prueba["slug"] == slug) & (prueba["temporada"] == s)]).shape[0])
                    l = lam[:, i]
                    p_y = np.mean(np.exp(-l) * l**y / np.exp(gammaln(y + 1)))
                    p_any = 1 - np.mean(np.exp(-l))
                    filas.append(
                        {
                            "episodio": f"{ep[0]}-{ep[-1]}" if len(ep) > 1 else str(ep[0]),
                            "temporada": s,
                            "slug": slug,
                            "modelo": nombre,
                            "dias": y,
                            "log_score": float(np.log(max(p_y, 1e-12))),
                            "brier": float((p_any - (y > 0)) ** 2),
                        }
                    )
    return pd.DataFrame(filas)


DESDE_PRINCIPAL = 2009  # SINPAD/DesInventar era with consistent reporting; 1983 is the sensitivity


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from . import filtro
    from . import nino as _nino
    from .catalogo import CATALOGO, cargar_cuencas, cargar_todos
    from .quebradas import cargar_referencias

    ap = argparse.ArgumentParser(description="Modelo Gamma-Poisson de quebradas y temporadas Niño")
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
    resumen = []
    for desde in (DESDE_PRINCIPAL, 1983):
        d = preparar(ranking, hist.activaciones, temporadas, desde)
        hiper = muestrear(d)
        if desde == DESDE_PRINCIPAL:
            rangos(d, hiper).round(4).to_csv(args.catalogo / "ranking_bayes_quebradas_nino.csv", index=False)
            validar(ranking, hist.activaciones, temporadas, desde).round(4).to_csv(
                args.catalogo / "validacion_modelo_nino.csv", index=False
            )
        resumen.append({"desde": desde, "temporadas_nino": d.n1, "temporadas_no_nino": d.n0,
                        **razon_de_tasas(hiper)})
    pd.DataFrame(resumen).round(3).to_csv(args.catalogo / "razon_de_tasas_nino.csv", index=False)
    print(pd.DataFrame(resumen).round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
