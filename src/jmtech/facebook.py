"""Reels en la página de Facebook de JM TECH (misma conexión de Meta que Instagram).

python -m jmtech.facebook verificar        lista las páginas y permisos a los que llega el token (no publica nada)

Se publica solo si en config/calendario.json hay «facebook_page_id». Si Facebook falla, Instagram no se ve afectado.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import requests

from .instagram import BASE, VERSION_API, ErrorInstagram, ocultar, traducir_error


class ErrorFacebook(ErrorInstagram):
    """Error al publicar en Facebook, con mensaje claro."""


def adaptar(texto: str) -> str:
    """En Facebook no hay «MD»: se escribe por mensaje directo."""
    return re.sub(r"\bMD\b", "mensaje directo", texto)


class ClienteFacebook:
    def __init__(self, token, page_id, sesion=requests, dormir=time.sleep):
        if not token:
            raise ErrorFacebook("Falta el token (secreto IG_ACCESS_TOKEN).")
        if not page_id:
            raise ErrorFacebook("Falta «facebook_page_id» en config/calendario.json.")
        self.token, self.page, self.sesion, self.dormir = token, str(page_id), sesion, dormir

    def _llamar(self, metodo, ruta, token=None, **datos):
        url = ruta if ruta.startswith("http") else f"{BASE}/{ruta}"
        cab = {"Authorization": f"Bearer {token or self.token}"}
        try:
            r = self.sesion.request(metodo, url, headers=cab, **({"params": datos} if metodo == "GET" else {"data": datos}), timeout=60)
        except requests.RequestException as e:
            raise ErrorFacebook("No se pudo contactar con Facebook.", tecnico=ocultar(e, self.token), temporal=True)
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = None
        if r.status_code >= 400 or (isinstance(cuerpo, dict) and "error" in cuerpo):
            e = traducir_error(cuerpo, r.status_code, self.token)
            raise ErrorFacebook(str(e).replace("Instagram", "Facebook"), e.codigo, e.subcodigo, e.tecnico, e.temporal)
        return cuerpo or {}

    def token_pagina(self):
        d = self._llamar("GET", self.page, fields="access_token,name")
        if not d.get("access_token"):
            raise ErrorFacebook("El token no da acceso de administración a la página (falta el permiso pages_manage_posts o la página no está asignada).",
                                tecnico=f"Respuesta sin access_token para la página {self.page}")
        return d["access_token"]

    def publicar_reel(self, ruta, descripcion, maximo_s=600):
        """Publica un reel (inicio, subida, final y comprobación). Devuelve (id, enlace)."""
        tp = self.token_pagina()
        inicio = self._llamar("POST", f"{self.page}/video_reels", tp, upload_phase="start")
        video_id = inicio["video_id"]
        contenido = Path(ruta).read_bytes()
        url = inicio.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSION_API}/{video_id}"
        try:
            r = self.sesion.post(url, headers={"Authorization": f"OAuth {tp}", "offset": "0", "file_size": str(len(contenido))},
                                 data=contenido, timeout=900)
        except requests.RequestException as e:
            raise ErrorFacebook("No se pudo subir el vídeo a Facebook.", tecnico=ocultar(e, tp), temporal=True)
        if r.status_code >= 400:
            raise ErrorFacebook("Facebook no aceptó la subida del vídeo.", tecnico=ocultar(f"HTTP {r.status_code} {r.text[:200]}", tp))
        self._llamar("POST", f"{self.page}/video_reels", tp, video_id=video_id, upload_phase="finish",
                     video_state="PUBLISHED", description=adaptar(descripcion))
        t0 = time.monotonic()
        while time.monotonic() - t0 < maximo_s:
            estado = self._llamar("GET", video_id, tp, fields="status")
            fase = (estado.get("status") or {}).get("video_status", "")
            if fase in ("ready", "published"):
                break
            if fase in ("error", "expired"):
                raise ErrorFacebook(f"Facebook no pudo procesar el reel (estado {fase}).")
            self.dormir(10)
        return video_id, f"https://www.facebook.com/reel/{video_id}"

    def verificar(self):
        paginas = self._llamar("GET", "me/accounts", fields="name,id")
        permisos = self._llamar("GET", "me/permissions")
        return paginas.get("data", []), [p.get("permission") for p in permisos.get("data", []) if p.get("status") == "granted"]


def compartir_en_facebook(cfg, ruta, texto, cliente=None, imprimir=print):
    """Publica el mismo reel en la página de Facebook, si está configurada. Nunca lanza errores: devuelve None si falla."""
    page_id = (cfg or {}).get("facebook_page_id")
    if not page_id:
        return None
    try:
        cliente = cliente or ClienteFacebook(os.environ.get("IG_ACCESS_TOKEN"), page_id)
        video_id, enlace = cliente.publicar_reel(ruta, texto)
        imprimir(f"PUBLICADO (Facebook): {enlace}")
        return {"facebook_id": video_id, "facebook_enlace": enlace}
    except ErrorInstagram as e:
        imprimir(f"::warning::No se pudo publicar en Facebook: {ocultar(e)} {getattr(e, 'tecnico', '')}")
    except Exception as e:  # noqa: BLE001  (Facebook nunca debe romper la publicación de Instagram)
        imprimir(f"::warning::Fallo inesperado al publicar en Facebook: {ocultar(e)}")
    return None


def main(argv=None):
    orden = (argv or sys.argv[1:] or [""])[0]
    if orden != "verificar":
        print(__doc__)
        return 1
    token = os.environ.get("IG_ACCESS_TOKEN")
    try:
        c = ClienteFacebook(token, "me")
        paginas, permisos = c.verificar()
    except ErrorInstagram as e:
        print(f"::error::{ocultar(e)} {getattr(e, 'tecnico', '')}")
        return 1
    print("Permisos concedidos al token:", ", ".join(sorted(p for p in permisos if p)) or "(ninguno)")
    print("Páginas a las que llega el token:" if paginas else "El token NO ve ninguna página de Facebook.")
    for p in paginas:
        print(f"  - {p.get('name')} · id {p.get('id')}")
    necesarios = {"pages_manage_posts", "pages_read_engagement", "pages_show_list"}
    falta = sorted(necesarios - set(permisos))
    print("Faltan permisos para publicar:", ", ".join(falta) if falta else "ninguno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
