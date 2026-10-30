"""Respectful client for the public data endpoints of the SENAMHI research portal.

What it does: reads the public station catalogue and the series that the portal's own
"Datos hidrometeorológicos" page shows to any visitor, one station and one month at a time,
with a pause between calls and a local cache in ``datos/senamhi/``.

What it never does: log in, use a key, create an account, or touch the documented REST API that
asks for a registered key. If an endpoint answers 401 or 403 the client stops and says so.

Terms (https://www.senamhi.gob.pe/?p=terminos-condiciones, read on 30 October 2026): the
information is "de uso público", but publication, reproduction, distribution and transformation
belong to SENAMHI, and using the site is not a licence for other purposes. Therefore the data
stay in ``datos/senamhi/`` (ignored by git, not in the Hugging Face mirror) and only aggregated
results and station metadata leave this machine, always credited as "Información recopilada y
trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú (SENAMHI)". The data come
without quality control; the portal says their use is the user's entire responsibility.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://servicios.senamhi.gob.pe/api"
USER_AGENT = "illapa-research/0.1 (+https://github.com/Illapa-Labs/illapa-research; research, low rate)"
PAUSA_S = 2.0
CITA = (
    "Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú "
    "(SENAMHI). Observatorio Nacional del Tiempo, Agua y Clima del Perú, https://observatorio.senamhi.gob.pe"
)


class AccesoRestringido(RuntimeError):
    """The endpoint asks for credentials: the client stops there."""


class Cliente:
    def __init__(self, carpeta: Path = Path("datos/senamhi"), pausa: float = PAUSA_S):
        self.carpeta = Path(carpeta)
        self.cache = self.carpeta / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.pausa = pausa
        self._ultimo = 0.0

    def _ruta(self, ruta: str, params: dict | None) -> Path:
        clave = ruta.strip("/").replace("/", "__")
        if params:
            clave += "__" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        return self.cache / f"{clave}.json"

    def get(self, ruta: str, params: dict | None = None, refrescar: bool = False) -> dict:
        """GET `API/ruta` as JSON, from the cache when it is there."""
        archivo = self._ruta(ruta, params)
        if archivo.exists() and not refrescar:
            return json.loads(archivo.read_text(encoding="utf-8"))
        espera = self.pausa - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        for intento in range(4):
            resp = requests.get(f"{API}/{ruta.strip('/')}", params=params, headers={"User-Agent": USER_AGENT}, timeout=120)
            self._ultimo = time.monotonic()
            if resp.status_code in (401, 403):
                raise AccesoRestringido(f"{ruta}: {resp.status_code}; este endpoint pide credenciales y no se usa")
            if resp.status_code < 500 and resp.status_code != 429:
                break
            time.sleep(10 * (intento + 1))
        resp.raise_for_status()
        datos = resp.json()
        archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return datos

    # --- catalogue (metadata: it can be published)
    def estaciones(self) -> pd.DataFrame:
        d = self.get("station/stations")["data"]
        df = pd.DataFrame(d)
        for c in ("longitude", "latitude"):
            df[c] = pd.to_numeric(df[c])
        return df

    def historicas(self) -> pd.DataFrame:
        """Stations with a long daily series in the researcher download (legacy codes)."""
        return pd.DataFrame(self.get("researchers/historical-download/stations")["data"])

    # --- series (data: local only)
    def periodos(self, estacion: str) -> list[str]:
        """Months (YYYYMM) with data for a station, newest first."""
        try:
            return [p["id"] for p in self.get(f"station/stations/{estacion}/periods")["data"]]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:  # station without published series
                return []
            raise

    def lecturas(self, estacion: str, periodo: str) -> pd.DataFrame:
        """One month of readings of a station (daily or sub-daily, whatever the station reports)."""
        d = self.get(f"station/stations/{estacion}/readings", {"period": periodo})["data"]
        filas = []
        for r in d["readings"]:
            fila = {"fecha": r["date"], "hora": r.get("time") or ""}
            fila.update({v["column"]: v["value"] for v in r["values"]})
            filas.append(fila)
        return pd.DataFrame(filas)

    def serie(self, estacion: str, periodos: list[str] | None = None) -> pd.DataFrame:
        """All the months (or the given ones) of a station, joined."""
        partes = [self.lecturas(estacion, p) for p in (periodos or sorted(self.periodos(estacion)))]
        partes = [p for p in partes if len(p)]
        if not partes:
            return pd.DataFrame()
        df = pd.concat(partes, ignore_index=True)
        hora = df["hora"].replace("", "00:00")
        if df["fecha"].str.contains("/").any():  # automatic stations: dd/mm/yyyy
            df["momento"] = pd.to_datetime(df["fecha"] + " " + hora, format="%d/%m/%Y %H:%M")
        else:
            df["momento"] = pd.to_datetime(df["fecha"] + " " + hora)
        return df.set_index("momento").drop(columns=["fecha", "hora"])

    def diaria_historica(self, codigo_historico: str) -> pd.DataFrame:
        """Daily precipitation and extreme temperatures from the researcher download (since 1989 or so)."""
        d = self.get(f"researchers/historical-download/stations/{codigo_historico}/series")["data"]
        df = pd.DataFrame(d)
        if df.empty:
            return df
        df["fecha"] = pd.to_datetime(df["fecha"] if "fecha" in df else df["date"])
        return df.drop(columns=["date"], errors="ignore").set_index("fecha").rename(
            columns={"precipitation": "lluvia_mm", "maximumTemperature": "tmax", "minimumTemperature": "tmin"}
        )


def distancia_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in km."""
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def cercanas(est: pd.DataFrame, lon: float, lat: float, radio_km: float, tipo: str | None = None) -> pd.DataFrame:
    """Stations within `radio_km` of a point, nearest first (`tipo`: "M" meteorological, "H" hydrological)."""
    d = est.copy()
    d["km"] = [distancia_km(lon, lat, x, y) for x, y in zip(d["longitude"], d["latitude"], strict=True)]
    d = d[d["km"] <= radio_km]
    if tipo:
        d = d[d["typeId"] == tipo]
    return d.sort_values("km")


def completitud(serie: pd.Series, inicio: str, fin: str) -> float:
    """Share of days in [inicio, fin] with a value."""
    dias = pd.date_range(inicio, fin, freq="D")
    s = serie.dropna()
    s = s[~s.index.duplicated()]
    return float(len(s.reindex(dias).dropna()) / len(dias)) if len(dias) else float("nan")
