"""Reels de ~9 s: texto + asset animados (1080x1920) y música propia sintetizada. Sin coste ni derechos de autor.

python -m jmtech.reel --tema tarjeta_grafica --asset gpu_triple_ventilador_aislado_01.png --salida reel.mp4
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .assets import cargar_catalogo, indice
from functools import lru_cache

from .base import BLUE, LOGO_OSCURO, S, _lockup, equilibrar, font, partir
from .contenido import indice_temas

W, H, FPS, DUR = 1080, 1920, 30, 9.0
BLANCO = (244, 248, 255)
ZONA_SEGURA = (250, 1600)          # Instagram tapa arriba y abajo con su interfaz


class _Med:
    def tw(self, t, f):
        return f.getlength(t) / S


MED = _Med()


# ---------- Utilidades de dibujo ----------
def _capa_texto(texto, f, color, pad=8):
    asc, desc = f.getmetrics()
    ancho, alto = int(f.getlength(texto) / S) + 2 * pad, int((asc + desc) / S) + 2 * pad
    im = Image.new("RGBA", (ancho * S, alto * S), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad * S, pad * S), texto, font=f, fill=color)
    return im.resize((ancho, alto), Image.LANCZOS)


def _capa_punto(texto, f, ancho_max):
    """Punto de la lista: casilla azul con marca + texto (una o dos líneas)."""
    lineas = equilibrar(MED, partir(MED, texto, f, ancho_max - 90), f)
    lh = 40
    alto = max(54, len(lineas) * lh + 8)
    im = Image.new("RGBA", (ancho_max * S, alto * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy = alto // 2
    d.rounded_rectangle([0, (cy - 26) * S, 52 * S, (cy + 26) * S], 14 * S, fill=BLUE)
    d.line([(12 * S, cy * S), (22 * S, (cy + 10) * S), (40 * S, (cy - 12) * S)], fill=(255, 255, 255), width=7 * S, joint="curve")
    y = cy - len(lineas) * lh / 2 + 2
    for ln in lineas:
        d.text((74 * S, y * S), ln, font=f, fill=BLANCO)
        y += lh
    return im.resize((ancho_max, alto), Image.LANCZOS)


def _capa_cta():
    w, h = 920, 112
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S, h * S], 30 * S, fill=BLUE)
    d.text((40 * S, 30 * S), "¿Quieres presupuesto?", font=font("Bold", 38), fill=(255, 255, 255), anchor="lm")
    d.text((40 * S, 76 * S), "Escríbenos por MD", font=font("Medium", 30), fill=(222, 238, 255), anchor="lm")
    r = 36
    ax, ay = w - 40 - r, h / 2
    d.ellipse([(ax - r) * S, (ay - r) * S, (ax + r) * S, (ay + r) * S], fill=(255, 255, 255))
    d.line([(ax - 15) * S, ay * S, (ax + 13) * S, ay * S], fill=BLUE, width=6 * S)
    d.line([(ax + 2) * S, (ay - 12) * S, (ax + 14) * S, ay * S, (ax + 2) * S, (ay + 12) * S], fill=BLUE, width=6 * S, joint="curve")
    return im.resize((w, h), Image.LANCZOS)


def _fondo():
    arriba, abajo = np.array((9, 15, 30), float), np.array((4, 8, 17), float)
    t = np.linspace(0, 1, H)[:, None, None]
    base = (arriba * (1 - t) + abajo * t) * np.ones((1, W, 1))
    im = Image.fromarray(base.astype(np.uint8), "RGB").convert("RGBA")
    brillo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse([380, -300, 1500, 700], fill=BLUE + (120,))
    ImageDraw.Draw(brillo).ellipse([-500, 1250, 560, 2200], fill=BLUE + (70,))
    im = Image.alpha_composite(im, brillo.filter(ImageFilter.GaussianBlur(120)))
    rejilla = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(rejilla)
    for x in range(0, W + 1, 54):
        d.line([(x, 0), (x, H)], fill=(30, 64, 120, 60), width=1)
    for y in range(0, H + 1, 54):
        d.line([(0, y), (W, y)], fill=(30, 64, 120, 60), width=1)
    return Image.alpha_composite(im, rejilla)


def _capa_asset(asset, caja=(840, 400)):
    im = Image.open(asset.ruta).convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox())
    k = min(caja[0] / im.width, caja[1] / im.height)
    return im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)


def _salida(t):                      # ease-out con ligera sobrepasada
    t = min(max(t, 0.0), 1.0)
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _suave(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def _poner(base, capa, x, y, alfa=1.0):
    if alfa <= 0.003:
        return
    if alfa < 0.997:
        a = (np.array(capa.getchannel("A"), dtype=np.float32) * alfa).astype(np.uint8)
        capa = capa.copy()
        capa.putalpha(Image.fromarray(a))
    x, y = max(0, int(x)), max(0, int(y))
    base.alpha_composite(capa, (x, y))


# ---------- Música propia (sintetizada con código: sin derechos) ----------
def sintetizar_musica(ruta_wav, dur=DUR, sr=44100, bpm=104, semilla=7):
    rng = np.random.default_rng(semilla)
    n = int(dur * sr)
    t = np.arange(n) / sr
    pista = np.zeros(n)
    beat = 60 / bpm

    def nota(f, ini, dur_n, amp=1.0, forma="tri", ataque=0.01, caida=3.0):
        i0, i1 = int(ini * sr), min(n, int((ini + dur_n) * sr))
        if i1 <= i0:
            return
        tt = np.arange(i1 - i0) / sr
        ph = 2 * np.pi * f * tt
        onda = {"tri": 2 / np.pi * np.arcsin(np.sin(ph)), "sin": np.sin(ph),
                "saw": 2 * ((f * tt) % 1) - 1}[forma]
        env = np.minimum(tt / ataque, 1) * np.exp(-caida * tt / dur_n)
        pista[i0:i1] += amp * onda * env

    # bombo en cada tiempo
    for b in np.arange(0, dur, beat):
        i0 = int(b * sr)
        i1 = min(n, i0 + int(0.28 * sr))
        tt = np.arange(i1 - i0) / sr
        f = 48 + 90 * np.exp(-tt * 28)
        pista[i0:i1] += 0.9 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 11)
    # hi-hat en los contratiempos
    for b in np.arange(beat / 2, dur, beat):
        i0 = int(b * sr)
        i1 = min(n, i0 + int(0.06 * sr))
        ruido = rng.normal(0, 1, i1 - i0)
        ruido = np.diff(np.concatenate([[0], ruido]))            # filtro paso alto muy simple
        pista[i0:i1] += 0.16 * ruido * np.exp(-np.arange(i1 - i0) / sr * 60)
    # bajo (La, Fa, Do, Sol)
    bajos = [55.0, 43.65, 65.41, 49.0]
    for compas, f in enumerate(bajos * 4):
        ini = compas * 2 * beat
        if ini >= dur:
            break
        nota(f, ini, 1.9 * beat, 0.5, "saw", 0.02, 1.8)
        nota(f, ini + beat, 0.9 * beat, 0.35, "saw", 0.02, 2.5)
    # arpegio suave
    acordes = [(220, 261.63, 329.63), (174.61, 220, 261.63), (261.63, 329.63, 392), (196, 246.94, 293.66)]
    for compas in range(int(dur / (2 * beat)) + 1):
        a = acordes[compas % 4]
        for i in range(8):
            nota(a[i % 3] * (2 if i % 2 else 1), compas * 2 * beat + i * beat / 2, beat * 0.9, 0.16, "tri", 0.005, 4)
    # eco
    eco = np.zeros_like(pista)
    d = int(0.29 * sr)
    eco[d:] += 0.32 * pista[:-d]
    pista += eco
    # fundidos y volumen
    env = np.minimum(t / 0.15, 1) * np.minimum((dur - t) / 1.0, 1)
    pista *= env
    pista = np.tanh(pista * 1.2)
    pista = pista / np.max(np.abs(pista)) * 0.7
    estereo = np.stack([pista, np.roll(pista, int(0.004 * sr))], axis=1)
    with wave.open(str(ruta_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((estereo * 32767).astype("<i2").tobytes())
    return Path(ruta_wav)


# ---------- Reel ----------
def _ffmpeg():
    exe = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("No se encuentra ffmpeg (herramienta gratuita de vídeo).")
    return exe


def preparar_musica(ruta_audio, ruta_wav, dur=DUR, inicio=0.0):
    """Recorta una canción a `dur` s desde `inicio`, con fundido de entrada y de salida y volumen normalizado."""
    filtro = f"afade=t=in:d=0.25,afade=t=out:st={dur - 1.0}:d=1.0,loudnorm=I=-16:TP=-1.5:LRA=11"
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-ss", str(inicio), "-t", str(dur), "-i", str(ruta_audio),
                    "-af", filtro, "-ar", "44100", "-ac", "2", str(ruta_wav)], check=True)
    return Path(ruta_wav)


FLOTE = 8              # px que sube y baja el asset
SOBREPASO = 1.1        # el asset crece hasta un 10 % al entrar
HUECO = 34             # separación mínima entre el asset y el texto (arriba y abajo)
Y_CTA = 1490


@lru_cache(maxsize=None)
def _logo_reel():
    """Logo del reel: más grande que en las publicaciones y con la frase bien separada del nombre."""
    grande = _lockup(Image.open(LOGO_OSCURO).convert("RGBA"), mw=350, tw=560, gap=36)
    return grande.resize((grande.width // S, grande.height // S), Image.LANCZOS)


def calcular_geometria(tema):
    """Capas de texto y posiciones de un reel. Reparte el espacio para que el asset nunca toque el texto."""
    l1, l2 = tema["titulo_linea1"], tema["titulo_linea2_azul"]
    size = 84
    while size > 60 and max(font("Bold", size).getlength(l1), font("Bold", size).getlength(l2)) / S > 940:
        size -= 2
    t1 = _capa_texto(l1, font("Bold", size), BLANCO)
    t2 = _capa_texto(l2, font("Bold", size), BLUE)
    f_sub = font("Regular", 34)
    sub = [_capa_texto(ln, f_sub, (170, 188, 218)) for ln in equilibrar(MED, partir(MED, tema["subtitulo"], f_sub, 900), f_sub)]
    puntos = [_capa_punto(p, font("Medium", 31), 900) for p in tema["puntos"]]
    cta = _capa_cta()
    logo = _logo_reel()
    y_logo = 205                                   # más alto
    y_t1 = y_logo + logo.height + 36               # y bien separado del título
    y_t2 = y_t1 + t1.height - 14
    y_sub = y_t2 + t2.height + 4
    y_sub_fin = y_sub + 44 * len(sub)
    gap = 8
    alto_puntos = [p.height for p in puntos]
    y_puntos = Y_CTA - 24 - (sum(alto_puntos) + gap * (len(puntos) - 1))     # la lista termina justo encima del botón
    ys_puntos = [y_puntos + sum(alto_puntos[:i]) + gap * i for i in range(len(puntos))]
    zona_arriba, zona_abajo = y_sub_fin + HUECO, y_puntos - HUECO
    alto_caja = max(120, int((zona_abajo - zona_arriba - 2 * FLOTE) / SOBREPASO))
    return dict(logo=logo, t1=t1, t2=t2, sub=sub, puntos=puntos, cta=cta, y_logo=y_logo, y_t1=y_t1, y_t2=y_t2, y_sub=y_sub,
                y_sub_fin=y_sub_fin, y_puntos=y_puntos, ys_puntos=ys_puntos, y_cta=Y_CTA, alto_caja=alto_caja,
                zona_asset=(zona_arriba, zona_abajo), y_asset_centro=(zona_arriba + zona_abajo) / 2)


def generar_reel(tema, asset, salida, previsualizar=None, dur=DUR, musica=None, musica_inicio=0.0):
    """Crea el MP4 del reel. `asset` es un jmtech.assets.Asset o None. Devuelve la ruta.

    Sin `musica` se usa música propia sintetizada (sin derechos). Con `musica` se recorta esa canción."""
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    fondo = _fondo()
    g = calcular_geometria(tema)
    logo, t1, t2, sub, puntos, cta = g["logo"], g["t1"], g["t2"], g["sub"], g["puntos"], g["cta"]
    y_logo, y_t1, y_t2, y_sub = g["y_logo"], g["y_t1"], g["y_t2"], g["y_sub"]
    ys_puntos, y_cta, y_asset_centro = g["ys_puntos"], g["y_cta"], g["y_asset_centro"]
    aset = _capa_asset(asset, (840, g["alto_caja"])) if asset else None
    brillo = None
    if aset:
        brillo = Image.new("RGBA", (aset.width + 240, aset.height + 240), (0, 0, 0, 0))
        ImageDraw.Draw(brillo).ellipse([40, 60, brillo.width - 40, brillo.height - 40], fill=BLUE + (90,))
        brillo = brillo.filter(ImageFilter.GaussianBlur(60))

    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    wav = salida.with_suffix(".wav")
    if musica:
        preparar_musica(musica, wav, dur, musica_inicio)
    else:
        sintetizar_musica(wav, dur)
    cmd += ["-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-level", "4.1",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest",
            "-movflags", "+faststart", str(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(dur * FPS)
    muestras = {int(2.0 * FPS): "02", int(4.0 * FPS): "04", int(5.8 * FPS): "06", int(8.0 * FPS): "08"}
    if previsualizar:
        Path(previsualizar).mkdir(parents=True, exist_ok=True)
    try:
        for i in range(n):
            t = i / FPS
            fr = fondo.copy()
            # logo
            _poner(fr, logo, (W - logo.width) // 2, y_logo - 20 * (1 - _suave(t / 0.6)), _suave(t / 0.6))
            # títulos
            _poner(fr, t1, 64, y_t1 + 40 * (1 - _suave((t - 0.3) / 0.6)), _suave((t - 0.3) / 0.5))
            _poner(fr, t2, 64, y_t2 + 40 * (1 - _suave((t - 0.55) / 0.6)), _suave((t - 0.55) / 0.5))
            for k, s in enumerate(sub):
                _poner(fr, s, 64, y_sub + 44 * k + 20 * (1 - _suave((t - 1.0) / 0.5)), _suave((t - 1.0) / 0.5))
            # asset: entra con rebote y luego flota
            if aset:
                p = _salida((t - 1.3) / 0.8)
                if t > 1.3:
                    esc = max(p, 0.01)
                    capa = aset.resize((max(1, int(aset.width * esc)), max(1, int(aset.height * esc))), Image.BILINEAR)
                    flot = FLOTE * math.sin((t - 1.3) * 2.2)
                    cx, cy = W // 2, y_asset_centro + flot
                    br = brillo.resize((int(brillo.width * esc), int(brillo.height * esc)), Image.BILINEAR)
                    _poner(fr, br, cx - br.width // 2, cy - br.height // 2, min(1.0, (t - 1.3) / 0.5))
                    _poner(fr, capa, cx - capa.width // 2, cy - capa.height // 2, min(1.0, (t - 1.3) / 0.35))
            # puntos uno a uno
            for k, (pt, yy) in enumerate(zip(puntos, ys_puntos)):
                ini = 2.6 + 0.7 * k
                a = _suave((t - ini) / 0.45)
                _poner(fr, pt, 90 - 50 * (1 - a), yy, a)
            # botón: entra y late suavemente
            ini = 5.6
            if t > ini:
                a = _suave((t - ini) / 0.4)
                pulso = 1 + 0.025 * math.sin((t - ini) * 5)
                c = cta if t < ini + 0.4 else cta.resize((int(cta.width * pulso), int(cta.height * pulso)), Image.BILINEAR)
                _poner(fr, c, (W - c.width) // 2, y_cta - (c.height - cta.height) // 2 + 30 * (1 - a), a)
            rgb = fr.convert("RGB")
            if previsualizar and i in muestras:
                rgb.save(Path(previsualizar) / f"reel_{muestras[i]}s.png")
            proc.stdin.write(rgb.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    wav.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg no pudo crear el vídeo.")
    return salida


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tema", required=True)
    p.add_argument("--asset", default="")
    p.add_argument("--salida", default="reel.mp4")
    p.add_argument("--previsualizar", default="")
    p.add_argument("--musica", default="", help="canción a usar (si no, música propia sintetizada)")
    p.add_argument("--musica-inicio", type=float, default=0.0, help="segundo de la canción por el que empezar")
    a = p.parse_args()
    tema = indice_temas()[a.tema]
    asset = indice(cargar_catalogo()).get(a.asset) if a.asset else None
    ruta = generar_reel(tema, asset, a.salida, a.previsualizar or None, musica=a.musica or None,
                        musica_inicio=a.musica_inicio)
    print("Reel creado:", ruta, f"({ruta.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
