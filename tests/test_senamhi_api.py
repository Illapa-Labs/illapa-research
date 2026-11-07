import json

import pytest

from illapa_research import senamhi_api as A


class _Resp:
    def __init__(self, codigo=200, cuerpo=None, texto=""):
        self.status_code, self._c, self.text = codigo, cuerpo, texto

    def json(self):
        return self._c

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def _cliente(tmp_path, respuestas, **kw):
    c = A.ClienteApi(tmp_path, pausa=0, clave="CLAVE-DE-PRUEBA", **kw)
    c.llamadas = []

    def get(url, params=None, headers=None, timeout=None):
        c.llamadas.append((url, headers))
        return respuestas.pop(0)

    c.s.get = get
    return c


def test_cachea_y_no_repite_la_llamada(tmp_path):
    ok = {"status": True, "message": None, "data": [{"ubigeo": "15", "name": "LIMA"}]}
    c = _cliente(tmp_path, [_Resp(200, ok)])
    assert c.departamentos()[0]["name"] == "LIMA"
    assert c.departamentos()[0]["name"] == "LIMA"
    assert len(c.llamadas) == 1 and c.llamadas_hoy() == 1
    assert c.llamadas[0][1]["apikey"] == "CLAVE-DE-PRUEBA"
    assert "CLAVE-DE-PRUEBA" not in "".join(p.read_text() for p in (tmp_path / "cache").glob("*.json"))


@pytest.mark.parametrize("codigo", [401, 403, 429])
def test_se_detiene_ante_un_rechazo_y_no_filtra_la_clave(tmp_path, codigo):
    c = _cliente(tmp_path, [_Resp(codigo, texto='{"message": "CLAVE-DE-PRUEBA no autorizada"}')])
    with pytest.raises(A.ApiDetenida) as e:
        c.departamentos()
    assert str(codigo) in str(e.value) and "CLAVE-DE-PRUEBA" not in str(e.value)


def test_tope_diario_propio(tmp_path):
    c = _cliente(tmp_path, [_Resp(200, {"status": True, "data": []}), _Resp(200, {"status": True, "data": []})], tope_dia=1)
    c.get("/a")
    with pytest.raises(A.ApiDetenida, match="Tope diario"):
        c.get("/b")


def test_la_clave_se_lee_del_archivo_sin_imprimirla(tmp_path, monkeypatch):
    monkeypatch.delenv(A.VARIABLE, raising=False)
    f = tmp_path / "env"
    f.write_text("export SENAMHI_APIKEY=abc123\n")
    assert A.leer_clave(f) == "abc123"
    f.write_text("")
    with pytest.raises(A.ApiDetenida):
        A.leer_clave(f)
    assert json.dumps({"k": 1})
