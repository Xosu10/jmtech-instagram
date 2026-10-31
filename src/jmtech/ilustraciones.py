"""Las 11 ilustraciones planas (sin marcas ni texto), dibujadas con Pillow.

Cada una se dibuja en una caja local de 320x300 y se escala al hueco que le da el estilo.
"""
from __future__ import annotations

import math

from .base import BLUE, BLUE_DARK, WHITE, font

SCREEN = (8, 18, 42)
LUZ = (110, 185, 255)


def paleta(dark):
    if dark:
        return dict(frame=(24, 40, 74), panel=(34, 60, 112), screen=SCREEN, edge=BLUE, soft=(58, 96, 164),
                    soft2=(38, 68, 128), ring=BLUE, tubo=LUZ, tinta=(236, 243, 255), sofa=(30, 76, 160))
    return dict(frame=(22, 24, 30), panel=(46, 52, 64), screen=SCREEN, edge=None, soft=(255, 255, 255),
                soft2=(208, 221, 242), ring=(150, 182, 230), tubo=(60, 170, 255), tinta=(22, 24, 30),
                sofa=BLUE_DARK)


class Local:
    """Dibuja en coordenadas 0..320 x 0..300 y lo traslada/escala al lienzo."""

    def __init__(self, c, ox, oy, k, dark):
        self.c, self.ox, self.oy, self.k, self.dark = c, ox, oy, k, dark

    def _p(self, x, y):
        return (self.ox + x * self.k, self.oy + y * self.k)

    def _b(self, box):
        x0, y0, x1, y1 = box
        return (*self._p(x0, y0), *self._p(x1, y1))

    def rr(self, box, r, fill=None, outline=None, width=0):
        self.c.rr(self._b(box), r * self.k, fill, outline, width * self.k)

    def rect(self, box, fill):
        self.c.rect(self._b(box), fill)

    def poly(self, pts, fill):
        self.c.poly([self._p(*p) for p in pts], fill)

    def line(self, pts, fill, width):
        self.c.line([self._p(*p) for p in pts], fill, width * self.k)

    def tubo(self, pts, fill, width):
        self.c.tubo([self._p(*p) for p in pts], fill, width * self.k)

    def ellipse(self, box, fill=None, outline=None, width=0):
        self.c.ellipse(self._b(box), fill, outline, width * self.k)

    def circ(self, cx, cy, r, fill=None, outline=None, width=0):
        self.ellipse((cx - r, cy - r, cx + r, cy + r), fill, outline, width)

    def arc(self, box, a0, a1, fill, width):
        self.c.arc(self._b(box), a0, a1, fill, width * self.k)

    def glow(self, box, color, alpha, blur):
        self.c.glow(self._b(box), color, alpha, blur * self.k)


# ---------- Piezas reutilizables ----------
def aura(L):
    """Resplandor azul en el tema oscuro; sombra suave en el claro."""
    if L.dark:
        L.glow((0, 0, 320, 300), BLUE, 55, 40)
    else:
        L.glow((40, 276, 280, 298), (16, 30, 70), 60, 8)


def cuerpo(L, p, box, r):
    L.rr(box, r, fill=p["frame"], outline=p["edge"], width=3 if p["edge"] else 0)


def union(L, p, formas):
    """Varias formas del mismo cuerpo con un solo contorno (borde azul en el tema oscuro)."""
    def trazar(grow, color):
        for f in formas:
            x0, y0, x1, y1 = f[1]
            box = (x0 - grow, y0 - grow, x1 + grow, y1 + grow)
            if f[0] == "e":
                L.ellipse(box, fill=color)
            else:
                L.rr(box, f[2] + grow, fill=color)

    if p["edge"]:
        trazar(3, p["edge"])
    trazar(0, p["frame"])


def estrella(L, cx, cy, r, color):
    q = 0.24
    L.poly([(cx, cy - r), (cx + r * q, cy - r * q), (cx + r, cy), (cx + r * q, cy + r * q), (cx, cy + r),
            (cx - r * q, cy + r * q), (cx - r, cy), (cx - r * q, cy - r * q)], color)


