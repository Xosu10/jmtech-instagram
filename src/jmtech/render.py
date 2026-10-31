"""Plantilla de publicación: 3 estilos (A claro, B oscuro, C mixto), 1080x1350, salida JPEG."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageCms, ImageDraw

from . import ilustraciones
from .base import (BLUE, H, INK, MUTED, S, W, WHITE, Canvas, equilibrar, font, lockup, partir)

PIE_DEFECTO = "Servicio solo en Murcia  ·  A domicilio o en nuestro taller"
MARGEN = 64
ANCHO_TEXTO = W - 2 * MARGEN
CTA_Y = 1045
ESTILOS = ("A", "B", "C")


# ---------- Elementos de diseño ----------
def pixels(c, x, y, k, color=BLUE):
    """Tres cuadraditos como los del logo."""
    c.rect(((x + 54 * k), y, (x + 102 * k), (y + 48 * k)), color)
    c.rect((x, (y + 42 * k), (x + 46 * k), (y + 88 * k)), color)
    c.rect(((x + 53 * k), (y + 87 * k), (x + 86 * k), (y + 120 * k)), color)


def check(c, x, y, size=44):
    c.rr((x, y, x + size, y + size), 12 * size / 44, fill=BLUE)
    k = size / 44
    c.line([(x + 11 * k, y + 23 * k), (x + 19 * k, y + 31 * k), (x + 33 * k, y + 14 * k)], WHITE, 5.5 * k)


def cta(c, x, y, w, h, dark_theme):
    if dark_theme:
        c.glow((x, y, x + w, y + h), BLUE, 110, 30)
    c.rr((x, y, x + w, y + h), 26, fill=BLUE)
    c.text((x + 40, y + h * 0.36), "¿Quieres presupuesto?", font("Bold", 40), WHITE, anchor="lm")
    c.text((x + 40, y + h * 0.70), "Escríbenos por MD", font("Medium", 32), (222, 238, 255), anchor="lm")
    r = 38
    ax, ay = x + w - 40 - r, y + h / 2
    c.ellipse((ax - r, ay - r, ax + r, ay + r), WHITE)
    c.line([(ax - 16, ay), (ax + 14, ay)], BLUE, 6)
    c.line([(ax + 2, ay - 13), (ax + 15, ay), (ax + 2, ay + 13)], BLUE, 6)


def chip(c, x_right, y, texto, dark_theme):
    f = font("Medium", 24)
    ancho = c.tw(texto, f)
    caja = (x_right - ancho - 48, y, x_right, y + 48)
    c.rr(caja, 24, outline=BLUE, width=2.5, fill=(8, 20, 48) if dark_theme else (232, 242, 255))
    c.text((caja[0] + 24, y + 24), texto, f, BLUE if not dark_theme else (120, 185, 255), anchor="lm")


# ---------- Texto con ajuste automático ----------
def titulo(c, tema, y_top, color1, info):
    """Dos líneas del mismo tamaño; baja el tamaño si alguna no cabe. Devuelve la base de la 2.ª línea."""
    l1, l2 = tema["titulo_linea1"], tema["titulo_linea2_azul"]
    size = 100
    while size > 64:
        f = font("Bold", size)
        if max(c.tw(l1, f), c.tw(l2, f)) <= ANCHO_TEXTO:
            break
        size -= 2
    f = font("Bold", size)
    base1 = y_top + font("Bold", 100).getmetrics()[0] / S
    base2 = base1 + 115
    c.text((MARGEN, base1), l1, f, color1, anchor="ls")
    c.text((MARGEN, base2), l2, f, BLUE, anchor="ls")
    info["titulo_size"] = size
    if max(c.tw(l1, f), c.tw(l2, f)) > ANCHO_TEXTO:
        info["avisos"].append("El título no cabe en el ancho disponible")
    return base2


def subtitulo(c, texto, y, color, info):
    """Una línea si cabe (hasta bajar a 27 px); si no, dos líneas equilibradas. Devuelve el borde inferior."""
    for size in (32, 31, 30, 29, 28, 27):
        f = font("Regular", size)
        if c.tw(texto, f) <= ANCHO_TEXTO:
            c.text((MARGEN, y), texto, f, color)
            info["sub_lineas"] = 1
            return y + size * 1.3
    f = font("Regular", 30)
    lineas = equilibrar(c, partir(c, texto, f, ANCHO_TEXTO), f)
    for i, ln in enumerate(lineas):
        c.text((MARGEN, y + i * 40), ln, f, color)
    info["sub_lineas"] = len(lineas)
    if len(lineas) > 2:
        info["avisos"].append("El subtítulo ocupa más de dos líneas")
    return y + len(lineas) * 40


def puntos(c, items, x, top, bottom, maxw, color, info):
    """Reparte los puntos en el hueco [top, bottom] sin solapes; reduce la letra si hace falta."""
    n = len(items)
    elegido = None
    for check_size, tamanos, hueco_min in ((44, (31, 30, 29, 28, 27, 26), 14), (38, (26, 25), 10)):
        for size in tamanos:
            f = font("Medium", size)
            lineas = [equilibrar(c, partir(c, it, f, maxw), f) for it in items]
            lh = size * 1.25
            alt = [max(check_size, len(ln) * lh) for ln in lineas]
            if sum(alt) + hueco_min * (n - 1) <= bottom - top:
                elegido = (check_size, size, f, lineas, lh, alt)
                break
        if elegido:
            break
    if not elegido:
        info["avisos"].append("Los puntos no caben en su zona")
        size = 25
        f = font("Medium", size)
        lineas = [equilibrar(c, partir(c, it, f, maxw), f) for it in items]
        lh = size * 1.25
        elegido = (38, size, f, lineas, lh, [max(38, len(ln) * lh) for ln in lineas])
    check_size, size, f, lineas, lh, alt = elegido
    hueco = min(42, (bottom - top - sum(alt)) / (n - 1)) if n > 1 else 0
    y = top + (bottom - top - (sum(alt) + hueco * (n - 1))) / 2
    for ln, a in zip(lineas, alt):
        check(c, x, y + (a - check_size) / 2, check_size)
        ty = y + (a - len(ln) * lh) / 2 + 2
        for texto in ln:
            c.text((x + 22 + check_size, ty), texto, f, color)
            ty += lh
        y += a + hueco
    info["puntos_size"] = size
    info["puntos_bottom"] = y - hueco
    return y - hueco


# ---------- Estilo A: claro futurista ----------
def estilo_a(tema, info, asset=None):
    c = Canvas()
    c.gradient((248, 251, 255), (222, 235, 255))
    c.grid((150, 185, 235), 70)
    c.overlay(lambda d: d.polygon([(640 * S, 0), (W * S, 0), (W * S, 360 * S), (880 * S, 360 * S)],
                                  fill=BLUE + (28,)))
    pixels(c, 930, 180, 0.8)
    c.paste(lockup(False), 64, 48)
    chip(c, W - 64, 78, tema["chip"], False)
    titulo(c, tema, 300, INK, info)
    sub_fin = subtitulo(c, tema["subtitulo"], 560, MUTED, info)
    ilustraciones.dibujar(c, tema["id"], (690, 672, 320, 340), False, asset)
    fin = puntos(c, tema["puntos"], 64, 672, 1012, 480, INK, info)
    if sub_fin > 672:
        info["avisos"].append("El subtítulo toca la lista de puntos")
    cta(c, 64, CTA_Y, W - 128, 140, False)
    return c, MUTED


# ---------- Estilo B: oscuro futurista ----------
def estilo_b(tema, info, asset=None):
    c = Canvas((7, 12, 24))
    c.gradient((9, 15, 30), (5, 9, 18))
    c.glow((520, -200, 1300, 560), BLUE, 120, 90)
    c.glow((-300, 900, 500, 1500), BLUE, 70, 90)
    c.grid((30, 64, 120), 80)
    pixels(c, 930, 180, 0.8)
    c.paste(lockup(True), 64, 48)
    chip(c, W - 64, 78, tema["chip"], True)
    titulo(c, tema, 300, (244, 248, 255), info)
    sub_fin = subtitulo(c, tema["subtitulo"], 560, (160, 178, 208), info)
    c.rr((64, 650, 650, 1020), 28, fill=(12, 24, 50), outline=(30, 74, 140), width=2.5)
    ilustraciones.dibujar(c, tema["id"], (688, 672, 330, 330), True, asset)
    puntos(c, tema["puntos"], 100, 684, 986, 440, (236, 243, 255), info)
    if sub_fin > 646:
        info["avisos"].append("El subtítulo toca el panel de puntos")
    cta(c, 64, CTA_Y, W - 128, 140, True)
    return c, (150, 170, 205)


# ---------- Estilo C: mezcla (arriba oscuro, abajo claro) ----------
def estilo_c(tema, info, asset=None):
    c = Canvas()
    c.gradient((248, 251, 255), (226, 238, 255))
    c.grid((150, 185, 235), 60, region=(0, 600, W, H))
    capa = Image.new("RGBA", c.im.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).polygon([(0, 0), (W * S, 0), (W * S, 640 * S), (0, 740 * S)], fill=(8, 14, 28, 255))
    c.im = Image.alpha_composite(c.im, capa)
    c.d = ImageDraw.Draw(c.im)
    c.glow((560, -240, 1300, 480), BLUE, 120, 80)
    c.grid((30, 64, 120), 80, region=(0, 0, W, 640))
    c.overlay(lambda d: d.polygon([(0, 735 * S), (W * S, 635 * S), (W * S, 650 * S), (0, 750 * S)],
                                  fill=BLUE + (255,)))
    pixels(c, 930, 150, 0.8)
    c.paste(lockup(True), 64, 48)
    chip(c, W - 64, 78, tema["chip"], True)
    titulo(c, tema, 290, (244, 248, 255), info)
    sub_fin = subtitulo(c, tema["subtitulo"], 545, (170, 188, 218), info)
    ilustraciones.dibujar(c, tema["id"], (718, 722, 296, 306), False, asset)
    puntos(c, tema["puntos"], 64, 772, 1010, 540, INK, info)
    if sub_fin > 630:
        info["avisos"].append("El subtítulo toca la diagonal")
    cta(c, 64, CTA_Y, W - 128, 140, False)
    return c, MUTED


_ESTILO = {"A": estilo_a, "B": estilo_b, "C": estilo_c}


def renderizar(tema, estilo, asset=None):
    """Devuelve (imagen RGB 1080x1350, info). info['avisos'] lista cualquier problema de maquetación.

    `asset` es un jmtech.assets.Asset; sin él se usa la ilustración dibujada de respaldo.
    """
    if estilo not in _ESTILO:
        raise ValueError(f"Estilo desconocido: {estilo!r} (usa A, B o C)")
    info = {"avisos": [], "tema": tema["id"], "estilo": estilo, "asset": asset.archivo if asset else "dibujo"}
    c, color_pie = _ESTILO[estilo](tema, info, asset)
    c.text((W / 2, 1255), tema.get("pie_imagen", PIE_DEFECTO), font("Medium", 28), color_pie, anchor="mm")
    return c.a_rgb(), info


_SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def guardar_jpeg(img, ruta, calidad=92):
    """JPEG sRGB (es el único formato que acepta la API de Instagram)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(ruta, "JPEG", quality=calidad, optimize=True, subsampling=0, icc_profile=_SRGB)
    return ruta
