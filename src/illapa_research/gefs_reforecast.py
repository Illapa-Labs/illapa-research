"""GEFSv12 reforecast (NOAA, 2000-2019) read by byte ranges from its public AWS bucket.

Why this source: it is the only long, homogeneous archive of *forecasts* (one model version for
20 years), which is what a fair backtest of "forecast rain -> probability of a huaico day" needs.
The ERA5-based models of chapters 05 and 15 only say what is possible with the right rain.

Bucket (anonymous HTTPS, no key, no account): ``s3://noaa-gefs-retrospective``, files
``GEFSv12/reforecast/AAAA/AAAAMMDD00/<member>/Days:1-10/<var>_AAAAMMDD00_<member>.grib2`` with a
``.idx`` next to each. One run per day at 00 UTC, 5 members (``c00``, ``p01``..``p04``), a global
0.25 degree grid (1440 x 721, latitude 90 to -90, longitude 0 to 359.75), 3-hourly steps in the
first 10 days. ``apcp_sfc`` holds both 3-hour and 6-hour accumulations; only the 6-hour windows
``6-12``, ``12-18``, ... are used. Licence: NOAA open data (attribute, do not imply endorsement).

Alignment with the local day (Lima is UTC-5). The run of day ``r`` starts at 00 UTC = 19:00 of day
``r-1``. Local day ``d`` runs from 05 UTC of ``d`` to 05 UTC of ``d+1``; its closest block of
6-hour windows is forecast hours 6 to 30 of run ``d`` (UTC 06 of ``d`` to 06 of ``d+1``, which is
01:00 to 01:00 local, a 1-hour offset that is documented, not corrected). A *lead* of ``k`` days
uses the run issued ``k-1`` days earlier, so every lead only uses information available before
the day starts:

* lead 1 (0-24 h): run ``d``,   hours 6-30
* lead 2 (24-48 h): run ``d-1``, hours 30-54
* lead 3 (48-72 h): run ``d-2``, hours 54-78

CAPE and total precipitable water (T29) are read from the control member only, at the two
3-hourly steps around the local afternoon (18 and 21 UTC-hours of each 24-hour block: 13:00 and
16:00 local).

Boxes (fixed before any result was looked at; cells whose 0.25 degree square intersects the box
are averaged): the six PISCOp cells of the Rímac valley used by `correccion_sesgo`
(``valle``) and the boxes of chapter 10 (``fuentes.CAJAS_CHIRPS``).
"""

from __future__ import annotations

import io
import re
import time
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BUCKET = "https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast"
MIEMBROS = ("c00", "p01", "p02", "p03", "p04")
# Boxes as (west, south, east, north) in degrees. The first one covers the six 0.1 degree PISCOp cells.
CAJAS = {
    "valle": (-76.80, -12.00, -76.50, -11.80),
    "chosica": (-76.80, -12.03, -76.60, -11.83),
    "santa-eulalia-alta": (-76.50, -11.80, -76.30, -11.60),
    "matucana": (-76.48, -11.94, -76.28, -11.74),
    "ticlio": (-76.30, -11.70, -76.10, -11.50),
}
VENTANAS_LLUVIA = tuple((h, h + 6) for h in range(6, 78, 6))  # 6-12 ... 72-78
# lead (days) -> (run offset in days, first forecast hour of the 24 h block)
LEADS = {1: (0, 6), 2: (1, 30), 3: (2, 54)}
HORAS_TARDE = (18, 21)  # hours inside a 24 h block counted from its first hour: 13:00 and 16:00 local


@dataclass(frozen=True)
class Mensaje:
    inicio: int
    fin: int | None  # None: until the end of the file
    descripcion: str
    h_ini: int | None
    h_fin: int | None


_RE_ACUM = re.compile(r"(\d+)-(\d+) hour acc fcst")
_RE_PASO = re.compile(r":(\d+) hour fcst")


