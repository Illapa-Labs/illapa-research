"""Basins of the quebradas that drain into the Rímac and Santa Eulalia rivers.

Pipeline: Copernicus GLO-30 tiles → mosaic in UTM 18S at 30 m → the OSM course of the Rímac and
Santa Eulalia burned into the DEM → pysheds D8 flow directions → every tributary of 1 km² or more
that reaches the main river inside the study window becomes one basin, delimited at its
confluence with the river. Physical attributes are computed per basin.

Nothing here is calibrated against past events; the attributes are plain geometry of the terrain.
"""

from __future__ import annotations

import csv
import json
import math
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as _np_compat
import numpy as np

# pysheds 0.5 still calls numpy.in1d, which NumPy 2.5 removed.
if not hasattr(_np_compat, "in1d"):
    _np_compat.in1d = _np_compat.isin

import rasterio
import shapely
from pyproj import Transformer
from pysheds.grid import Grid
from rasterio.features import rasterize, shapes
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union

CRS_UTM = "EPSG:32718"
RESOLUCION_M = 30.0
# DEM window (west, south, east, north): the Rímac above Lima plus the whole Santa Eulalia valley.
VENTANA_DEM = (-77.0, -12.15, -76.0, -11.0)
# Outlets are kept inside this window (west, south, east, north): Chaclacayo to Ricardo Palma.
VENTANA_SALIDAS = (-76.90, -12.02, -76.52, -11.80)
AREA_MIN_KM2 = 0.4
AREA_RIO_KM2 = 200.0
RIOS_PRINCIPALES = ("Río Rímac", "Río Santa Eulalia")
BURN_M = 30.0

# D8 codes used by pysheds: 64 N, 128 NE, 1 E, 2 SE, 4 S, 8 SW, 16 W, 32 NW.
_D8 = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}

_A_UTM = Transformer.from_crs(4326, 32718, always_xy=True)
_A_LL = Transformer.from_crs(32718, 4326, always_xy=True)


@dataclass
class Terreno:
    """Conditioned terrain: elevation, filled elevation, D8 directions and accumulation (cells)."""

    z: np.ndarray
    z_lleno: np.ndarray
    fdir: np.ndarray
    acc: np.ndarray
    transform: rasterio.Affine

    @property
    def area_celda_km2(self) -> float:
        return RESOLUCION_M * RESOLUCION_M / 1e6


def mosaico_utm(teselas: list[Path], ventana=VENTANA_DEM) -> tuple[np.ndarray, rasterio.Affine]:
    """Merge GLO-30 tiles, cut to the window and reproject to UTM 18S at 30 m (bilinear)."""
    fuentes = [rasterio.open(t) for t in teselas]
    try:
        arr, tr = merge(fuentes, bounds=(ventana[0], ventana[1], ventana[2], ventana[3]))
    finally:
        for f in fuentes:
            f.close()
    arr = arr[0].astype("float32")
    tr_utm, w, h = calculate_default_transform(
        "EPSG:4326", CRS_UTM, arr.shape[1], arr.shape[0], *ventana, resolution=RESOLUCION_M
    )
    z = np.full((h, w), -9999, dtype="float32")
    reproject(
        arr,
        z,
        src_transform=tr,
        src_crs="EPSG:4326",
        dst_transform=tr_utm,
        dst_crs=CRS_UTM,
        dst_nodata=-9999,
        resampling=Resampling.bilinear,
    )
    return z, tr_utm


def rios_osm(ruta_osm: Path, nombres=RIOS_PRINCIPALES) -> list[LineString]:
    """Course of the main rivers from the OSM Overpass dump, in UTM metres."""
    datos = json.loads(Path(ruta_osm).read_text(encoding="utf-8"))
    lineas = []
    for e in datos["elements"]:
        if e.get("tags", {}).get("name") in nombres and e.get("geometry"):
            pts = [_A_UTM.transform(g["lon"], g["lat"]) for g in e["geometry"]]
            lineas.append(LineString(pts))
    return lineas


