"""Ranking of quebradas by how likely they are to activate as a huaico during an El Niño season.

Two kinds of evidence, kept apart so nobody mistakes one for the other:

* Physical susceptibility (0-100): the mean percentile rank, among the quebradas of 2 to 50 km²,
  of the Melton ratio, the channel slope (10-85 %) and the mean basin slope. No weights were
  fitted. Basins under 2 km² are not scored: a 30 m DEM cannot resolve them.
* Documented history: how many Niño seasons had a catalogued activation, with a Jeffreys 80 %
  interval. Only quebradas that could be placed on the map (see `quebradas_referencias.csv`)
  have history; the rest are "sin historial ubicado", not "never activated".

The level is a fixed rule, not a model fitted to the past (see `clasificar`). It is a research
ranking, not an alert and not a prediction to decide evacuations.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from scipy.stats import beta

from .catalogo import Evento
from .nino import temporada_de

AREA_MAX_QUEBRADA_KM2 = 50.0
AREA_MIN_FIABLE_KM2 = 2.0
VARIABLES_FISICAS = ("melton", "pendiente_cauce_1085_pct", "pendiente_media_pct")
ALTO, MEDIO = 100 * 2 / 3, 100 / 3  # physical-score tertile cut-offs


def normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9()]+", " ", base).split())


def es_generico(token: str) -> bool:
    n = normalizar(token)
    return (
        not n
        or "sin quebrada" in n
        or "varias" in n
        or "ver tabla" in n
        or n in {"huaycos", "inundacion"}
        or n.startswith("(")
        or n.endswith(")") and "(" not in n
    )


@dataclass
class Historial:
    """Result of placing each catalogue event on the basins."""

    activaciones: pd.DataFrame  # fecha, temporada, slug
    resumen: dict[str, int] = field(default_factory=dict)
    sin_ubicar: dict[str, int] = field(default_factory=dict)  # names without a basin


def asignar_historial(eventos: list[Evento], referencias: list[dict], cuencas: pd.DataFrame) -> Historial:
    """Map the free-text `quebradas` field onto basins through the reference table."""
    alias: dict[str, dict] = {}
    for r in referencias:
        for a in (r["nombre"], *r["alias"]):
            alias[normalizar(a)] = r
    slug_de = {c.nombre.removeprefix("Quebrada "): c.slug for c in cuencas.itertuples() if c.nombre}
    filas = set()
    fechas = {e.fecha for e in eventos}
    con_cuenca, con_nombre, sin_nombre = set(), set(), set()
    sin_ubicar: dict[str, int] = defaultdict(int)
    for e in eventos:
        ubicadas, nombradas = [], []
        for token in e.quebradas:
            if es_generico(token):
                continue
            ref = alias.get(normalizar(token))
            if ref is None:
                nombradas.append(token)
            elif slug_de.get(ref["nombre"]):
                ubicadas.append(slug_de[ref["nombre"]])
            else:
                nombradas.append(ref["nombre"])
        for s in ubicadas:
            filas.add((e.fecha, s))
        if ubicadas:
            con_cuenca.add(e.fecha)
        elif nombradas:
            con_nombre.add(e.fecha)
            for n in set(nombradas):
                sin_ubicar[n] += 1
        else:
            sin_nombre.add(e.fecha)
    con_nombre -= con_cuenca
    sin_nombre -= con_cuenca | con_nombre
    df = pd.DataFrame(sorted(filas), columns=["fecha", "slug"])
    df["temporada"] = [temporada_de(f) for f in df["fecha"]]
    resumen = {
        "fechas": len(fechas),
        "con_quebrada_ubicada": len(con_cuenca),
        "con_nombre_sin_ubicar": len(con_nombre),
        "sin_quebrada": len(sin_nombre),
    }
    return Historial(df, resumen, dict(sorted(sin_ubicar.items(), key=lambda kv: -kv[1])))


def susceptibilidad_fisica(cuencas: pd.DataFrame) -> pd.Series:
    """Mean percentile rank (0-100) of the physical variables among the quebradas."""
    rangos = pd.concat([cuencas[v].rank(pct=True) for v in VARIABLES_FISICAS], axis=1)
    return rangos.mean(axis=1) * 100


def intervalo_jeffreys(k: int, n: int, nivel: float = 0.80) -> tuple[float, float, float]:
    """Posterior mean and equal-tailed interval of a rate k/n with a Beta(1/2, 1/2) prior."""
    a, b = k + 0.5, n - k + 0.5
    lo, hi = beta.ppf([(1 - nivel) / 2, 1 - (1 - nivel) / 2], a, b)
    return a / (a + b), float(lo), float(hi)


NIVELES = {
    1: "activada en 2 o más temporadas Niño (documentada)",
    2: "activada en 1 temporada Niño (documentada)",
    3: "sin historial ubicado; susceptibilidad física alta (tercio superior)",
    4: "sin historial ubicado; susceptibilidad física media",
    5: "sin historial ubicado; susceptibilidad física baja",
    6: "no evaluable: menos de 2 km², bajo la resolución del DEM",
}


def clasificar(fisica: float, temporadas_nino_activas: int, evaluable: bool = True) -> int:
    """Fixed level rule, from 1 (strongest evidence) to 6 (not scored).

    Documented activations in Niño seasons come first because they are observations; the
    physical score only orders the quebradas that have none located. Within a level the
    quebradas are ordered by physical score. Nothing here was tuned on the past events.
    """
    if temporadas_nino_activas >= 2:
        return 1
    if temporadas_nino_activas == 1:
        return 2
    if not evaluable:
        return 6
    if fisica >= ALTO:
        return 3
    return 4 if fisica >= MEDIO else 5


def tabla(cuencas: pd.DataFrame, hist: Historial, temporadas: pd.DataFrame) -> pd.DataFrame:
    """Ranking table of the quebradas (basins up to 50 km²)."""
    return _tabla(cuencas, hist.activaciones, temporadas)


def _tabla(
    cuencas: pd.DataFrame, act: pd.DataFrame, temporadas: pd.DataFrame, ubicadas: set[str] | None = None
) -> pd.DataFrame:
    q = cuencas[cuencas["area_km2"] <= AREA_MAX_QUEBRADA_KM2].copy()
    evaluable = q["area_km2"] >= AREA_MIN_FIABLE_KM2
    q["fisica"] = susceptibilidad_fisica(q[evaluable])
    nino = set(temporadas.index[temporadas["nino"]])
    n_nino, n_no = len(nino), len(temporadas) - len(nino)
    ubicadas = ubicadas if ubicadas is not None else set(q.loc[q["ubicacion"] == "referencia", "slug"])
    filas = []
    for r in q.itertuples():
        a = act[act["slug"] == r.slug]
        ts = set(a["temporada"]) & set(temporadas.index)
        k_nino, k_no = len(ts & nino), len(ts - nino)
        tiene = r.slug in ubicadas
        nivel = clasificar(r.fisica, k_nino if tiene else 0, r.area_km2 >= AREA_MIN_FIABLE_KM2)
        p, lo, hi = intervalo_jeffreys(k_nino, n_nino) if tiene else (float("nan"),) * 3
        filas.append(
            {
                "slug": r.slug,
                "nombre": r.nombre,
                "salida_lon": r.salida_lon,
                "salida_lat": r.salida_lat,
                "area_km2": r.area_km2,
                "melton": r.melton,
                "pendiente_cauce_1085_pct": r.pendiente_cauce_1085_pct,
                "pendiente_media_pct": r.pendiente_media_pct,
                "fisica": r.fisica,
                "edificios_1km": r.edificios_1km,
                "dias_activacion": a["fecha"].nunique(),
                "temporadas_nino_activas": k_nino if tiene else None,
                "temporadas_nino": n_nino,
                "temporadas_no_nino_activas": k_no if tiene else None,
                "temporadas_no_nino": n_no,
                "tasa_nino": p,
                "tasa_nino_ic80_bajo": lo,
                "tasa_nino_ic80_alto": hi,
                "evidencia": "fisica+historial" if tiene else "solo fisica",
                "nivel": nivel,
            }
        )
    out = pd.DataFrame(filas)
    out["descripcion_nivel"] = out["nivel"].map(NIVELES)
    out = out.sort_values(["nivel", "tasa_nino", "fisica"], ascending=[True, False, False], na_position="last")
    out.insert(0, "posicion", range(1, len(out) + 1))
    return out.reset_index(drop=True)


def dejar_un_nino_fuera(
    cuencas: pd.DataFrame, hist: Historial, temporadas: pd.DataFrame
) -> pd.DataFrame:
    """Leave-one-Niño-out check.

    For each Niño season with a located activation, the season is removed, the ranking is rebuilt
    from the rest, and we look at the level of each quebrada that did activate in it.
    `percentil_fisica` is where the physical score alone puts it (0 = most susceptible; 50 is what
    a random order gives). `con_historial` is the share of scored quebradas in levels 1 and 2:
    a hit in level 1 or 2 is expected by chance at that rate.

    Caveat: only quebradas that could be placed on the map can appear here, and those are the
    best-known ones, so this checks consistency, not skill on unseen quebradas.
    """
    act = hist.activaciones
    ubicadas = set(cuencas.loc[cuencas["ubicacion"] == "referencia", "slug"])
    filas = []
    for s in sorted(set(act["temporada"]) & set(temporadas.index[temporadas["nino"]])):
        real = set(act.loc[act["temporada"] == s, "slug"])
        t = _tabla(cuencas, act[act["temporada"] != s], temporadas.drop(index=s), ubicadas)
        evaluables = t[t["nivel"] < 6]
        for slug in sorted(real & set(t["slug"])):
            fila = t[t["slug"] == slug].iloc[0]
            if pd.isna(fila["fisica"]):
                continue  # under 2 km²: no physical score to compare
            filas.append(
                {
                    "temporada": s,
                    "slug": slug,
                    "nivel": int(fila["nivel"]),
                    "percentil_fisica": float((evaluables["fisica"] > fila["fisica"]).mean() * 100),
                    "con_historial": float((evaluables["nivel"] <= 2).mean() * 100),
                }
            )
    return pd.DataFrame(filas)


def efecto_nino(eventos: list[Evento], temporadas: pd.DataFrame) -> dict[str, float]:
    """Do Niño seasons have more catalogued huaico days than the others? (any quebrada)

    The catalogue is not complete (1999 to 2008 is thin), so this is a rough contrast.
    """
    from scipy.stats import fisher_exact, mannwhitneyu

    dias = fechas_por_temporada(eventos).reindex(temporadas.index, fill_value=0)
    nino = temporadas["nino"]
    con = dias > 0
    tabla2 = [[int(con[nino].sum()), int((~con[nino]).sum())],
              [int(con[~nino].sum()), int((~con[~nino]).sum())]]
    return {
        "temporadas_nino": int(nino.sum()),
        "temporadas_no_nino": int((~nino).sum()),
        "con_huaico_nino": tabla2[0][0],
        "con_huaico_no_nino": tabla2[1][0],
        "mediana_dias_nino": float(dias[nino].median()),
        "mediana_dias_no_nino": float(dias[~nino].median()),
        "p_fisher": float(fisher_exact(tabla2)[1]),
        "p_mannwhitney": float(mannwhitneyu(dias[nino], dias[~nino]).pvalue),
    }


def fechas_por_temporada(eventos: list[Evento]) -> pd.Series:
    """Number of distinct catalogued huaico days per rainy season, any quebrada."""
    dias: dict[int, set[date]] = defaultdict(set)
    for e in eventos:
        dias[temporada_de(e.fecha)].add(e.fecha)
    return pd.Series({s: len(v) for s, v in sorted(dias.items())})


def cuencas_a_tabla(geojson: dict) -> pd.DataFrame:
    return pd.DataFrame([f["properties"] for f in geojson["features"]])


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from . import nino as _nino
    from .catalogo import CATALOGO, cargar_cuencas, cargar_todos
    from .quebradas import cargar_referencias

    ap = argparse.ArgumentParser(description="Ranking de quebradas para temporadas El Niño")
    ap.add_argument("--datos", type=Path, default=Path("datos"))
    ap.add_argument("--catalogo", type=Path, default=CATALOGO)
    args = ap.parse_args(argv)
    cuencas = cuencas_a_tabla(cargar_cuencas(args.catalogo / "cuencas.geojson"))
    refs = cargar_referencias(args.catalogo / "quebradas_referencias.csv")
    eventos = cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)
    temporadas = _nino.cargar_temporadas(args.datos)
    hist = asignar_historial(eventos, refs, cuencas)
    tabla(cuencas, hist, temporadas).round(4).to_csv(
        args.catalogo / "ranking_quebradas_nino.csv", index=False
    )
    dejar_un_nino_fuera(cuencas, hist, temporadas).round(2).to_csv(
        args.catalogo / "validacion_dejar_un_nino_fuera.csv", index=False
    )
    temporadas.round(3).to_csv(args.catalogo / "temporadas_nino.csv")
    print(hist.resumen)
    print(efecto_nino(eventos, temporadas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
