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
    e = cur.cargar_espec(ruta)
    d = cur.construir_descripcion(e)
    assert "Voz generada con IA" in d
    if e.get("fuentes"):
        assert "Fuentes consultadas" in d
    else:
        assert ("Ejemplo ilustrativo" in d) if e.get("serie") == "automatizacion" else ("Contenido informativo" in d)
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
                try:
                    ruta, _ = cur.imagen_de_escena(esc, e["id"])       # definitiva o, si falta, la provisional
                except FileNotFoundError:
                    bib = {i["archivo"] for i in json.loads((RAIZ / "contenido" / "biblioteca_imagenes.json").read_text(encoding="utf-8"))["imagenes"]}
                    assert esc["imagen"] in bib, f"{e['id']}: {esc['imagen']} no existe ni está pedida"       # pendiente de entregar
                    continue
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
    assert decidir(utc(2026, 11, 2, 18), cfg(posts=True), solo_curiosidad, tipo="post").accion == "publicar"


def test_el_flujo_de_la_nube_coincide_con_el_calendario():
    texto = (RAIZ / ".github" / "workflows" / "publicar-curiosidad.yml").read_text(encoding="utf-8")
    assert '"0 15 * * *"' in texto and '"0 16 * * *"' in texto       # todos los días, también fines de semana
    assert cargar_config()["hora_curiosidad"] == "17:00"


# ---------- Plan completo ----------
def _plan():
    return json.loads((RAIZ / "contenido" / "plan_curiosidades.json").read_text(encoding="utf-8"))["plan"]


def test_el_plan_tiene_una_ficha_por_dia_y_fechas_validas():
    from datetime import date
    fechas = [p["fecha"] for p in _plan()]
    assert len(set(fechas)) == len(fechas)
    assert len(fechas) == 312 and fechas[0] == "2026-11-02"
    semana = {date.fromisoformat(f).weekday() for f in fechas}
    assert semana == {0, 1, 2, 3, 4, 5, 6}                                         # hay vídeo cualquier día de la semana
    assert fechas == sorted(fechas)
    for p in _plan():
        assert (RAIZ / "contenido" / "curiosidades" / f"{p['id']}.json").exists(), p["id"]


def test_toda_imagen_pedida_a_la_otra_ia_esta_en_la_biblioteca_o_entregada():
    bib = {i["archivo"] for i in json.loads((RAIZ / "contenido" / "biblioteca_imagenes.json").read_text(encoding="utf-8"))["imagenes"]}
    anteriores = {"refrigeracion_aire_vs_liquida_aislado_01.png", "cpu_calor_aislado_01.png", "cpu_circuitos_aislado_01.png",
                  "cpu_termometro_aislado_01.png", "ram_ddr5_unico_aislado_01.png", "metafora_mesa_trabajo_aislado_01.png",
                  "ia_modelo_chip_aislado_01.png", "pc_polvo_interior_aislado_01.png", "ventilador_polvo_aislado_01.png",
                  "limpieza_pc_herramientas_aislado_01.png"}
    for ruta in ESPECS:
        e = cur.cargar_espec(ruta)
        for archivo, escena in cur.imagenes_pendientes(e):
            assert archivo in bib or archivo in anteriores, f"{e['id']} escena {escena}: {archivo} no está pedida"


