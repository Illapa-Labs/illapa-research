"""Event catalog and basin polygons for the Chosica and Chaclacayo pilot."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CATALOGO = Path(__file__).resolve().parents[2] / "catalogo"


@dataclass(frozen=True)
class Evento:
    fecha: date
    precision_fecha: str
    distrito: str
    quebradas: tuple[str, ...]
    fuente: str
    confianza: str
    notas: str


def cargar_eventos(ruta: Path = CATALOGO / "eventos.csv", solo_dia_exacto: bool = False) -> list[Evento]:
    """Read the event catalog, optionally keeping only events with an exact day."""
    eventos = []
    with open(ruta, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if solo_dia_exacto and r["precision_fecha"] != "dia":
                continue
            eventos.append(
                Evento(
                    fecha=date.fromisoformat(r["fecha"]),
                    precision_fecha=r["precision_fecha"],
                    distrito=r["distrito"],
                    quebradas=tuple(q for q in r["quebradas"].split(";") if q),
                    fuente=r["fuente"],
                    confianza=r["confianza"],
                    notas=r["notas"],
                )
            )
    return eventos


def cargar_cuencas(ruta: Path = CATALOGO / "cuencas.geojson") -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))
