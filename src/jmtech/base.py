"""Piezas básicas del dibujo: colores, fuentes, lienzo con supersampling y logo."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]
FUENTES = RAIZ / "assets" / "fonts"
LOGO_CLARO = RAIZ / "assets" / "logo_fondo_claro.png"
LOGO_OSCURO = RAIZ / "assets" / "logo_fondo_oscuro.png"

W, H, S = 1080, 1350, 2
BLUE = (0, 127, 255)
BLUE_DARK = (0, 92, 200)
INK = (16, 22, 36)
MUTED = (84, 98, 122)
WHITE = (255, 255, 255)


@lru_cache(maxsize=None)
def font(weight, size):
    return ImageFont.truetype(str(FUENTES / f"Poppins-{weight}.ttf"), int(round(size * S)))


# ---------- Logo apilado: marca + lema agrandado ----------
def _tight(im):
    caja = Image.fromarray((np.array(im)[..., 3] > 20).astype(np.uint8) * 255).getbbox()
    return im.crop(caja)


def _lockup(img, mw=270, tw=470, gap=16):
    """Separa el lema del logo y lo agranda por su cuenta. Devuelve RGBA a escala S."""
    a = np.array(img)[..., 3] > 20
    filas = a.any(axis=1)
    huecos, ini = [], None
    for i, r in enumerate(filas):
        if not r and ini is None:
            ini = i
        if r and ini is not None:
            huecos.append((ini, i))
            ini = None
    g = huecos[-1]
    main = _tight(img.crop((0, 0, img.width, g[0])))
    tag = _tight(img.crop((0, g[1], img.width, img.height)))
    mh, th = int(main.height * mw / main.width), int(tag.height * tw / tag.width)
    m2 = main.resize((mw * S, mh * S), Image.LANCZOS)
    t2 = tag.resize((tw * S, th * S), Image.LANCZOS)
    out = Image.new("RGBA", (max(mw, tw) * S, (mh + gap + th) * S), (0, 0, 0, 0))
    out.alpha_composite(m2, (((max(mw, tw) - mw) // 2) * S, 0))
    out.alpha_composite(t2, (0, (mh + gap) * S))
    return out


@lru_cache(maxsize=None)
def lockup(oscuro: bool):
    ruta = LOGO_OSCURO if oscuro else LOGO_CLARO
    return _lockup(Image.open(ruta).convert("RGBA"))


# ---------- Lienzo con supersampling ----------
class Canvas:
    def __init__(self, bg=WHITE):
        self.im = Image.new("RGBA", (W * S, H * S), bg + (255,))
        self.d = ImageDraw.Draw(self.im)

    def _sc(self, v):
        return [x * S for x in v]

    def rr(self, box, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle(self._sc(box), r * S, fill=fill, outline=outline, width=int(round(width * S)))

    def rect(self, box, fill):
        self.d.rectangle(self._sc(box), fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def line(self, pts, fill, width):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(round(width * S)), joint="curve")

    def tubo(self, pts, fill, width):
        """Línea con extremos y codos redondeados."""
        self.line(pts, fill, width)
        r = width / 2
        for x, y in pts:
            self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=fill)

    def ellipse(self, box, fill=None, outline=None, width=0):
        self.d.ellipse(self._sc(box), fill=fill, outline=outline, width=int(round(width * S)))

    def arc(self, box, a0, a1, fill, width):
        self.d.arc(self._sc(box), a0, a1, fill=fill, width=int(round(width * S)))

    def text(self, xy, t, f, fill, anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), t, font=f, fill=fill, anchor=anchor)

    def tw(self, t, f):
        return f.getlength(t) / S

    def overlay(self, fn, blur=0):
        capa = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(capa))
        if blur:
            capa = capa.filter(ImageFilter.GaussianBlur(blur * S))
        self.im = Image.alpha_composite(self.im, capa)
        self.d = ImageDraw.Draw(self.im)

    def glow(self, box, color, alpha, blur):
        self.overlay(lambda d: d.ellipse(self._sc(box), fill=color + (alpha,)), blur)

    def grid(self, color, alpha, step=54, region=None):
        x0, y0, x1, y1 = region or (0, 0, W, H)

        def fn(d):
            for x in range(int(x0), int(x1) + 1, step):
                d.line([(x * S, y0 * S), (x * S, y1 * S)], fill=color + (alpha,), width=S)
            for y in range(int(y0), int(y1) + 1, step):
                d.line([(x0 * S, y * S), (x1 * S, y * S)], fill=color + (alpha,), width=S)

        self.overlay(fn)

    def gradient(self, top, bottom, region=None):
        x0, y0, x1, y1 = [int(v * S) for v in (region or (0, 0, W, H))]
        h = y1 - y0
        arr = np.zeros((h, x1 - x0, 4), dtype=np.uint8)
        for i in range(h):
            t = i / max(h - 1, 1)
            arr[i, :, :3] = [int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)]
            arr[i, :, 3] = 255
        self.im.paste(Image.fromarray(arr, "RGBA"), (x0, y0))
        self.d = ImageDraw.Draw(self.im)

    def paste(self, img, x, y):
        self.im.alpha_composite(img, (int(x * S), int(y * S)))
        self.d = ImageDraw.Draw(self.im)

    def a_rgb(self):
        return self.im.resize((W, H), Image.LANCZOS).convert("RGB")


# ---------- Ajuste de texto ----------
def partir(c, texto, f, maxw):
    """Reparte el texto en líneas que no pasen de maxw."""
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if c.tw(prueba, f) <= maxw:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    return lineas


def equilibrar(c, lineas, f):
    """Si hay dos líneas, las iguala para que no quede una palabra suelta."""
    if len(lineas) != 2:
        return lineas
    a, b = lineas[0].split(), lineas[1].split()
    mejor = (max(c.tw(" ".join(a), f), c.tw(" ".join(b), f)), list(a), list(b))
    while len(a) > 1:
        b = [a.pop()] + b
        ancho = max(c.tw(" ".join(a), f), c.tw(" ".join(b), f))
        if ancho < mejor[0]:
            mejor = (ancho, list(a), list(b))
        else:
            break
    return [" ".join(mejor[1]), " ".join(mejor[2])]