def engranaje(L, cx, cy, r_ext, r_int, dientes, color, centro, rot=0.0):
    pts = []
    for i in range(dientes):
        a = rot + 2 * math.pi * i / dientes
        paso = math.pi / dientes
        for da, r in ((-0.62, r_int), (-0.34, r_ext), (0.34, r_ext), (0.62, r_int)):
            ang = a + da * paso * 1.6
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    L.poly(pts, color)
    L.circ(cx, cy, r_int + 1, fill=color)
    L.circ(cx, cy, r_int * 0.42, fill=centro)


def ventilador(L, p, cx, cy, r):
    L.circ(cx, cy, r, fill=(10, 22, 52), outline=BLUE, width=2.5)
    for i in range(7):
        a = 2 * math.pi * i / 7
        L.line([(cx + r * 0.2 * math.cos(a), cy + r * 0.2 * math.sin(a)),
                (cx + r * 0.78 * math.cos(a + 0.55), cy + r * 0.78 * math.sin(a + 0.55))], LUZ, r * 0.2)
    L.circ(cx, cy, r * 0.2, fill=BLUE)


def flecha_arco(L, cx, cy, r, a0, a1, color, ancho):
    """Arco con punta de flecha al final (sentido de las agujas del reloj)."""
    L.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, color, ancho)
    a = math.radians(a1)
    px, py = cx + r * math.cos(a), cy + r * math.sin(a)
    tx, ty = -math.sin(a), math.cos(a)
    nx, ny = math.cos(a), math.sin(a)
    hl, hw = ancho * 2.1, ancho * 1.7
    L.poly([(px + tx * hl, py + ty * hl), (px + nx * hw, py + ny * hw), (px - nx * hw, py - ny * hw)], color)


def portatil(L, p, pantalla):
    cuerpo(L, p, (50, 34, 270, 196), 16)
    L.rr((62, 46, 258, 184), 8, fill=SCREEN)
    L.glow((70, 54, 250, 176), BLUE, 60, 18)
    pantalla()
    cuerpo(L, p, (18, 196, 302, 224), 10)
    L.rr((130, 196, 190, 205), 4, fill=p["panel"])


# ---------- 1. streaming (monitor aprobado) ----------
def _monitor(c, x, y, w, dark):
    h = w * 0.62
    frame = (24, 40, 74) if dark else (22, 24, 30)
    if dark:
        c.glow((x - 40, y - 30, x + w + 40, y + h + 60), BLUE, 90, 40)
    c.rr((x, y, x + w, y + h), 26, fill=frame, outline=BLUE if dark else None, width=3 if dark else 0)
    ins = 14
    sx0, sy0, sx1, sy1 = x + ins, y + ins, x + w - ins, y + h - ins
    c.rr((sx0, sy0, sx1, sy1), 14, fill=SCREEN)
    c.glow((sx0 + 10, sy0 + 10, sx1 - 10, sy1 - 10), BLUE, 70, 28)
    cx, cy, r = x + w / 2, y + h / 2 - 6, w * 0.115
    c.ellipse((cx - r, cy - r, cx + r, cy + r), BLUE)
    c.poly([(cx - r * 0.3, cy - r * 0.5), (cx - r * 0.3, cy + r * 0.5), (cx + r * 0.55, cy)], WHITE)
    f = font("Bold", w * 0.045)
    c.rr((sx0 + 14, sy0 + 14, sx0 + 14 + w * 0.2, sy0 + 14 + w * 0.075), w * 0.037, fill=BLUE)
    c.text((sx0 + 14 + w * 0.1, sy0 + 14 + w * 0.0375), "LIVE", f, WHITE, anchor="mm")
    bx = sx0 + 16
    for bh in [0.05, 0.09, 0.06, 0.11, 0.07, 0.04, 0.08]:
        c.rect((bx, sy1 - 14 - w * bh, bx + 9, sy1 - 14), BLUE)
        bx += 16
    c.poly([(x + w / 2 - w * 0.06, y + h), (x + w / 2 + w * 0.06, y + h),
            (x + w / 2 + w * 0.10, y + h + w * 0.11), (x + w / 2 - w * 0.10, y + h + w * 0.11)], frame)
    c.rr((x + w / 2 - w * 0.22, y + h + w * 0.105, x + w / 2 + w * 0.22, y + h + w * 0.14), 10, fill=frame)


def ilu_streaming(c, slot, dark):
    x, y, w, h = slot
    w = min(w, h / 0.76)
    _monitor(c, x + (slot[2] - w) / 2, y + (h - 0.76 * w) / 2, w, dark)