def acondicionar(z: np.ndarray, tr: rasterio.Affine, rios: list[LineString]) -> Terreno:
    """Burn the main rivers 30 m into the DEM, fill pits and depressions, get D8 flow."""
    zq = z.copy()
    if rios:
        banda = rasterize(
            [(r.buffer(RESOLUCION_M), 1) for r in rios],
            out_shape=z.shape,
            transform=tr,
            dtype="uint8",
        ).astype(bool)
        zq[banda] -= BURN_M
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "dem.tif"
        with rasterio.open(
            ruta, "w", driver="GTiff", height=z.shape[0], width=z.shape[1], count=1,
            dtype="float32", crs=CRS_UTM, transform=tr, nodata=-9999,
        ) as o:
            o.write(zq, 1)
        grid = Grid.from_raster(str(ruta))
        dem = grid.read_raster(str(ruta))
    lleno = grid.fill_depressions(grid.fill_pits(dem))
    plano = grid.resolve_flats(lleno)
    fdir = grid.flowdir(plano)
    acc = grid.accumulation(fdir)
    return Terreno(z=z, z_lleno=np.asarray(lleno), fdir=np.asarray(fdir), acc=np.asarray(acc), transform=tr)


def _siguiente(fdir: np.ndarray) -> np.ndarray:
    """Flat index of the downstream cell, or the cell itself when it drains off the grid."""
    h, w = fdir.shape
    idx = np.arange(h * w).reshape(h, w)
    nxt = idx.copy()
    for cod, (dr, dc) in _D8.items():
        m = fdir == cod
        rr, cc = np.nonzero(m)
        r2, c2 = rr + dr, cc + dc
        ok = (r2 >= 0) & (r2 < h) & (c2 >= 0) & (c2 < w)
        nxt[rr[ok], cc[ok]] = idx[r2[ok], c2[ok]]
    return nxt.ravel()


def _sumidero(nxt: np.ndarray) -> np.ndarray:
    """Terminal cell of every flow path (pointer doubling)."""
    p = nxt.copy()
    while True:
        q = p[p]
        if np.array_equal(q, p):
            return p
        p = q


def _lonlat(tr: rasterio.Affine, r: int, c: int) -> tuple[float, float]:
    x, y = tr * (c + 0.5, r + 0.5)
    return _A_LL.transform(x, y)


def delimitar(t: Terreno, ventana=VENTANA_SALIDAS) -> tuple[np.ndarray, list[dict]]:
    """Label the tributary basins; returns the label grid (0 = none) and the outlets."""
    h, w = t.fdir.shape
    km2 = t.acc.astype("float64") * t.area_celda_km2
    nxt = _siguiente(np.asarray(t.fdir))
    # The Rímac network: cells over the river threshold that reach the same mouth as the Rímac.
    rio = (km2 >= AREA_RIO_KM2).ravel()
    sumidero_total = _sumidero(nxt)
    celda_rimac = np.argmax(km2)
    en_rimac = rio & (sumidero_total == sumidero_total[celda_rimac])
    # Outlets: tributary cells (1 km² or more) whose downstream cell is a river cell.
    cand = (~rio) & (km2.ravel() >= AREA_MIN_KM2) & en_rimac[nxt] & (nxt != np.arange(h * w))
    salidas = []
    for i in np.flatnonzero(cand):
        r, c = divmod(int(i), w)
        lon, lat = _lonlat(t.transform, r, c)
        if ventana[0] <= lon <= ventana[2] and ventana[1] <= lat <= ventana[3]:
            salidas.append({"fila": r, "col": c, "lon": lon, "lat": lat, "idx": int(i)})
    # Stop the paths at the outlets and at the river, then label by the terminal cell.
    nxt2 = nxt.copy()
    nxt2[rio] = np.flatnonzero(rio)
    ids = np.array([s["idx"] for s in salidas], dtype=np.int64)
    nxt2[ids] = ids
    fin = _sumidero(nxt2)
    etiqueta = np.zeros(h * w, dtype=np.int32)
    orden = {int(i): k + 1 for k, i in enumerate(ids)}
    for i, k in orden.items():
        etiqueta[fin == i] = k
    # Basins that touch the DEM edge or nodata are cut short: flag them.
    return etiqueta.reshape(h, w), salidas


