"""Publicador y cliente de Instagram, siempre con una API simulada (nunca se llama a Instagram de verdad)."""
import json
from datetime import datetime, timezone

import pytest
import requests

from jmtech import estado as est
from jmtech import publicador
from jmtech.calendario import cargar_config as _cargar_config


def cargar_config():
    c = _cargar_config()
    c["posts"] = True                      # el post de las 19:00 está en pausa en la configuración real
    return c
from jmtech.instagram import ClienteInstagram, ErrorInstagram, ocultar, traducir_error

TOKEN = "EAA" + "x" * 40          # falso, construido aquí para no dejar nada con forma de token en el código


def utc(h, mi=0, dia=2):
    return datetime(2026, 11, dia, h, mi, tzinfo=timezone.utc)


# ---------- Simulaciones ----------
class Respuesta:
    def __init__(self, cuerpo, codigo=200, tipo="application/json", bytes_=b""):
        self._c, self.status_code, self.headers, self.content = cuerpo, codigo, {"Content-Type": tipo}, bytes_

    def json(self):
        if self._c is None:
            raise ValueError
        return self._c


class SesionApi:
    """Responde a las llamadas de la API según una lista de respuestas y anota lo enviado."""

    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    def request(self, metodo, url, headers=None, timeout=None, params=None, data=None):
        self.llamadas.append(dict(metodo=metodo, url=url, headers=headers, params=params, data=data))
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class ClienteFalso:
    def __init__(self, medios=None, fallo_publicar=None):
        self.llamadas, self.medios, self.fallo_publicar = [], medios or [], fallo_publicar

    def ultimos_medios(self, n=10):
        return self.medios

    def crear_contenedor(self, url, caption, alt):
        self.llamadas.append(("crear", url, alt))
        return "contenedor1"

    def esperar_listo(self, c):
        self.llamadas.append(("listo", c))

    def publicar(self, c):
        self.llamadas.append(("publicar", c))
        if self.fallo_publicar:
            raise self.fallo_publicar
        return "media1"

    def permalink(self, m):
        return "https://www.instagram.com/p/ABC/"


class SesionWeb:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)

    def get(self, url, timeout=None):
        return self.respuestas.pop(0)


JPEG_OK = Respuesta(None, 200, "image/jpeg", b"x" * 6000)


@pytest.fixture
def pend(tmp_path):
    return publicador.preparar(utc(18), carpeta=tmp_path, ruta_pendiente=tmp_path / "p.json",
                               estado={"publicaciones": []}, cfg=cargar_config())


def lanzar(pend, tmp_path, cliente, **kw):
    return publicador.publicar(pend, cliente=cliente, ruta_estado=tmp_path / "estado.json", ahora_utc=utc(18, 3),
                               informe=False, sesion=SesionWeb([JPEG_OK]), dormir=lambda s: None, **kw)


# ---------- Preparar ----------
def test_preparar_genera_jpeg_pie_y_texto_alternativo(pend, tmp_path):
    assert pend["archivo"] == "2026-11-02.jpg" and (tmp_path / pend["archivo"]).exists()
    assert pend["pie"].count("#") >= 5 and "sin compromiso" in pend["pie"] and pend["alt"]
    assert json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))["tema"] == pend["tema"]


def test_preparar_fuera_de_hora_no_hace_nada(tmp_path):
    assert publicador.preparar(utc(12), carpeta=tmp_path, ruta_pendiente=tmp_path / "p.json",
                               estado={"publicaciones": []}, cfg=cargar_config()) is None
    assert not (tmp_path / "p.json").exists() and not list(tmp_path.glob("*.jpg"))


def test_una_campana_sin_disenar_falla_con_mensaje_claro(tmp_path):
    cfg = cargar_config()
    cfg["_campanas"] = {datetime(2026, 11, 2).date(): {"id": "black_friday"}}
    with pytest.raises(publicador.ErrorPublicacion, match="campaña"):
        publicador.preparar(utc(18), carpeta=tmp_path, ruta_pendiente=tmp_path / "p.json",
                            estado={"publicaciones": []}, cfg=cfg)


