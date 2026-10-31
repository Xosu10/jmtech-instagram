"""Publicación opcional de reels en Facebook: sin configurar no hace nada y un fallo no afecta a Instagram."""
from pathlib import Path

from jmtech import facebook as fb


class Resp:
    def __init__(self, cuerpo, estado=200, texto=""):
        self._c, self.status_code, self.text = cuerpo, estado, texto

    def json(self):
        return self._c


class Sesion:
    def __init__(self):
        self.llamadas = []

    def request(self, metodo, url, headers=None, params=None, data=None, timeout=0):
        self.llamadas.append((metodo, url, params or data))
        if url.endswith("/video_reels") and (data or {}).get("upload_phase") == "start":
            return Resp({"video_id": "V1", "upload_url": "https://rupload.example/V1"})
        if url.endswith("/video_reels"):
            return Resp({"success": True})
        if url.endswith("/PAG"):
            return Resp({"access_token": "TOKENPAGINA", "name": "JM TECH"})
        if url.endswith("/V1"):
            return Resp({"status": {"video_status": "ready"}})
        return Resp({})

    def post(self, url, headers=None, data=None, timeout=0):
        self.llamadas.append(("SUBIDA", url, headers["file_size"]))
        return Resp({"success": True})


def test_sin_pagina_configurada_no_se_hace_nada():
    assert fb.compartir_en_facebook({"facebook_page_id": ""}, "x.mp4", "texto") is None


def test_publica_un_reel_en_la_pagina(tmp_path):
    v = tmp_path / "v.mp4"
    v.write_bytes(b"12345")
    c = fb.ClienteFacebook("EAAtokenfalso123456", "PAG", sesion=Sesion(), dormir=lambda s: None)
    r = fb.compartir_en_facebook({"facebook_page_id": "PAG"}, v, "Escríbenos por MD", cliente=c, imprimir=lambda *_: None)
    assert r == {"facebook_id": "V1", "facebook_enlace": "https://www.facebook.com/reel/V1"}
    pasos = [x[0] for x in c.sesion.llamadas]
    assert pasos.count("SUBIDA") == 1 and pasos.count("POST") == 2
    finalizar = [x for x in c.sesion.llamadas if x[0] == "POST" and x[2].get("upload_phase") == "finish"][0]
    assert "mensaje directo" in finalizar[2]["description"] and "MD" not in finalizar[2]["description"]


def test_un_fallo_de_facebook_no_rompe_nada(tmp_path):
    class Rota(Sesion):
        def request(self, *a, **k):
            return Resp({"error": {"code": 190, "message": "token EAAxxxxxxxxxxxxxxxx caducado"}}, 400)
    v = tmp_path / "v.mp4"
    v.write_bytes(b"1")
    c = fb.ClienteFacebook("EAAtokenfalso123456", "PAG", sesion=Rota(), dormir=lambda s: None)
    mensajes = []
    assert fb.compartir_en_facebook({"facebook_page_id": "PAG"}, v, "t", cliente=c, imprimir=mensajes.append) is None
    assert mensajes and "EAAxxxx" not in mensajes[0] and "warning" in mensajes[0]
