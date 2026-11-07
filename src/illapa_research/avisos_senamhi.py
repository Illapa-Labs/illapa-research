"""SENAMHI official warnings (interoperability API) against the catalogued huaico days.

Two products:

* weather warnings (``/weather-warnings``): issued per province, a level from 1 to 4 and an active
  window; history by year;
* short-term rain warnings (``/short-term-warnings``): issued per district, only 2025 and 2026.

``descargar`` stores the raw answers through the cached client; ``tabla_avisos`` makes one row per
warning and day it was active. ``cobertura`` asks how many catalogued huaico days had an active
warning for the province and how many warning-days had a huaico, in the rainy seasons.

The warnings are SENAMHI information: the outputs repeat the legend (`senamhi.LEYENDA`) and say that
the series are not official products of this repository.
"""

from __future__ import annotations

import pandas as pd

from .senamhi_api import ApiDetenida, ClienteApi

PROVINCIAS = {"1501": "LIMA", "1507": "HUAROCHIRI"}
DISTRITOS = {"150118": "LURIGANCHO", "150107": "CHACLACAYO", "150714": "RICARDO PALMA", "150728": "SANTA EULALIA",
             "150701": "MATUCANA"}


def descargar(c: ClienteApi, anios: range, provincias=PROVINCIAS, distritos=DISTRITOS) -> dict[str, list[dict]]:
    """Raw weather warnings by (province, year) and short-term warnings by district; stops on a refusal."""
    generales: list[dict] = []
    for ub, nombre in provincias.items():
        for a in anios:
            try:
                d = c.get("/weather-warnings", {"ubigeo": ub, "year": a})
            except ApiDetenida:
                raise
            except Exception as e:  # noqa: BLE001 - a 400 for a year without data must not stop the rest
                print(f"  {nombre} {a}: {str(e)[:80]}", flush=True)
                continue
            for x in d:
                generales.append({**x, "provincia_ubigeo": ub, "provincia": nombre})
            print(f"  avisos {nombre} {a}: {len(d)}", flush=True)
    corto: list[dict] = []
    for ub, nombre in distritos.items():
        d = c.get("/short-term-warnings", {"ubigeo": ub})
        for x in d:
            corto.append({**x, "distrito_ubigeo": ub, "distrito": nombre})
        print(f"  corto plazo {nombre}: {len(d)}", flush=True)
    return {"generales": generales, "corto_plazo": corto}


def tabla_avisos(avisos: list[dict]) -> pd.DataFrame:
    """One row per warning with its active window; duplicates (same id and province) are dropped."""
    filas = []
    for x in avisos:
        ini = x.get("activeStartDate") or x.get("startDate")
        fin = x.get("activeEndDate") or x.get("endDate")
        filas.append({
            "id": x.get("id"), "numero": x.get("number"), "provincia": x.get("provincia"),
            "titulo": x.get("title"), "nivel": x.get("level"), "publicado": x.get("publishedDate"),
            "inicio": ini, "fin": fin,
        })
    t = pd.DataFrame(filas).drop_duplicates(["id", "provincia"])
    for k in ("inicio", "fin", "publicado"):
        t[k] = pd.to_datetime(t[k], errors="coerce")
    return t.sort_values("inicio").reset_index(drop=True)


def dias_con_aviso(t: pd.DataFrame, provincia: str, nivel_min: int = 1) -> set:
    """Calendar days covered by at least one warning of the province with level >= nivel_min."""
    dias: set = set()
    s = t[(t["provincia"] == provincia) & (pd.to_numeric(t["nivel"], errors="coerce") >= nivel_min)]
    for ini, fin in zip(s["inicio"], s["fin"], strict=True):
        if pd.isna(ini) or pd.isna(fin):
            continue
        dias |= {d.date() for d in pd.date_range(ini.normalize(), fin.normalize(), freq="D")}
    return dias


def cobertura(t: pd.DataFrame, fechas_huaico: list, provincia: str, nivel_min: int = 1) -> dict[str, float]:
    """Share of huaico days with an active warning, and share of rainy-season days with warning that had a huaico.

    Rainy season: 1 December to 30 April. Only days from the first warning onwards are compared.
    """
    con = dias_con_aviso(t, provincia, nivel_min)
    if not con:
        return {"huaicos": 0, "con_aviso": 0, "pod": float("nan"), "dias_aviso": 0, "far": float("nan")}
    desde = min(con)
    huaicos = {f for f in fechas_huaico if f >= desde and (f.month >= 12 or f.month <= 4)}
    temporada = {d for d in con if d.month >= 12 or d.month <= 4}
    hit = huaicos & con
    return {
        "huaicos": len(huaicos), "con_aviso": len(hit), "pod": len(hit) / len(huaicos) if huaicos else float("nan"),
        "dias_aviso": len(temporada), "dias_aviso_con_huaico": len(temporada & huaicos),
        "far": 1 - len(temporada & huaicos) / len(temporada) if temporada else float("nan"),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    from .catalogo import CATALOGO, cargar_todos

    ap = argparse.ArgumentParser(description="Avisos del SENAMHI contra los días con huaico")
    ap.add_argument("--desde", type=int, default=2014)
    ap.add_argument("--hasta", type=int, default=2026)
    a = ap.parse_args(argv)
    c = ClienteApi()
    try:
        crudo = descargar(c, range(a.desde, a.hasta + 1))
    except ApiDetenida as e:
        print("DETENIDA:", e)
        return 1
    print("llamadas hoy:", c.llamadas_hoy())
    t = tabla_avisos(crudo["generales"])
    carpeta = Path("datos/senamhi_api")
    t.to_csv(carpeta / "avisos_meteorologicos.csv", index=False)
    pd.DataFrame(crudo["corto_plazo"]).drop(columns=["districts"], errors="ignore").to_csv(
        carpeta / "avisos_corto_plazo.csv", index=False)
    fechas = sorted({e.fecha for e in cargar_todos(solo_dia_exacto=True, sin_baja_confianza=True, solo_zona=True)})
    filas = []
    for prov in PROVINCIAS.values():
        for nivel in (1, 2, 3):
            filas.append({"provincia": prov, "nivel_minimo": nivel, **cobertura(t, fechas, prov, nivel)})
    out = pd.DataFrame(filas)
    out.round(4).to_csv(CATALOGO / "senamhi_avisos_cobertura.csv", index=False)
    print(out.round(3).to_string(index=False))
    print("avisos por año y provincia:\n", t.groupby([t["inicio"].dt.year, "provincia"]).size().unstack(fill_value=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
