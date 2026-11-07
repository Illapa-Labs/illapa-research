"""Client for the SENAMHI interoperability REST API (registered account, API key).

Base ``https://interoperabilidad.senamhi.gob.pe/api``; read only (GET); the key travels in the
``apikey`` header and the call must leave from an IP registered in the account. Limits stated by the
account: 1 000 queries per day and 60 per minute (the documentation adds one per second with bursts
of up to 60). Guide: https://observatorio.senamhi.gob.pe/investigadores/interoperabilidad/apis

What the client does to stay far from the limits and from the key:

* the key is read from the environment variable ``SENAMHI_APIKEY`` or from ``~/.senamhi_env``
  (a line ``export SENAMHI_APIKEY=...``), is never printed, logged or written to the cache;
* every answer is cached on disk, so a call is never repeated;
* a pause between network calls (``PAUSA_S``) and a daily budget (``TOPE_DIA``, below the 1 000 of
  the account) kept in ``datos/senamhi_api/contador.json``; past the budget it stops;
* on 401, 403 or 429 it stops at once with the reason and does not retry.

The data keeps the SENAMHI terms of use (`senamhi.LEYENDA`): not sold, not presented as official.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date
from pathlib import Path

import requests

from .senamhi import CITA, LEYENDA  # noqa: F401  (re-exported: outputs must repeat the legend)

BASE = "https://interoperabilidad.senamhi.gob.pe/api"
USER_AGENT = "illapa-research/0.1 (+https://github.com/Illapa-Labs/illapa-research; research, low rate)"
PAUSA_S = 1.5
TOPE_DIA = 800
VARIABLE = "SENAMHI_APIKEY"


class ApiDetenida(RuntimeError):
    """The API refused the call (401, 403, 429) or the daily budget is spent: stop and read the reason."""


def leer_clave(env_file: Path | None = None) -> str:
    """The key from the environment or from ``~/.senamhi_env``; raises if there is none. Never prints it."""
    clave = os.environ.get(VARIABLE, "").strip()
    if not clave:
        ruta = env_file or Path.home() / ".senamhi_env"
        if ruta.exists():
            m = re.search(rf"{VARIABLE}=(?P<v>.+)", ruta.read_text(encoding="utf-8"))
            if m:
                clave = m["v"].strip().strip("'\"").replace("\\", "")
    if not clave:
        raise ApiDetenida(f"No hay clave: define {VARIABLE} o crea ~/.senamhi_env (ver docs/notas/senamhi_api.md)")
    return clave


class ClienteApi:
    def __init__(self, carpeta: Path = Path("datos/senamhi_api"), pausa: float = PAUSA_S, tope_dia: int = TOPE_DIA,
                 clave: str | None = None):
        self.carpeta = Path(carpeta)
        (self.carpeta / "cache").mkdir(parents=True, exist_ok=True)
        self.pausa, self.tope_dia = pausa, tope_dia
        self._clave = clave
        self._ultimo = 0.0
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT

    # ---- budget -------------------------------------------------------------------------
    @property
    def _contador(self) -> Path:
        return self.carpeta / "contador.json"

    def llamadas_hoy(self) -> int:
        if not self._contador.exists():
            return 0
        return int(json.loads(self._contador.read_text()).get(date.today().isoformat(), 0))

    def _contar(self) -> None:
        datos = json.loads(self._contador.read_text()) if self._contador.exists() else {}
        datos[date.today().isoformat()] = int(datos.get(date.today().isoformat(), 0)) + 1
        self._contador.write_text(json.dumps(datos))

    # ---- calls --------------------------------------------------------------------------
    def _ruta_cache(self, ruta: str, params: dict | None) -> Path:
        clave = json.dumps([ruta, sorted((params or {}).items())], ensure_ascii=False)
        return self.carpeta / "cache" / (hashlib.sha1(clave.encode()).hexdigest()[:16] + ".json")

    def get(self, ruta: str, params: dict | None = None):
        """GET ``BASE + ruta``; returns the ``data`` field of the envelope. Cached; budgeted; stops on refusals."""
        cache = self._ruta_cache(ruta, params)
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))["data"]
        if self.llamadas_hoy() >= self.tope_dia:
            raise ApiDetenida(f"Tope diario propio alcanzado ({self.tope_dia} llamadas); la cuenta permite 1 000")
        clave = self._clave or leer_clave()  # before counting: a missing key must not use the budget
        falta = self.pausa - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()
        self._contar()
        r = self.s.get(BASE + ruta, params=params, headers={"apikey": clave}, timeout=60)
        if r.status_code in (401, 403, 429):
            motivo = r.text[:200].replace(clave, "***")
            raise ApiDetenida(f"{r.status_code}: {motivo}")
        r.raise_for_status()
        cuerpo = r.json()
        if cuerpo.get("status") is False:
            raise ApiDetenida(f"La API respondió con error: {cuerpo.get('message')} {cuerpo.get('validations')}")
        cache.write_text(json.dumps(cuerpo, ensure_ascii=False), encoding="utf-8")
        return cuerpo["data"]

    # ---- endpoints seen in the guide (parameters not yet confirmed) -------------------------
    def departamentos(self):
        return self.get("/locations/departments")
