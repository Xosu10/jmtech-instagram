"""Genera unas pruebas rápidas: python -m jmtech.prueba_rapida [tema_id ...]"""
import sys
from pathlib import Path

from .base import RAIZ
from .contenido import indice_temas
from .render import ESTILOS, guardar_jpeg, renderizar

if __name__ == "__main__":
    temas = indice_temas()
    ids = sys.argv[1:] or list(temas)
    salida = RAIZ / "previsualizacion" / "pruebas"
    for tid in ids:
        for e in ESTILOS:
            img, info = renderizar(temas[tid], e)
            guardar_jpeg(img, salida / f"{tid}_{e}.jpg")
            print(tid, e, info["avisos"] or "ok", "titulo", info["titulo_size"], "puntos", info["puntos_size"])
