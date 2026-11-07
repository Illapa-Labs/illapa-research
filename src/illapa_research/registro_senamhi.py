"""Daily snapshot of what the SENAMHI says, for the prospective validation of the 2026-27 season.

A warning that is active today can not be reconstructed tomorrow: the API gives history by year, but not
what was published when. Each run saves, with its time stamp, the active and the issued (not started)
weather warnings of the Lima and Huarochirí provinces, the short-term rain warnings of five districts
and the recent daily series of three stations. About 15 calls per run (the account allows 1 000 a day).

``uv run python -m illapa_research.registro_senamhi`` (once a day; a second run on the same day is a no-op
unless ``--forzar``). Files go to ``datos/senamhi_api/registro/`` (outside git and the public mirror) with
the SENAMHI legend in each one.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .avisos_senamhi import DISTRITOS, PROVINCIAS
from .senamhi_api import LEYENDA, ApiDetenida, ClienteApi

ESTACIONES = {"111060": "CHOSICA (pluviómetro)", "111086": "SANTA EULALIA (pluviómetro)", "111291": "SAN MATEO DE OTAO"}


def llamadas() -> list[tuple[str, dict | None, str]]:
    """The endpoint, its parameters and a short name for each call of one snapshot."""
    out: list[tuple[str, dict | None, str]] = []
    for ub, nombre in PROVINCIAS.items():
        for estado in ("active", "issued"):
            out.append((f"/weather-warnings/{estado}", {"ubigeo": ub}, f"avisos_{estado}_{nombre}"))
    for ub, nombre in DISTRITOS.items():
        for estado in ("active", "issued"):
            out.append((f"/short-term-warnings/{estado}", {"ubigeo": ub}, f"corto_{estado}_{nombre}"))
    for est, nombre in ESTACIONES.items():
        out.append((f"/stations/{est}/time-series", None, f"serie_{est}"))
    return out


def tomar_foto(c: ClienteApi, carpeta: Path = Path("datos/senamhi_api/registro"), ahora: datetime | None = None,
               forzar: bool = False) -> list[Path]:
    """Save one snapshot; returns the files written (none if there is already one today)."""
    ahora = ahora or datetime.now(ZoneInfo("America/Lima"))
    carpeta.mkdir(parents=True, exist_ok=True)
    hoy = ahora.strftime("%Y-%m-%d")
    if not forzar and any(carpeta.glob(f"{hoy}T*__*.json")):
        return []
    escritos = []
    for ruta, params, nombre in llamadas():
        d = c.get(ruta, params, fresco=True)
        archivo = carpeta / f"{ahora.strftime('%Y-%m-%dT%H%M')}__{nombre}.json"
        archivo.write_text(json.dumps({"consultado": ahora.isoformat(), "ruta": ruta, "parametros": params,
                                       "leyenda": LEYENDA, "data": d}, ensure_ascii=False), encoding="utf-8")
        escritos.append(archivo)
    return escritos


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Foto diaria de los avisos y estaciones del SENAMHI")
    ap.add_argument("--forzar", action="store_true", help="tomar otra foto aunque ya haya una hoy")
    a = ap.parse_args(argv)
    c = ClienteApi()
    try:
        escritos = tomar_foto(c, forzar=a.forzar)
    except ApiDetenida as e:
        print("DETENIDA:", e)
        return 1
    print(f"{len(escritos)} archivos guardados" if escritos else "ya hay una foto de hoy (usa --forzar)",
          "| llamadas hoy:", c.llamadas_hoy())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
