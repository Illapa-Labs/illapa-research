"""Run the satellite pilot: seasonal change per basin against the catalogue activations.

``uv run --extra satelite python -m illapa_research.satelite_piloto`` (on the remote PC: it reads from the cloud)
Writes ``catalogo/satelite_cambio_temporadas.csv`` and ``catalogo/satelite_validacion.csv``.
The design (scenes, windows, primary index, direction) is fixed in ``satelite.py`` before the run.
"""

from __future__ import annotations

import json

import pandas as pd
from shapely.geometry import shape

from . import filtro
from . import quebradas as q
from . import satelite as S
from .catalogo import CATALOGO, cargar_cuencas, cargar_todos


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Piloto de cambio satelital por temporada")
    ap.add_argument("--desde", type=int, default=2019)
    ap.add_argument("--hasta", type=int, default=2026)
    a = ap.parse_args(argv)

    rank = pd.read_csv(CATALOGO / "ranking_quebradas_nino.csv")
    core = rank[rank["evidencia"] == "fisica+historial"]
    cuencas = core[["slug", "salida_lon", "salida_lat"]].to_dict("records")
    geo = json.loads((CATALOGO / "cuencas.geojson").read_text(encoding="utf-8"))
    b = [shape(f["geometry"]).bounds for f in geo["features"] if f["properties"].get("slug") in set(core["slug"])]
    bbox = (min(x[0] for x in b) - 0.005, min(x[1] for x in b) - 0.005, max(x[2] for x in b) + 0.005,
            max(x[3] for x in b) + 0.005)

    filas = []
    for anio in range(a.desde, a.hasta + 1):
        r = S.cambio_temporada(anio, cuencas, bbox)
        print(anio, "cuencas:", len(r), "|", (r[0]["antes"], r[0]["despues"]) if r else "sin escenas", flush=True)
        filas += r
    t = pd.DataFrame(filas)

    ev = cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True)
    cu = filtro.cuencas_a_tabla(cargar_cuencas())
    refs = q.cargar_referencias(CATALOGO / "quebradas_referencias.csv")
    act = filtro.asignar_historial(ev, refs, cu).activaciones.copy()
    act["f"] = pd.to_datetime(act["fecha"])
    activa = {(s, int(y)) for s, y in zip(act["slug"], act["f"].dt.year + (act["f"].dt.month >= 11), strict=True)}
    t["activa"] = [(s, int(y)) in activa for s, y in zip(t["slug"], t["temporada"], strict=True)]
    t.round(5).to_csv(CATALOGO / "satelite_cambio_temporadas.csv", index=False)

    val = []
    for col, signo in (S.PRIMARIA, *S.SECUNDARIAS):
        val.append({"indice": col, "signo_esperado": signo, **S.auc_dentro_de_temporada(t, col, signo)})
    v = pd.DataFrame(val)
    v.round(4).to_csv(CATALOGO / "satelite_validacion.csv", index=False)
    print(v.round(3).to_string(index=False))
    print(t.groupby("temporada").agg(n=("slug", "size"), validas=("nbr_media", lambda s: int(s.notna().sum())),
                                     activas=("activa", "sum")).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
