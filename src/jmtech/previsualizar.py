"""Previsualizaciones para revisar el diseño y los textos.

python -m jmtech.previsualizar hoja        -> hoja de contactos 11 temas x 3 estilos
python -m jmtech.previsualizar mes 2026 11 -> todos los días laborables de un mes
"""
from __future__ import annotations

import calendar
import html
import sys
from datetime import date

from PIL import Image, ImageDraw

from .assets import Selector, cargar_catalogo
from .assets import indice as indice_assets
from .base import RAIZ, font
from .calendario import cargar_config, planificar
from .contenido import cargar_temas, indice_temas, pie_de_foto
from .render import ESTILOS, guardar_jpeg, renderizar

SALIDA = RAIZ / "previsualizacion"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def hoja_contactos():
    temas = cargar_temas()
    destino = SALIDA / "hoja_contactos"
    catalogo = cargar_catalogo()
    nombres = indice_assets(catalogo)
    semilla = cargar_config()["semilla"]
    tw, th, margen, cab = 360, 450, 16, 64
    hoja = Image.new("RGB", (margen + len(temas) * (tw + margen), cab + 3 * (th + margen) + margen), (240, 244, 250))
    d = ImageDraw.Draw(hoja)
    avisos = []
    for i, t in enumerate(temas):
        x = margen + i * (tw + margen)
        d.text((x, 18), t["id"], font=font("Bold", 13), fill=(16, 22, 36))
        for j, e in enumerate(ESTILOS):
            cands = Selector(catalogo, semilla).candidatos(t["id"], e)
            elegido = next((c for c in cands if c != "dibujo"), "dibujo")       # en la hoja se prefiere el asset
            img, info = renderizar(t, e, nombres.get(elegido))
            guardar_jpeg(img, destino / f"{t['id']}_{e}.jpg")
            avisos += [f"{t['id']} {e}: {a}" for a in info["avisos"]]
            hoja.paste(img.resize((tw, th), Image.LANCZOS), (x, cab + j * (th + margen)))
    hoja.save(SALIDA / "hoja_contactos.jpg", quality=88)
    print("Hoja:", SALIDA / "hoja_contactos.jpg")
    print("Avisos de maquetación:", avisos or "ninguno")


def mes(anio, mes_n):
    cfg = cargar_config()
    ultimo = date(anio, mes_n, calendar.monthrange(anio, mes_n)[1])
    catalogo = cargar_catalogo()
    nombres = indice_assets(catalogo)
    plan = [p for p in planificar(ultimo, cfg, catalogo=catalogo) if p.fecha.month == mes_n and p.fecha.year == anio]
    temas = indice_temas()
    destino = SALIDA / f"{MESES[mes_n]}_{anio}"
    previstas = {p["fecha"]: p for p in cfg.get("campanas_previstas", [])}
    filas, avisos = [], []
    for p in plan:
        nota = ""
        if p.tipo == "campana":
            nota = f"Campaña: {p.campana_id}"
            continue
        t = temas[p.tema_id]
        img, info = renderizar(t, p.estilo, nombres.get(p.asset))
        avisos += [f"{p.fecha} {t['id']} {p.estilo}: {a}" for a in info["avisos"]]
        archivo = f"{p.fecha.isoformat()}.jpg"
        guardar_jpeg(img, destino / archivo)
        prev = previstas.get(p.fecha.isoformat())
        if prev:
            nota = f"⚠ Aquí está prevista: {prev['nombre']} (se sustituirá en la Fase 7)"
        filas.append((p, t, archivo, pie_de_foto(t, p.variante), nota))

    celdas = []
    for p, t, archivo, pie, nota in filas:
        celdas.append(
            f"<tr><td><img src='{archivo}' width='220'></td>"
            f"<td><b>{DIAS[p.fecha.weekday()]} {p.fecha.day}</b><br>{html.escape(t['nombre'])}<br>"
            f"Estilo {p.estilo} · pie nº {p.variante % len(t['pies_de_foto']) + 1} · imagen: {p.asset}"
            f"<br><i>{html.escape(nota)}</i></td>"
            f"<td><pre>{html.escape(pie)}</pre></td></tr>"
        )
    (destino / "indice.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>JM TECH · " + f"{MESES[mes_n]} {anio}</title>"
        "<style>body{font-family:Segoe UI,Arial;margin:24px;background:#f3f6fb}table{border-collapse:collapse}"
        "td{border:1px solid #ccd6e6;padding:10px;vertical-align:top;background:#fff}"
        "pre{white-space:pre-wrap;font-family:inherit;margin:0;max-width:520px}</style>"
        f"<h1>JM TECH · publicaciones de {MESES[mes_n]} {anio}</h1><table>" + "".join(celdas) + "</table>",
        encoding="utf-8",
    )
    resumen = [f"| {DIAS[p.fecha.weekday()][:3]} {p.fecha.day:02d} | {t['id']} | {p.estilo} | {p.variante % len(t['pies_de_foto']) + 1} |"
               for p, t, *_ in filas]
    (destino / "tabla.md").write_text("| Día | Tema | Estilo | Pie |\n|---|---|---|---|\n" + "\n".join(resumen) + "\n",
                                      encoding="utf-8")
    print("Mes:", destino / "indice.html", f"({len(filas)} publicaciones)")
    print("Avisos de maquetación:", avisos or "ninguno")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "hoja"
    if modo == "hoja":
        hoja_contactos()
    elif modo == "mes":
        mes(int(sys.argv[2]), int(sys.argv[3]))
    else:
        sys.exit("Uso: hoja | mes AAAA M")
