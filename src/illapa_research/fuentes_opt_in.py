"""Sources that `descargar-datos` does not download unless they are named (opt-in).

SENAMHI: its terms of use (https://www.senamhi.gob.pe/?p=terminos-condiciones) make the information
public and free to use, with or without profit, provided that the SENAMHI is credited with its exact
legend in every medium, the data are not sold, and they are not presented as official. The source is
opt-in only because of its size (about 1 000 requests, 2 s apart) and as a courtesy to the service:
``uv run descargar-datos --solo senamhi``. The files stay in ``datos/senamhi/``, which git ignores;
the Hugging Face mirror carries them with the legend, the "no quality control" warning and the
conditions in its card (see ``espejo_hf.py``).
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
AUTOMATICAS = {
    "47278214": "Chosica (hidrometeorológica)", "472CE45A": "Matucana", "111290": "Ñaña",
    "472EC742": "San Mateo de Otao", "472CA750": "Santiago de Tuna", "472E24B0": "Santa Eulalia (hidrometeorológica)",
}


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
        nombre="SENAMHI: catálogo de estaciones, series diarias históricas y horarias de 6 estaciones automáticas",
        url="https://observatorio.senamhi.gob.pe/investigadores/",
        licencia="Términos de uso del SENAMHI: acceso público y gratuito, con o sin fines de lucro, con la leyenda exacta; no se comercializa ni se presenta como oficial; sin control de calidad",
        atribucion="Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del "
        "Perú (SENAMHI)",
        descargar=_senamhi,
    )
}