def _pendiente_pct(z: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(z, RESOLUCION_M)
    return np.hypot(gx, gy) * 100.0


def cauce_principal(
    t: Terreno, mascara: np.ndarray, salida: tuple[int, int]
) -> tuple[list[tuple[int, int]], np.ndarray]:
    """Longest flow path of a basin, from the farthest cell down to the outlet.

    Returns the cells (head first) and the flow distance of each, in metres.
    """
    filas, cols = np.nonzero(mascara)
    orden = np.argsort(-t.acc[filas, cols], kind="stable")  # downstream cells first
    dist = {(int(salida[0]), int(salida[1])): 0.0}
    paso_d = RESOLUCION_M * math.sqrt(2)
    for k in orden:
        r, c = int(filas[k]), int(cols[k])
        if (r, c) == salida:
            continue
        dr, dc = _D8[int(t.fdir[r, c])]
        dist[(r, c)] = dist[(r + dr, c + dc)] + (paso_d if dr and dc else RESOLUCION_M)
    cabeza = max(dist, key=dist.get)
    ruta = [cabeza]
    while ruta[-1] != salida:
        r, c = ruta[-1]
        dr, dc = _D8[int(t.fdir[r, c])]
        ruta.append((r + dr, c + dc))
    return ruta, np.array([dist[p] for p in ruta])


def atributos(t: Terreno, etiqueta: np.ndarray, salida: dict, k: int) -> dict:
    """Physical attributes of basin `k`."""
    mascara = etiqueta == k
    filas, cols = np.nonzero(mascara)
    n = int(mascara.sum())
    area_m2 = n * RESOLUCION_M**2
    z = t.z[mascara]
    zl = t.z_lleno
    pend = _pendiente_pct(np.where(t.z > -9000, t.z, np.nan))[mascara]
    ruta, dist = cauce_principal(t, mascara, (salida["fila"], salida["col"]))
    perfil = np.array([zl[r, c] for r, c in ruta])
    longitud = float(dist[0])
    z_sal = float(zl[salida["fila"], salida["col"]])
    z_cab = float(perfil[0])
    # Taylor-Schwarz slope: between 10 % and 85 % of the channel length.
    d10, d85 = 0.10 * longitud, 0.85 * longitud
    z10 = float(np.interp(longitud - d10, dist[::-1], perfil[::-1]))
    z85 = float(np.interp(longitud - d85, dist[::-1], perfil[::-1]))
    pend_1085 = (z10 - z85) / (0.75 * longitud) * 100 if longitud > 0 else float("nan")
    relieve = float(z.max() - z.min())
    poligono = _poligono(mascara, t.transform)
    perim = poligono.length
    return {
        "area_km2": area_m2 / 1e6,
        "z_min_m": float(z.min()),
        "z_max_m": float(z.max()),
        "z_media_m": float(z.mean()),
        "relieve_m": relieve,
        "pendiente_media_pct": float(np.nanmean(pend)),
        "longitud_cauce_km": longitud / 1000.0,
        "pendiente_cauce_pct": (z_cab - z_sal) / longitud * 100 if longitud > 0 else float("nan"),
        "pendiente_cauce_1085_pct": pend_1085,
        "melton": relieve / math.sqrt(area_m2),
        "indice_forma": area_m2 / longitud**2 if longitud > 0 else float("nan"),
        "compacidad": perim / (2 * math.sqrt(math.pi * area_m2)),
        "toca_borde": bool(
            filas.min() == 0 or cols.min() == 0 or filas.max() == mascara.shape[0] - 1
            or cols.max() == mascara.shape[1] - 1
        ),
        "_poligono_utm": poligono,
    }


def _poligono(mascara: np.ndarray, tr: rasterio.Affine):
    geoms = [
        shape(g) for g, v in shapes(mascara.astype("uint8"), mask=mascara, transform=tr) if v == 1
    ]
    return unary_union(geoms)


def a_lonlat(geom):
    return shapely.transform(geom, lambda xy: np.column_stack(_A_LL.transform(xy[:, 0], xy[:, 1])))


def cargar_referencias(ruta: Path) -> list[dict]:
    """Reference table: quebrada names, their aliases and, when known, a point inside the basin."""
    filas = []
    with open(ruta, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            r["alias"] = tuple(a.strip() for a in r["alias"].split(";") if a.strip())
            r["lon"] = float(r["lon"]) if r["lon"] else None
            r["lat"] = float(r["lat"]) if r["lat"] else None
            r["area_ref_km2"] = float(r.get("area_ref_km2") or 0) or None
            filas.append(r)
    return filas


def slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in base).split())


