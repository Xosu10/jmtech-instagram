"""Registro de lo publicado (estado/publicaciones.json) e informe legible (ESTADO.md)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .base import RAIZ
from .calendario import cargar_config, planificar
from .contenido import indice_temas

RUTA_ESTADO = RAIZ / "estado" / "publicaciones.json"
RUTA_INFORME = RAIZ / "ESTADO.md"
ZONA = ZoneInfo("Europe/Madrid")
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def cargar(ruta: Path | None = None) -> dict:
    ruta = Path(ruta or RUTA_ESTADO)
    if not ruta.exists():
        return {"publicaciones": []}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar(estado: dict, ruta: Path | None = None) -> None:
    ruta = Path(ruta or RUTA_ESTADO)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publicado_el(estado: dict, dia: date, tipo: str = "post") -> dict | None:
    """Publicación regular de ese día y tipo ("post" o "reel"); las pruebas manuales no cuentan."""
    for p in estado["publicaciones"]:
        if (p["fecha"] == dia.isoformat() and not p.get("prueba") and p.get("resultado") == "publicado"
                and p.get("tipo", "post") == tipo):
            return p
    return None


def registrar(estado: dict, **campos) -> dict:
    estado["publicaciones"].append(campos)
    estado["publicaciones"].sort(key=lambda p: (p["fecha"], p.get("publicado_utc", "")))
    return campos


def generar_informe(estado: dict, ahora_utc: datetime | None = None, ruta: Path | None = None) -> str:
    ahora = (ahora_utc or datetime.now(ZoneInfo("UTC"))).astimezone(ZONA)
    cfg, temas = cargar_config(), indice_temas()
    hechas = [p for p in estado["publicaciones"] if p.get("resultado") == "publicado"]
    ultimas = sorted(hechas, key=lambda p: p.get("publicado_utc", ""), reverse=True)[:10]

    plan = [p for p in planificar(ahora.date() + timedelta(days=45), cfg) if p.fecha >= ahora.date()]
    ya_hoy = publicado_el(estado, ahora.date())
    proximas = [p for p in plan if not (ya_hoy and p.fecha == ahora.date())][:10]

    lineas = [
        "# Estado del publicador de Instagram",
        f"_Actualizado: {ahora:%Y-%m-%d %H:%M} (hora de Madrid)_",
        "",
        "## Resumen",
        f"- Sistema: {'⏸ **PAUSADO** (en `config/calendario.json`, `pausado`)' if cfg.get('pausado') else '✅ activo'}",
        "- Token de Instagram: no caduca (usuario del sistema). Si algún día falla, se genera otro y se guarda en el secreto `IG_ACCESS_TOKEN`.",
        f"- Publicaciones hechas: {len(hechas)}",
        f"- Última: {ultimas[0]['fecha'] + ' · ' + ultimas[0].get('permalink', '') if ultimas else 'ninguna todavía'}",
        "",
        "## Últimas publicaciones",
        "| Fecha | Tema | Estilo | Retraso | Enlace |",
        "|---|---|---|---|---|",
    ]
    for p in ultimas:
        nombre = temas.get(p.get("tema"), {}).get("nombre", p.get("tema", ""))
        lineas.append(f"| {p['fecha']}{' (fuera de calendario)' if p.get('prueba') else ''}{' · reel' if p.get('tipo') == 'reel' else ''} | {nombre} | {p.get('estilo', '')} | "
                      f"{p.get('retraso_min', 0)} min | {p.get('permalink', '')} |")
    if not ultimas:
        lineas.append("| – | – | – | – | – |")
    lineas += ["", "## Próximas 10 previstas", "| Fecha | Tema | Estilo |", "|---|---|---|"]
    for p in proximas:
        nombre = temas[p.tema_id]["nombre"] if p.tema_id else f"Campaña {p.campana_id}"
        lineas.append(f"| {DIAS[p.fecha.weekday()]} {p.fecha:%Y-%m-%d} | {nombre} | {p.estilo} |")
    pend = cfg.get("campanas_previstas", [])
    if pend:
        lineas += ["", "## Campañas por diseñar", *[f"- {c['fecha']}: {c['nombre']} ({c['pendiente']})" for c in pend]]
    texto = "\n".join(lineas) + "\n"
    Path(ruta or RUTA_INFORME).write_text(texto, encoding="utf-8")
    return texto
