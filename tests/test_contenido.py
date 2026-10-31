"""Textos: sin precios ni contacto, pies de foto correctos, 3-4 puntos."""
import pytest

from jmtech.contenido import cargar_temas, pie_de_foto
from jmtech.validacion import MAX_PIE, problemas_pie, problemas_texto, problemas_tema

TEMAS = cargar_temas()


def test_hay_11_temas_con_ids_unicos():
    ids = [t["id"] for t in TEMAS]
    assert len(ids) == 11 == len(set(ids))


@pytest.mark.parametrize("tema", TEMAS, ids=[t["id"] for t in TEMAS])
def test_tema_cumple_las_reglas(tema):
    assert problemas_tema(tema) == []


@pytest.mark.parametrize("tema", TEMAS, ids=[t["id"] for t in TEMAS])
def test_tiene_al_menos_dos_pies_y_caben_en_instagram(tema):
    assert len(tema["pies_de_foto"]) >= 2
    assert all(len(p) <= MAX_PIE for p in tema["pies_de_foto"])


def test_la_variante_se_da_la_vuelta():
    t = TEMAS[0]
    assert pie_de_foto(t, 0) != pie_de_foto(t, 1)
    assert pie_de_foto(t, 2) == pie_de_foto(t, 0)


@pytest.mark.parametrize("malo", [
    "Solo 50 € al mes", "Descuento del 20%", "Gran oferta", "Llámanos al 612 345 678", "Visita www.ejemplo.es",
    "Escribe a info@ejemplo.com", "Con garantía de 2 años", "Precio cerrado"])
def test_detecta_precios_ofertas_y_contacto(malo):
    assert problemas_texto(malo)


def test_el_pie_debe_tener_5_o_6_hashtags_y_md():
    ok = "Hola\n📩 Pide presupuesto sin compromiso por MD.\n#a #b #c #d #e"
    assert problemas_pie(ok) == []
    assert problemas_pie(ok.replace("#e", ""))                 # 4 hashtags
    assert problemas_pie(ok + " #f #g")                        # 7 hashtags
    assert problemas_pie(ok.replace("sin compromiso", ""))
    assert problemas_pie("x" * (MAX_PIE + 1) + " #a #b #c #d #e")