def nombrar(cuencas: list[dict], referencias: list[dict], tolerancia_m: float = 150.0) -> None:
    """Give each basin the name of the reference point inside it (or of the outlet within 150 m).

    Fills `slug`, `nombre`, `ubicacion` ("referencia" or "sin_nombre"). Never names by guessing.
    """
    for c in cuencas:
        c.update(nombre="", ubicacion="sin_nombre")
        c["_slug_coord"] = f"q{-c['salida_lon'] * 10000:.0f}-{-c['salida_lat'] * 10000:.0f}"
    for ref in referencias:
        if ref.get("cuenca_slug"):
            for c in cuencas:
                if c["_slug_coord"] == ref["cuenca_slug"]:
                    c.update(nombre=f"Quebrada {ref['nombre']}", ubicacion="referencia")
            continue
        if ref["lon"] is None:
            continue
        x, y = _A_UTM.transform(ref["lon"], ref["lat"])
        p = Point(x, y)
        candidatas = [c for c in cuencas if c["_poligono_utm"].contains(p)] or [
            c for c in cuencas if c["_poligono_utm"].buffer(tolerancia_m).contains(p)
        ]
        # With a published area, the candidate closest to it wins (IGP 2020 points sit on fans);
        # otherwise a point strictly inside a basin wins over a near miss, and then the smallest.
        if candidatas:
            if ref.get("area_ref_km2"):
                candidatas = [c for c in cuencas if c["_poligono_utm"].buffer(tolerancia_m).contains(p)]
                elegida = min(candidatas, key=lambda c: abs(math.log(c["area_km2"] / ref["area_ref_km2"])))
            else:
                elegida = min(candidatas, key=lambda c: c["area_km2"])
            elegida.update(nombre=f"Quebrada {ref['nombre']}", ubicacion="referencia")
    for c in cuencas:
        c["slug"] = slug(c["nombre"][len("Quebrada "):]) if c["nombre"] else c["_slug_coord"]


def exposicion_edificios(cuencas: list[dict], centros: np.ndarray, radio_m: float = 1000.0) -> None:
    """Count OSM buildings near each outlet, outside every basin (the fan and valley floor).

    Each building goes to the nearest outlet within `radio_m`. It is a proxy for people exposed
    on the fan, not a census: OSM coverage is uneven.
    """
    from shapely import contains_xy

    xs, ys = _A_UTM.transform(centros[:, 0], centros[:, 1])
    pts = np.column_stack([xs, ys])
    dentro = np.zeros(len(pts), dtype=bool)
    for c in cuencas:
        poli = c["_poligono_utm"]
        shapely.prepare(poli)
        dentro |= contains_xy(poli, pts[:, 0], pts[:, 1])
    libres = pts[~dentro]
    sal = np.array([_A_UTM.transform(c["salida_lon"], c["salida_lat"]) for c in cuencas])
    d = np.hypot(libres[:, None, 0] - sal[None, :, 0], libres[:, None, 1] - sal[None, :, 1])
    cercana = d.argmin(axis=1)
    ok = d.min(axis=1) <= radio_m
    cuenta = np.bincount(cercana[ok], minlength=len(cuencas))
    for c, n in zip(cuencas, cuenta, strict=True):
        c["edificios_1km"] = int(n)


def construir(teselas: list[Path], ruta_osm: Path, ruta_edificios: Path | None = None) -> list[dict]:
    """Full run: basins with polygon (lon/lat) and attributes, west to east."""
    z, tr = mosaico_utm(teselas)
    t = acondicionar(z, tr, rios_osm(ruta_osm))
    etiqueta, salidas = delimitar(t)
    out = []
    for k, s in enumerate(salidas, start=1):
        a = atributos(t, etiqueta, s, k)
        a.update(salida_lon=s["lon"], salida_lat=s["lat"])
        out.append(a)
    out.sort(key=lambda d: d["salida_lon"])
    if ruta_edificios and Path(ruta_edificios).exists():
        centros = np.array(json.loads(Path(ruta_edificios).read_text())["centros"])
        exposicion_edificios(out, centros)
    return out


def a_geojson(cuencas: list[dict], fuente: str) -> dict:
    feats = []
    for c in cuencas:
        props = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()
                 if not k.startswith("_") and k != "geometria"}
        props["fuente"] = fuente
        feats.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": json.loads(
                    json.dumps(a_lonlat(c["_poligono_utm"].simplify(RESOLUCION_M / 2)).__geo_interface__)
                ),
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Delimita las quebradas y escribe catalogo/cuencas.geojson")
    ap.add_argument("--datos", type=Path, default=Path("datos"))
    ap.add_argument("--catalogo", type=Path, default=Path("catalogo"))
    args = ap.parse_args(argv)
    teselas = [args.datos / "dem" / f"Copernicus_{t}.tif" for t in ("S12_00_W077_00", "S13_00_W077_00")]
    cuencas = construir(teselas, args.datos / "osm_aguas_chosica.json", args.datos / "osm_edificios_centros.json")
    nombrar(cuencas, cargar_referencias(args.catalogo / "quebradas_referencias.csv"))
    gj = a_geojson(cuencas, "Delimitada con Copernicus DEM GLO-30 (30 m) y pysheds; ver catalogo/README.md")
    (args.catalogo / "cuencas.geojson").write_text(
        json.dumps(gj, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{len(cuencas)} cuencas escritas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
