"""JM TECH - foto de perfil con monograma + lema en dos líneas (1080x1080, segura para círculo)."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1]
S, N = 2, 1080
BLUE = (0, 127, 255)


def tight(im):
    b = Image.fromarray((np.array(im)[..., 3] > 20).astype(np.uint8) * 255).getbbox()
    return im.crop(b)


def parts(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)[..., 3] > 20
    rows = a.any(axis=1)
    gaps, st = [], None
    for i, r in enumerate(rows):
        if not r and st is None:
            st = i
        if r and st is not None:
            gaps.append((st, i))
            st = None
    mark = tight(im.crop((0, 0, im.width, gaps[0][0])))
    tag = tight(im.crop((0, gaps[-1][1], im.width, im.height)))
    # dividir el lema en dos líneas tras la tercera palabra ("... técnico y | soluciones ...")
    cols = np.array(tag)[..., 3].max(axis=0) > 20
    runs, st = [], None
    for i, c in enumerate(cols):
        if not c and st is None:
            st = i
        if c and st is not None:
            runs.append((st, i))
            st = None
    wide = [r for r in runs if r[1] - r[0] >= 8]  # espacios entre palabras
    cut = wide[2]
    l1 = tight(tag.crop((0, 0, cut[0], tag.height)))
    l2 = tight(tag.crop((cut[1], 0, tag.width, tag.height)))
    return mark, l1, l2


def grid(size, color, alpha, step=54):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, size[0] + 1, step * S):
        d.line([(x, 0), (x, size[1])], fill=color + (alpha,), width=S)
    for y in range(0, size[1] + 1, step * S):
        d.line([(0, y), (size[0], y)], fill=color + (alpha,), width=S)
    return layer


def background(dark):
    size = (N * S, N * S)
    if dark:
        base = Image.new("RGBA", size, (7, 12, 24, 255))
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((150 * S, 160 * S, 930 * S, 820 * S), fill=BLUE + (110,))
        base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(110 * S)))
        return Image.alpha_composite(base, grid(size, (30, 64, 120), 80))
    arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    t = np.linspace(0, 1, size[1])[:, None]
    top, bot = np.array([248, 251, 255]), np.array([222, 235, 255])
    arr[..., :3] = (top + (bot - top) * t[..., None]).astype(np.uint8)
    arr[..., 3] = 255
    return Image.alpha_composite(Image.fromarray(arr, "RGBA"), grid(size, (150, 185, 235), 70))


def build(dark, logo_path, name):
    base = background(dark)
    mark, l1, l2 = parts(logo_path)
    mw = 600
    mh = int(mark.height * mw / mark.width)
    f = mw / l2.width  # misma escala para las dos líneas (la 2.ª ocupa todo el ancho)
    l1s = l1.resize((int(l1.width * f * S), int(l1.height * f * S)), Image.LANCZOS)
    l2s = l2.resize((int(l2.width * f * S), int(l2.height * f * S)), Image.LANCZOS)
    mk = mark.resize((mw * S, mh * S), Image.LANCZOS)
    gap1, gap2 = 46 * S, 18 * S
    total = mk.height + gap1 + l1s.height + gap2 + l2s.height
    y = (N * S - total) // 2
    for im, g in ((mk, gap1), (l1s, gap2), (l2s, 0)):
        base.alpha_composite(im, ((N * S - im.width) // 2, y))
        y += im.height + g
    out = base.resize((N, N), Image.LANCZOS).convert("RGB")
    out.save(f"{OUT}/foto_perfil_lema_{name}.png", optimize=True)
    return out


def circle(img, px):
    prev = img.resize((px, px), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (px * 4, px * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, px * 4 - 1, px * 4 - 1), fill=255)
    prev.putalpha(mask.resize((px, px), Image.LANCZOS))
    return prev


if __name__ == "__main__":
    a = build(False, "/home/claude/jmtech/out/logo_fondo_claro.png", "claro")
    b = build(True, "/home/claude/jmtech/out/logo_fondo_oscuro.png", "oscuro")
    sheet = Image.new("RGBA", (760, 340), (255, 255, 255, 255))
    sheet.alpha_composite(circle(a, 300), (15, 20))
    sheet.alpha_composite(circle(b, 300), (335, 20))
    sheet.alpha_composite(circle(b, 110), (650, 20))   # tamaño real aproximado en el perfil
    sheet.alpha_composite(circle(a, 110), (650, 150))
    sheet.convert("RGB").save(OUT + "/_vista_previa_lema.png")
    print("ok")
