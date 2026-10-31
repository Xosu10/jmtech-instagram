"""Catálogo de assets (ADDENDUM): se valida lo que haya aprobado; vacío también es válido."""
import json
from pathlib import Path

import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "assets" / "ilustraciones"
CAMPOS = ["archivo", "original", "tipo", "categoria", "etiquetas", "temas", "tamano_px", "transparencia",
          "zona_libre", "estilos_compatibles", "notas_calidad", "aprobado", "fecha"]
MAX_LADO = 1600

CATALOGO = json.loads((CARPETA / "catalogo.json").read_text(encoding="utf-8"))
ENTRADAS = CATALOGO["entradas"]


def ruta(e):
    return CARPETA / {"aislado": "aislados", "ambiente": "ambiente", "fondo": "fondos", "flatlay": "flatlay"}[e["tipo"]] / e["archivo"]


def test_las_carpetas_existen():
    for c in ("nuevas", "originales", "aislados", "ambiente", "fondos", "flatlay", "descartadas"):
        assert (CARPETA / c).is_dir()


@pytest.mark.parametrize("e", ENTRADAS, ids=lambda e: e.get("archivo", "?"))
def test_entrada_aprobada_completa_y_existe(e):
    assert all(c in e for c in CAMPOS)
    if e["aprobado"]:
        assert ruta(e).exists()


@pytest.mark.parametrize("e", [e for e in ENTRADAS if e["aprobado"] and e["tipo"] == "aislado"],
                         ids=lambda e: e["archivo"])
def test_los_aislados_tienen_transparencia_real(e):
    with Image.open(ruta(e)) as im:
        alfa = im.convert("RGBA").getchannel("A")
        transparentes = sum(1 for v in alfa.getdata() if v < 10) / (im.width * im.height)
    assert transparentes > 0.15


@pytest.mark.parametrize("e", [e for e in ENTRADAS if e["aprobado"]], ids=lambda e: e["archivo"])
def test_tamano_razonable(e):
    with Image.open(ruta(e)) as im:
        assert max(im.size) <= MAX_LADO
    assert ruta(e).stat().st_size < 3_000_000


def test_no_se_usan_assets_descartados():
    descartadas = {p.name for p in (CARPETA / "descartadas").iterdir() if p.name != ".gitkeep"}
    assert not any(e["aprobado"] and e["archivo"] in descartadas for e in ENTRADAS)