# ---------- 2 y 3. torre de PC (normal y con custom loop) ----------
def _torre(L, p, loop):
    cuerpo(L, p, (62, 8, 258, 286), 22)
    L.rr((86, 286, 120, 296), 4, fill=p["panel"])
    L.rr((200, 286, 234, 296), 4, fill=p["panel"])
    L.rr((76, 22, 244, 262), 14, fill=(14, 32, 72), outline=(40, 96, 180), width=2)   # panel de cristal
    L.glow((84, 34, 236, 250), BLUE, 60, 26)
    L.rr((124, 34, 236, 146), 8, fill=(22, 46, 100), outline=(44, 100, 190), width=1.5)  # placa base
    for y in (64, 112, 160):                                                           # ventiladores frontales
        ventilador(L, p, 100, y, 17)
    L.rr((76, 232, 244, 262), 10, fill=(10, 18, 36))                                   # fuente de alimentación
    L.rect((88, 244, 232, 248), BLUE)
    if not loop:
        ventilador(L, p, 160, 86, 26)                                                  # disipador
        for i in range(3):                                                             # memoria RAM
            L.rr((196 + i * 11, 50, 203 + i * 11, 114), 2, fill=LUZ)
    else:
        L.rr((146, 62, 176, 92), 6, fill=LUZ, outline=WHITE, width=1.5)                # bloque de agua CPU
        L.rr((206, 40, 226, 134), 10, fill=(10, 30, 70), outline=LUZ, width=2.5)       # depósito
        L.rr((210, 78, 222, 130), 6, fill=BLUE)
        for i in range(2):
            L.rr((186 + i * 8, 52, 190 + i * 8, 112), 2, fill=LUZ)
        L.tubo([(161, 62), (161, 44), (216, 44)], p["tubo"], 8)
        L.tubo([(161, 92), (161, 124), (140, 124), (140, 152)], p["tubo"], 8)
        L.tubo([(216, 134), (216, 152)], p["tubo"], 8)
    L.rr((126, 152, 236, 204), 8, fill=p["panel"], outline=BLUE, width=2)             # tarjeta gráfica
    if loop:
        L.rr((128, 154, 234, 168), 6, fill=LUZ)
    ventilador(L, p, 156, 180, 18)
    ventilador(L, p, 208, 180, 18)


def ilu_montaje_pc(L, p):
    _torre(L, p, loop=False)


def ilu_custom_loop(L, p):
    _torre(L, p, loop=True)
    estrella(L, 38, 60, 16, LUZ if L.dark else BLUE)
    estrella(L, 290, 232, 12, LUZ if L.dark else BLUE)


# ---------- 4. consola + mando genéricos con destellos ----------
def ilu_consola(L, p):
    cuerpo(L, p, (24, 46, 296, 134), 28)
    L.rr((52, 94, 196, 102), 4, fill=p["panel"])
    L.circ(50, 72, 6, fill=BLUE)
    for i in range(6):
        L.rr((228 + i * 9, 66, 232 + i * 9, 116), 2, fill=p["panel"])
    union(L, p, [("r", (92, 168, 228, 238), 30), ("e", (56, 176, 136, 276)), ("e", (184, 176, 264, 276))])
    L.circ(116, 196, 15, fill=p["panel"])                                   # palanca izquierda
    L.circ(116, 196, 9, fill=p["soft2"] if L.dark else (120, 134, 160))
    L.rect((110, 226, 134, 234), p["panel"])                                # cruceta
    L.rect((118, 218, 126, 242), p["panel"])
    for dx, dy in ((0, -15), (0, 15), (-15, 0), (15, 0)):                   # botones
        L.circ(204 + dx, 198 + dy, 6.5, fill=BLUE if dx + dy > 0 else p["panel"])
    L.circ(176, 232, 13, fill=p["panel"])                                   # palanca derecha
    estrella(L, 30, 24, 14, LUZ if L.dark else BLUE)
    estrella(L, 292, 20, 18, LUZ if L.dark else BLUE)
    estrella(L, 300, 156, 11, LUZ if L.dark else BLUE)


