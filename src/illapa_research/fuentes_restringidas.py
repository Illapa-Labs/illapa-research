"""Sources that are opt-in: `descargar-datos` without arguments does not download them.

SENAMHI: its terms (https://www.senamhi.gob.pe/?p=terminos-condiciones) make the information
"de uso público" but reserve publication, reproduction, distribution and transformation, and the
project still has no written authorisation. So the files stay in ``datos/senamhi/`` (ignored by
git, left out of the Hugging Face mirror) and are fetched only when asked for by name:
``uv run descargar-datos --solo senamhi``.
"""

from __future__ import annotations

from pathlib import Path

from .fuentes import Fuente

# Legacy codes of the daily series in the researcher download, and the automatic stations whose
# hourly series are kept (Chosica river-level and rain gauge, Matucana and Ñaña weather stations).
HISTORICAS = {
    "151209": "Chosica", "000543": "Ñaña", "000548": "Matucana", "155213": "Santa Eulalia",
    "155122": "Autisha", "155223": "Carampoma", "151205": "Canchacalla", "155224": "Santiago de Tuna",
    "155218": "Huaros", "155217": "Lachaqui", "151213": "Sheque",
}
AUTOMATICAS = {"47278214": "Chosica (hidrometeorológica)", "472CE45A": "Matucana", "111290": "Ñaña"}


def _senamhi(destino: Path) -> list[str]:
    from .senamhi import Cliente

    c = Cliente(destino / "senamhi")
    est = c.estaciones()
    catalogo = destino / "senamhi" / "estaciones.csv"
    est.to_csv(catalogo, index=False)
    for cod in HISTORICAS:
        c.diaria_historica(cod)
    for sid in AUTOMATICAS:
        for periodo in sorted(c.periodos(sid)):
            c.lecturas(sid, periodo)
    return [str(catalogo.relative_to(destino.parent)), str((destino / "senamhi" / "cache").relative_to(destino.parent))]


FUENTES_OPT_IN: dict[str, Fuente] = {
    "senamhi": Fuente(
        id="senamhi",
        nombre="SENAMHI: catálogo de estaciones, series diarias históricas y horarias de 3 estaciones (solo uso local)",
        url="https://observatorio.senamhi.gob.pe/investigadores/",
        licencia="Sin licencia explícita: «uso público» pero sin permiso de redistribuir; NO se sube a git ni al espejo",
        atribucion="Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del "
        "Perú (SENAMHI)",
        descargar=_senamhi,
    )
}
