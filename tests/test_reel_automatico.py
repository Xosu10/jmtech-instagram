"""Reel automático del día: horario, música, duplicados y convivencia con la publicación de las 19:00."""
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from jmtech import estado as est
from jmtech import publicador
from jmtech.calendario import cargar_config, completar_config
from jmtech.publicador import decidir, elegir_musica, reel_hoy, ya_en_instagram

RAIZ = Path(__file__).resolve().parents[1]
VACIO = {"publicaciones": []}


def utc(a, m, d, h, mi=0):
    return datetime(a, m, d, h, mi, tzinfo=timezone.utc)


def cfg(**cambios):
    c = cargar_config()
    c.update(cambios)
    return completar_config(c)


def accion(ahora, estado=VACIO, **kw):
    return decidir(ahora, kw.pop("cfg", cfg()), estado, tipo="reel", **kw).accion


@pytest.mark.parametrize("ahora, esperado", [
    (utc(2026, 11, 2, 13, 0), "omitir"),     # invierno: 14:00 en Madrid, todavía no
    (utc(2026, 11, 2, 14, 0), "publicar"),   # invierno: 15:00
    (utc(2026, 11, 2, 15, 29), "publicar"),  # invierno: 16:29, con retraso aceptable
    (utc(2026, 11, 2, 15, 30), "omitir"),    # invierno: 16:30, demasiado tarde
    (utc(2027, 4, 5, 12, 59), "omitir"),     # verano: 14:59
    (utc(2027, 4, 5, 13, 0), "publicar"),    # verano: 15:00
    (utc(2027, 4, 5, 14, 0), "publicar"),    # verano: 16:00 (segundo disparo, solo si el primero falló)
    (utc(2027, 4, 5, 14, 30), "omitir"),     # verano: 16:30
])
def test_ventana_del_reel(ahora, esperado):
    assert accion(ahora) == esperado


def test_el_reel_y_la_publicacion_son_independientes_el_mismo_dia():
    solo_post = {"publicaciones": [{"fecha": "2026-11-02", "resultado": "publicado", "prueba": False}]}
    assert accion(utc(2026, 11, 2, 14), solo_post) == "publicar"                       # el post no bloquea el reel
    solo_reel = {"publicaciones": [{"fecha": "2026-11-02", "resultado": "publicado", "prueba": False, "tipo": "reel"}]}
    assert accion(utc(2026, 11, 2, 14), solo_reel) == "omitir"                         # un reel por día
    assert decidir(utc(2026, 11, 2, 18), cfg(), solo_reel, tipo="post").accion == "publicar"   # el reel no bloquea el post


def test_pausa_fines_de_semana_y_reels_desactivados():
    assert accion(utc(2026, 11, 2, 14), cfg=cfg(pausado=True)) == "omitir"
    assert accion(utc(2026, 11, 2, 14), cfg=cfg(reels=False)) == "omitir"
    assert accion(utc(2026, 11, 7, 14)) == "omitir"                                      # sábado


def test_el_reel_y_la_publicacion_del_dia_usan_el_mismo_servicio_y_la_misma_imagen():
    a = decidir(utc(2026, 11, 2, 14), cfg(), VACIO, tipo="reel", catalogo=publicador.cargar_catalogo()).publicacion
    b = decidir(utc(2026, 11, 2, 18), cfg(), VACIO, tipo="post", catalogo=publicador.cargar_catalogo()).publicacion
    assert (a.tema_id, a.asset, a.variante) == (b.tema_id, b.asset, b.variante)


# ---------- Música ----------
def test_musica_reproducible_y_sin_repetir_dos_dias_seguidos(tmp_path):
    for i in range(5):
        (tmp_path / f"pista{i}.mp3").write_bytes(b"x")
    dias = [date(2026, 11, 2).fromordinal(date(2026, 11, 2).toordinal() + k) for k in range(60)]
    elegidas = [elegir_musica(d, tmp_path) for d in dias]
    assert elegidas == [elegir_musica(d, tmp_path) for d in dias]
    assert all(a[0] != b[0] for a, b in zip(elegidas, elegidas[1:]))
    assert len({p.name for p, _ in elegidas}) == 5 and all(8 <= ini < 38 for _, ini in elegidas)


