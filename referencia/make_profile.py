"""JM TECH - foto de perfil cuadrada 1080x1080 (monograma centrado, segura para recorte circular)."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1]
S, N = 2, 1080
BLUE = (0, 127, 255)


def mark_only(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)[..., 3] > 20
    rows = a.any(axis=1)
    first_gap_start = next(i for i, r in enumerate(rows) if not r and i > 50)
    m = im.crop((0, 0, im.width, first_gap_start))
    box = Image.fromarray((np.array(m)[..., 3] > 20).astype(np.uint8) * 255).getbbox()
    return m.crop(box)


def grid(size, color, alpha, step=54):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, size[0] + 1, step * S):
        d.line([(x, 0), (x, size[1])], fill=color + (alpha,), width=S)
    for y in range(0, size[1] + 1, step * S):
        d.line([(0, y), (size[0], y)], fill=color + (alpha,), width=S)
    return layer


def build(dark, logo_path, name):
    size = (N * S, N * S)
    if dark:
        base = Image.new("RGBA", size, (7, 12, 24, 255))
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((150 * S, 200 * S, 930 * S, 880 * S), fill=BLUE + (120,))
        base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(110 * S)))
        base = Image.alpha_composite(base, grid(size, (30, 64, 120), 80))
    else:
        arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
        t = np.linspace(0, 1, size[1])[:, None]
        top, bot = np.array([248, 251, 255]), np.array([222, 235, 255])
        arr[..., :3] = (top + (bot - top) * t[..., None]).astype(np.uint8)
        arr[..., 3] = 255
        base = Image.fromarray(arr, "RGBA")
        base = Image.alpha_composite(base, grid(size, (150, 185, 235), 70))
    mk = mark_only(logo_path)
    w = 680
    h = int(mk.height * w / mk.width)
    mk = mk.resize((w * S, h * S), Image.LANCZOS)
    base.alpha_composite(mk, ((size[0] - mk.width) // 2, (size[1] - mk.height) // 2))
    out = base.resize((N, N), Image.LANCZOS).convert("RGB")
    out.save(f"{OUT}/foto_perfil_{name}.png", optimize=True)
    # vista previa tal como la recorta Instagram (círculo pequeño)
    prev = out.resize((220, 220), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (220 * 4, 220 * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 220 * 4 - 1, 220 * 4 - 1), fill=255)
    prev.putalpha(mask.resize((220, 220), Image.LANCZOS))
    return prev


if __name__ == "__main__":
    pl = build(False, "/home/claude/jmtech/out/logo_fondo_claro.png", "claro")
    pd = build(True, "/home/claude/jmtech/out/logo_fondo_oscuro.png", "oscuro")
    sheet = Image.new("RGBA", (500, 260), (255, 255, 255, 255))
    sheet.alpha_composite(pl, (15, 20))
    sheet.alpha_composite(pd, (265, 20))
    sheet.convert("RGB").save(OUT + "/_vista_previa_circulo.png")
    print("ok")
