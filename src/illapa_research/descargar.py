"""`descargar-datos`: download and structure the open data into a local folder."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .fuentes import FUENTES


def descargar(destino: Path, ids: list[str]) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    manifiesto_ruta = destino / "MANIFIESTO.json"
    manifiesto = (
        json.loads(manifiesto_ruta.read_text(encoding="utf-8")) if manifiesto_ruta.exists() else {}
    )
    for id_ in ids:
        fuente = FUENTES[id_]
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
    ap.add_argument("--solo", nargs="+", choices=sorted(FUENTES), help="descargar solo estas fuentes")
    ap.add_argument("--listar", action="store_true", help="mostrar las fuentes y salir")
    ap.add_argument("--desde-hf", metavar="USUARIO/REPO", help="bajar el espejo en Hugging Face en vez de las fuentes originales")
    ap.add_argument("--subir-hf", metavar="USUARIO/REPO", help="subir datos/ a un dataset de Hugging Face (privado) y salir")
    ap.add_argument("--publico", action="store_true", help="con --subir-hf: repositorio público, sin las fuentes sin licencia explícita")
    args = ap.parse_args(argv)

    if args.listar:
        for f in FUENTES.values():
            print(f"{f.id:14} {f.licencia:55} {f.nombre}")
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
    descargar(args.destino, args.solo or list(FUENTES))
    print(f"Listo. Licencias y atribuciones en {args.destino / 'MANIFIESTO.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
