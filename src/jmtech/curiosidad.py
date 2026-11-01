"""Vídeos de curiosidades de informática: guion -> voz (Ximena) -> imágenes en movimiento -> subtítulos -> MP4 vertical.

python -m jmtech.curiosidad render contenido/curiosidades/01_aire_o_liquida.json --salida video.mp4
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .assets import cargar_catalogo, indice
from .base import BLUE, LOGO_OSCURO, RAIZ, S, _lockup, font
from .graficos import TIPOS, grafico
from .reel import FPS, W, H, _capa_cta, _fondo, _ffmpeg, _poner, _suave
from .validacion import _CONTACTO

# En los vídeos de curiosidades se puede hablar de precios del mercado (la RAM sube, una gráfica cuesta...), pero no
# ofrecer descuentos, ofertas ni garantías ni dar datos de contacto: eso queda solo para las publicaciones comerciales.
_PROHIBIDO_CURIOSIDAD = re.compile(r"\bdescuentos?\b|\bofertas?\b|\bgratis\b|\bgratuit\w*|\bgarant[ií]\w*|\brebajas?\b|%", re.IGNORECASE)


def problemas_texto(texto: str) -> list[str]:
    fallos = []
    m = _PROHIBIDO_CURIOSIDAD.search(texto)
    if m:
        fallos.append(f"contiene «{m.group(0)}» (sin descuentos, ofertas, garantías ni porcentajes)")
    m = _CONTACTO.search(texto)
    if m:
        fallos.append(f"contiene datos de contacto («{m.group(0)}»): el contacto es solo por MD")
    return fallos

VOZ = "es-ES-XimenaNeural"
VELOCIDAD = "+4%"
PAUSA = 0.35                       # silencio entre escenas (s)
BLANCO = (244, 248, 255)
CARPETA_ESPECS = RAIZ / "contenido" / "curiosidades"
CARPETA_IMAGENES = Path(os.environ.get("CURIOSIDADES_DIR") or r"C:\Users\xosu1\Documents\Codex\curiosidades") / "entregas"
CAJA = (940, 560)                  # hueco de la imagen
Y_LOGO, Y_TITULO, Y_IMAGEN, Y_SUB, Y_BARRA, Y_PIE = 180, 455, 625, 1240, 1500, 1535
HASHTAGS = (5, 9)
MAX_DESCRIPCION = 2200


# ---------- Guion ----------
def cargar_espec(ruta) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def problemas_espec(e: dict) -> list[str]:
    """Comprobaciones del guion y de la descripción antes de montar el vídeo."""
    fallos = []
    for k in ("id", "titulo", "titulo_pantalla", "escenas") + (() if e.get("serie") else ("fuentes",)):
        if not e.get(k):
            fallos.append(f"falta «{k}»")
    if not e.get("descripcion") and not e.get("puntos"):
        fallos.append("falta «descripcion» (o «puntos» para generarla)")
    e = {**e, "hashtags": hashtags_de(e), "descripcion": e.get("descripcion") or descripcion_de(e)}
    if not 4 <= len(e.get("escenas", [])) <= 9:
        fallos.append("debe tener entre 4 y 9 escenas")
    palabras = 0
    for i, esc in enumerate(e.get("escenas", []), 1):
        palabras += len(esc.get("texto", "").split())
        if esc.get("grafico") and esc["grafico"] not in TIPOS:
            fallos.append(f"escena {i}: gráfico «{esc['grafico']}» desconocido")
        elif not esc.get("imagen") and not esc.get("grafico") and not esc.get("cierre") and not esc.get("clip"):
            fallos.append(f"escena {i}: falta la imagen o el gráfico")
        fallos += [f"escena {i}: {f}" for f in problemas_texto(esc.get("texto", ""))]
    if palabras > e.get("max_palabras", 150):
        fallos.append(f"el guion tiene {palabras} palabras (máximo {e.get('max_palabras', 150)})")
    if not HASHTAGS[0] <= len(e.get("hashtags", [])) <= HASHTAGS[1]:
        fallos.append(f"debe tener entre {HASHTAGS[0]} y {HASHTAGS[1]} hashtags")
    if len(construir_descripcion(e)) > MAX_DESCRIPCION:
        fallos.append("la descripción supera los 2.200 caracteres")
    fallos += [f"descripción: {f}" for f in problemas_texto(e.get("descripcion", ""))]
    return fallos


BASE_HASHTAGS = ["#informatica", "#curiosidades", "#tecnologia", "#murcia"]
INVITACIONES = ["¿Dudas con tu PC? Escríbenos por MD.", "¿Quieres que lo revisemos por ti? Escríbenos por MD.",
                "¿Te pasa algo parecido? Cuéntanoslo por MD.", "Si tu equipo necesita ayuda, escríbenos por MD."]


def hashtags_de(e: dict) -> list[str]:
    """Los de la ficha o, si no hay, los comunes más las etiquetas propias del tema."""
    if e.get("hashtags"):
        return e["hashtags"]
    extra = [h if h.startswith("#") else f"#{h}" for h in e.get("etiquetas", [])]
    return BASE_HASHTAGS + [h for h in extra if h not in BASE_HASHTAGS]


def descripcion_de(e: dict) -> str:
    """Texto de la publicación generado con los puntos clave del vídeo."""
    emoji = e.get("emoji", "💡")
    invitacion = e.get("invitacion") or INVITACIONES[sum(map(ord, e["id"])) % len(INVITACIONES)]
    puntos = "\n".join(f"• {p}" for p in e["puntos"])
    return f"{e['titulo']} {emoji}\n\n{puntos}\n\n{invitacion}"


def construir_descripcion(e: dict) -> str:
    fuentes = "\n".join(f"• {f}" for f in e.get("fuentes", []))
    cabecera_fuentes = ("📚 Fuentes consultadas:" if fuentes else
                        "ℹ️ Ejemplo ilustrativo de lo que podemos automatizar: cada caso se estudia por separado."
                        if e.get("serie") == "automatizacion" else "ℹ️ Contenido informativo y orientativo.")
    etiquetas = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags_de(e))
    return (f"{e.get('descripcion') or descripcion_de(e)}\n\n"
            f"{cabecera_fuentes}\n{fuentes}\n\n"
            f"🎙️ Voz generada con IA. {e.get('aviso_legal') or 'Imágenes ilustrativas.'}\n"
            "🔧 JM TECH · Servicio técnico y soluciones tecnológicas en Murcia. Presupuesto sin compromiso por MD.\n\n"
            f"{etiquetas}")


# ---------- Voz ----------
async def _tts(texto, voz, velocidad, ruta_mp3):
    import edge_tts
    com = edge_tts.Communicate(texto, voz, rate=velocidad, boundary="WordBoundary")
    palabras = []
    with open(ruta_mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                palabras.append((ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]))
    return palabras


def _a_wav(ruta_audio, ruta_wav):
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(ruta_audio), "-ar", "44100", "-ac", "1", str(ruta_wav)], check=True)
    with wave.open(str(ruta_wav)) as w:
        return w.getnframes() / w.getframerate()


def _pronunciar(texto: str) -> str:
    """Cómo se debe decir en voz alta lo que en pantalla se escribe de otra forma (el número de palabras no cambia)."""
    return re.sub(r"\bVI\b", "seis", texto)             # «GTA VI» se escribe con numeral romano pero se dice «GTA seis»


def sintetizar_escena(texto, ruta_base, voz=VOZ, velocidad=VELOCIDAD):
    """Devuelve (wav, palabras[(inicio, duración, texto)], duración). Con Edge TTS (voz Ximena)."""
    mp3 = Path(f"{ruta_base}.mp3")
    palabras = asyncio.run(_tts(_pronunciar(texto), voz, velocidad, mp3))
    dur = _a_wav(mp3, Path(f"{ruta_base}.wav"))
    mp3.unlink(missing_ok=True)
    if not palabras:                           # plan B: reparto proporcional a la longitud de cada palabra
        palabras = _repartir(texto, dur)
    elif len(palabras) == len(texto.split()):  # Edge devuelve las palabras sin signos: recuperamos los del guion
        palabras = [(i, d, t) for (i, d, _), t in zip(palabras, texto.split())]
    return Path(f"{ruta_base}.wav"), palabras, dur


def _repartir(texto, dur):
    ws = texto.split()
    total = sum(len(w) + 1 for w in ws)
    t, salida = 0.0, []
    for w in ws:
        d = dur * (len(w) + 1) / total
        salida.append((t, d, w))
        t += d
    return salida


# ---------- Dibujo ----------
def _capa_texto(texto, f, color, pad=6):
    asc, desc = f.getmetrics()
    ancho, alto = int(f.getlength(texto) / S) + 2 * pad, int((asc + desc) / S) + 2 * pad
    im = Image.new("RGBA", (ancho * S, alto * S), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad * S, pad * S), texto, font=f, fill=color)
    return im.resize((ancho, alto), Image.LANCZOS)


def _partir_titulo(titulo, ancho_max=940, tam=54):
    f = font("Bold", tam)
    lineas, actual = [], ""
    for p in titulo.split():
        prueba = (actual + " " + p).strip()
        if f.getlength(prueba) / S <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    lineas.append(actual)
    return lineas[:2]


def _fondo_video(titulo_pantalla):
    """Fondo fijo del vídeo: degradado, logo, título del tema y pie de marca."""
    bg = _fondo()
    logo = _lockup(Image.open(LOGO_OSCURO).convert("RGBA"), mw=210, tw=340, gap=18)
    logo = logo.resize((logo.width // S, logo.height // S), Image.LANCZOS)
    bg.alpha_composite(logo, ((W - logo.width) // 2, Y_LOGO))
    y = Y_TITULO
    for ln in _partir_titulo(titulo_pantalla):
        capa = _capa_texto(ln, font("Bold", 54), BLANCO)
        bg.alpha_composite(capa, ((W - capa.width) // 2, y))
        y += 70
    pie = _capa_texto("JM TECH · Servicio técnico en Murcia", font("Medium", 28), (150, 170, 205))
    bg.alpha_composite(pie, ((W - pie.width) // 2, Y_PIE))
    return bg


def _imagen_escena(ruta):
    """Prepara la imagen de una escena: objeto con transparencia (se centra con resplandor) o escena completa (tarjeta)."""
    im = Image.open(ruta).convert("RGBA")
    if np.array(im.getchannel("A")).min() < 250:                      # objeto aislado
        im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox())
        k = min(CAJA[0] / im.width, CAJA[1] / im.height)
        return "objeto", im.resize((int(im.width * k * 1.1), int(im.height * k * 1.1)), Image.LANCZOS)
    k = max(CAJA[0] / im.width, CAJA[1] / im.height) * 1.18
    return "escena", im.convert("RGB").resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)


def _componer_imagen(fr, tipo, im, t_rel, dur, alfa):
    """Pone la imagen de la escena con un movimiento suave (acercamiento lento)."""
    p = min(max(t_rel / max(dur, 0.01), 0.0), 1.0)
    cx, cy = W // 2, Y_IMAGEN + CAJA[1] // 2
    if tipo == "objeto":
        esc = (0.92 + 0.08 * _suave(p * 1.0)) / 1.1 * (1.0 + 0.05 * p)
        capa = im.resize((max(1, int(im.width * esc)), max(1, int(im.height * esc))), Image.BILINEAR)
        halo = Image.new("RGBA", (capa.width + 200, capa.height + 200), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([30, 50, halo.width - 30, halo.height - 30], fill=BLUE + (80,))
        halo = halo.filter(ImageFilter.GaussianBlur(50))
        _poner(fr, halo, cx - halo.width // 2, cy - halo.height // 2, alfa)
        _poner(fr, capa, cx - capa.width // 2, cy - capa.height // 2 + 6 * math.sin(t_rel * 1.8), alfa)
    else:
        z = 1.0 - 0.1 * p                                                    # ventana que se acerca despacio
        ancho, alto = int(CAJA[0] / 1.0 * (z + 0.02)), int(CAJA[1] / 1.0 * (z + 0.02))
        ancho, alto = min(ancho, im.width), min(alto, im.height)
        x0 = int((im.width - ancho) * (0.5 - 0.15 * p))
        y0 = (im.height - alto) // 2
        corte = im.crop((x0, y0, x0 + ancho, y0 + alto)).resize(CAJA, Image.BILINEAR)
        mascara = Image.new("L", CAJA, 0)
        ImageDraw.Draw(mascara).rounded_rectangle([0, 0, CAJA[0] - 1, CAJA[1] - 1], 36, fill=255)
        capa = corte.convert("RGBA")
        capa.putalpha(mascara)
        _poner(fr, capa, cx - CAJA[0] // 2, Y_IMAGEN, alfa)


def _dibujar_escena(fr, e, rel, alfa):
    """Dibuja el visual de una escena en su hueco: gráfico animado o imagen en movimiento."""
    esc = e["esc"]
    if esc.get("grafico"):
        capa = grafico(esc["grafico"], esc.get("params", {}), rel, e["dur"] + PAUSA)
        _poner(fr, capa, (W - capa.width) // 2, Y_IMAGEN, alfa)
    else:
        _componer_imagen(fr, *e["imagen"], rel, e["dur"], alfa)


def _tarjeta_final(lineas=None):
    capa = Image.new("RGBA", (W, CAJA[1]), (0, 0, 0, 0))
    y = 90
    a, b = lineas or ("Más curiosidades de informática", "Lunes, miércoles y viernes")
    for texto, tam, color in ((a, 54, BLANCO), (b, 38, (170, 188, 218))):
        t = _capa_texto(texto, font("Bold" if tam > 40 else "Medium", tam), color)
        capa.alpha_composite(t, ((W - t.width) // 2, y))
        y += 90
    cta = _capa_cta()
    capa.alpha_composite(cta, ((W - cta.width) // 2, y + 70))
    return capa


def _trozos(palabras, max_pal=3, max_car=22):
    """Agrupa las palabras habladas en subtítulos cortos."""
    trozos, actual = [], []
    for ini, d, txt in palabras:
        if actual and (len(actual) >= max_pal or len(" ".join(p[2] for p in actual + [(0, 0, txt)])) > max_car
                       or actual[-1][2].endswith((".", "?", "!", ":", ",", ";"))):
            trozos.append(actual)
            actual = []
        actual.append((ini, d, txt))
    if actual:
        trozos.append(actual)
    return trozos


def _capa_trozo(trozo, resaltada):
    f = font("Bold", 76)
    textos = [p[2] for p in trozo]
    anchos = [f.getlength(t + " ") / S for t in textos]
    total = int(sum(anchos)) + 24
    im = Image.new("RGBA", (total * S, 120 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 12
    for i, t in enumerate(textos):
        color = BLUE if i == resaltada else BLANCO
        d.text((x * S + 3 * S, 14 * S + 4 * S), t, font=f, fill=(0, 0, 0, 170))          # sombra
        d.text((x * S, 14 * S), t, font=f, fill=color)
        x += anchos[i]
    return im.resize((total, 120), Image.LANCZOS)


# ---------- Montaje ----------
def _mezclar_audio(wavs, pausas, musica, ruta_wav, dur_total, inicio_musica=10.0, volumen_musica=0.11):
    sr = 44100
    voz = np.zeros(int((dur_total + 0.2) * sr), dtype=np.float32)
    t = 0.0
    for wv, pausa in zip(wavs, pausas):
        with wave.open(str(wv)) as w:
            d = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        i = int(t * sr)
        voz[i:i + len(d)] += d[:len(voz) - i]
        t += len(d) / sr + pausa
    mezcla = np.stack([voz, voz], axis=1)
    if musica:
        tmp = Path(ruta_wav).with_name("musica_tmp.wav")
        subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-ss", str(inicio_musica), "-t", str(dur_total + 0.2), "-i", str(musica),
                        "-ar", str(sr), "-ac", "2", str(tmp)], check=True)
        with wave.open(str(tmp)) as w:
            m = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32).reshape(-1, 2) / 32768
        tmp.unlink(missing_ok=True)
        n = min(len(m), len(mezcla))
        mezcla[:n] += m[:n] * volumen_musica
    n = len(mezcla)
    env = np.minimum(np.arange(n) / sr / 0.1, 1) * np.minimum((n / sr - np.arange(n) / sr) / 1.0, 1)
    mezcla *= env[:, None]
    pico = np.max(np.abs(mezcla)) or 1.0
    mezcla = np.tanh(mezcla / pico * 1.1) * 0.85
    with wave.open(str(ruta_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((mezcla * 32767).astype("<i2").tobytes())


def resolver_imagen(nombre, id_video):
    """Busca la imagen en el catálogo de assets o en la carpeta compartida de la otra IA."""
    cat = indice(cargar_catalogo())
    if nombre in cat:
        return cat[nombre].ruta
    for base in (CARPETA_IMAGENES / id_video, CARPETA_IMAGENES / "biblioteca", CARPETA_IMAGENES):
        if (base / nombre).exists():
            return base / nombre
    if CARPETA_IMAGENES.exists():                      # entregada en la carpeta de otro vídeo: sirve igual
        for ruta in CARPETA_IMAGENES.rglob(nombre):
            return ruta
    raise FileNotFoundError(f"No encuentro la imagen «{nombre}» (catálogo ni carpeta compartida).")


def imagen_de_escena(esc, id_video):
    """Imagen definitiva de la escena o, mientras la otra IA no la entrega, la provisional (un asset que ya tenemos)."""
    try:
        return resolver_imagen(esc["imagen"], id_video), False
    except FileNotFoundError:
        if not esc.get("provisional"):
            raise
        return resolver_imagen(esc["provisional"], id_video), True


def imagenes_pendientes(espec):
    """Imágenes definitivas que la otra IA aún no ha entregado: [(archivo, escena)]."""
    pendientes = []
    for i, esc in enumerate(espec["escenas"], 1):
        if esc.get("imagen") and not esc.get("grafico"):
            try:
                resolver_imagen(esc["imagen"], espec["id"])
            except FileNotFoundError:
                pendientes.append((esc["imagen"], i))
    return pendientes


# ---------- Escenas con trozos de vídeo (especiales) ----------
CARPETA_TRAILERS = Path(os.environ.get("TRAILERS_DIR") or r"C:\Users\xosu1\GarageVI Script\trailers")


class _LectorClip:
    """Lee un trozo de vídeo apaisado como fotogramas verticales (recorte central con un suave desplazamiento lateral)."""

    def __init__(self, ruta, inicio, dur, pan=(0.35, 0.65), recorte=(0.8, 0.1)):
        x0, x1 = pan
        alto, desde = recorte                    # quita las franjas negras de arriba y abajo del tráiler
        vf = f"crop=iw:ih*{alto}:0:ih*{desde},scale=-2:{H},crop={W}:{H}:'(iw-{W})*({x0}+({x1}-{x0})*t/{max(dur, 0.1)})':0"
        self.p = subprocess.Popen([_ffmpeg(), "-loglevel", "error", "-ss", str(inicio), "-t", str(dur), "-i", str(ruta), "-vf", vf,
                                   "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.tam, self.ultimo = W * H * 3, None

    def siguiente(self):
        b = self.p.stdout.read(self.tam)
        if len(b) == self.tam:
            self.ultimo = Image.frombytes("RGB", (W, H), b)
        return self.ultimo

    def cerrar(self):
        try:
            self.p.kill()
            self.p.stdout.close()
        except OSError:
            pass


def _adornos_clip(insignia):
    """Capas fijas sobre el vídeo: degradados para leer el texto, logo, insignia y pie de marca."""
    y = np.arange(H, dtype=np.float32)[:, None]
    alfa = np.maximum(165 * np.clip(1 - y / 560, 0, 1), 215 * np.clip((y - 980) / 700, 0, 1))
    velos = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), np.broadcast_to(alfa, (H, W)).astype(np.uint8)]), "RGBA")
    logo = _lockup(Image.open(LOGO_OSCURO).convert("RGBA"), mw=190, tw=300, gap=14)
    logo = logo.resize((logo.width // S, logo.height // S), Image.LANCZOS)
    capas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    capas.alpha_composite(logo, ((W - logo.width) // 2, 130))
    if insignia:
        f = font("Bold", 36)
        ancho = int(f.getlength(insignia) / S) + 70
        pill = Image.new("RGBA", (ancho * S, 76 * S), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle([0, 0, ancho * S, 76 * S], 38 * S, fill=(255, 70, 160, 235))
        ImageDraw.Draw(pill).text((ancho * S // 2, 38 * S), insignia, font=f, fill=(255, 255, 255), anchor="mm")
        pill = pill.resize((ancho, 76), Image.LANCZOS)
        capas.alpha_composite(pill, ((W - ancho) // 2, 360))
    pie = _capa_texto("JM TECH · Servicio técnico en Murcia", font("Medium", 28), (205, 220, 245))
    capas.alpha_composite(pie, ((W - pie.width) // 2, Y_PIE))
    velos.alpha_composite(capas)
    return velos


def _fotograma_clip(e, rel, adornos, escena_grafico):
    esc = e["esc"]["clip"]
    if e.get("lector") is None:
        ruta = Path(esc["archivo"])
        ruta = ruta if ruta.is_absolute() else CARPETA_TRAILERS / ruta
        e["lector"] = _LectorClip(ruta, esc["inicio"], e["dur"] + PAUSA + 1.5, tuple(esc.get("pan", (0.35, 0.65))), tuple(esc.get("recorte", (0.8, 0.1))))
    f = e["lector"].siguiente() or Image.new("RGB", (W, H))
    fr = f.convert("RGBA")
    fr.alpha_composite(adornos)
    if escena_grafico:
        capa = grafico(e["esc"]["grafico"], e["esc"].get("params", {}), rel, e["dur"] + PAUSA)
        _poner(fr, capa, (W - capa.width) // 2, 560, _suave(rel / 0.3))
    a = _suave(rel / 0.25)
    return fr if a >= 1 else Image.blend(Image.new("RGBA", fr.size, (0, 0, 0, 255)), fr, a)


def generar_video(espec, salida, musica=None, inicio_musica=10.0, sintetizador=sintetizar_escena, previsualizar=None):
    """Monta el MP4 de una curiosidad. Devuelve (ruta, duración_s)."""
    fallos = problemas_espec(espec)
    if fallos:
        raise ValueError("El guion no pasa las comprobaciones: " + "; ".join(fallos))
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    tmp = salida.with_suffix(".tmp")
    tmp.mkdir(exist_ok=True)

    # 1) voz por escena
    escenas, t = [], 0.0
    for i, esc in enumerate(espec["escenas"]):
        wav, palabras, dur = sintetizador(esc["texto"], tmp / f"voz_{i:02d}")
        escenas.append(dict(esc=esc, wav=wav, palabras=palabras, dur=dur, ini=t, trozos=_trozos(palabras)))
        t += dur + PAUSA
    total = t + 0.4
    # 2) audio
    audio = tmp / "audio.wav"
    _mezclar_audio([e["wav"] for e in escenas], [PAUSA] * len(escenas), musica, audio, total, inicio_musica)

    # 3) imágenes y capas
    fondo = _fondo_video(espec["titulo_pantalla"])
    for e in escenas:
        esc = e["esc"]
        e["imagen"] = _imagen_escena(imagen_de_escena(esc, espec["id"])[0]) if esc.get("imagen") and not esc.get("grafico") else None
        e["capas"] = [[_capa_trozo(tr, k) for k in range(len(tr))] for tr in e["trozos"]]
    final = _tarjeta_final(espec.get("cierre_lineas"))
    adornos = _adornos_clip(espec.get("insignia")) if any(x["esc"].get("clip") for x in escenas) else None
    ultimo = -1

    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-level", "4.1",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest", "-movflags", "+faststart",
           str(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(total * FPS)
    muestras = {int((e["ini"] + e["dur"] * 0.8) * FPS) for e in escenas} if previsualizar else set()
    if previsualizar:
        Path(previsualizar).mkdir(parents=True, exist_ok=True)
    try:
        for i in range(n):
            tt = i / FPS
            idx = max(k for k, e in enumerate(escenas) if e["ini"] <= tt)
            e = escenas[idx]
            rel = tt - e["ini"]
            if idx != ultimo:
                if ultimo >= 0 and escenas[ultimo].get("lector"):
                    escenas[ultimo]["lector"].cerrar()
                ultimo = idx
            # imagen o tarjeta final, con fundido de entrada
            alfa = _suave(rel / 0.3)
            if e["esc"].get("clip"):
                fr = _fotograma_clip(e, rel, adornos, bool(e["esc"].get("grafico")))
            elif e["esc"].get("cierre"):
                fr = fondo.copy()
                _poner(fr, final, 0, Y_IMAGEN, alfa)
            else:
                fr = fondo.copy()
                if idx > 0 and rel < 0.3 and not escenas[idx - 1]["esc"].get("cierre") and not escenas[idx - 1]["esc"].get("clip"):  # fundido cruzado
                    _dibujar_escena(fr, escenas[idx - 1], escenas[idx - 1]["dur"] + rel, 1 - alfa)
                _dibujar_escena(fr, e, rel, alfa)
            # subtítulo: el trozo que se está diciendo, con la palabra actual en azul
            for tr, capas in zip(e["trozos"], e["capas"]):
                if tr[0][0] - 0.05 <= rel < tr[-1][0] + tr[-1][1] + 0.18:
                    k = max(j for j, p in enumerate(tr) if p[0] <= rel + 0.02) if tr[0][0] <= rel else 0
                    capa = capas[k]
                    fr.alpha_composite(capa, ((W - capa.width) // 2, Y_SUB))
                    break
            # barra de progreso
            ImageDraw.Draw(fr).rounded_rectangle([90, Y_BARRA, 90 + int((W - 180) * tt / total), Y_BARRA + 8], 4, fill=BLUE)
            rgb = fr.convert("RGB")
            if i in muestras:
                rgb.save(Path(previsualizar) / f"curiosidad_{i:05d}.png")
            proc.stdin.write(rgb.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    for f in tmp.glob("*"):
        f.unlink(missing_ok=True)
    tmp.rmdir()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg no pudo crear el vídeo.")
    return salida, total


# ---------- Banco: vídeos montados sin fecha asignada ----------
def montar_banco(carpeta, musica_dir, avisar=print):
    """Monta los vídeos que existen como ficha pero aún no están en el plan. Se guardan en carpeta/banco/ sin fecha."""
    carpeta = Path(carpeta)
    (carpeta / "banco").mkdir(parents=True, exist_ok=True)
    ruta_banco = carpeta / "banco.json"
    banco = {v["id"]: v for v in json.loads(ruta_banco.read_text(encoding="utf-8"))["videos"]} if ruta_banco.exists() else {}
    plan_ids = {p["id"] for p in json.loads((RAIZ / "contenido" / "plan_curiosidades.json").read_text(encoding="utf-8"))["plan"]}
    pistas = sorted(Path(musica_dir).glob("*.mp3")) if musica_dir and Path(musica_dir).exists() else []
    hechos, esperando = [], []
    for k, ruta in enumerate(sorted(CARPETA_ESPECS.glob("*.json"))):
        espec = cargar_espec(ruta)
        if espec["id"] in plan_ids or espec["id"] in {v["id"] for v in cargar_cola(carpeta)}:
            continue
        fallos = problemas_espec(espec)
        if fallos:
            avisar(f"{espec['id']}: el guion tiene problemas: {'; '.join(fallos)}")
            continue
        try:
            h = huella(espec)
        except FileNotFoundError as e:
            esperando.append((espec["id"], str(e)))
            continue
        previo = banco.get(espec["id"])
        if previo and previo.get("huella") == h and (carpeta / previo["video"]).exists():
            continue
        pista, inicio = (pistas[(k * 5) % len(pistas)], float(8 + (k * 11) % 30)) if pistas else (None, 10.0)
        avisar(f"Montando {espec['id']}")
        salida = carpeta / "banco" / f"{espec['id']}.mp4"
        generar_video(espec, salida, pista, inicio)
        banco[espec["id"]] = {"id": espec["id"], "video": f"banco/{salida.name}", "titulo": espec["titulo"], "serie": espec.get("serie", ""),
                              "pie": construir_descripcion(espec), "huella": h}
        ruta_banco.write_text(json.dumps({"videos": sorted(banco.values(), key=lambda v: v["id"])}, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        hechos.append(espec["id"])
    return hechos, esperando


# ---------- Cola y publicación ----------
def cargar_cola(carpeta) -> list[dict]:
    ruta = Path(carpeta) / "cola.json"
    return json.loads(ruta.read_text(encoding="utf-8"))["videos"] if ruta.exists() else []


def guardar_cola(carpeta, videos) -> None:
    ruta = Path(carpeta) / "cola.json"
    videos = sorted(videos, key=lambda v: v["fecha"])
    ruta.write_text(json.dumps({"videos": videos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def encolar(espec, fecha, carpeta, musica=None, inicio_musica=10.0, extra=None):
    """Crea el vídeo, lo guarda en la carpeta de la cola y lo anota para publicarlo en `fecha` (AAAA-MM-DD)."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta, dur = generar_video(espec, carpeta / f"{espec['id']}.mp4", musica, inicio_musica)
    videos = [v for v in cargar_cola(carpeta) if v["id"] != espec["id"]]
    videos.append({"fecha": fecha, "id": espec["id"], "video": ruta.name, "pie": construir_descripcion(espec), **(extra or {})})
    guardar_cola(carpeta, videos)
    return ruta, dur