# ---------- Publicar ----------
def test_prueba_en_seco_no_llama_a_nada(pend, tmp_path):
    cliente = ClienteFalso()
    assert publicador.publicar(pend, dry_run=True, cliente=cliente, ruta_estado=tmp_path / "e.json") is None
    assert cliente.llamadas == [] and not (tmp_path / "e.json").exists()


def test_publica_registra_y_no_duplica(pend, tmp_path):
    cliente = ClienteFalso()
    reg = lanzar(pend, tmp_path, cliente)
    assert reg["resultado"] == "publicado" and reg["permalink"].startswith("https://www.instagram.com/")
    assert [c[0] for c in cliente.llamadas] == ["crear", "listo", "publicar"]
    assert "raw.githubusercontent.com" in cliente.llamadas[0][1] and cliente.llamadas[0][1].endswith("2026-11-02.jpg")
    assert est.publicado_el(est.cargar(tmp_path / "estado.json"), datetime(2026, 11, 2).date())
    # segunda ejecución del mismo día: no vuelve a llamar a Instagram
    otro = ClienteFalso()
    assert lanzar(pend, tmp_path, otro) is None and otro.llamadas == []


def test_si_instagram_ya_tiene_la_publicacion_no_la_repite(pend, tmp_path):
    ya = [{"id": "m9", "caption": pend["pie"], "timestamp": "2026-11-02T18:00:10+0000", "permalink": "https://i/p/1"}]
    cliente = ClienteFalso(medios=ya)
    reg = lanzar(pend, tmp_path, cliente)
    assert reg["media_id"] == "m9" and cliente.llamadas == []


def test_si_falla_la_respuesta_de_publicar_pero_se_publico_lo_recupera(pend, tmp_path):
    cliente = ClienteFalso(fallo_publicar=ErrorInstagram("red", temporal=True))
    cliente.medios = []
    original = cliente.ultimos_medios
    cliente.ultimos_medios = lambda n=10: [] if not any(c[0] == "publicar" for c in cliente.llamadas) else [
        {"id": "m7", "caption": pend["pie"], "timestamp": "2026-11-02T18:00:20+0000", "permalink": "https://i/p/7"}]
    assert lanzar(pend, tmp_path, cliente)["media_id"] == "m7"


def test_si_falla_de_verdad_el_error_sube_y_no_se_anota(pend, tmp_path):
    cliente = ClienteFalso(fallo_publicar=ErrorInstagram("rechazado"))
    with pytest.raises(ErrorInstagram):
        lanzar(pend, tmp_path, cliente)
    assert est.cargar(tmp_path / "estado.json")["publicaciones"] == []


def test_publicacion_de_prueba_no_bloquea_la_del_dia(tmp_path):
    p = publicador.preparar(utc(18), prueba=True, tema="streaming", estilo="B", carpeta=tmp_path,
                            ruta_pendiente=tmp_path / "p.json", estado={"publicaciones": []}, cfg=cargar_config())
    assert p["archivo"].startswith("prueba_") and p["prueba"] and p["tema"] == "streaming"
    lanzar(p, tmp_path, ClienteFalso())
    assert est.publicado_el(est.cargar(tmp_path / "estado.json"), datetime(2026, 11, 2).date()) is None


def test_esperar_url_reintenta_hasta_que_responde_jpeg():
    web = SesionWeb([Respuesta(None, 404), Respuesta(None, 200, "text/html", b"x" * 9000), JPEG_OK])
    publicador.esperar_url("https://x/a.jpg", sesion=web, dormir=lambda s: None)


def test_esperar_url_falla_con_mensaje_claro():
    web = SesionWeb([Respuesta(None, 404)] * 3)
    with pytest.raises(publicador.ErrorPublicacion, match="no está disponible"):
        publicador.esperar_url("https://x/a.jpg", sesion=web, intentos=3, dormir=lambda s: None)