def leer_idx(texto: str) -> list[Mensaje]:
    """Parse a wgrib2-style ``.idx`` into messages with their byte range and forecast hours."""
    filas = [f for f in texto.strip().split("\n") if f]
    inicios = [int(f.split(":")[1]) for f in filas]
    out = []
    for i, f in enumerate(filas):
        fin = inicios[i + 1] - 1 if i + 1 < len(filas) else None
        m = _RE_ACUM.search(f)
        if m:
            h_ini, h_fin = int(m.group(1)), int(m.group(2))
        else:
            p = _RE_PASO.search(f)
            h_ini, h_fin = (None, int(p.group(1))) if p else (None, None)
        out.append(Mensaje(inicios[i], fin, f, h_ini, h_fin))
    return out


def ventanas_6h(mensajes: Iterable[Mensaje], hasta: int = 78) -> list[Mensaje]:
    """The 6-hour accumulation windows (6-12, 12-18, ...) up to forecast hour `hasta`."""
    sel = [m for m in mensajes if m.h_ini is not None and m.h_fin - m.h_ini == 6 and m.h_ini >= 6
           and m.h_ini % 6 == 0 and m.h_fin <= hasta]
    return sorted(sel, key=lambda m: m.h_ini)


def pasos(mensajes: Iterable[Mensaje], horas: Iterable[int]) -> list[Mensaje]:
    """Instantaneous messages at the given forecast hours (CAPE, precipitable water)."""
    horas = set(horas)
    return sorted((m for m in mensajes if m.h_ini is None and m.h_fin in horas), key=lambda m: m.h_fin)


def url_archivo(fecha_run: date, miembro: str, variable: str) -> str:
    f = f"{fecha_run:%Y%m%d}00"
    return f"{BUCKET}/{fecha_run.year}/{f}/{miembro}/Days:1-10/{variable}_{f}_{miembro}.grib2"


def _get(sesion: requests.Session, url: str, rango: tuple[int, int | None] | None = None, intentos: int = 6):
    """GET with exponential backoff inside the call (never a blind sleep between checks)."""
    cab = {}
    if rango is not None:
        cab["Range"] = f"bytes={rango[0]}-{'' if rango[1] is None else rango[1]}"
    for k in range(intentos):
        try:
            r = sesion.get(url, headers=cab, timeout=60)
            if r.status_code in (200, 206):
                return r.content
            if r.status_code == 404:
                raise FileNotFoundError(url)
        except requests.RequestException:
            pass
        time.sleep(min(30.0, 0.5 * 2**k))
    raise RuntimeError(f"sin respuesta tras {intentos} intentos: {url}")


def celdas_de_caja(lat: np.ndarray, lon: np.ndarray, caja: tuple[float, float, float, float]):
    """Indices (rows, cols) of the 0.25 degree cells whose square intersects the box.

    `lat` runs 90 to -90 and `lon` 0 to 359.75, as in the files. Longitudes of the box are given
    in -180..180.
    """
    w, s, e, n = caja
    lon180 = np.where(lon > 180, lon - 360, lon)
    cols = np.flatnonzero((lon180 + 0.125 > w) & (lon180 - 0.125 < e))
    filas = np.flatnonzero((lat + 0.125 > s) & (lat - 0.125 < n))
    return filas, cols


def decodificar(contenido: bytes) -> np.ndarray:
    """GRIB2 message -> 2-D array (721 x 1440). Needs `eccodes` (extra `gefs`)."""
    import eccodes

    h = eccodes.codes_new_from_message(contenido)
    try:
        ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
        return eccodes.codes_get_values(h).reshape(nj, ni)
    finally:
        eccodes.codes_release(h)


LAT = np.linspace(90, -90, 721)
LON = np.linspace(0, 359.75, 1440)
_CELDAS = {k: celdas_de_caja(LAT, LON, v) for k, v in CAJAS.items()}


def medias_por_caja(campo: np.ndarray) -> dict[str, float]:
    """Mean of the field over the cells of each box."""
    return {k: float(campo[np.ix_(f, c)].mean()) for k, (f, c) in _CELDAS.items()}


