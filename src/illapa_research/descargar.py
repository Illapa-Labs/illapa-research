"""`descargar-datos`: download and structure the open data into a local folder."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .fuentes import FUENTES
from .fuentes_restringidas import FUENTES_OPT_IN

TODAS = {**FUENTES, **FUENTES_OPT_IN}


def descargar(destino: Path, ids: list[str]) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    manifiesto_ruta = destino / "MANIFIESTO.json"
    manifiesto = (
        json.loads(manifiesto_ruta.read_text(encoding="utf-8")) if manifiesto_ruta.exists() else {}
    )
    for id_ in ids:
        fuente = TODAS[id_]
        print(f"→ {fuente.nombre}", flush=True)
        archivos = fuente.descargar(destino)
        manifiesto[id_] = {
            "nombre": fuente.nombre,
            "url": fuente.url,
            "licencia": fuente.licencia,
            "atribucion": fuente.atribucion,
            "descargado": datetime.now(UTC).isoformat(timespec="seconds"),
            "archivos": archivos,
        }
        manifiesto_ruta.write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return manifiesto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="descargar-datos",
        description="Descarga las fuentes abiertas y deja un MANIFIESTO.json con la licencia de cada una.",
    )
    ap.add_argument("--destino", type=Path, default=Path("datos"), help="carpeta local (datos/)")
    ap.add_argument("--solo", nargs="+", choices=sorted(TODAS), help="descargar solo estas fuentes (las de uso restringido, como senamhi, solo se bajan si se nombran)")
    ap.add_argument("--listar", action="store_true", help="mostrar las fuentes y salir")
    ap.add_argument("--desde-hf", metavar="USUARIO/REPO", help="bajar el espejo en Hugging Face en vez de las fuentes originales")
    ap.add_argument("--subir-hf", metavar="USUARIO/REPO", help="subir datos/ a un dataset de Hugging Face (privado) y salir")
    ap.add_argument("--publico", action="store_true", help="con --subir-hf: repositorio público, sin las fuentes sin licencia explícita")
    args = ap.parse_args(argv)

    if args.listar:
        for f in TODAS.values():
            marca = " (opt-in)" if f.id in FUENTES_OPT_IN else ""
            print(f"{f.id:14} {f.licencia:55} {f.nombre}{marca}")
        return 0

    if args.desde_hf:
        from .espejo_hf import bajar

        print(f"Espejo bajado en {bajar(args.desde_hf, args.destino)}")
        return 0
    if args.subir_hf:
        from .espejo_hf import subir

        print("Subido:", ", ".join(subir(args.subir_hf, args.destino, args.publico)),
              "(repositorio público)" if args.publico else "(repositorio privado)")
        return 0
    descargar(args.destino, args.solo or list(FUENTES))  # opt-in sources never run by default
    print(f"Listo. Licencias y atribuciones en {args.destino / 'MANIFIESTO.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
