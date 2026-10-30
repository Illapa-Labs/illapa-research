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

import numpy as np
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
        archivo.parent.mkdir(parents=True, exist_ok=True)
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


def lluvia_diaria_horaria(serie: pd.DataFrame, columna: str = "N_LLUVIA", minimo_horas: int = 20) -> pd.Series:
    """Daily rain (calendar day) from an hourly gauge; days with fewer than `minimo_horas` hours are NaN."""
    h = serie[columna].astype(float)
    cuenta = h.resample("D").count()
    suma = h.resample("D").sum(min_count=1)
    return suma.where(cuenta >= minimo_horas)


def acuerdo(a: pd.Series, b: pd.Series, dias_evento: list | None = None, rezago: int = 0) -> dict[str, float]:
    """How two daily rain series agree (gauge `a` against reanalysis `b`).

    `rezago` shifts `a` by that many days before comparing (the conventional gauges are read at
    07:00 and report the previous 24 h). Pearson on log(1+x), Spearman, the ratio of the 95th
    percentiles of the wet days, and, for the dates in `dias_evento`, the median of `a` and `b`.
    """
    from scipy.stats import pearsonr, spearmanr

    j = pd.concat([a.shift(rezago).rename("a"), b.rename("b")], axis=1).dropna()
    out = {"n": float(len(j)),
           "pearson_log": float(pearsonr(np.log1p(j["a"].clip(lower=0)), np.log1p(j["b"].clip(lower=0)))[0]),
           "spearman": float(spearmanr(j["a"], j["b"])[0])}
    humedos = j[(j["a"] > 0.5) | (j["b"] > 0.5)]
    out["p95_a"], out["p95_b"] = float(humedos["a"].quantile(0.95)), float(humedos["b"].quantile(0.95))
    if dias_evento:
        ev = j.reindex(pd.DatetimeIndex(dias_evento)).dropna()
        out["n_eventos"] = float(len(ev))
        out["mediana_eventos_a"], out["mediana_eventos_b"] = float(ev["a"].median()), float(ev["b"].median())
    return out


def caracteristicas_pluviometros(lluvia: pd.DataFrame, idx: pd.DatetimeIndex, prefijo: str = "pluv") -> pd.DataFrame:
    """Daily features of a network of gauges (one column per station, mm per day).

    Rain of the day (mean, maximum, number of wet stations) and antecedent rain (previous 7 and
    30 days, mean over stations). Missing stations are ignored day by day, so a feature exists
    whenever at least two stations reported.
    """
    r = lluvia.reindex(idx)
    ok = r.notna().sum(axis=1) >= 2
    f = pd.DataFrame(index=idx)
    media = r.mean(axis=1).where(ok)
    f[f"{prefijo}_media_1d"] = media
    f[f"{prefijo}_max_1d"] = r.max(axis=1).where(ok)
    f[f"{prefijo}_humedas"] = (r > 1.0).sum(axis=1).where(ok)
    f[f"{prefijo}_media_3d"] = media.rolling(3, min_periods=2).sum()
    f[f"{prefijo}_media_7d_previa"] = media.shift(1).rolling(7, min_periods=4).sum()
    f[f"{prefijo}_media_30d_previa"] = media.shift(1).rolling(30, min_periods=15).sum()
    return f


HISTORICAS_NOMBRES = {
    "151209": "chosica", "000543": "nana", "000548": "matucana", "155213": "santa_eulalia",
    "155122": "autisha", "155223": "carampoma", "151205": "canchacalla", "155224": "santiago_tuna",
    "155218": "huaros", "155217": "lachaqui", "151213": "sheque",
}
AUTOMATICAS_NOMBRES = {
    "47278214": "chosica_auto", "472CE45A": "matucana_auto", "111290": "nana_auto",
    "472EC742": "san_mateo_otao_auto", "472CA750": "santiago_tuna_auto", "472E24B0": "santa_eulalia_auto",
}
VALLE = ["chosica", "nana", "chosica_auto", "nana_auto"]


def red_historica(c: Cliente) -> pd.DataFrame:
    """Daily rain (mm) of the conventional gauges near the Rímac and Santa Eulalia valleys."""
    return pd.DataFrame({n: c.diaria_historica(k)["lluvia_mm"] for k, n in HISTORICAS_NOMBRES.items()})


