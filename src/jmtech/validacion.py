"""Comprobaciones de contenido e imagen antes de publicar (y en las pruebas)."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

MAX_PIE = 2200
HASHTAGS = (5, 6)
TAMANO = (1080, 1350)

_PROHIBIDO = re.compile(
    r"€|\$|\beuros?\b|\bdescuentos?\b|\bofertas?\b|\bgratis\b|\bgratuit\w*|\bgarant[ií]\w*|%|\bprecios?\b|\brebajas?\b",
    re.IGNORECASE)
_CONTACTO = re.compile(r"https?://|www\.|\+34|\b\d{3}[ .]?\d{3}[ .]?\d{3}\b|[\w.]+@[\w.]+\.\w+", re.IGNORECASE)


def problemas_texto(texto: str) -> list[str]:
    """Comprueba un texto comercial (título, puntos, pie de foto...)."""
    fallos = []
    m = _PROHIBIDO.search(texto)
    if m:
        fallos.append(f"contiene «{m.group(0)}» (sin precios, descuentos, ofertas ni garantías)")
    m = _CONTACTO.search(texto)
    if m:
        fallos.append(f"contiene datos de contacto («{m.group(0)}»): el contacto es solo por MD")
    return fallos


def problemas_pie(pie: str) -> list[str]:
    fallos = problemas_texto(pie)
    if len(pie) > MAX_PIE:
        fallos.append(f"mide {len(pie)} caracteres (máximo {MAX_PIE})")
    n = len(re.findall(r"#\w+", pie))
    if not HASHTAGS[0] <= n <= HASHTAGS[1]:
        fallos.append(f"tiene {n} hashtags (debe haber entre {HASHTAGS[0]} y {HASHTAGS[1]})")
    if "sin compromiso" not in pie.lower():
        fallos.append("no dice «sin compromiso»")
    if "MD" not in pie:
        fallos.append("no invita a escribir por MD")
    return fallos


def problemas_imagen(ruta) -> list[str]:
    ruta = Path(ruta)
    if not ruta.exists():
        return [f"no existe el archivo {ruta.name}"]
    try:
        with Image.open(ruta) as im:
            im.load()
            fallos = []
            if im.format != "JPEG":
                fallos.append(f"el formato es {im.format}, debe ser JPEG")
            if im.size != TAMANO:
                fallos.append(f"el tamaño es {im.size[0]}x{im.size[1]}, debe ser {TAMANO[0]}x{TAMANO[1]}")
            if im.mode != "RGB":
                fallos.append(f"el modo de color es {im.mode}, debe ser RGB")
            return fallos
    except OSError as e:
        return [f"no es una imagen válida ({e})"]


def problemas_tema(tema: dict) -> list[str]:
    """Todos los textos de un tema: sin precios ni contacto, pies correctos, alt_text presente."""
    fallos = []
    campos = [tema["titulo_linea1"], tema["titulo_linea2_azul"], tema["subtitulo"], *tema["puntos"]]
    for c in campos:
        fallos += [f"{tema['id']}: «{c}» {f}" for f in problemas_texto(c)]
    for i, pie in enumerate(tema["pies_de_foto"], 1):
        fallos += [f"{tema['id']} pie {i}: {f}" for f in problemas_pie(pie)]
    if not tema.get("texto_alternativo"):
        fallos.append(f"{tema['id']}: falta el texto alternativo")
    if not 3 <= len(tema["puntos"]) <= 4:
        fallos.append(f"{tema['id']}: debe tener 3 o 4 puntos")
    return fallos
