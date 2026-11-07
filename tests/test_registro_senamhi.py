from datetime import datetime
from zoneinfo import ZoneInfo

from illapa_research import registro_senamhi as R
from illapa_research import senamhi_api as A


class _Resp:
    status_code = 200
    text = ""

    def json(self):
        return {"status": True, "message": None, "data": [{"id": 1}]}

    def raise_for_status(self):
        pass


def _cliente(tmp_path):
    c = A.ClienteApi(tmp_path / "api", pausa=0, clave="CLAVE")
    c.n = 0

    def get(url, params=None, headers=None, timeout=None):
        c.n += 1
        return _Resp()

    c.s.get = get
    return c


def test_foto_guarda_un_archivo_por_llamada_y_no_se_repite_el_mismo_dia(tmp_path):
    c = _cliente(tmp_path)
    ahora = datetime(2026, 11, 8, 6, 0, tzinfo=ZoneInfo("America/Lima"))
    carpeta = tmp_path / "reg"
    escritos = R.tomar_foto(c, carpeta, ahora)
    assert len(escritos) == len(R.llamadas()) and c.n == len(R.llamadas())
    assert R.tomar_foto(c, carpeta, ahora) == [] and c.n == len(R.llamadas())
    assert len(R.tomar_foto(c, carpeta, ahora, forzar=True)) == len(R.llamadas())
    assert "CLAVE" not in "".join(p.read_text() for p in carpeta.glob("*.json"))


def test_get_fresco_no_usa_ni_escribe_la_cache(tmp_path):
    c = _cliente(tmp_path)
    c.get("/x", fresco=True)
    c.get("/x", fresco=True)
    assert c.n == 2 and not list((tmp_path / "api" / "cache").glob("*.json"))
