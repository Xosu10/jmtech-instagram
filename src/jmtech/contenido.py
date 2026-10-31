"""Banco de contenido: temas, textos y pies de foto (contenido/temas.json)."""
from __future__ import annotations

import json
from pathlib import Path

from .base import RAIZ

RUTA_TEMAS = RAIZ / "contenido" / "temas.json"


def cargar_temas(ruta: Path | None = None) -> list[dict]:
    with open(ruta or RUTA_TEMAS, encoding="utf-8") as f:
        return json.load(f)["temas"]


def indice_temas(ruta: Path | None = None) -> dict[str, dict]:
    return {t["id"]: t for t in cargar_temas(ruta)}


def pie_de_foto(tema: dict, variante: int) -> str:
    """Devuelve la variante `variante` del pie de foto (se da la vuelta si hay menos variantes)."""
    pies = tema["pies_de_foto"]
    return pies[variante % len(pies)]
