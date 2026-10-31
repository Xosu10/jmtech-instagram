"""Gráficos animados dibujados con código para los vídeos de curiosidades (no necesitan imágenes externas).

grafico(tipo, params, t, dur) -> imagen RGBA de ANCHO x ALTO. Tipos: flujo (aire|liquido), barras, tarjeta, resumen.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .base import BLUE, S, font

ANCHO, ALTO = 940, 560
BLANCO = (244, 248, 255)
NARANJA = (255, 138, 40)
AZUL_CLARO = (110, 190, 255)
GRIS = (150, 170, 200)
ACENTOS = {"azul": BLUE, "naranja": NARANJA}


# ---------- Utilidades ----------
def _lienzo():
    im = Image.new("RGBA", (ANCHO * S, ALTO * S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im, "RGBA")


def _salida(im):
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def _mezcla(a, b, t):
    t = min(max(t, 0.0), 1.0)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _paso(p, ini, fin):
    """0 -> 1 entre dos instantes (con suavizado de salida)."""
    t = min(max((p - ini) / max(fin - ini, 1e-6), 0.0), 1.0)
    return 1 - (1 - t) ** 3


def _rect(d, x0, y0, x1, y1, fill=None, r=0, outline=None, w=1):
    caja = [x0 * S, y0 * S, x1 * S, y1 * S]
    if r:
        d.rounded_rectangle(caja, r * S, fill=fill, outline=outline, width=w * S)
    else:
        d.rectangle(caja, fill=fill, outline=outline, width=w * S)


def _punto(d, x, y, r, color, alfa=255):
    d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=color + (alfa,))


def _linea(d, puntos, color, ancho):
    d.line([(x * S, y * S) for x, y in puntos], fill=color, width=int(ancho * S), joint="curve")


def _texto(d, xy, texto, f, color, alfa=1.0, anchor="mm"):
    d.text((xy[0] * S, xy[1] * S), texto, font=f, fill=color + (int(255 * alfa),), anchor=anchor)


def _etiqueta(d, texto, x, y, alfa, tam=28):
    if alfa > 0.02:
        _texto(d, (x, y + 8 * (1 - alfa)), texto, font("Medium", tam), BLANCO, alfa)


# ---------- Refrigeración por aire ----------
def _flujo_aire(t, dur):
    p = t / max(dur, 0.01)
    im, d = _lienzo()
    _rect(d, 60, 500, 880, 545, (28, 38, 62), 12)
    # calor del procesador (late suavemente)
    pulso = 0.5 + 0.5 * math.sin(t * 3)
    _rect(d, 380, 462, 560, 500, _mezcla((74, 90, 122), NARANJA, 0.35 + 0.25 * pulso), 6)
    # tubos de calor
    tubos = [405, 455, 505, 555]
    for x in tubos:
        _rect(d, x - 6, 150, x + 6, 462, (190, 200, 222), 5)
    # aletas: se van calentando
    calor = min(0.75, p * 1.1)
    for y in range(150, 441, 16):
        cerca = (y - 150) / 290                                   # abajo (cerca del procesador) se calienta más
        _rect(d, 330, y, 620, y + 7, _mezcla((150, 170, 205), NARANJA, calor * (0.1 + 0.9 * cerca)), 3)
    # ventilador (las aspas giran)
    _rect(d, 235, 150, 290, 440, (36, 50, 82), 14, outline=(96, 120, 165), w=3)
    for k in range(7):
        y = 162 + (k * 40 + t * 150) % 270
        _rect(d, 247, y, 278, y + 9, (120, 150, 205), 4)
    # calor que sube por los tubos
    for i in range(16):
        f = (t * 0.55 + i / 16) % 1
        y = 462 - f * 300
        _punto(d, tubos[i % 4], y, 4.5, NARANJA, int(255 * min(1, (1 - f) * 2.5)))
    # aire que atraviesa las aletas y sale caliente
    for i in range(44):
        x = 300 + (t * 190 + i * 41) % 600
        y = 162 + (i % 11) * 26 + 4 * math.sin(t * 4 + i)
        h = (x - 330) / 290
        _punto(d, x, y, 4.2, _mezcla(AZUL_CLARO, NARANJA, h), 235)
    # etiquetas
    _etiqueta(d, "Ventilador", 262, 112, _paso(p, 0.10, 0.22))
    _etiqueta(d, "Aletas de metal", 475, 112, _paso(p, 0.28, 0.40))
    _etiqueta(d, "Aire caliente fuera", 770, 112, _paso(p, 0.52, 0.64))
    _etiqueta(d, "Procesador", 470, 523, _paso(p, 0.04, 0.16), 24)
    return _salida(im)


# ---------- Refrigeración líquida ----------
CAMINO_LIQUIDO = [(210, 330), (210, 200), (560, 200), (860, 200), (860, 260), (560, 260), (560, 320), (860, 320),
                  (860, 470), (210, 470), (210, 420)]


def _longitudes(puntos):
    acum = [0.0]
    for (x0, y0), (x1, y1) in zip(puntos, puntos[1:]):
        acum.append(acum[-1] + math.hypot(x1 - x0, y1 - y0))
    return acum


def _en_camino(puntos, acum, s):
    for i in range(len(puntos) - 1):
        if s <= acum[i + 1]:
            f = (s - acum[i]) / max(acum[i + 1] - acum[i], 1e-6)
            return (puntos[i][0] + (puntos[i + 1][0] - puntos[i][0]) * f, puntos[i][1] + (puntos[i + 1][1] - puntos[i][1]) * f)
    return puntos[-1]


def _flujo_liquido(t, dur):
    p = t / max(dur, 0.01)
    im, d = _lienzo()
    camino = CAMINO_LIQUIDO
    acum = _longitudes(camino)
    total = acum[-1]
    # radiador y ventilador
    _rect(d, 560, 150, 860, 340, (24, 36, 64), 10, outline=(150, 170, 205), w=3)
    for x in range(575, 860, 18):
        _rect(d, x, 156, x + 4, 334, (60, 82, 125), 2)
    _rect(d, 875, 150, 915, 340, (36, 50, 82), 12, outline=(96, 120, 165), w=3)
    for k in range(5):
        y = 160 + (k * 40 + t * 150) % 170
        _rect(d, 884, y, 906, y + 8, (120, 150, 205), 3)
    # tubos: calientes a la ida, fríos a la vuelta
    ida = camino[:3]
    _linea(d, ida, (150, 80, 40), 18)
    _linea(d, camino[2:8], (40, 80, 140), 16)
    _linea(d, camino[7:], (20, 80, 170), 18)
    # bloque sobre el procesador, con la bomba
    _rect(d, 150, 330, 270, 420, (60, 78, 112), 12, outline=(110, 140, 190), w=3)
    _rect(d, 170, 350, 250, 400, (20, 32, 60), 8)
    ang = t * 6
    for k in range(3):
        a = ang + k * 2.094
        _linea(d, [(210, 375), (210 + 24 * math.cos(a), 375 + 24 * math.sin(a))], BLUE, 5)
    # agua que circula: se calienta en el bloque y se enfría en el radiador
    sal_rad = acum[7]
    ent_rad = acum[2]
    for i in range(34):
        s = (t * 150 + i * total / 34) % total
        x, y = _en_camino(camino, acum, s)
        if s < ent_rad:
            c = NARANJA
        elif s < sal_rad:
            c = _mezcla(NARANJA, AZUL_CLARO, (s - ent_rad) / (sal_rad - ent_rad))
        else:
            c = AZUL_CLARO
        _punto(d, x, y, 4.5, c, 240)
    # aire que se lleva el calor del radiador
    for i in range(30):
        x = 520 + (t * 180 + i * 53) % 410
        y = 165 + (i % 10) * 17.5 + 3 * math.sin(t * 4 + i)
        _punto(d, x, y, 3.6, _mezcla(AZUL_CLARO, NARANJA, (x - 560) / 300), 220)
    # etiquetas
    _etiqueta(d, "Bloque y bomba", 210, 522, _paso(p, 0.08, 0.20), 26)
    _etiqueta(d, "Agua caliente", 380, 168, _paso(p, 0.25, 0.37), 24)
    _etiqueta(d, "Radiador", 690, 112, _paso(p, 0.42, 0.54))
    _etiqueta(d, "Ventilador", 855, 112, _paso(p, 0.60, 0.72), 24)
    _etiqueta(d, "Agua fría", 540, 522, _paso(p, 0.72, 0.84), 24)
    return _salida(im)


# ---------- Barras ----------
def _barras(t, dur, params):
    p = t / max(dur, 0.01)
    im, d = _lienzo()
    items = params["items"]
    tope = max(i["valor"] for i in items)
    _texto(d, (ANCHO / 2, 40), params.get("titulo", ""), font("Medium", 32), (170, 188, 218))
    y = 110
    alto_fila = (ALTO - 190) / len(items)
    for n, it in enumerate(items):
        acento = ACENTOS.get(it.get("acento", "azul"), BLUE)
        a = _paso(p, 0.12 + n * 0.28, 0.40 + n * 0.28)
        _texto(d, (40, y + 18), it["etiqueta"], font("Bold", 38), BLANCO, min(1, a * 2), "lm")
        largo = 860 * it["valor"] / tope * a
        _rect(d, 40, y + 56, 900, y + 118, (20, 32, 58), 16)
        if largo > 8:
            _rect(d, 40, y + 56, 40 + largo, y + 118, acento, 16)
        if a > 0.6:
            _texto(d, (40 + max(largo, 120) - 18, y + 87), it["texto"], font("Bold", 36), (255, 255, 255), (a - 0.6) / 0.4, "rm")
        y += alto_fila
    if params.get("nota"):
        _texto(d, (ANCHO / 2, ALTO - 28), params["nota"], font("Medium", 24), (130, 150, 185), _paso(p, 0.6, 0.8))
    return _salida(im)


# ---------- Tarjetas ----------
def _ajustar(texto, peso, tam, ancho):
    while tam > 22 and font(peso, tam).getlength(texto) / S > ancho:
        tam -= 2
    return font(peso, tam)


def _tarjeta_base(d, x0, y0, x1, y1, acento, alfa):
    _rect(d, x0, y0, x1, y1, (12, 24, 48, int(235 * alfa)), 30, outline=acento + (int(255 * alfa),), w=3)


def _tarjeta(t, dur, params):
    p = t / max(dur, 0.01)
    im, d = _lienzo()
    acento = ACENTOS.get(params.get("acento", "azul"), BLUE)
    _tarjeta_base(d, 20, 20, 920, 540, acento, 1.0)
    _texto(d, (60, 80), params["cabecera"].upper(), font("Medium", 28), acento, 1.0, "lm")
    _texto(d, (60, 150), params["titulo"], _ajustar(params["titulo"], "Bold", 56, 840), BLANCO, 1.0, "lm")
    d.line([(60 * S, 200 * S), (880 * S, 200 * S)], fill=(60, 80, 120, 255), width=2 * S)
    puntos = params["puntos"]
    paso = 300 / max(len(puntos), 1)
    for i, txt in enumerate(puntos):
        a = _paso(p, 0.10 + i * 0.22, 0.26 + i * 0.22)
        y = 250 + i * min(paso, 90)
        if a < 0.02:
            continue
        _punto(d, 80, y + 6 * (1 - a), 22, acento, int(255 * a))
        _linea(d, [(70, y + 6 * (1 - a)), (78, y + 14 * (1 - a) + 8 * a - 2), (92, y + 6 * (1 - a) - 8 * a)], (255, 255, 255, 255)[:3], 5)
        _texto(d, (125, y + 6 * (1 - a)), txt, _ajustar(txt, "Medium", 36, 760), BLANCO, a, "lm")
    return _salida(im)


def _resumen(t, dur, params):
    p = t / max(dur, 0.01)
    im, d = _lienzo()
    filas = params["filas"]
    alto = (ALTO - 40 - 30 * (len(filas) - 1)) / len(filas)
    for i, fila in enumerate(filas):
        a = _paso(p, 0.12 + i * 0.35, 0.36 + i * 0.35)
        if a < 0.02:
            continue
        acento = ACENTOS.get(fila.get("acento", "azul"), BLUE)
        y0 = 20 + i * (alto + 30) + 20 * (1 - a)
        _tarjeta_base(d, 20, y0, 920, y0 + alto, acento, a)
        _texto(d, (60, y0 + alto * 0.30), fila["cabecera"].upper(), font("Medium", 28), acento, a, "lm")
        _texto(d, (60, y0 + alto * 0.68), fila["titulo"], _ajustar(fila["titulo"], "Bold", 52, 700), BLANCO, a, "lm")
        cx, cy = 840, y0 + alto / 2
        _punto(d, cx, cy, 38, acento, int(255 * a))
        _linea(d, [(cx - 16, cy), (cx + 14, cy)], (255, 255, 255), 7)
        _linea(d, [(cx + 2, cy - 14), (cx + 16, cy), (cx + 2, cy + 14)], (255, 255, 255), 7)
    return _salida(im)


def _pasos(t, dur, params):
    """Cadena de pasos que van apareciendo, del azul (origen) al naranja (resultado)."""
    p = t / max(dur, 0.01)
    im, d = _lienzo()
    pasos = params["pasos"]
    alto = (ALTO - 40 - 56 * (len(pasos) - 1)) / len(pasos)
    for i, txt in enumerate(pasos):
        a = _paso(p, 0.10 + i * 0.28, 0.28 + i * 0.28)
        if a < 0.02:
            continue
        f = i / max(len(pasos) - 1, 1)                     # azul -> violeta -> naranja (sin pasar por gris)
        color = _mezcla(BLUE, (160, 110, 255), f * 2) if f < 0.5 else _mezcla((160, 110, 255), NARANJA, f * 2 - 1)
        y0 = 20 + i * (alto + 56) + 24 * (1 - a)
        _tarjeta_base(d, 20, y0, 920, y0 + alto, color, a)
        _punto(d, 90, y0 + alto / 2, 34, color, int(255 * a))
        _texto(d, (90, y0 + alto / 2), str(i + 1), font("Bold", 40), (255, 255, 255), a)
        _texto(d, (150, y0 + alto / 2), txt, _ajustar(txt, "Bold", 44, 740), BLANCO, a, "lm")
        if i < len(pasos) - 1 and a > 0.5:
            cx, cy = ANCHO / 2, y0 + alto + 28
            _linea(d, [(cx - 18, cy - 10), (cx, cy + 10), (cx + 18, cy - 10)], color, 7)
    return _salida(im)


TIPOS = ("flujo", "barras", "tarjeta", "resumen", "pasos")


def grafico(tipo, params, t, dur):
    if tipo == "flujo":
        return _flujo_aire(t, dur) if params.get("modo") == "aire" else _flujo_liquido(t, dur)
    if tipo == "barras":
        return _barras(t, dur, params)
    if tipo == "tarjeta":
        return _tarjeta(t, dur, params)
    if tipo == "resumen":
        return _resumen(t, dur, params)
    if tipo == "pasos":
        return _pasos(t, dur, params)
    raise ValueError(f"Tipo de gráfico desconocido: {tipo}")
