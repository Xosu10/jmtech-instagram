"""Ningún secreto ni dato personal en el repositorio público."""
import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
OMITIR = {".git", "previsualizacion", "__pycache__", ".pytest_cache", ".venv", "venv"}
TEXTO = {".py", ".md", ".json", ".yml", ".yaml", ".txt", ".ini", ".gitignore", ".gitkeep"}

SECRETOS = re.compile(
    r"EAA[A-Za-z0-9]{20,}|IGAA[A-Za-z0-9_-]{20,}|IGQ[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|"
    r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY")
PERSONAL = re.compile(r"gmail" + r"\.com|hotmail\.|outlook\.|yahoo\.|\b\d{3}[ .]?\d{3}[ .]?\d{3}\b")


# Notas privadas que el .gitignore deja fuera del repositorio público (existen solo en el ordenador de José)
PRIVADOS = {"CLAUDE.md", "PROMPT_MAESTRO.md", "LEEME_PRIMERO.txt", "PROGRESO.md", "ADDENDUM_ASSETS.md"}
# Este archivo y el de contenido llevan ejemplos falsos a propósito
EJEMPLOS = {"tests/test_contenido.py", "tests/test_seguridad.py"}


def archivos():
    """Archivos de texto que SÍ se publican."""
    for carpeta, dirs, nombres in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in OMITIR]
        for n in nombres:
            ruta = Path(carpeta) / n
            publico = not (ruta.parent == RAIZ and n in PRIVADOS) and not n.startswith(".pendiente")
            if publico and (ruta.suffix in TEXTO or n.startswith(".")):
                yield ruta


def test_no_hay_tokens_ni_claves_en_el_codigo():
    malos = [str(r.relative_to(RAIZ)) for r in archivos()
             if r.relative_to(RAIZ).as_posix() not in EJEMPLOS
             and SECRETOS.search(r.read_text(encoding="utf-8", errors="ignore"))]
    assert malos == []


def test_no_hay_correos_ni_telefonos_personales():
    malos = []
    for r in archivos():
        rel = r.relative_to(RAIZ).as_posix()
        if rel in EJEMPLOS or rel.startswith("assets/fonts"):
            continue
        if PERSONAL.search(r.read_text(encoding="utf-8", errors="ignore")):
            malos.append(rel)
    assert malos == []


def test_el_gitignore_protege_secretos_y_notas_privadas():
    g = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for linea in (".env", "CLAUDE.md", "PROMPT_MAESTRO.md", "PROGRESO.md", ".pendiente*.json"):
        assert linea in g


def test_los_flujos_usan_el_secreto_y_no_escriben_el_token():
    for flujo in (RAIZ / ".github" / "workflows").glob("*.yml"):
        t = flujo.read_text(encoding="utf-8")
        assert "secrets.IG_ACCESS_TOKEN" in t or "IG_ACCESS_TOKEN" not in t, flujo.name
        assert not re.search(r"echo[^\n]*\$IG_ACCESS_TOKEN", t), flujo.name
        assert not re.search(r"set -x", t), flujo.name


@pytest.mark.parametrize("flujo", ["publicar.yml"])
def test_el_flujo_de_publicar_es_seguro_por_defecto(flujo):
    t = (RAIZ / ".github" / "workflows" / flujo).read_text(encoding="utf-8")
    assert "concurrency:" in t and "contents: write" in t
    assert re.search(r"dry_run:\s*\n\s*description:[^\n]*\n\s*type: boolean\s*\n\s*default: true", t)
