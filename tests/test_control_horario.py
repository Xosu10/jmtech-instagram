from datetime import datetime, timezone

import pytest

from jmtech.calendario import cargar_config
from jmtech.control_horario import comprobar_fecha, falta_publicacion
from jmtech.publicador import ErrorPublicacion, ya_en_instagram
from jmtech.instagram import ErrorInstagram


def test_rechaza_disparo_del_dia_anterior():
    with pytest.raises(ValueError):
        comprobar_fecha("2026-11-02", datetime(2026, 11, 3, 14, tzinfo=timezone.utc))


def test_fecha_madrid_y_no_utc():
    comprobar_fecha("2026-11-03", datetime(2026, 11, 2, 23, 30, tzinfo=timezone.utc))


def test_omision_tardia_no_es_publicacion_correcta():
    assert falta_publicacion("reel", cargar_config(), {"publicaciones": []}, datetime(2026, 11, 2, 18, tzinfo=timezone.utc))


def test_prueba_no_satisface_publicacion_y_tipo_distinto_tampoco():
    estado = {"publicaciones": [{"fecha": "2026-11-02", "tipo": "curiosidad", "resultado": "publicado"}, {"fecha": "2026-11-02", "tipo": "reel", "resultado": "publicado", "prueba": True}]}
    assert falta_publicacion("reel", cargar_config(), estado, datetime(2026, 11, 2, 18, tzinfo=timezone.utc))


def test_no_exige_publicacion_antes_de_hora_ni_con_pausa():
    cfg = cargar_config()
    assert not falta_publicacion("reel", cfg, {"publicaciones": []}, datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
    cfg["pausado"] = True
    assert not falta_publicacion("reel", cfg, {"publicaciones": []}, datetime(2026, 11, 2, 18, tzinfo=timezone.utc))


def test_no_se_publica_si_no_se_puede_descartar_un_duplicado():
    class Fallo:
        def ultimos_medios(self, n):
            raise ErrorInstagram("red no disponible")
    with pytest.raises(ErrorPublicacion, match="evitar duplicados"):
        ya_en_instagram(Fallo(), "pie", datetime(2026, 11, 2, 18, tzinfo=timezone.utc))