def _extraer(sesion, fecha_run: date, miembro: str, variable: str, seleccion) -> list[dict]:
    url = url_archivo(fecha_run, miembro, variable)
    idx = leer_idx(_get(sesion, url + ".idx").decode())
    msgs = seleccion(idx)
    if not msgs:
        return []
    out = []
    if variable.startswith("apcp"):
        # one contiguous read covers all the windows (the 3 h messages in between are skipped)
        ini, fin = msgs[0].inicio, msgs[-1].fin
        bloque = _get(sesion, url, (ini, fin))
        for m in msgs:
            trozo = bloque[m.inicio - ini : (m.fin + 1 - ini) if m.fin is not None else None]
            for caja, v in medias_por_caja(decodificar(trozo)).items():
                out.append({"miembro": miembro, "variable": "apcp", "h_ini": m.h_ini, "h_fin": m.h_fin,
                            "caja": caja, "valor": v})
    else:
        for m in msgs:
            trozo = _get(sesion, url, (m.inicio, m.fin))
            for caja, v in medias_por_caja(decodificar(trozo)).items():
                out.append({"miembro": miembro, "variable": variable.split("_")[0], "h_ini": None,
                            "h_fin": m.h_fin, "caja": caja, "valor": v})
    return out


def horas_tarde() -> list[int]:
    """Forecast hours of the afternoon CAPE / PWAT steps of the three leads (13:00 and 16:00 local)."""
    return sorted(h0 + h for _, h0 in LEADS.values() for h in HORAS_TARDE)


def procesar_corrida(fecha_run: date, miembros: Iterable[str] = MIEMBROS, con_convectivas: bool = True) -> pd.DataFrame:
    """Everything needed from the run of `fecha_run` (00 UTC): 6-hour rain of all members in the
    boxes and, from the control member only, CAPE and precipitable water in the afternoons."""
    s = requests.Session()
    filas: list[dict] = []
    for m in miembros:
        filas += _extraer(s, fecha_run, m, "apcp_sfc", lambda idx: ventanas_6h(idx))
    if con_convectivas:
        for var in ("cape_sfc", "pwat_eatm"):
            filas += _extraer(s, fecha_run, "c00", var, lambda idx: pasos(idx, horas_tarde()))
    df = pd.DataFrame(filas)
    df.insert(0, "run", pd.Timestamp(fecha_run))
    return df


def fechas_de_corridas(desde: int, hasta: int) -> list[date]:
    """Runs needed for the rainy seasons `desde`..`hasta` (December to April), plus two days
    before December so that leads 2 and 3 of 1 December are covered."""
    out = []
    for a in range(desde, hasta + 1):
        d = date(a - 1, 11, 29)
        while d <= date(a, 4, 30):
            out.append(d)
            d += timedelta(days=1)
    return out


def _trabajo(args: tuple[date, str, bool]) -> str:
    d, carpeta, con_convectivas = args
    try:
        df = procesar_corrida(d, con_convectivas=con_convectivas)
    except FileNotFoundError:
        return f"falta {d}"
    df.to_csv(Path(carpeta) / f"{d:%Y%m%d}.csv", index=False, float_format="%.4f")
    return ""


def descargar(destino: Path, desde: int = 2000, hasta: int = 2019, hilos: int = 5,
              con_convectivas: bool = True) -> int:
    """Download and reduce every run to a small CSV in `destino/runs/`; resumable.

    Decoding GRIB2 holds the interpreter, so the work runs in processes, not threads (the first
    version with threads did about 10 runs a minute).
    """
    carpeta = Path(destino) / "runs"
    carpeta.mkdir(parents=True, exist_ok=True)
    pendientes = [d for d in fechas_de_corridas(desde, hasta) if not (carpeta / f"{d:%Y%m%d}.csv").exists()]
    trabajos = [(d, str(carpeta), con_convectivas) for d in pendientes]
    hechos = 0
    with ProcessPoolExecutor(hilos) as pool:
        for r in pool.map(_trabajo, trabajos, chunksize=2):
            hechos += 1
            if r:
                print(r, flush=True)
            if hechos % 100 == 0:
                print(f"{hechos}/{len(pendientes)} corridas", flush=True)
    return hechos


