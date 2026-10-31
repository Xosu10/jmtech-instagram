"""Catálogo de assets de imagen y elección reproducible del asset de cada publicación."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from .base import RAIZ

CARPETA_ASSETS = RAIZ / "assets" / "ilustraciones"
RUTA_CATALOGO = CARPETA_ASSETS / "catalogo.json"
SUBCARPETA = {"aislado": "aislados", "ambiente": "ambiente", "fondo": "fondos", "flatlay": "flatlay"}
DIBUJO = "dibujo"       # ilustración dibujada con Pillow (plan B)


@dataclass(frozen=True)
class Asset:
    archivo: str
    tipo: str
    categoria: str
    temas: tuple
    estilos: tuple
    ruta: Path


def cargar_catalogo(ruta: Path | None = None) -> list[Asset]:
    with open(ruta or RUTA_CATALOGO, encoding="utf-8") as f:
        entradas = json.load(f)["entradas"]
    return [Asset(e["archivo"], e["tipo"], e["categoria"], tuple(e["temas"]), tuple(e["estilos_compatibles"]),
                  CARPETA_ASSETS / SUBCARPETA[e["tipo"]] / e["archivo"])
            for e in entradas if e["aprobado"]]


def indice(catalogo: list[Asset]) -> dict[str, Asset]:
    return {a.archivo: a for a in catalogo}


class Selector:
    """Elige el asset de cada publicación, en orden de fechas y de forma reproducible.

    - Nunca el mismo asset dos días seguidos.
    - Cuando un tema se repite, cambia el asset (si hay al menos dos opciones).
    - Si un tema tiene menos de 2 assets para ese estilo, la ilustración dibujada hace de segunda opción.
    """

    def __init__(self, catalogo: list[Asset], semilla):
        self.catalogo, self.semilla = sorted(catalogo, key=lambda a: a.archivo), semilla
        self.ultimo_global, self.ultimo_tema, self.contador = None, {}, {}

    def candidatos(self, tema_id: str, estilo: str) -> list[str]:
        c = [a.archivo for a in self.catalogo if tema_id in a.temas and estilo in a.estilos and a.tipo in ("aislado", "ambiente")]
        return c + [DIBUJO] if len(c) < 2 else c

    def elegir(self, tema_id: str, estilo: str) -> str:
        cands = self.candidatos(tema_id, estilo)
        orden = list(cands)
        random.Random(f"{self.semilla}-{tema_id}").shuffle(orden)
        n = self.contador.get(tema_id, 0)
        self.contador[tema_id] = n + 1
        giro = n % len(orden)
        rot = orden[giro:] + orden[:giro]
        previo_tema = self.ultimo_tema.get(tema_id)
        elegido = (next((c for c in rot if c != self.ultimo_global and c != previo_tema), None)
                   or next((c for c in rot if c != self.ultimo_global), None) or rot[0])
        self.ultimo_global = None if elegido == DIBUJO else elegido
        self.ultimo_tema[tema_id] = elegido
        return elegido
