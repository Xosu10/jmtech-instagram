"""Vídeos de curiosidades: guion, descripción, cola, horario y duplicados (sin llamar a Instagram ni a la voz)."""
import json
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from jmtech import curiosidad as cur
from jmtech.calendario import cargar_config, completar_config

RAIZ = Path(__file__).resolve().parents[1]
ESPECS = sorted((RAIZ / "contenido" / "curiosidades").glob("*.json"))
VACIO = {"publicaciones": []}


def utc(a, m, d, h, mi=0):
    return datetime(a, m, d, h, mi, tzinfo=timezone.utc)


def cfg(**cambios):
    c = cargar_config()
    c.update(cambios)
    return completar_config(c)


class FalsoInstagram:
    def __init__(self, medios=()):
        self.medios, self.subidos = list(medios), []

    def ultimos_medios(self, n):
        return self.medios

    def publicar_reel(self, ruta, pie, video_url=None):
        self.subidos.append((Path(ruta).name, pie))
        return "999"

    def permalink(self, media_id):
        return f"https://instagram.com/reel/{media_id}"


@pytest.fixture
def cola(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"video")
    (tmp_path / "cola.json").write_text(json.dumps({"videos": [
        {"fecha": "2026-11-02", "id": "tema_1", "video": "v.mp4", "pie": "Pie de prueba"}]}), encoding="utf-8")
    return tmp_path


# ---------- Guiones ----------
def test_hay_guiones():
    assert len(ESPECS) >= 1


@pytest.mark.parametrize("ruta", ESPECS, ids=lambda r: r.stem)
def test_cada_guion_pasa_las_comprobaciones(ruta):
    assert cur.problemas_espec(cur.cargar_espec(ruta)) == []


@pytest.mark.parametrize("ruta", ESPECS, ids=lambda r: r.stem)
def test_la_descripcion_avisa_de_voz_ia_cita_fuentes_y_marca(ruta):
    d = cur.construir_descripcion(cur.cargar_espec(ruta))
    assert "Voz generada con IA" in d and "Fuentes consultadas" in d
    assert "sin compromiso" in d and "MD" in d and "Murcia" in d
    assert len(d) <= cur.MAX_DESCRIPCION


def test_un_guion_con_precios_o_demasiado_largo_se_rechaza():
    e = cur.cargar_espec(ESPECS[0])
    e["escenas"][0]["texto"] = "Es gratis y con un descuento del 20 %."
    assert any("gratis" in f or "descuento" in f for f in cur.problemas_espec(e))
    e["escenas"][0]["texto"] = "Un SSD cuesta más y los precios de la RAM suben."      # el mercado sí se puede comentar
    assert cur.problemas_espec(e) == []
    e = cur.cargar_espec(ESPECS[0])
    e["escenas"][1]["texto"] = "palabra " * 200
    assert any("palabras" in f for f in cur.problemas_espec(e))
    e = cur.cargar_espec(ESPECS[0])
    e["escenas"] = e["escenas"][:2]
    assert any("escenas" in f for f in cur.problemas_espec(e))


def test_cada_imagen_del_guion_existe():
    for ruta in ESPECS:
        e = cur.cargar_espec(ruta)
        for esc in e["escenas"]:
            if esc.get("imagen") and not esc.get("grafico"):
                ruta, _ = cur.imagen_de_escena(esc, e["id"])       # definitiva o, si falta, la provisional
                assert ruta.exists()


def test_una_imagen_sin_entregar_usa_la_provisional_y_se_avisa(tmp_path, monkeypatch):
    monkeypatch.setattr(cur, "CARPETA_IMAGENES", tmp_path)
    esc = {"imagen": "nueva_aislado_01.png", "provisional": "pc_gaming_aio_blanco_aislado_01.png"}
    ruta, provisional = cur.imagen_de_escena(esc, "v")
    assert provisional and ruta.exists()
    assert cur.imagenes_pendientes({"id": "v", "escenas": [esc]}) == [("nueva_aislado_01.png", 1)]
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "nueva_aislado_01.png").write_bytes(b"png")
    assert cur.imagen_de_escena(esc, "v") == (tmp_path / "v" / "nueva_aislado_01.png", False)
    assert cur.imagenes_pendientes({"id": "v", "escenas": [esc]}) == []
    with pytest.raises(FileNotFoundError):
        cur.imagen_de_escena({"imagen": "no_existe.png"}, "v")


# ---------- Subtítulos y audio ----------
def test_los_subtitulos_son_cortos_y_cortan_en_los_signos():
    palabras = [(i * 0.3, 0.25, w) for i, w in enumerate("Es sencillo, fiable y casi no da problemas.".split())]
    trozos = cur._trozos(palabras)
    assert all(len(t) <= 3 for t in trozos)
    assert [p[2] for t in trozos for p in t] == [p[2] for p in palabras]
    assert any(t[-1][2].endswith(",") for t in trozos)