VERSION_MOTOR = "1"          # súbela si cambia el aspecto del vídeo: todos se montan de nuevo


def huella(espec) -> str:
    """Resumen del guion y de las imágenes usadas: si no cambia, no hace falta montar el vídeo otra vez."""
    h = hashlib.sha1(json.dumps(espec, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    h.update(VERSION_MOTOR.encode())
    for esc in espec["escenas"]:
        if esc.get("imagen") and not esc.get("grafico"):
            ruta, provisional = imagen_de_escena(esc, espec["id"])
            h.update(f"{ruta.name}:{ruta.stat().st_size}:{provisional}".encode())
    return h.hexdigest()[:16]


def montar_plan(carpeta, musica_dir, hasta=None, provisional=False, avisar=print):
    """Monta y encola los vídeos del plan cuyas imágenes ya están (o, con `provisional`, usando las provisionales).

    Solo repite los que han cambiado desde la última vez. Devuelve (montados, esperando)."""
    plan = json.loads((RAIZ / "contenido" / "plan_curiosidades.json").read_text(encoding="utf-8"))["plan"]
    pistas = sorted(Path(musica_dir).glob("*.mp3")) if musica_dir and Path(musica_dir).exists() else []
    cola = {v["id"]: v for v in cargar_cola(carpeta)}
    montados, esperando = [], []
    for k, p in enumerate(plan):
        if hasta and p["fecha"] > hasta:
            break
        ruta_espec = CARPETA_ESPECS / f"{p['id']}.json"
        if not ruta_espec.exists():
            continue
        espec = cargar_espec(ruta_espec)
        fallos = problemas_espec(espec)
        if fallos:
            avisar(f"{p['id']}: el guion tiene problemas: {'; '.join(fallos)}")
            continue
        pendientes = imagenes_pendientes(espec)
        try:
            h = huella(espec)
        except FileNotFoundError as e:
            esperando.append((p["fecha"], p["id"], str(e)))
            continue
        if pendientes and not provisional:
            esperando.append((p["fecha"], p["id"], "faltan " + ", ".join(a for a, _ in pendientes)))
            continue
        previo = cola.get(p["id"])
        if previo and previo.get("huella") == h and previo.get("fecha") == p["fecha"] and (Path(carpeta) / previo["video"]).exists():
            continue
        pista, inicio = (pistas[(k * 7) % len(pistas)], float(8 + (k * 13) % 30)) if pistas else (None, 10.0)
        avisar(f"Montando {p['fecha']} · {p['id']} ({'definitivo' if not pendientes else 'con imágenes provisionales'})")
        encolar(espec, p["fecha"], carpeta, pista, inicio, {"huella": h, "definitivo": not pendientes})
        montados.append((p["fecha"], p["id"]))
    return montados, esperando


def _publicar_url_publica(ruta, nombre):
    """Copia el vídeo a una carpeta pública del repositorio y lo sube, para que Instagram pueda
    descargarlo si la subida directa falla (ver `ClienteInstagram.publicar_reel`). Solo actúa dentro de
    GitHub Actions (nunca en local ni en los tests, para no tocar el repositorio real). Nunca lanza: si
    algo falla (sin red, sin permiso de escritura), se sigue sin dirección de respaldo."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        destino = RAIZ / "salida_curiosidades" / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(Path(ruta).read_bytes())
        subprocess.run(["git", "add", "--", str(destino)], cwd=RAIZ, check=True, capture_output=True)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ).returncode != 0:
            subprocess.run(["git", "commit", "-m", f"chore: vídeo público para Instagram ({nombre})"],
                           cwd=RAIZ, check=True, capture_output=True)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=RAIZ, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=RAIZ, check=True, capture_output=True)
        repo = os.environ.get("GITHUB_REPOSITORY", "Xosu10/jmtech-instagram")
        return f"https://raw.githubusercontent.com/{repo}/main/salida_curiosidades/{nombre}"
    except Exception as e:
        print(f"AVISO: no se pudo preparar la dirección pública de respaldo ({e}).")
        return None


def publicar_curiosidad(video, pie, id_video, fecha, *, dry_run=False, cliente=None, ruta_estado=None, ahora_utc=None,
                        cfg=None, prueba=False, tipo="curiosidad", clave_hora="hora_curiosidad"):
    """Sube el vídeo como reel y lo anota en el estado (tipo «curiosidad» o «noticias»). No repite si ya está en Instagram."""
    from datetime import datetime
    from . import estado as est
    from .instagram import ClienteInstagram
    from .publicador import (AVISO_RETRASO_MIN, IG_USER_ID, UTC, ahora_madrid, retraso_min, ya_en_instagram)
    from .calendario import cargar_config

    ahora_utc = ahora_utc or datetime.now(UTC)
    cfg = cfg or cargar_config()
    ruta = Path(video)
    print(f"{tipo.capitalize()} listo: {id_video} ({ruta.stat().st_size / 1e6:.1f} MB)")
    if dry_run:
        print(f"PRUEBA EN SECO: no se llama a Instagram. Pie:\n---\n{pie}\n---")
        return None
    cliente = cliente or ClienteInstagram(os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID", IG_USER_ID))
    previo = ya_en_instagram(cliente, pie, ahora_utc, "reel")
    if previo:
        media_id, permalink = previo["id"], previo.get("permalink")
        print("Instagram ya tiene este vídeo; se anota sin repetirlo.")
    else:
        video_url = None if prueba else _publicar_url_publica(ruta, f"{id_video}.mp4")
        media_id = cliente.publicar_reel(ruta, pie, video_url=video_url)
        permalink = cliente.permalink(media_id)
    from .facebook import compartir_en_facebook
    fb = None if previo else compartir_en_facebook(cfg, ruta, pie)
    retraso = 0 if prueba else retraso_min(ahora_madrid(ahora_utc), cfg, clave_hora)
    if retraso > AVISO_RETRASO_MIN:
        print(f"::warning::El vídeo ({tipo}) salió con {retraso} minutos de retraso.")
    estado = est.cargar(ruta_estado)
    registro = est.registrar(estado, fecha=fecha, tema=id_video, estilo=tipo, variante=0, imagen=ruta.name,
                             asset=tipo, resultado="publicado", prueba=False, tipo=tipo,
                             media_id=media_id, permalink=permalink,
                             publicado_utc=ahora_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), retraso_min=retraso, **(fb or {}))
    est.guardar(estado, ruta_estado)
    est.generar_informe(estado, ahora_utc)
    print(f"PUBLICADO ({tipo}): {permalink}")
    return registro


def curiosidad_hoy(carpeta, ahora_utc=None, *, dry_run=False, ignorar_hora=False, cfg=None, estado=None, cliente=None,
                   ruta_estado=None, tipo="curiosidad", clave_hora="hora_curiosidad", clave_ajuste="curiosidades", subcarpeta=""):
    """Publica el vídeo de la cola que toca hoy (cada día a las 17:00 de Madrid, también fines de semana)."""
    from datetime import datetime
    from . import estado as est
    from .calendario import cargar_config
    from .publicador import UTC, ahora_madrid, en_ventana

    ahora_utc = ahora_utc or datetime.now(UTC)
    cfg = cfg or cargar_config()
    if cfg.get("pausado") or not cfg.get(clave_ajuste, True):
        print(f"No hay {tipo}: el sistema está pausado.")
        return None
    ahora = ahora_madrid(ahora_utc)
    estado = est.cargar(ruta_estado) if estado is None else estado
    if not ignorar_hora and not en_ventana(ahora, cfg, clave_hora):
        print(f"No hay {tipo} ahora: fuera de la ventana de las {cfg[clave_hora]}.")
        return None
    hoy = ahora.date().isoformat()
    if any(p.get("tipo") == tipo and p["fecha"] == hoy and p.get("resultado") == "publicado" for p in estado["publicaciones"]):
        print(f"No hay {tipo} ahora: ya se publicó hoy.")
        return None
    carpeta = Path(carpeta) / subcarpeta
    toca = [v for v in cargar_cola(carpeta) if v["fecha"] == hoy]
    if not toca:
        print(f"No hay {tipo} ahora: no hay ningún vídeo en la cola para {hoy}.")
        return None
    v = toca[0]
    return publicar_curiosidad(carpeta / v["video"], v["pie"], v["id"], hoy, dry_run=dry_run, cliente=cliente,
                               ruta_estado=ruta_estado, ahora_utc=ahora_utc, cfg=cfg, tipo=tipo, clave_hora=clave_hora)


def noticias_hoy(carpeta, ahora_utc=None, **kw):
    """Publica «Las noticias de la semana» si hoy toca (domingos a las 19:00 de Madrid; cola propia en carpeta/noticias)."""
    return curiosidad_hoy(carpeta, ahora_utc, tipo="noticias", clave_hora="hora_noticias", clave_ajuste="noticias",
                          subcarpeta="noticias", **kw)


def main():
    p = argparse.ArgumentParser(prog="jmtech.curiosidad")
    p.add_argument("orden", choices=["render", "comprobar", "encolar", "publicar", "hoy", "noticias", "pendientes", "montar", "banco"])
    p.add_argument("--musica-dir", default="", help="montar: carpeta con las canciones (mp3)")
    p.add_argument("--hasta", default="", help="montar: última fecha del plan que se monta (AAAA-MM-DD)")
    p.add_argument("--provisional", action="store_true", help="montar: usar imágenes provisionales si faltan las definitivas")
    p.add_argument("espec", nargs="?")
    p.add_argument("--salida", default="curiosidad.mp4")
    p.add_argument("--musica", default="")
    p.add_argument("--inicio-musica", type=float, default=10.0)
    p.add_argument("--previsualizar", default="")
    p.add_argument("--fecha", default="", help="encolar: día de publicación (AAAA-MM-DD); publicar: día que se anota (por defecto hoy)")
    p.add_argument("--carpeta", default=os.environ.get("CURIOSIDADES_COLA", ""), help="carpeta de la cola (cola.json y los mp4)")
    p.add_argument("--video", default="", help="publicar: vídeo ya creado")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ignorar-hora", action="store_true")
    a = p.parse_args()
    from .instagram import ErrorInstagram, ocultar
    try:
        if a.orden == "hoy":
            curiosidad_hoy(a.carpeta, dry_run=a.dry_run, ignorar_hora=a.ignorar_hora)
            return 0
        if a.orden == "noticias":
            noticias_hoy(a.carpeta, dry_run=a.dry_run, ignorar_hora=a.ignorar_hora)
            return 0
        if a.orden == "banco":
            hechos, esperando = montar_banco(a.carpeta, a.musica_dir)
            print(f"Montados ahora: {len(hechos)}")
            for id_video, motivo in esperando:
                print(f"  espera · {id_video}: {motivo}")
            return 0
        if a.orden == "montar":
            if not a.carpeta:
                p.error("montar necesita --carpeta")
            montados, esperando = montar_plan(a.carpeta, a.musica_dir, a.hasta or None, a.provisional)
            print(f"Montados ahora: {len(montados)}")
            for fecha, id_video, motivo in esperando:
                print(f"  espera · {fecha} · {id_video}: {motivo}")
            return 0
        if a.orden == "pendientes":
            hay = False
            for ruta in sorted(CARPETA_ESPECS.glob("*.json")):
                e = cargar_espec(ruta)
                for archivo, escena in imagenes_pendientes(e):
                    hay = True
                    print(f"{e['id']} · escena {escena}: falta {archivo}")
            print("Todas las imágenes definitivas están entregadas." if not hay else "")
            return 0
        if not a.espec:
            p.error(f"{a.orden} necesita el archivo del guion")
        espec = cargar_espec(a.espec)
        if a.orden == "comprobar":
            fallos = problemas_espec(espec)
            print("Guion correcto." if not fallos else "Problemas:\n- " + "\n- ".join(fallos))
        elif a.orden == "render":
            ruta, dur = generar_video(espec, a.salida, a.musica or None, a.inicio_musica, previsualizar=a.previsualizar or None)
            print(f"Vídeo creado: {ruta} ({dur:.0f} s, {ruta.stat().st_size / 1e6:.1f} MB)")
        elif a.orden == "encolar":
            if not (a.fecha and a.carpeta):
                p.error("encolar necesita --fecha y --carpeta")
            ruta, dur = encolar(espec, a.fecha, a.carpeta, a.musica or None, a.inicio_musica)
            print(f"En cola para {a.fecha}: {ruta} ({dur:.0f} s)")
        elif a.orden == "publicar":
            from datetime import date
            fallos = problemas_espec(espec)
            if fallos:
                p.error("El guion no pasa las comprobaciones: " + "; ".join(fallos))
            publicar_curiosidad(a.video, construir_descripcion(espec), espec["id"], a.fecha or date.today().isoformat(),
                                dry_run=a.dry_run, prueba=True)
    except ErrorInstagram as e:
        print(f"::error::{ocultar(e)}")
        tecnico = getattr(e, "tecnico", "")
        if tecnico:
            print(f"Detalle técnico: {tecnico}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
