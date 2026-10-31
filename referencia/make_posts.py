"""JM TECH - Fase 2: imágenes de prueba (3 estilos) para Instagram 1080x1350."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

LOGO_SRC = sys.argv[1]
OUT_DIR = sys.argv[2]

W, H, S = 1080, 1350, 2
BLUE = (0, 127, 255)
BLUE_DARK = (0, 92, 200)
INK = (16, 22, 36)
MUTED = (84, 98, 122)
WHITE = (255, 255, 255)
FP = "/usr/share/fonts/truetype/google-fonts/Poppins-"


def font(weight, size):
    return ImageFont.truetype(FP + weight + ".ttf", int(size * S))


# ---------- Logo: quitar fondo blanco y crear versión para fondo oscuro ----------
def build_logos(path):
    rgb = np.array(Image.open(path).convert("RGB")).astype(float)
    mn = rgb.min(axis=2)
    a = np.clip((255 - mn - 14) / 241.0, 0, 1)
    safe = np.where(a > 0.02, a, 1)[..., None]
    fg = np.clip((rgb - 255 * (1 - a[..., None])) / safe, 0, 255)
    ys, xs = np.where(a > 0.06)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)

    def make(dark):
        col = fg.copy()
        if dark:
            neutral = (col[..., 2] - col[..., 0]) < 70
            col[neutral] = (244, 248, 255)
        out = np.dstack([col, (a * 255)]).astype(np.uint8)
        return Image.fromarray(out, "RGBA").crop(box)

    return make(False), make(True)


LOGO_LIGHT, LOGO_DARK = build_logos(LOGO_SRC)


# ---------- Logo apilado: marca + lema agrandado ----------
def _tight(im):
    b = Image.fromarray((np.array(im)[..., 3] > 20).astype(np.uint8) * 255).getbbox()
    return im.crop(b)


def make_lockup(img, mw=270, tw=470, gap=16):
    """Separa el lema del logo y lo agranda por su cuenta. Devuelve imagen RGBA a escala S."""
    a = np.array(img)[..., 3] > 20
    rows = a.any(axis=1)
    gaps, st = [], None
    for i, r in enumerate(rows):
        if not r and st is None:
            st = i
        if r and st is not None:
            gaps.append((st, i))
            st = None
    g = gaps[-1]
    main = _tight(img.crop((0, 0, img.width, g[0])))
    tag = _tight(img.crop((0, g[1], img.width, img.height)))
    mh, th = int(main.height * mw / main.width), int(tag.height * tw / tag.width)
    m2 = main.resize((mw * S, mh * S), Image.LANCZOS)
    t2 = tag.resize((tw * S, th * S), Image.LANCZOS)
    out = Image.new("RGBA", (max(mw, tw) * S, (mh + gap + th) * S), (0, 0, 0, 0))
    out.alpha_composite(m2, (((max(mw, tw) - mw) // 2) * S, 0))
    out.alpha_composite(t2, (0, (mh + gap) * S))
    return out


LK_LIGHT = make_lockup(LOGO_LIGHT)
LK_DARK = make_lockup(LOGO_DARK)


# ---------- Lienzo con supersampling ----------
class Canvas:
    def __init__(self, bg=WHITE):
        self.im = Image.new("RGBA", (W * S, H * S), bg + (255,))
        self.d = ImageDraw.Draw(self.im)

    def _sc(self, v):
        return [x * S for x in v]

    def rr(self, box, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle(self._sc(box), r * S, fill=fill, outline=outline, width=int(width * S))

    def poly(self, pts, fill):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def line(self, pts, fill, width):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(width * S), joint="curve")

    def ellipse(self, box, fill):
        self.d.ellipse(self._sc(box), fill=fill)

    def text(self, xy, t, f, fill, anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), t, font=f, fill=fill, anchor=anchor)

    def tw(self, t, f):
        return f.getlength(t) / S

    def overlay(self, fn, blur=0):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer))
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur * S))
        self.im = Image.alpha_composite(self.im, layer)
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

    def logo(self, img, x, y, w):
        h = int(img.height * (w / img.width))
        small = img.resize((int(w * S), int(h * S)), Image.LANCZOS)
        self.im.alpha_composite(small, (int(x * S), int(y * S)))
        self.d = ImageDraw.Draw(self.im)
        return h

    def paste(self, img, x, y):
        self.im.alpha_composite(img, (int(x * S), int(y * S)))
        self.d = ImageDraw.Draw(self.im)

    def save(self, path):
        self.im.resize((W, H), Image.LANCZOS).convert("RGB").save(path, optimize=True)


def wrap(c, t, f, maxw):
    words, lines, cur = t.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.tw(test, f) <= maxw:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


# ---------- Elementos de diseño ----------
def pixels(c, x, y, k, color=BLUE):
    """Tres cuadraditos como los del logo."""
    c.d.rectangle([(x + 54 * k) * S, y * S, (x + 102 * k) * S, (y + 48 * k) * S], fill=color)
    c.d.rectangle([x * S, (y + 42 * k) * S, (x + 46 * k) * S, (y + 88 * k) * S], fill=color)
    c.d.rectangle([(x + 53 * k) * S, (y + 87 * k) * S, (x + 86 * k) * S, (y + 120 * k) * S], fill=color)


def check(c, x, y, size=44):
    c.rr((x, y, x + size, y + size), 12, fill=BLUE)
    k = size / 44
    c.line([(x + 11 * k, y + 23 * k), (x + 19 * k, y + 31 * k), (x + 33 * k, y + 14 * k)], WHITE, 5.5 * k)


def bullets(c, x, y, items, step, size, color, maxw):
    f = font("Medium", size)
    for it in items:
        check(c, x, y)
        lines = wrap(c, it, f, maxw)
        ty = y + 22 - (len(lines) * size * 1.25) / 2 + 2
        for ln in lines:
            c.text((x + 66, ty), ln, f, color)
            ty += size * 1.25
        y += step
    return y


def monitor(c, x, y, w, dark_theme):
    h = w * 0.62
    frame = (24, 40, 74) if dark_theme else (22, 24, 30)
    if dark_theme:
        c.glow((x - 40, y - 30, x + w + 40, y + h + 60), BLUE, 90, 40)
    c.rr((x, y, x + w, y + h), 26, fill=frame, outline=BLUE if dark_theme else None, width=3 if dark_theme else 0)
    ins = 14
    sx0, sy0, sx1, sy1 = x + ins, y + ins, x + w - ins, y + h - ins
    c.rr((sx0, sy0, sx1, sy1), 14, fill=(8, 18, 42))
    c.glow((sx0 + 10, sy0 + 10, sx1 - 10, sy1 - 10), BLUE, 70, 28)
    # botón play
    cx, cy, r = x + w / 2, y + h / 2 - 6, w * 0.115
    c.ellipse((cx - r, cy - r, cx + r, cy + r), BLUE)
    c.poly([(cx - r * 0.3, cy - r * 0.5), (cx - r * 0.3, cy + r * 0.5), (cx + r * 0.55, cy)], WHITE)
    # chip LIVE
    f = font("Bold", w * 0.045)
    c.rr((sx0 + 14, sy0 + 14, sx0 + 14 + w * 0.2, sy0 + 14 + w * 0.075), w * 0.037, fill=BLUE)
    c.text((sx0 + 14 + w * 0.1, sy0 + 14 + w * 0.0375), "LIVE", f, WHITE, anchor="mm")
    # barras tipo ecualizador
    bx = sx0 + 16
    for i, bh in enumerate([0.05, 0.09, 0.06, 0.11, 0.07, 0.04, 0.08]):
        c.d.rectangle([bx * S, (sy1 - 14 - w * bh) * S, (bx + 9) * S, (sy1 - 14) * S], fill=BLUE)
        bx += 16
    # soporte
    c.poly([(x + w / 2 - w * 0.06, y + h), (x + w / 2 + w * 0.06, y + h),
            (x + w / 2 + w * 0.10, y + h + w * 0.11), (x + w / 2 - w * 0.10, y + h + w * 0.11)], frame)
    c.rr((x + w / 2 - w * 0.22, y + h + w * 0.105, x + w / 2 + w * 0.22, y + h + w * 0.14), 10, fill=frame)


def cta(c, x, y, w, h, dark_theme):
    if dark_theme:
        c.glow((x, y, x + w, y + h), BLUE, 110, 30)
    c.rr((x, y, x + w, y + h), 26, fill=BLUE)
    c.text((x + 40, y + h * 0.36), "¿Quieres presupuesto?", font("Bold", 40), WHITE, anchor="lm")
    c.text((x + 40, y + h * 0.70), "Escríbenos por MD", font("Medium", 32), (222, 238, 255), anchor="lm")
    # flecha
    r = 38
    ax, ay = x + w - 40 - r, y + h / 2
    c.ellipse((ax - r, ay - r, ax + r, ay + r), WHITE)
    c.line([(ax - 16, ay), (ax + 14, ay)], BLUE, 6)
    c.line([(ax + 2, ay - 13), (ax + 15, ay), (ax + 2, ay + 13)], BLUE, 6)


def chip(c, x_right, y, text, dark_theme):
    f = font("Medium", 24)
    tw = c.tw(text, f)
    box = (x_right - tw - 48, y, x_right, y + 48)
    c.rr(box, 24, outline=BLUE, width=2.5, fill=(8, 20, 48) if dark_theme else (232, 242, 255))
    c.text((box[0] + 24, y + 24), text, f, BLUE if not dark_theme else (120, 185, 255), anchor="lm")


ITEMS = ["Montaje de tu PC", "Instalación de drivers", "Plataformas de gaming y streaming", "Configuración de OBS"]
SUB = "Pack completo: lo dejamos todo listo para tu primer directo."
FOOT = "Murcia  ·  A domicilio o en nuestro taller"


# ---------- Estilo A: claro futurista ----------
def style_a(path):
    c = Canvas()
    c.gradient((248, 251, 255), (222, 235, 255))
    c.grid((150, 185, 235), 70)
    c.overlay(lambda d: d.polygon([(640 * S, 0), (W * S, 0), (W * S, 360 * S), (880 * S, 360 * S)], fill=BLUE + (28,)))
    pixels(c, 930, 180, 0.8)
    c.paste(LK_LIGHT, 64, 48)
    chip(c, W - 64, 78, "STREAMING", False)
    f = font("Bold", 100)
    c.text((64, 300), "Empieza a hacer", f, INK)
    c.text((64, 415), "streaming", f, BLUE)
    c.text((64, 560), SUB, font("Regular", 32), MUTED)
    bullets(c, 64, 680, ITEMS, 86, 31, INK, 380)
    monitor(c, 690, 700, 320, False)
    cta(c, 64, 1045, W - 128, 140, False)
    c.text((W / 2, 1255), FOOT, font("Medium", 28), MUTED, anchor="mm")
    c.save(path)


# ---------- Estilo B: oscuro futurista ----------
def style_b(path):
    c = Canvas((7, 12, 24))
    c.gradient((9, 15, 30), (5, 9, 18))
    c.glow((520, -200, 1300, 560), BLUE, 120, 90)
    c.glow((-300, 900, 500, 1500), BLUE, 70, 90)
    c.grid((30, 64, 120), 80)
    pixels(c, 930, 180, 0.8)
    c.paste(LK_DARK, 64, 48)
    chip(c, W - 64, 78, "STREAMING", True)
    f = font("Bold", 100)
    c.text((64, 300), "Empieza a hacer", f, (244, 248, 255))
    c.text((64, 415), "streaming", f, BLUE)
    c.text((64, 560), SUB, font("Regular", 32), (160, 178, 208))
    c.rr((64, 650, 650, 1020), 28, fill=(12, 24, 50), outline=(30, 74, 140), width=2.5)
    bullets(c, 100, 688, ITEMS, 84, 31, (236, 243, 255), 390)
    monitor(c, 700, 720, 310, True)
    cta(c, 64, 1045, W - 128, 140, True)
    c.text((W / 2, 1255), FOOT, font("Medium", 28), (150, 170, 205), anchor="mm")
    c.save(path)


# ---------- Estilo C: mezcla (arriba oscuro, abajo claro) ----------
def style_c(path):
    c = Canvas()
    c.gradient((248, 251, 255), (226, 238, 255))
    c.grid((150, 185, 235), 60, region=(0, 600, W, H))
    # bloque oscuro superior con diagonal
    top = Image.new("RGBA", c.im.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    td.polygon([(0, 0), (W * S, 0), (W * S, 640 * S), (0, 740 * S)], fill=(8, 14, 28, 255))
    c.im = Image.alpha_composite(c.im, top)
    c.d = ImageDraw.Draw(c.im)
    c.glow((560, -240, 1300, 480), BLUE, 120, 80)
    c.grid((30, 64, 120), 80, region=(0, 0, W, 640))
    c.overlay(lambda d: d.polygon([(0, 735 * S), (W * S, 635 * S), (W * S, 650 * S), (0, 750 * S)], fill=BLUE + (255,)))
    pixels(c, 930, 150, 0.8)
    c.paste(LK_DARK, 64, 48)
    chip(c, W - 64, 78, "STREAMING", True)
    f = font("Bold", 100)
    c.text((64, 290), "Empieza a hacer", f, (244, 248, 255))
    c.text((64, 405), "streaming", f, BLUE)
    c.text((64, 545), SUB, font("Regular", 32), (170, 188, 218))
    bullets(c, 64, 775, ITEMS, 68, 31, INK, 560)
    monitor(c, 722, 690, 290, False)
    cta(c, 64, 1045, W - 128, 140, False)
    c.text((W / 2, 1255), FOOT, font("Medium", 28), MUTED, anchor="mm")
    c.save(path)


if __name__ == "__main__":
    style_a(OUT_DIR + "/prueba_A_claro.png")
    style_b(OUT_DIR + "/prueba_B_oscuro.png")
    style_c(OUT_DIR + "/prueba_C_mixto.png")
    # logos recortados para reutilizar
    LOGO_LIGHT.save(OUT_DIR + "/logo_fondo_claro.png")
    LOGO_DARK.save(OUT_DIR + "/logo_fondo_oscuro.png")
    print("ok")