def cargar_corridas(destino: Path) -> pd.DataFrame:
    """All reduced runs in one table."""
    archivos = sorted((Path(destino) / "runs").glob("*.csv"))
    if not archivos:  # the mirror ships the same table as a single file
        unica = Path(destino) / "gefs_corridas.csv.gz"
        return pd.read_csv(unica, parse_dates=["run"]) if unica.exists() else pd.DataFrame()
    return pd.concat((pd.read_csv(a, parse_dates=["run"]) for a in archivos), ignore_index=True)


def lluvia_por_dia_y_plazo(corridas: pd.DataFrame) -> pd.DataFrame:
    """Rain (mm) of local day ``d`` by lead, member and box: sum of four 6-hour windows.

    Index: (dia, plazo, miembro, caja). Only days whose run is available are returned.
    """
    ll = corridas[corridas["variable"] == "apcp"]
    filas = []
    for plazo, (desfase, h0) in LEADS.items():
        sel = ll[(ll["h_ini"] >= h0) & (ll["h_fin"] <= h0 + 24)]
        g = sel.groupby(["run", "miembro", "caja"])["valor"].agg(["sum", "count"]).reset_index()
        g = g[g["count"] == 4]
        g["dia"] = g["run"] + pd.Timedelta(days=desfase)
        g["plazo"] = plazo
        filas.append(g[["dia", "plazo", "miembro", "caja", "sum"]].rename(columns={"sum": "mm"}))
    return pd.concat(filas, ignore_index=True)


def resumen_de_ensamble(lluvia: pd.DataFrame, umbrales: tuple[float, ...] = (1.0, 5.0, 10.0)) -> pd.DataFrame:
    """Ensemble mean, maximum, spread and exceedance probabilities per (day, lead, box)."""
    def agr(x: pd.Series) -> pd.Series:
        v = x.to_numpy()
        d = {"media": v.mean(), "maximo": v.max(), "dispersion": v.std(ddof=0), "miembros": len(v)}
        d.update({f"p_gt{u:g}": float((v > u).mean()) for u in umbrales})
        return pd.Series(d)

    return lluvia.groupby(["dia", "plazo", "caja"])["mm"].apply(agr).unstack()


def convectivas_por_dia(corridas: pd.DataFrame) -> pd.DataFrame:
    """Afternoon CAPE and precipitable water of the control member, mean of the two steps, by (day, lead)."""
    c = corridas[corridas["variable"].isin(["cape", "pwat"])]
    filas = []
    for plazo, (desfase, h0) in LEADS.items():
        horas = [h0 + h for h in HORAS_TARDE]
        sel = c[c["h_fin"].isin(horas)]
        g = sel.groupby(["run", "variable", "caja"])["valor"].agg(["mean", "count"]).reset_index()
        g = g[g["count"] == len(horas)]
        g["dia"] = g["run"] + pd.Timedelta(days=desfase)
        g["plazo"] = plazo
        filas.append(g)
    if not filas:
        return pd.DataFrame()
    t = pd.concat(filas)
    return t.pivot_table(index=["dia", "plazo", "caja"], columns="variable", values="mean")


def a_texto(df: pd.DataFrame) -> str:
    b = io.StringIO()
    df.to_csv(b, index=False)
    return b.getvalue()


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Baja y reduce el reforecast GEFSv12 (2000-2019) a series por caja")
    ap.add_argument("--destino", type=Path, default=Path("datos/gefs_reforecast"))
    ap.add_argument("--desde", type=int, default=2000)
    ap.add_argument("--hasta", type=int, default=2019)
    ap.add_argument("--hilos", type=int, default=5)
    ap.add_argument("--sin-convectivas", action="store_true", help="solo lluvia (sin CAPE ni agua precipitable)")
    args = ap.parse_args(argv)
    n = descargar(args.destino, args.desde, args.hasta, args.hilos, not args.sin_convectivas)
    print(f"{n} corridas procesadas en {args.destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