def test_mezcla_de_audio_sin_musica_ni_recortes(tmp_path):
    wavs = []
    for i in range(2):
        ruta = tmp_path / f"v{i}.wav"
        with wave.open(str(ruta), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes((np.sin(np.arange(44100) / 20) * 20000).astype("<i2").tobytes())
        wavs.append(ruta)
    salida = tmp_path / "mezcla.wav"
    cur._mezclar_audio(wavs, [0.35, 0.35], None, salida, 2.7)
    with wave.open(str(salida)) as w:
        assert w.getnchannels() == 2 and w.getnframes() >= 2.7 * 44100
        datos = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    assert np.abs(datos).max() < 32767 * 0.9


# ---------- Horario y cola ----------
@pytest.mark.parametrize("ahora, publica", [
    (utc(2026, 11, 2, 15, 59), False),    # invierno: 16:59 en Madrid, todavía no
    (utc(2026, 11, 2, 16, 0), True),      # invierno: 17:00
    (utc(2026, 11, 2, 17, 29), True),     # 18:29
    (utc(2026, 11, 2, 17, 30), False),    # 18:30, demasiado tarde
])
def test_ventana_de_las_17(cola, ahora, publica):
    ig = FalsoInstagram()
    r = cur.curiosidad_hoy(cola, ahora, cfg=cfg(), estado=VACIO, cliente=ig, ruta_estado=cola / "estado.json")
    assert bool(r) is publica and len(ig.subidos) == int(publica)


def test_solo_publica_el_dia_que_figura_en_la_cola(cola):
    ig = FalsoInstagram()
    assert cur.curiosidad_hoy(cola, utc(2026, 11, 3, 16), cfg=cfg(), estado=VACIO, cliente=ig,
                              ruta_estado=cola / "estado.json") is None
    assert ig.subidos == []


def test_publica_y_anota_y_no_repite(cola):
    ig, ruta = FalsoInstagram(), cola / "estado.json"
    r = cur.curiosidad_hoy(cola, utc(2026, 11, 2, 16), cfg=cfg(), cliente=ig, ruta_estado=ruta)
    assert r["tipo"] == "curiosidad" and r["fecha"] == "2026-11-02" and r["permalink"].endswith("999")
    assert ig.subidos == [("v.mp4", "Pie de prueba")]
    assert cur.curiosidad_hoy(cola, utc(2026, 11, 2, 17), cfg=cfg(), cliente=ig, ruta_estado=ruta) is None     # segundo disparo
    assert len(ig.subidos) == 1


def test_si_instagram_ya_lo_tiene_no_se_sube_otra_vez(cola):
    medio = {"id": "55", "media_type": "VIDEO", "caption": "Pie de prueba", "permalink": "https://x/55",
             "timestamp": "2026-11-02T16:00:30+0000"}
    ig = FalsoInstagram([medio])
    r = cur.curiosidad_hoy(cola, utc(2026, 11, 2, 16, 30), cfg=cfg(), cliente=ig, ruta_estado=cola / "estado.json")
    assert r["media_id"] == "55" and ig.subidos == []


def test_pausa_y_curiosidades_desactivadas(cola):
    for c in (cfg(pausado=True), cfg(curiosidades=False)):
        ig = FalsoInstagram()
        assert cur.curiosidad_hoy(cola, utc(2026, 11, 2, 16), cfg=c, estado=VACIO, cliente=ig) is None
        assert ig.subidos == []


def test_en_seco_no_llama_a_instagram(cola):
    ig = FalsoInstagram()
    assert cur.curiosidad_hoy(cola, utc(2026, 11, 2, 16), cfg=cfg(), estado=VACIO, cliente=ig, dry_run=True) is None
    assert ig.subidos == []


def test_la_curiosidad_no_bloquea_ni_es_bloqueada_por_la_publicacion_y_el_reel():
    from jmtech.publicador import decidir
    solo_curiosidad = {"publicaciones": [{"fecha": "2026-11-02", "resultado": "publicado", "prueba": False, "tipo": "curiosidad"}]}
    assert decidir(utc(2026, 11, 2, 14), cfg(), solo_curiosidad, tipo="reel").accion == "publicar"
    assert decidir(utc(2026, 11, 2, 18), cfg(), solo_curiosidad, tipo="post").accion == "publicar"


def test_el_flujo_de_la_nube_coincide_con_el_calendario():
    texto = (RAIZ / ".github" / "workflows" / "publicar-curiosidad.yml").read_text(encoding="utf-8")
    assert '"0 15 * * 1,3,5"' in texto and '"0 16 * * 1,3,5"' in texto
    assert cargar_config()["hora_curiosidad"] == "17:00"