def test_sin_musica_se_usa_la_propia(tmp_path):
    assert elegir_musica(date(2026, 11, 2), tmp_path) == (None, 0.0)
    assert elegir_musica(date(2026, 11, 2), tmp_path / "no_existe") == (None, 0.0)


# ---------- Duplicados: la publicación y su reel comparten pie ----------
def test_el_reel_no_se_confunde_con_la_publicacion_al_buscar_duplicados():
    class C:
        def ultimos_medios(self, n=10):
            return [{"id": "v1", "caption": "pie", "timestamp": "2026-11-02T14:00:10+0000", "media_type": "VIDEO"}]

    ahora = utc(2026, 11, 2, 18)
    assert ya_en_instagram(C(), "pie", ahora, "post") is None           # un reel NO cuenta como la publicación
    assert ya_en_instagram(C(), "pie", ahora, "reel")["id"] == "v1"


# ---------- Flujo completo con piezas simuladas ----------
class ClienteReel:
    def __init__(self):
        self.llamadas = []

    def ultimos_medios(self, n=10):
        return []

    def publicar_reel(self, ruta, pie, **kw):
        self.llamadas.append((Path(ruta).name, pie))
        return "r1"

    def permalink(self, m):
        return "https://www.instagram.com/reel/XYZ/"


def test_reel_hoy_publica_una_vez_y_registra(tmp_path, monkeypatch):
    import jmtech.reel as modulo
    creados = []

    def falso(tema, asset, salida, musica=None, musica_inicio=0.0, **kw):
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_bytes(b"mp4")
        creados.append((tema["id"], asset.archivo if asset else None, musica))
        return salida

    monkeypatch.setattr(modulo, "generar_reel", falso)
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "a.mp3").write_bytes(b"x")
    cliente = ClienteReel()
    ruta = tmp_path / "estado.json"
    reg = reel_hoy(utc(2026, 11, 2, 14), cliente=cliente, ruta_estado=ruta, carpeta_musica=tmp_path / "m")
    assert reg["tipo"] == "reel" and reg["permalink"].endswith("/XYZ/") and reg["musica"] == "a.mp3"
    assert creados[0][2] is not None and len(cliente.llamadas) == 1
    assert est.publicado_el(est.cargar(ruta), date(2026, 11, 2), "reel") is not None
    assert est.publicado_el(est.cargar(ruta), date(2026, 11, 2), "post") is None
    # segunda ejecución (segundo disparo del día): no repite
    assert reel_hoy(utc(2026, 11, 2, 14, 30), cliente=ClienteReel(), ruta_estado=ruta, carpeta_musica=tmp_path / "m") is None


def test_reel_hoy_en_seco_no_llama_a_instagram(tmp_path, monkeypatch):
    import jmtech.reel as modulo
    monkeypatch.setattr(modulo, "generar_reel", lambda t, a, s, **kw: (s.parent.mkdir(parents=True, exist_ok=True), s.write_bytes(b"x"), s)[2])
    cliente = ClienteReel()
    assert reel_hoy(utc(2026, 11, 2, 14), dry_run=True, cliente=cliente, ruta_estado=tmp_path / "e.json",
                    carpeta_musica=tmp_path) is None
    assert cliente.llamadas == [] and not (tmp_path / "e.json").exists()


# ---------- El flujo programado ----------
def test_el_flujo_de_reels_esta_programado_y_es_seguro():
    t = (RAIZ / ".github" / "workflows" / "publicar-reel.yml").read_text(encoding="utf-8")
    assert '"0 13 * * 1-5"' in t and '"0 14 * * 1-5"' in t                       # invierno y verano (15:00 Madrid)
    assert "concurrency:" in t and "contents: write" in t
    assert re.search(r"dry_run:\s*\n\s*description:[^\n]*\n\s*type: boolean\s*\n\s*default: true", t)
    usos = re.findall(r"secrets\.MUSICA_DEPLOY_KEY[^\n]*", t)
    assert usos and all(u.startswith(("secrets.MUSICA_DEPLOY_KEY != ''", "secrets.MUSICA_DEPLOY_KEY }}")) for u in usos)
    assert not re.search(r"echo[^\n]*(MUSICA_DEPLOY_KEY|IG_ACCESS_TOKEN)", t)
