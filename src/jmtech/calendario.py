"""Calendario y rotación: qué tema, estilo y pie de foto toca cada día (reproducible)."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .base import RAIZ
from .contenido import cargar_temas

RUTA_CONFIG = RAIZ / "config" / "calendario.json"
ESTILOS = ("A", "B", "C")


@dataclass(frozen=True)
class Publicacion:
    fecha: date
    tipo: str              # "rotacion" o "campana"
    tema_id: str | None    # None en las campañas
    estilo: str
    variante: int          # índice del pie de foto
    ciclo: int             # nº de ciclo de temas (0, 1, 2...)
    campana_id: str | None = None


def cargar_config(ruta: Path | None = None) -> dict:
    with open(ruta or RUTA_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_inicio"] = date.fromisoformat(cfg["fecha_inicio"])
    cfg["_festivos"] = {date.fromisoformat(d) for d in cfg.get("dias_sin_publicar", [])}
    cfg["_campanas"] = {date.fromisoformat(c["fecha"]): c for c in cfg.get("campanas", [])}
    return cfg


def es_dia_publicable(dia: date, cfg: dict) -> bool:
    return dia.weekday() < 5 and dia >= cfg["_inicio"] and dia not in cfg["_festivos"]


def dias_publicables(hasta: date, cfg: dict):
    dia = cfg["_inicio"]
    while dia <= hasta:
        if es_dia_publicable(dia, cfg):
            yield dia
        dia += timedelta(days=1)


def _barajar(elementos, semilla, numero, evitar_primero):
    """Orden reproducible de un ciclo. El primero nunca coincide con `evitar_primero`."""
    lista = list(elementos)
    random.Random(f"{semilla}-{numero}").shuffle(lista)
    if evitar_primero is not None and len(lista) > 1 and lista[0] == evitar_primero:
        lista[0], lista[1] = lista[1], lista[0]
    return lista


def _ciclos(elementos, semilla):
    """Genera ciclos sin fin: no repite hasta agotar la lista, ni en la unión de dos ciclos."""
    anterior, n = None, 0
    while True:
        ciclo = _barajar(elementos, semilla, n, anterior)
        yield n, ciclo
        anterior, n = ciclo[-1], n + 1


def planificar(hasta: date, cfg: dict | None = None, temas: list[dict] | None = None) -> list[Publicacion]:
    """Plan desde `fecha_inicio` hasta `hasta` (incluida). Las campañas no consumen turno de la rotación."""
    cfg = cfg or cargar_config()
    ids = [t["id"] for t in (temas or cargar_temas())]
    temas_it = ((n, t) for n, ciclo in _ciclos(ids, cfg["semilla"]) for t in ciclo)
    estilos_it = (e for _, ciclo in _ciclos(ESTILOS, cfg["semilla"] + 7) for e in ciclo)
    plan = []
    for dia in dias_publicables(hasta, cfg):
        estilo = next(estilos_it)
        if dia in cfg["_campanas"]:
            camp = cfg["_campanas"][dia]
            plan.append(Publicacion(dia, "campana", None, estilo, 0, -1, camp["id"]))
            continue
        ciclo, tema = next(temas_it)
        plan.append(Publicacion(dia, "rotacion", tema, estilo, ciclo, ciclo))
    return plan


def publicacion_del_dia(dia: date, cfg: dict | None = None) -> Publicacion | None:
    cfg = cfg or cargar_config()
    if not es_dia_publicable(dia, cfg):
        return None
    return planificar(dia, cfg)[-1]