def test_el_montaje_no_repite_lo_que_no_ha_cambiado(tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(cur, "encolar", lambda espec, fecha, carpeta, musica=None, inicio=10.0, extra=None: (
        llamadas.append(espec["id"]), cur.guardar_cola(carpeta, [v for v in cur.cargar_cola(carpeta) if v["id"] != espec["id"]] +
                                                       [{"fecha": fecha, "id": espec["id"], "video": "v.mp4", "pie": "x", **extra}]),
        (tmp_path / "v.mp4").write_bytes(b"v"))[-1] or (None, 0))
    mont, esp = cur.montar_plan(tmp_path, None, hasta="2026-11-09", provisional=True, avisar=lambda *_: None)
    assert len(mont) == len(llamadas) >= 3
    mont2, _ = cur.montar_plan(tmp_path, None, hasta="2026-11-09", provisional=True, avisar=lambda *_: None)
    assert mont2 == []                                 # nada ha cambiado: no se vuelve a montar


def test_gta_vi_se_dice_gta_seis_sin_cambiar_el_numero_de_palabras():
    texto = "Mañana sale GTA VI. Vice City, VIVA."
    voz = cur._pronunciar(texto)
    assert "GTA seis" in voz and "Vice City" in voz and "VIVA" in voz
    assert len(voz.split()) == len(texto.split())


# ---------- Las noticias de la semana (domingos a las 19:00, cola propia) ----------
@pytest.fixture
def cola_noticias(cola):
    carpeta = cola / "noticias"
    carpeta.mkdir()
    (carpeta / "n.mp4").write_bytes(b"video")
    (carpeta / "cola.json").write_text(json.dumps({"videos": [
        {"fecha": "2026-11-01", "id": "noticias_1", "video": "n.mp4", "pie": "Pie de noticias"}]}), encoding="utf-8")
    return cola


@pytest.mark.parametrize("ahora, publica", [
    (utc(2026, 11, 1, 17, 59), False),    # invierno: 18:59 en Madrid, todavía no
    (utc(2026, 11, 1, 18, 0), True),      # 19:00
    (utc(2026, 11, 1, 19, 29), True),     # 20:29
    (utc(2026, 11, 1, 19, 30), False),    # 20:30, demasiado tarde
])
def test_ventana_de_las_noticias_de_las_19(cola_noticias, ahora, publica):
    ig = FalsoInstagram()
    r = cur.noticias_hoy(cola_noticias, ahora, cfg=cfg(), estado=VACIO, cliente=ig, ruta_estado=cola_noticias / "e.json")
    assert bool(r) is publica and len(ig.subidos) == int(publica)


def test_las_noticias_tienen_cola_propia_y_no_bloquean_a_la_curiosidad(cola_noticias):
    ig, ruta = FalsoInstagram(), cola_noticias / "e.json"
    r = cur.noticias_hoy(cola_noticias, utc(2026, 11, 1, 18), cfg=cfg(), cliente=ig, ruta_estado=ruta)
    assert r["tipo"] == "noticias" and r["fecha"] == "2026-11-01" and ig.subidos == [("n.mp4", "Pie de noticias")]
    assert cur.noticias_hoy(cola_noticias, utc(2026, 11, 1, 19), cfg=cfg(), cliente=ig, ruta_estado=ruta) is None   # no se repite
    # la cola de curiosidades no se mezcla con la de noticias, ni al revés
    assert cur.curiosidad_hoy(cola_noticias, utc(2026, 11, 1, 16), cfg=cfg(), cliente=ig, ruta_estado=ruta) is None
    assert cur.curiosidad_hoy(cola_noticias, utc(2026, 11, 2, 16), cfg=cfg(), cliente=ig, ruta_estado=ruta)["tipo"] == "curiosidad"


def test_noticias_se_pueden_pausar(cola_noticias):
    ig = FalsoInstagram()
    assert cur.noticias_hoy(cola_noticias, utc(2026, 11, 1, 18), cfg=cfg(noticias=False), estado=VACIO, cliente=ig) is None
    assert ig.subidos == []


def test_el_flujo_de_las_noticias_coincide_con_el_calendario():
    texto = (RAIZ / ".github" / "workflows" / "publicar-noticias.yml").read_text(encoding="utf-8")
    assert '"0 17 * * 0"' in texto and '"0 18 * * 0"' in texto and "noticias --carpeta musica/curiosidades" in texto
    assert cargar_config()["hora_noticias"] == "19:00" and cargar_config()["noticias"] is True


def test_los_guiones_de_noticias_pasan_las_comprobaciones():
    for ruta in (RAIZ / "contenido" / "noticias").glob("*.json"):
        assert cur.problemas_espec(cur.cargar_espec(ruta)) == [], ruta.name


def test_la_url_publica_de_respaldo_no_toca_nada_fuera_de_github_actions(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(cur, "RAIZ", tmp_path)
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x")
    assert cur._publicar_url_publica(v, "x.mp4") is None
    assert not (cur.RAIZ / "salida_curiosidades").exists()
