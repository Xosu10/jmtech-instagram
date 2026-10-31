"""Calendario para subir a TikTok a mano: textos adaptados y nombres de archivo ordenados."""
from jmtech import tiktok


def test_la_descripcion_se_adapta_a_tiktok_sin_md():
    t = tiktok.a_tiktok("Escríbenos por MD. Presupuesto sin compromiso por MD. #MDF")
    assert "MD." not in t and "por mensaje directo" in t and "#MDF" in t


def test_slug_de_archivo_es_ascii_y_corto():
    s = tiktok.slug("¿Por qué se calienta tanto el procesador? Ñandú & más…")
    assert s == s.lower() and s.isascii() and " " not in s and len(s) <= 48 and "--" not in s


def test_el_html_tiene_hoy_y_las_descripciones_se_copian():
    h = tiktok._HTML
    for clave in ("Copiar descripción", "Ya subido a TikTok", "reel_ya_en_instagram", "Mañana", "localStorage", "__DATOS__"):
        assert clave in h
