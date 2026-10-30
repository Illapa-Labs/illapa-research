"""Stream and river network as a directed graph, to propagate risk downstream.

OpenStreetMap draws waterways in the direction of flow, so each way becomes a
chain of edges from upstream to downstream.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import networkx as nx


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in metres between two (lon, lat) points."""
    (lon1, lat1), (lon2, lat2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def cargar_osm(ruta: Path) -> nx.DiGraph:
    """Build the graph from an Overpass `out geom` response."""
    return desde_elementos(json.loads(Path(ruta).read_text(encoding="utf-8"))["elements"])


def desde_elementos(elementos: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    for el in elementos:
        if el.get("type") != "way" or "nodes" not in el or "geometry" not in el:
            continue
        ids, geom = el["nodes"], el["geometry"]
        if len(ids) != len(geom):
            continue
        tags = el.get("tags", {})
        for i, (n, p) in enumerate(zip(ids, geom, strict=True)):
            g.add_node(n, lon=p["lon"], lat=p["lat"])
            if i == 0:
                continue
            a = (geom[i - 1]["lon"], geom[i - 1]["lat"])
            b = (p["lon"], p["lat"])
            g.add_edge(
                ids[i - 1],
                n,
                way=el["id"],
                tipo=tags.get("waterway", ""),
                nombre=tags.get("name", ""),
                largo_m=_haversine_m(a, b),
            )
    return g


def aguas_abajo(g: nx.DiGraph, origen: int) -> set[int]:
    """Every node the water can reach from `origen`."""
    return nx.descendants(g, origen)


def nodo_mas_cercano(g: nx.DiGraph, lon: float, lat: float) -> int:
    return min(g.nodes, key=lambda n: _haversine_m((lon, lat), (g.nodes[n]["lon"], g.nodes[n]["lat"])))


def propagar_riesgo(g: nx.DiGraph, riesgo: dict[int, float], decaimiento_km: float = 10.0) -> dict[int, float]:
    """Spread risk downstream with an exponential decay by distance.

    Each node takes the largest risk reaching it from any upstream source, so
    two sources never add up beyond the worst of them.
    """
    salida = dict.fromkeys(g.nodes, 0.0)
    for origen, valor in riesgo.items():
        if origen not in g:
            raise KeyError(f"nodo desconocido: {origen}")
        dist = nx.single_source_dijkstra_path_length(g, origen, weight="largo_m")
        for n, d in dist.items():
            salida[n] = max(salida[n], valor * math.exp(-d / (decaimiento_km * 1000)))
    return salida
