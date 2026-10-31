"""Publicador diario de Instagram.

python -m jmtech.publicador preparar [--dry-run]   decide qué toca hoy y genera el JPEG
python -m jmtech.publicador publicar [--dry-run]   sube a Instagram lo preparado
python -m jmtech.publicador hoy --dry-run          las dos cosas seguidas, sin tocar Instagram
python -m jmtech.publicador simular DESDE HASTA    prueba en seco de un rango de fechas
python -m jmtech.publicador verificar              comprueba token, cuenta y permiso (no publica)
python -m jmtech.publicador informe                regenera ESTADO.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from datetime import time as hora_t
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import estado as est
from .base import RAIZ
from .assets import DIBUJO, Selector, cargar_catalogo
from .assets import indice as indice_assets
from .calendario import Publicacion, cargar_config, es_dia_publicable, publicacion_del_dia
from .contenido import indice_temas, pie_de_foto
from .instagram import ClienteInstagram, ErrorInstagram, ocultar
from .render import guardar_jpeg, renderizar
from .validacion import problemas_imagen, problemas_tema

ZONA = ZoneInfo("Europe/Madrid")
UTC = timezone.utc
IG_USER_ID = "17841471351315429"
VENTANA_MIN = 90                       # se publica entre las 19:00 y las 20:30 (hora de Madrid)
AVISO_RETRASO_MIN = 30
RUTA_PENDIENTE = RAIZ / ".pendiente.json"
CARPETA_IMAGENES = RAIZ / "publicaciones"
CARPETA_DRY = RAIZ / "previsualizacion" / "dry_run"


class ErrorPublicacion(Exception):
    """Algo impide publicar; el mensaje está en español claro."""


# ---------- Hora de Madrid ----------
def ahora_madrid(ahora_utc: datetime | None = None) -> datetime:
    ahora_utc = ahora_utc or datetime.now(UTC)
    if ahora_utc.tzinfo is None:
        ahora_utc = ahora_utc.replace(tzinfo=UTC)
    return ahora_utc.astimezone(ZONA)


def inicio_ventana(dia: date, cfg: dict) -> datetime:
    return datetime.combine(dia, hora_t.fromisoformat(cfg["hora_publicacion"]), tzinfo=ZONA)


def en_ventana(ahora: datetime, cfg: dict) -> bool:
    ini = inicio_ventana(ahora.date(), cfg)
    return ini <= ahora < ini + timedelta(minutes=VENTANA_MIN)


def retraso_min(ahora: datetime, cfg: dict) -> int:
    return max(0, int((ahora - inicio_ventana(ahora.date(), cfg)).total_seconds() // 60))


# ---------- Qué toca hoy ----------
@dataclass
class Decision:
    accion: str                      # "publicar" u "omitir"
    motivo: str
    fecha: date
    publicacion: Publicacion | None = None
    prueba: bool = False


def decidir(ahora_utc, cfg, estado, *, ignorar_hora=False, tema=None, estilo=None, prueba=False,
            catalogo=None, asset=None) -> Decision:
    ahora = ahora_madrid(ahora_utc)
    hoy = ahora.date()
    if prueba:
        temas = indice_temas()
        tema = tema or next(iter(temas))
        if tema not in temas:
            raise ErrorPublicacion(f"El tema «{tema}» no existe. Temas: {', '.join(temas)}")
        estilo = estilo or "A"
        if asset is None and catalogo is not None:
            asset = Selector(catalogo, cfg["semilla"]).elegir(tema, estilo)
        return Decision("publicar", "prueba manual", hoy, Publicacion(hoy, "rotacion", tema, estilo, 0, 0, None, asset), True)
    if cfg.get("pausado"):
        return Decision("omitir", "el sistema está pausado (config/calendario.json)", hoy)
    if not es_dia_publicable(hoy, cfg):
        return Decision("omitir", "hoy no toca publicar (fin de semana, festivo o antes de la fecha de inicio)", hoy)
    if not ignorar_hora and not en_ventana(ahora, cfg):
        return Decision("omitir", f"en Madrid son las {ahora:%H:%M}, fuera de la ventana de publicación "
                                  f"({cfg['hora_publicacion']} + {VENTANA_MIN} min)", hoy)
    if est.publicado_el(estado, hoy):
        return Decision("omitir", "ya se publicó hoy (evita duplicados)", hoy)
    return Decision("publicar", "toca publicar", hoy, publicacion_del_dia(hoy, cfg, catalogo))


# ---------- Preparar la imagen ----------
def preparar(ahora_utc=None, *, dry_run=False, ignorar_hora=False, tema=None, estilo=None, prueba=False,
             asset=None, cfg=None, estado=None, carpeta=None, ruta_pendiente=RUTA_PENDIENTE,
             catalogo=None) -> dict | None:
    cfg = cfg or cargar_config()
    estado = est.cargar() if estado is None else estado
    catalogo = cargar_catalogo() if catalogo is None else catalogo
    ahora = ahora_madrid(ahora_utc)
    d = decidir(ahora_utc, cfg, estado, ignorar_hora=ignorar_hora, tema=tema, estilo=estilo, prueba=prueba,
                catalogo=catalogo, asset=asset)
    Path(ruta_pendiente).unlink(missing_ok=True)
    if d.accion == "omitir":
        print(f"No se publica: {d.motivo}.")
        return None
    pub = d.publicacion
    if pub.tipo == "campana":
        raise ErrorPublicacion(f"Hoy hay una campaña ({pub.campana_id}) pero aún no está diseñada. "
                               "Se diseña en la Fase 7; mientras tanto, quítala de config/calendario.json.")
    t = indice_temas()[pub.tema_id]
    fallos = problemas_tema(t)
    if fallos:
        raise ErrorPublicacion("El contenido no pasa las comprobaciones: " + "; ".join(fallos))
    pie = pie_de_foto(t, pub.variante)
    nombre = f"prueba_{d.fecha.isoformat()}_{ahora:%H%M%S}_{pub.tema_id}.jpg" if prueba else f"{d.fecha.isoformat()}.jpg"
    objeto_asset = indice_assets(catalogo).get(pub.asset)
    if pub.asset not in (None, DIBUJO) and objeto_asset is None:
        raise ErrorPublicacion(f"El asset «{pub.asset}» no está en el catálogo de assets aprobados.")
    img, info = renderizar(t, pub.estilo, objeto_asset)
    if info["avisos"]:
        raise ErrorPublicacion("La maquetación tiene problemas: " + "; ".join(info["avisos"]))
    ruta = guardar_jpeg(img, (carpeta or (CARPETA_DRY if dry_run else CARPETA_IMAGENES)) / nombre)
    fallos = problemas_imagen(ruta)
    if fallos:
        raise ErrorPublicacion("La imagen no es válida: " + "; ".join(fallos))
    pend = dict(fecha=d.fecha.isoformat(), tema=pub.tema_id, estilo=pub.estilo, variante=pub.variante, archivo=nombre,
                pie=pie, alt=t["texto_alternativo"], prueba=prueba, asset=pub.asset or DIBUJO)
    Path(ruta_pendiente).write_text(json.dumps(pend, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Preparado: {t['nombre']} · estilo {pub.estilo} · pie nº {pub.variante % len(t['pies_de_foto']) + 1} · "
          f"imagen {pend['asset']} · {nombre}")
    return pend


# ---------- Publicar ----------
def url_publica(nombre: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "Xosu10/jmtech-instagram")
    return f"https://raw.githubusercontent.com/{repo}/main/publicaciones/{nombre}"


def esperar_url(url, *, sesion=requests, intentos=18, cada_s=10, dormir=time.sleep):
    """Espera a que la imagen esté pública y se sirva como JPEG."""
    ultimo = "sin respuesta"
    for i in range(intentos):
        try:
            r = sesion.get(url, timeout=30)
            tipo = r.headers.get("Content-Type", "")
            if r.status_code == 200 and tipo.startswith("image/jpeg") and len(r.content) > 5000:
                return
            ultimo = f"código {r.status_code}, tipo {tipo or 'desconocido'}"
        except requests.RequestException as e:
            ultimo = str(e)
        if i < intentos - 1:
            dormir(cada_s)
    raise ErrorPublicacion(f"La imagen no está disponible en {url} ({ultimo}). ¿Se subió al repositorio?")


def ya_en_instagram(cliente, pie, ahora_utc):
    """Si Instagram ya tiene una publicación con este pie en las últimas 24 h, la devuelve."""
    try:
        for m in cliente.ultimos_medios(10):
            if m.get("caption") == pie:
                ts = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
                if ahora_utc - ts < timedelta(hours=24):
                    return m
    except (ErrorInstagram, KeyError, ValueError) as e:
        print(f"AVISO: no se pudo comprobar lo ya publicado en Instagram ({ocultar(e)}).")
    return None


def publicar(pend, *, dry_run=False, cliente=None, ruta_estado=None, ahora_utc=None, informe=True,
             sesion=requests, dormir=time.sleep) -> dict | None:
    ahora_utc = ahora_utc or datetime.now(UTC)
    if dry_run:
        print(f"PRUEBA EN SECO: no se llama a Instagram. Se publicaría {pend['archivo']} con este pie:\n---\n{pend['pie']}\n---")
        return None
    cfg = cargar_config()
    estado = est.cargar(ruta_estado)
    fecha = date.fromisoformat(pend["fecha"])
    if not pend["prueba"] and est.publicado_el(estado, fecha):
        print("Ya estaba publicado hoy; no se repite.")
        return None
    cliente = cliente or ClienteInstagram(os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID", IG_USER_ID))
    media_id, permalink = None, None
    if not pend["prueba"]:
        previo = ya_en_instagram(cliente, pend["pie"], ahora_utc)
        if previo:
            print("Instagram ya tiene esta publicación; se anota sin repetirla.")
            media_id, permalink = previo["id"], previo.get("permalink")
    if media_id is None:
        esperar_url(url_publica(pend["archivo"]), sesion=sesion, dormir=dormir)
        contenedor = cliente.crear_contenedor(url_publica(pend["archivo"]), pend["pie"], pend["alt"])
        cliente.esperar_listo(contenedor)
        try:
            media_id = cliente.publicar(contenedor)
        except ErrorInstagram:
            previo = None if pend["prueba"] else ya_en_instagram(cliente, pend["pie"], ahora_utc)
            if not previo:
                raise
            media_id = previo["id"]
        permalink = cliente.permalink(media_id)
    ahora = ahora_madrid(ahora_utc)
    retraso = retraso_min(ahora, cfg)
    if retraso > AVISO_RETRASO_MIN and not pend["prueba"]:
        print(f"::warning::La publicación salió con {retraso} minutos de retraso (GitHub tardó en lanzar el flujo).")
    registro = est.registrar(estado, fecha=pend["fecha"], tema=pend["tema"], estilo=pend["estilo"],
                             variante=pend["variante"], imagen=pend["archivo"], asset=pend.get("asset"),
                             resultado="publicado",
                             prueba=pend["prueba"], media_id=media_id, permalink=permalink,
                             publicado_utc=ahora_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             retraso_min=retraso)
    est.guardar(estado, ruta_estado)
    if informe:
        est.generar_informe(estado, ahora_utc)
    print(f"PUBLICADO: {permalink}")
    return registro


# ---------- Reels ----------
def publicar_reel(tema_id, asset_nombre, video=None, musica=None, musica_inicio=0.0, dry_run=False, cliente=None,
                  ruta_estado=None, ahora_utc=None):
    """Genera (si no se da `video`) y publica un reel con el texto y el asset de la publicación."""
    from .reel import generar_reel

    ahora_utc = ahora_utc or datetime.now(UTC)
    temas = indice_temas()
    if tema_id not in temas:
        raise ErrorPublicacion(f"El tema «{tema_id}» no existe.")
    t = temas[tema_id]
    problemas = problemas_tema(t)
    if problemas:
        raise ErrorPublicacion("El contenido no pasa las comprobaciones: " + "; ".join(problemas))
    pie = pie_de_foto(t, 0)
    asset = indice_assets(cargar_catalogo()).get(asset_nombre) if asset_nombre else None
    if video and Path(video).exists():
        ruta = Path(video)
    else:
        ruta = generar_reel(t, asset, RAIZ / "salida_reels" / f"reel_{tema_id}.mp4", musica=musica, musica_inicio=musica_inicio)
    print(f"Reel listo: {ruta.name} ({ruta.stat().st_size / 1e6:.1f} MB)")
    if dry_run:
        print(f"PRUEBA EN SECO: no se llama a Instagram. Pie:\n---\n{pie}\n---")
        return None
    cliente = cliente or ClienteInstagram(os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID", IG_USER_ID))
    video_url = None
    try:
        rel = ruta.resolve().relative_to(RAIZ).as_posix()
        repo = os.environ.get("GITHUB_REPOSITORY", "Xosu10/jmtech-instagram")
        video_url = f"https://raw.githubusercontent.com/{repo}/main/{rel}"
    except ValueError:
        pass
    media_id = cliente.publicar_reel(ruta, pie, video_url=video_url)
    permalink = cliente.permalink(media_id)
    estado = est.cargar(ruta_estado)
    ahora = ahora_madrid(ahora_utc)
    registro = est.registrar(estado, fecha=ahora.date().isoformat(), tema=tema_id, estilo="reel", variante=0,
                             imagen=ruta.name, asset=asset_nombre or DIBUJO, resultado="publicado", prueba=True, tipo="reel",
                             media_id=media_id, permalink=permalink,
                             publicado_utc=ahora_utc.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), retraso_min=0)
    est.guardar(estado, ruta_estado)
    est.generar_informe(estado, ahora_utc)
    print(f"PUBLICADO (reel): {permalink}")
    return registro


# ---------- Prueba en seco de un rango ----------
def simular(desde: date, hasta: date) -> int:
    """Recorre cada día como si fueran las 19:00 en Madrid, sin tocar Instagram. Devuelve nº de problemas."""
    cfg = cargar_config()
    estado = {"publicaciones": []}
    problemas, dia = 0, desde
    print("| Día | Resultado |\n|---|---|")
    while dia <= hasta:
        ahora = inicio_ventana(dia, cfg).astimezone(UTC)
        try:
            pend = preparar(ahora, dry_run=True, cfg=cfg, estado=estado, ruta_pendiente=RAIZ / ".pendiente_simulacion.json")
            if pend:
                est.registrar(estado, fecha=pend["fecha"], tema=pend["tema"], resultado="publicado", prueba=False)
                otra = preparar(ahora, dry_run=True, cfg=cfg, estado=estado, ruta_pendiente=RAIZ / ".pendiente_simulacion.json")
                if otra is not None:
                    raise ErrorPublicacion("la segunda ejecución del mismo día no debería publicar")
                print(f"| {dia} | ✔ {pend['tema']} · {pend['estilo']} · {pend['asset']} |")
            else:
                print(f"| {dia} | – no toca |")
        except ErrorPublicacion as e:
            problemas += 1
            print(f"| {dia} | ✘ {e} |")
        dia += timedelta(days=1)
    (RAIZ / ".pendiente_simulacion.json").unlink(missing_ok=True)
    return problemas


# ---------- Línea de comandos ----------
def _salida_github(clave, valor):
    ruta = os.environ.get("GITHUB_OUTPUT")
    if ruta:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{clave}={valor}\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="jmtech.publicador")
    p.add_argument("orden", choices=["preparar", "publicar", "hoy", "simular", "verificar", "informe", "reel"])
    p.add_argument("fechas", nargs="*", help="solo para simular: DESDE HASTA (AAAA-MM-DD)")
    p.add_argument("--dry-run", action="store_true", help="no llama a Instagram")
    p.add_argument("--ignorar-hora", action="store_true", help="publica aunque no sea la hora (solo manual)")
    p.add_argument("--prueba", action="store_true", help="publicación de prueba: no cuenta como la del día")
    p.add_argument("--tema")
    p.add_argument("--estilo", choices=["A", "B", "C"])
    p.add_argument("--asset", help="solo para pruebas: archivo del catálogo (o «dibujo»)")
    p.add_argument("--video", help="reel: vídeo ya creado (si no, se genera)")
    p.add_argument("--musica", help="reel: canción a usar (si no, música propia)")
    p.add_argument("--musica-inicio", type=float, default=0.0)
    a = p.parse_args(argv)
    try:
        if a.orden == "reel":
            if not a.tema:
                p.error("reel necesita --tema")
            publicar_reel(a.tema, a.asset, a.video, a.musica, a.musica_inicio, dry_run=a.dry_run)
            return 0
        if a.orden in ("preparar", "hoy"):
            pend = preparar(dry_run=a.dry_run, ignorar_hora=a.ignorar_hora, tema=a.tema, estilo=a.estilo,
                            prueba=a.prueba, asset=a.asset)
            _salida_github("hay_publicacion", "true" if pend else "false")
            if a.orden == "hoy" and pend:
                publicar(pend, dry_run=a.dry_run)
        elif a.orden == "publicar":
            if not RUTA_PENDIENTE.exists():
                print("No hay nada preparado que publicar.")
                return 0
            publicar(json.loads(RUTA_PENDIENTE.read_text(encoding="utf-8")), dry_run=a.dry_run)
        elif a.orden == "simular":
            if len(a.fechas) != 2:
                p.error("simular necesita DESDE y HASTA")
            return 1 if simular(date.fromisoformat(a.fechas[0]), date.fromisoformat(a.fechas[1])) else 0
        elif a.orden == "verificar":
            c = ClienteInstagram(os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID", IG_USER_ID))
            cuenta = c.cuenta()
            usadas, total = c.limite()
            print(f"CONEXION CORRECTA · usuario {cuenta.get('username')} · id {cuenta.get('id')} · "
                  f"publicaciones usadas hoy: {usadas} de {total}")
        elif a.orden == "informe":
            est.generar_informe(est.cargar())
            print("ESTADO.md regenerado.")
    except (ErrorPublicacion, ErrorInstagram) as e:
        print(f"::error::{ocultar(e)}")
        tecnico = getattr(e, "tecnico", "")
        if tecnico:
            print(f"Detalle técnico: {tecnico}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
