"""Imágenes: los 11 temas × 3 estilos se generan sin problemas de maquetación y como JPEG válido."""
import pytest
from PIL import Image

from jmtech.contenido import cargar_temas
from jmtech.ilustraciones import REGISTRO
from jmtech.render import ESTILOS, guardar_jpeg, renderizar
from jmtech.validacion import problemas_imagen

TEMAS = cargar_temas()
CASOS = [(t, e) for t in TEMAS for e in ESTILOS]


@pytest.fixture(scope="module")
def generadas(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("imagenes")
    salida = {}
    for t, e in CASOS:
        img, info = renderizar(t, e)
        salida[(t["id"], e)] = (guardar_jpeg(img, carpeta / f"{t['id']}_{e}.jpg"), info)
    return salida


def test_cada_tema_tiene_ilustracion_de_respaldo():
    assert set(REGISTRO) | {"streaming"} == {t["id"] for t in TEMAS}


def test_sin_problemas_de_maquetacion(generadas):
    malos = {k: v[1]["avisos"] for k, v in generadas.items() if v[1]["avisos"]}
    assert malos == {}


def test_son_jpeg_1080x1350_rgb(generadas):
    for k, (ruta, _) in generadas.items():
        assert problemas_imagen(ruta) == [], k


def test_pesan_poco_para_subirse_al_repositorio(generadas):
    assert all(ruta.stat().st_size < 1_500_000 for ruta, _ in generadas.values())


def test_tamano_de_letra_razonable(generadas):
    for k, (_, info) in generadas.items():
        assert info["titulo_size"] >= 80, k
        assert info["puntos_size"] >= 26, k


def test_estilo_desconocido_da_error():
    with pytest.raises(ValueError):
        renderizar(TEMAS[0], "Z")


def test_problemas_imagen_detecta_formatos_y_tamanos_malos(tmp_path):
    Image.new("RGB", (1080, 1350)).save(tmp_path / "a.png")
    Image.new("RGB", (500, 500)).save(tmp_path / "b.jpg")
    assert problemas_imagen(tmp_path / "a.png")
    assert problemas_imagen(tmp_path / "b.jpg")
    assert problemas_imagen(tmp_path / "no_existe.jpg")