# ---------- 5. SSD genérico + barra de almacenamiento ----------
def ilu_ssd(L, p):
    cuerpo(L, p, (36, 52, 270, 196), 22)
    L.rr((52, 68, 214, 180), 12, fill=p["panel"])
    for i in range(3):
        L.rr((68 + i * 42, 84, 98 + i * 42, 114), 5, fill=BLUE)
    L.rr((68, 130, 196, 138), 4, fill=p["soft2"] if L.dark else (120, 134, 160))
    L.rr((68, 150, 150, 158), 4, fill=p["soft2"] if L.dark else (120, 134, 160))
    L.rr((270, 90, 298, 160), 6, fill=p["soft2"] if L.dark else (120, 134, 160))
    for i in range(5):
        L.rect((276, 98 + i * 12, 292, 102 + i * 12), p["frame"])
    L.rr((36, 222, 298, 254), 16, fill=p["soft"], outline=p["ring"], width=2)
    L.rr((40, 226, 218, 250), 12, fill=BLUE)
    estrella(L, 292, 36, 15, LUZ if L.dark else BLUE)
    estrella(L, 28, 24, 11, LUZ if L.dark else BLUE)


# ---------- 6. disco duro abierto + flecha de recuperación + archivos ----------
def ilu_datos(L, p):
    cuerpo(L, p, (14, 40, 232, 268), 20)
    L.circ(118, 150, 84, fill=p["soft"] if not L.dark else (70, 112, 186))
    L.circ(118, 150, 84, outline=p["ring"], width=3)
    L.circ(118, 150, 52, outline=p["ring"], width=2)
    L.circ(118, 150, 26, fill=(120, 136, 164) if not L.dark else (36, 62, 118))
    L.circ(118, 150, 9, fill=p["frame"])
    L.line([(206, 244), (150, 178)], p["panel"], 12)                         # brazo del cabezal
    L.circ(206, 244, 10, fill=p["panel"])
    L.circ(148, 176, 6, fill=BLUE)
    for i, (x, y) in enumerate(((236, 28), (270, 56))):                      # archivos que vuelven
        L.rr((x, y, x + 44, y + 58), 6, fill=WHITE, outline=BLUE, width=2.5)
        L.poly([(x + 30, y), (x + 44, y + 14), (x + 30, y + 14)], (190, 215, 250))
        L.rr((x + 8, y + 26, x + 36, y + 31), 2, fill=BLUE)
        L.rr((x + 8, y + 38, x + 28, y + 43), 2, fill=(150, 180, 225))
    L.circ(258, 208, 48, fill=BLUE)
    flecha_arco(L, 258, 208, 24, 40, 330, WHITE, 8)


# ---------- 7. portátil + lupa + verificación + engranaje ----------
def ilu_diagnostico(L, p):
    def pantalla():
        L.line([(78, 150), (110, 150), (124, 116), (146, 164), (162, 100), (182, 150), (240, 150)], BLUE, 5)
        for i, h in enumerate((18, 30, 22)):
            L.rect((80 + i * 12, 78 - h + 18, 86 + i * 12, 96), LUZ)

    portatil(L, p, pantalla)
    engranaje(L, 288, 34, 24, 17, 8, BLUE, p["soft"] if not L.dark else p["frame"])
    L.glow((176, 118, 276, 218), WHITE, 70, 0)
    L.circ(226, 168, 50, outline=BLUE, width=13)
    L.line([(262, 204), (296, 244)], p["frame"], 16)
    L.circ(296, 244, 8, fill=p["frame"])
    L.line([(204, 170), (221, 187), (250, 150)], BLUE, 10)


# ---------- 8. televisor en pared con soporte y sofá ----------
def ilu_tv(L, p):
    L.rr((0, 10, 320, 290), 26, fill=p["soft"] if not L.dark else p["soft2"], outline=p["ring"], width=2.5)
    cuerpo(L, p, (34, 34, 286, 172), 10)
    L.rr((42, 42, 278, 164), 6, fill=SCREEN)
    L.glow((56, 50, 264, 160), BLUE, 70, 22)
    L.poly([(42, 164), (112, 112), (160, 146), (206, 100), (278, 164)], (0, 92, 200))
    L.poly([(42, 164), (92, 130), (140, 164)], BLUE)
    L.circ(232, 70, 12, fill=WHITE)
    L.rr((140, 172, 180, 190), 4, fill=p["panel"])                             # soporte
    L.rr((120, 188, 200, 196), 4, fill=p["frame"])
    L.rr((76, 198, 244, 244), 16, fill=p["sofa"], outline=p["edge"], width=2)  # respaldo
    L.rr((50, 220, 90, 274), 14, fill=p["sofa"], outline=p["edge"], width=2)
    L.rr((230, 220, 270, 274), 14, fill=p["sofa"], outline=p["edge"], width=2)
    L.rr((84, 226, 236, 272), 14, fill=BLUE if not L.dark else (0, 100, 210), outline=p["edge"], width=2)
    L.line([(160, 232), (160, 268)], p["sofa"], 3)


