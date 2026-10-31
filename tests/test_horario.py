"""Cambio de hora: se publica solo si en Madrid son las 19:00-20:30, en invierno y en verano."""
from datetime import datetime, timezone

import pytest

from jmtech.calendario import cargar_config, completar_config
from jmtech.publicador import ahora_madrid, decidir, en_ventana, retraso_min

VACIO = {"publicaciones": []}


def utc(a, m, d, h, mi=0):
    return datetime(a, m, d, h, mi, tzinfo=timezone.utc)


def cfg(**cambios):
    c = cargar_config()
    c.update(cambios)
    return completar_config(c)


def accion(ahora, estado=VACIO, **kw):
    return decidir(ahora, kw.pop("cfg", cfg()), estado, **kw).accion


def test_madrid_es_utc_mas_1_en_invierno_y_mas_2_en_verano():
    assert ahora_madrid(utc(2026, 11, 2, 18)).hour == 19
    assert ahora_madrid(utc(2027, 4, 5, 17)).hour == 19


@pytest.mark.parametrize("ahora, esperado", [
    (utc(2026, 11, 2, 17, 0), "omitir"),    # invierno: 18:00 en Madrid -> todavía no
    (utc(2026, 11, 2, 18, 0), "publicar"),  # invierno: 19:00
    (utc(2026, 11, 2, 19, 29), "publicar"),  # invierno: 20:29, con retraso aceptable
    (utc(2026, 11, 2, 19, 30), "omitir"),   # invierno: 20:30, demasiado tarde
    (utc(2027, 4, 5, 16, 59), "omitir"),    # verano: 18:59
    (utc(2027, 4, 5, 17, 0), "publicar"),   # verano: 19:00
    (utc(2027, 4, 5, 18, 0), "publicar"),   # verano: 20:00 (segundo disparo, solo si el primero falló)
    (utc(2027, 4, 5, 18, 29), "publicar"),  # verano: 20:29
    (utc(2027, 4, 5, 18, 30), "omitir"),    # verano: 20:30
    (utc(2027, 4, 5, 19, 0), "omitir"),     # verano: 21:00
])
def test_ventana_de_publicacion(ahora, esperado):
    assert accion(ahora) == esperado


def test_dias_del_cambio_de_hora():
    c = cfg(fecha_inicio="2026-10-01")
    # lunes antes del cambio de octubre (horario de verano)
    assert accion(utc(2026, 10, 19, 17), cfg=c) == "publicar"
    # lunes después del cambio de octubre (horario de invierno)
    assert accion(utc(2026, 10, 26, 17), cfg=c) == "omitir"
    assert accion(utc(2026, 10, 26, 18), cfg=c) == "publicar"
    # lunes antes y después del cambio de marzo de 2027 (el domingo 28)
    assert accion(utc(2027, 3, 22, 17), cfg=c) == "omitir"
    assert accion(utc(2027, 3, 22, 18), cfg=c) == "publicar"
    assert accion(utc(2027, 3, 29, 17), cfg=c) == "publicar"
    assert accion(utc(2027, 3, 29, 16), cfg=c) == "omitir"


def test_no_publica_en_fin_de_semana_festivo_pausa_o_antes_del_inicio():
    assert accion(utc(2026, 11, 7, 18)) == "omitir"                                         # sábado
    assert accion(utc(2026, 11, 8, 18)) == "omitir"                                         # domingo
    assert accion(utc(2026, 11, 4, 18), cfg=cfg(dias_sin_publicar=["2026-11-04"])) == "omitir"
    assert accion(utc(2026, 11, 2, 18), cfg=cfg(pausado=True)) == "omitir"
    assert accion(utc(2026, 10, 26, 18)) == "omitir"                                        # antes del inicio


def test_dos_disparos_en_el_mismo_dia_solo_publican_una_vez():
    ya = {"publicaciones": [{"fecha": "2027-04-05", "resultado": "publicado", "prueba": False}]}
    assert accion(utc(2027, 4, 5, 17), ya) == "omitir"
    assert accion(utc(2027, 4, 5, 18), ya) == "omitir"


def test_una_prueba_manual_no_bloquea_ni_cuenta_como_la_del_dia():
    solo_prueba = {"publicaciones": [{"fecha": "2026-11-02", "resultado": "publicado", "prueba": True}]}
    assert accion(utc(2026, 11, 2, 18), solo_prueba) == "publicar"
    d = decidir(utc(2026, 11, 7, 3), cfg(), VACIO, prueba=True, tema="streaming", estilo="B")
    assert d.accion == "publicar" and d.publicacion.tema_id == "streaming" and d.publicacion.estilo == "B"


def test_ignorar_hora_solo_salta_la_ventana():
    assert accion(utc(2026, 11, 2, 12), ignorar_hora=True) == "publicar"
    assert accion(utc(2026, 11, 7, 12), ignorar_hora=True) == "omitir"      # sigue sin publicar en sábado


def test_retraso_y_ventana():
    c = cfg()
    assert retraso_min(ahora_madrid(utc(2026, 11, 2, 18, 0)), c) == 0
    assert retraso_min(ahora_madrid(utc(2026, 11, 2, 18, 47)), c) == 47
    assert en_ventana(ahora_madrid(utc(2026, 11, 2, 19, 0)), c)