def red_automatica(c: Cliente) -> pd.DataFrame:
    """Daily rain (mm, calendar day) of the automatic stations, summed from hourly readings."""
    out = {}
    for k, n in AUTOMATICAS_NOMBRES.items():
        s = c.serie(k)
        if len(s) and "N_LLUVIA" in s:
            out[n] = lluvia_diaria_horaria(s)
    return pd.DataFrame(out)


def diferencia_ap(y: np.ndarray, p1: np.ndarray, p2: np.ndarray, ts: np.ndarray, n: int = 400, semilla: int = 0) -> dict:
    """Paired bootstrap over whole seasons of AP(p1) - AP(p2): median and 90 % interval."""
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(semilla)
    seasons = np.unique(ts)
    por = {s: np.flatnonzero(ts == s) for s in seasons}
    d = []
    for _ in range(n):
        b = np.concatenate([por[s] for s in rng.choice(seasons, len(seasons))])
        if y[b].sum() < 3:
            continue
        d.append(average_precision_score(y[b], p1[b]) - average_precision_score(y[b], p2[b]))
    lo, med, hi = np.percentile(d, [5, 50, 95])
    return {"diferencia_mediana": float(med), "p5": float(lo), "p95": float(hi), "p_mayor_que_0": float(np.mean(np.array(d) > 0))}


def experimento_pluviometros(
    raiz: Path, red: pd.DataFrame, desde: int, hasta: int, n_jobs: int = 4, separar_valle: bool = True
) -> dict:
    """Does a rain-gauge network improve the daily huaico-day model of chapter 05?

    Window `desde`-`hasta` (the years the network covers). Feature sets are compared with season-out
    cross-validation: date only, ERA5 rain, gauges, ERA5 + gauges, and the same with antecedents.
    With `separar_valle` the mountain stations and the valley stations (Chosica, Ñaña) make two
    groups of features. Gauge rain is the rain *of the day* (it is a nowcast: the daily value is read the next morning).
    """
    from . import evaluacion_diaria as E
    from . import modelo_diario as md

    D = md.cargar_datos(Path(raiz))
    X, y, ts, mes = md.matrices(D)
    mask = D.inventario["mask"]
    idx = D.F.index
    sel = ((idx.year >= desde) & (idx.year <= hasta))[mask]
    if separar_valle:
        montana = red.drop(columns=[c for c in VALLE if c in red], errors="ignore")
        valle = red[[c for c in VALLE if c in red]]
        partes = [caracteristicas_pluviometros(montana, idx, "cuenca")]
        if valle.shape[1] >= 2:
            partes.append(caracteristicas_pluviometros(valle, idx, "valle"))
    else:  # a short network: use every station together
        partes = [caracteristicas_pluviometros(red, idx, "red")]
    G = pd.concat(partes, axis=1)[mask][sel]
    G_dia = G[[c for c in G.columns if "7d" not in c and "30d" not in c]]
    ys, tss, ms = y[sel].reset_index(drop=True), ts[sel], mes[sel]
    folds = [f for f in E.pliegues(tss, "temporada") if len(f)]
    era_dia, era_ant = X["lluvia_dia"][sel].reset_index(drop=True), X["antecedentes"][sel].reset_index(drop=True)
    G, G_dia = G.reset_index(drop=True), G_dia.reset_index(drop=True)
    conjuntos = {
        "ERA5 lluvia del día": era_dia,
        "pluviómetros del día": G_dia,
        "pluviómetros del día + previa": G,
        "ERA5 + pluviómetros del día": pd.concat([era_dia, G_dia], axis=1),
        "ERA5 día + antecedentes": pd.concat([era_dia, era_ant], axis=1),
        "ERA5 día + antecedentes + pluviómetros": pd.concat([era_dia, era_ant, G], axis=1),
    }
    pref = E.p_climatologia(ys, ms, folds)
    p = {"solo fecha": pref}
    for k, Xk in conjuntos.items():
        p[k] = md.validar_anidado(Xk, ys, tss, folds, n_jobs=n_jobs).p
    tabla = pd.DataFrame({k: md.metricas_completas(ys.to_numpy(), v, pref) for k, v in p.items()}).T
    return {"tabla": tabla, "p": p, "y": ys.to_numpy(), "ts": tss, "ref": pref, "n_dias": len(ys),
            "n_eventos": int(ys.sum()), "n_temporadas": len(np.unique(tss)), "G": G}