# ---------- 9. ventana de sistema genérica con engranaje y barra de progreso ----------
def ilu_windows(L, p):
    L.rr((16, 28, 304, 270), 22, fill=p["soft"] if not L.dark else p["soft2"], outline=p["ring"], width=2.5)
    L.rr((16, 28, 304, 76), 22, fill=BLUE)
    L.rect((16, 58, 304, 76), BLUE)
    for i in range(3):
        L.circ(44 + i * 22, 52, 6, fill=WHITE)
    fondo = p["soft"] if not L.dark else p["soft2"]
    engranaje(L, 118, 156, 58, 44, 8, BLUE, fondo)
    engranaje(L, 218, 120, 36, 26, 7, BLUE_DARK, fondo, rot=0.3)
    L.circ(250, 190, 24, fill=BLUE)
    L.line([(238, 190), (247, 200), (264, 180)], WHITE, 6)
    L.rr((44, 232, 276, 252), 10, fill=p["soft2"] if not L.dark else p["frame"])
    L.rr((44, 232, 200, 252), 10, fill=BLUE)


# ---------- 10. portátil con batería llena y rayo ----------
def ilu_bateria(L, p):
    def pantalla():
        L.rr((96, 76, 200, 156), 12, outline=WHITE, width=6)
        L.rr((200, 102, 214, 130), 4, fill=WHITE)
        for i in range(4):
            L.rr((106 + i * 23, 86, 123 + i * 23, 146), 4, fill=BLUE)
        L.poly([(158, 66), (132, 118), (154, 118), (144, 168), (182, 104), (160, 104), (172, 66)], WHITE)

    portatil(L, p, pantalla)
    L.circ(286, 62, 22, fill=BLUE)
    L.poly([(290, 46), (276, 66), (286, 66), (282, 80), (298, 58), (288, 58)], WHITE)
    estrella(L, 30, 252, 13, LUZ if L.dark else BLUE)
    estrella(L, 300, 250, 10, LUZ if L.dark else BLUE)


# ---------- 11. engranajes, flechas y reloj ----------
def ilu_automatizacion(L, p):
    fondo = (10, 22, 52) if L.dark else WHITE
    engranaje(L, 112, 158, 82, 64, 10, BLUE, fondo)
    engranaje(L, 232, 78, 48, 36, 8, BLUE_DARK, fondo, rot=0.2)
    flecha_arco(L, 112, 158, 104, 195, 292, LUZ if L.dark else BLUE, 7)
    L.circ(236, 214, 52, fill=WHITE if not L.dark else p["soft2"], outline=BLUE, width=8)
    for a in (0, 90, 180, 270):
        r = math.radians(a)
        L.line([(236 + 40 * math.cos(r), 214 + 40 * math.sin(r)), (236 + 33 * math.cos(r), 214 + 33 * math.sin(r))],
               p["tinta"], 4)
    L.line([(236, 214), (236, 184)], p["tinta"], 6)
    L.line([(236, 214), (258, 226)], p["tinta"], 6)
    L.circ(236, 214, 6, fill=BLUE)


REGISTRO = {
    "montaje_pc": ilu_montaje_pc,
    "custom_loop": ilu_custom_loop,
    "consola_mantenimiento": ilu_consola,
    "ssd_consola": ilu_ssd,
    "recuperacion_datos": ilu_datos,
    "diagnostico": ilu_diagnostico,
    "tv_pared": ilu_tv,
    "windows": ilu_windows,
    "bateria_portatil": ilu_bateria,
    "automatizacion": ilu_automatizacion,
}


def dibujar(c, tema_id, slot, dark):
    """Dibuja la ilustración del tema dentro del hueco slot=(x, y, ancho, alto)."""
    if tema_id == "streaming":
        return ilu_streaming(c, slot, dark)
    x, y, w, h = slot
    k = min(w / 320, h / 300)
    L = Local(c, x + (w - 320 * k) / 2, y + (h - 300 * k) / 2, k, dark)
    aura(L)
    REGISTRO[tema_id](L, paleta(dark))