def test_el_informe_lista_ultimas_y_proximas(tmp_path):
    estado = {"publicaciones": [dict(fecha="2026-11-02", tema="streaming", estilo="A", resultado="publicado",
                                     prueba=False, permalink="https://i/p/1", publicado_utc="2026-11-02T18:00:00Z",
                                     retraso_min=1)]}
    texto = est.generar_informe(estado, utc(19, 0, 3), tmp_path / "ESTADO.md")
    assert "https://i/p/1" in texto and "Próximas 10" in texto and "no caduca" in texto
    assert texto.count("| ") > 20


# ---------- Cliente de la API ----------
def cliente(*respuestas):
    s = SesionApi(respuestas)
    return ClienteInstagram(TOKEN, "123", sesion=s, dormir=lambda s_: None), s


def test_el_token_va_en_la_cabecera_nunca_en_la_direccion_ni_los_datos():
    c, s = cliente(Respuesta({"id": "c1"}))
    c.crear_contenedor("https://x/a.jpg", "pie", "alt")
    llamada = s.llamadas[0]
    assert llamada["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in llamada["url"] and TOKEN not in json.dumps(llamada["data"])
    assert llamada["data"]["alt_text"] == "alt" and llamada["url"].endswith("/123/media")


def test_flujo_completo_contenedor_estado_publicacion():
    c, s = cliente(Respuesta({"id": "c1"}), Respuesta({"status_code": "IN_PROGRESS"}),
                   Respuesta({"status_code": "FINISHED"}), Respuesta({"id": "m1"}))
    cid = c.crear_contenedor("https://x/a.jpg", "pie")
    assert c.esperar_listo(cid, cada_s=0) == "FINISHED"
    assert c.publicar(cid) == "m1"
    assert s.llamadas[-1]["data"] == {"creation_id": "c1"}


def test_estado_error_del_contenedor_da_mensaje_claro():
    c, _ = cliente(Respuesta({"status_code": "ERROR", "status": "Error: fallo"}))
    with pytest.raises(ErrorInstagram, match="no pudo procesar"):
        c.esperar_listo("c1")


def test_error_de_token_se_explica_en_espanol_sin_filtrar_el_token():
    c, _ = cliente(Respuesta({"error": {"code": 190, "message": f"Invalid OAuth access token {TOKEN}"}}, 400))
    with pytest.raises(ErrorInstagram) as e:
        c.cuenta()
    assert "IG_ACCESS_TOKEN" in str(e.value) and TOKEN not in str(e.value) and TOKEN not in e.value.tecnico


def test_errores_temporales_se_reintentan_y_luego_funciona():
    c, s = cliente(Respuesta({"error": {"code": 4, "message": "limit"}}, 400),
                   Respuesta({"error": {"code": 2, "message": "temp"}}, 500), Respuesta({"id": "1", "username": "jm"}))
    assert c.cuenta()["username"] == "jm" and len(s.llamadas) == 3


def test_fallo_de_red_no_filtra_el_token():
    c, _ = cliente(*[requests.ConnectionError(f"fallo con {TOKEN}")] * 3)
    with pytest.raises(ErrorInstagram) as e:
        c.cuenta()
    assert e.value.temporal and TOKEN not in e.value.tecnico


def test_si_instagram_rechaza_el_texto_alternativo_se_publica_sin_el():
    c, s = cliente(Respuesta({"error": {"code": 100, "message": "Invalid parameter alt_text too long"}}, 400),
                   Respuesta({"id": "c2"}))
    assert c.crear_contenedor("https://x/a.jpg", "pie", "alt") == "c2"
    assert "alt_text" not in s.llamadas[1]["data"]


def test_limite_de_publicacion():
    c, _ = cliente(Respuesta({"data": [{"quota_usage": 3, "config": {"quota_total": 100}}]}))
    assert c.limite() == (3, 100)


def test_sin_token_da_mensaje_claro():
    with pytest.raises(ErrorInstagram, match="IG_ACCESS_TOKEN"):
        ClienteInstagram("", "123")


def test_ocultar_quita_tokens_aunque_no_se_conozcan():
    assert TOKEN not in ocultar(f"x {TOKEN} y") and "***" in ocultar(f"x {TOKEN} y")
    assert traducir_error({"error": {"code": 368, "message": "m"}}, 400).codigo == 368
