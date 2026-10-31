"""Reels: música propia, vídeo 1080x1920 y publicación (con la API simulada)."""
import shutil
import subprocess
import wave

import pytest

from jmtech.assets import cargar_catalogo, indice
from jmtech.contenido import indice_temas
from jmtech.instagram import ClienteInstagram, ErrorInstagram
from jmtech.reel import generar_reel, sintetizar_musica

from test_publicador import Respuesta, SesionApi, TOKEN

FFMPEG = shutil.which("ffmpeg")
requiere_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg no está instalado")


def test_la_musica_propia_dura_lo_pedido_y_es_estereo(tmp_path):
    ruta = sintetizar_musica(tmp_path / "m.wav", dur=3.0)
    with wave.open(str(ruta)) as w:
        assert w.getnchannels() == 2 and w.getframerate() == 44100
        assert abs(w.getnframes() / w.getframerate() - 3.0) < 0.05


@requiere_ffmpeg
def test_el_reel_se_genera_en_mp4_vertical_con_audio(tmp_path):
    tema = indice_temas()["tarjeta_grafica"]
    asset = indice(cargar_catalogo())["gpu_triple_ventilador_aislado_01.png"]
    mp4 = generar_reel(tema, asset, tmp_path / "r.mp4", dur=1.5)
    assert mp4.exists() and 5_000 < mp4.stat().st_size < 5_000_000
    salida = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mp4)], capture_output=True, text=True).stderr
    assert "h264" in salida and "1080x1920" in salida and "aac" in salida and "Duration: 00:00:01" in salida


def test_publicar_reel_sube_espera_y_publica(tmp_path):
    video = tmp_path / "r.mp4"
    video.write_bytes(b"x" * 2000)
    s = SesionApi([Respuesta({"id": "c1", "uri": "https://rupload.facebook.com/ig-api-upload/v25.0/c1"}),
                   Respuesta({"success": True}),                      # subida del vídeo
                   Respuesta({"status_code": "IN_PROGRESS"}), Respuesta({"status_code": "FINISHED"}),
                   Respuesta({"id": "m1"})])
    s.post = lambda url, headers=None, data=None, timeout=None: s.respuestas.pop(0) if "rupload" in url else None
    s.request = _mezclar(s)
    c = ClienteInstagram(TOKEN, "123", sesion=s, dormir=lambda _: None)
    assert c.publicar_reel(video, "pie") == "m1"
    primera = s.llamadas[0]
    assert primera["data"]["media_type"] == "REELS" and primera["data"]["upload_type"] == "resumable"
    assert TOKEN not in primera["url"] and primera["headers"]["Authorization"] == f"Bearer {TOKEN}"


def _mezclar(s):
    """La subida usa .post y el resto .request, pero comparten la lista de respuestas."""
    original = s.request

    def request(metodo, url, headers=None, timeout=None, params=None, data=None):
        s.llamadas.append(dict(metodo=metodo, url=url, headers=headers, params=params, data=data))
        return s.respuestas.pop(0)

    return request


def test_si_falla_la_subida_directa_se_usa_la_direccion_publica(tmp_path):
    video = tmp_path / "r.mp4"
    video.write_bytes(b"x" * 2000)
    s = SesionApi([Respuesta({"id": "c1", "uri": "https://rupload.facebook.com/x"}),
                   Respuesta({"id": "c2"}), Respuesta({"status_code": "FINISHED"}), Respuesta({"id": "m9"})])
    s.post = lambda url, headers=None, data=None, timeout=None: Respuesta({"error": {"code": 100, "message": "no permitido"}}, 400)
    s.request = _mezclar(s)
    c = ClienteInstagram(TOKEN, "123", sesion=s, dormir=lambda _: None)
    assert c.publicar_reel(video, "pie", video_url="https://x/r.mp4") == "m9"
    assert any(l["data"].get("video_url") == "https://x/r.mp4" for l in s.llamadas if l["data"])


def test_sin_dar_direccion_publica_el_fallo_de_subida_sube(tmp_path):
    video = tmp_path / "r.mp4"
    video.write_bytes(b"x")
    s = SesionApi([Respuesta({"id": "c1"})])
    s.post = lambda url, headers=None, data=None, timeout=None: Respuesta({"error": {"code": 100, "message": "no"}}, 400)
    s.request = _mezclar(s)
    c = ClienteInstagram(TOKEN, "123", sesion=s, dormir=lambda _: None)
    with pytest.raises(ErrorInstagram):
        c.publicar_reel(video, "pie")
