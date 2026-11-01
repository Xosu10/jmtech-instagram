"""Cliente mínimo de la API oficial de Instagram (token de usuario del sistema, host graph.facebook.com).

El token viaja en la cabecera Authorization, nunca en la dirección, y se oculta de cualquier mensaje de error.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

VERSION_API = "v25.0"
BASE = f"https://graph.facebook.com/{VERSION_API}"

_PATRON_TOKEN = re.compile(r"(EAA[A-Za-z0-9]{10,}|IGA[A-Za-z0-9_-]{10,}|IGQ[A-Za-z0-9_-]{10,})")


class ErrorInstagram(Exception):
    """Error de la API con un mensaje claro en español y los datos técnicos aparte."""

    def __init__(self, mensaje, codigo=None, subcodigo=None, tecnico="", temporal=False):
        super().__init__(mensaje)
        self.codigo, self.subcodigo, self.tecnico, self.temporal = codigo, subcodigo, tecnico, temporal


def ocultar(texto, token=None):
    """Quita el token (y cualquier cosa con forma de token) de un texto."""
    texto = str(texto)
    if token:
        texto = texto.replace(token, "***")
    return _PATRON_TOKEN.sub("***", texto)


def traducir_error(cuerpo, estado_http, token=None):
    err = (cuerpo or {}).get("error", {}) if isinstance(cuerpo, dict) else {}
    codigo, sub = err.get("code"), err.get("error_subcode")
    msg = ocultar(err.get("message", "sin detalle"), token)
    tecnico = f"HTTP {estado_http} · código {codigo} · subcódigo {sub} · {msg}"
    if codigo == 190:
        texto = ("El token de Instagram no es válido o ha sido revocado. Genera uno nuevo en el administrador de "
                 "empresas de Meta y guárdalo en el secreto IG_ACCESS_TOKEN de GitHub.")
    elif codigo in (4, 17, 32, 613):
        texto, temporal = "Instagram ha limitado temporalmente las peticiones. Se reintentará en la próxima ejecución.", True
        return ErrorInstagram(texto, codigo, sub, tecnico, temporal)
    elif codigo == 368:
        texto = "Instagram ha bloqueado temporalmente esta acción en la cuenta. No insistas: espera y revisa la app de Instagram."
    elif codigo in (10, 3) or (codigo is not None and 200 <= codigo <= 299):
        texto = "Al token le falta un permiso (instagram_basic o instagram_content_publish) o acceso a la cuenta."
    elif codigo in (1, 2) or (isinstance(estado_http, int) and estado_http >= 500):
        return ErrorInstagram("Meta ha tenido un fallo temporal. Se reintentará.", codigo, sub, tecnico, True)
    elif sub in (2207003, 2207052, 9004) or "download" in msg.lower() or "fetch" in msg.lower():
        texto = "Instagram no pudo descargar la imagen desde su dirección pública. Comprueba que está subida al repositorio."
    elif codigo == 100:
        texto = f"Instagram ha rechazado un dato de la petición ({msg})."
    else:
        texto = f"Instagram devolvió un error (código {codigo}): {msg}"
    return ErrorInstagram(texto, codigo, sub, tecnico, False)


class ClienteInstagram:
    def __init__(self, token, ig_user_id, sesion=None, base=BASE, dormir=time.sleep):
        if not token:
            raise ErrorInstagram("Falta el token de Instagram (secreto IG_ACCESS_TOKEN).")
        self.token, self.ig, self.base, self.dormir = token, ig_user_id, base, dormir
        self.sesion = sesion or requests.Session()

    def _llamar(self, metodo, ruta, reintentos=1, **datos):
        cabeceras = {"Authorization": f"Bearer {self.token}"}
        ultimo = None
        for intento in range(reintentos):
            if intento:
                self.dormir(5 * intento)
            try:
                r = self.sesion.request(metodo, f"{self.base}/{ruta}", headers=cabeceras, timeout=60,
                                        **({"params": datos} if metodo == "GET" else {"data": datos}))
            except requests.RequestException as e:
                ultimo = ErrorInstagram("No se pudo conectar con Instagram.", tecnico=ocultar(e, self.token), temporal=True)
                continue
            try:
                cuerpo = r.json()
            except ValueError:
                cuerpo = None
            if r.status_code >= 400 or (isinstance(cuerpo, dict) and "error" in cuerpo):
                ultimo = traducir_error(cuerpo, r.status_code, self.token)
                if ultimo.temporal:
                    continue
                raise ultimo
            return cuerpo
        raise ultimo

    # --- consultas ---
    def cuenta(self):
        return self._llamar("GET", self.ig, reintentos=3, fields="id,username")

    def limite(self):
        d = self._llamar("GET", f"{self.ig}/content_publishing_limit", reintentos=3, fields="quota_usage,config")
        fila = (d.get("data") or [{}])[0]
        return fila.get("quota_usage", 0), (fila.get("config") or {}).get("quota_total")

    def ultimos_medios(self, n=10):
        d = self._llamar("GET", f"{self.ig}/media", reintentos=3, fields="id,caption,timestamp,permalink,media_type", limit=n)
        return d.get("data", [])

    def permalink(self, media_id):
        return self._llamar("GET", media_id, reintentos=3, fields="permalink").get("permalink")

    # --- publicación ---
    def crear_contenedor(self, image_url, caption, alt_text=None):
        datos = {"image_url": image_url, "caption": caption}
        if alt_text:
            datos["alt_text"] = alt_text
        try:
            return self._llamar("POST", f"{self.ig}/media", reintentos=3, **datos)["id"]
        except ErrorInstagram as e:
            if alt_text and e.codigo == 100 and "alt" in e.tecnico.lower():
                print("AVISO: Instagram rechazó el texto alternativo; se publica sin él.")
                datos.pop("alt_text")
                return self._llamar("POST", f"{self.ig}/media", reintentos=3, **datos)["id"]
            raise

    def esperar_listo(self, contenedor, maximo_s=300, cada_s=10):
        inicio = time.monotonic()
        while True:
            d = self._llamar("GET", contenedor, reintentos=3, fields="status_code,status")
            estado = d.get("status_code")
            if estado in ("FINISHED", "PUBLISHED"):
                return estado
            if estado in ("ERROR", "EXPIRED"):
                raise ErrorInstagram(f"Instagram no pudo procesar la imagen (estado {estado}).",
                                     tecnico=ocultar(d.get("status", ""), self.token))
            if time.monotonic() - inicio > maximo_s:
                raise ErrorInstagram("Instagram tarda demasiado en procesar la imagen. Se reintentará en la próxima ejecución.",
                                     temporal=True)
            self.dormir(cada_s)

    def publicar(self, contenedor):
        return self._llamar("POST", f"{self.ig}/media_publish", creation_id=contenedor)["id"]

    # --- reels ---
    def crear_contenedor_reel(self, caption, video_url=None, resumable=False, thumb_offset=3000):
        datos = {"media_type": "REELS", "caption": caption, "share_to_feed": "true", "thumb_offset": str(thumb_offset)}
        if video_url:
            datos["video_url"] = video_url
        if resumable:
            datos["upload_type"] = "resumable"
        return self._llamar("POST", f"{self.ig}/media", reintentos=3, **datos)

    def subir_video(self, contenedor, ruta, uri=None):
        """Subida directa del vídeo a Instagram (sin tener que alojarlo en una dirección pública)."""
        contenido = Path(ruta).read_bytes()
        url = uri or f"https://rupload.facebook.com/ig-api-upload/{VERSION_API}/{contenedor}"
        cabeceras = {"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(len(contenido))}
        try:
            r = self.sesion.post(url, headers=cabeceras, data=contenido, timeout=600)
        except requests.RequestException as e:
            raise ErrorInstagram("No se pudo subir el vídeo a Instagram.", tecnico=ocultar(e, self.token), temporal=True)
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = None
        if r.status_code >= 400 or not (isinstance(cuerpo, dict) and cuerpo.get("success")):
            if isinstance(cuerpo, dict) and "error" in cuerpo:
                raise traducir_error(cuerpo, r.status_code, self.token)
            try:
                estado = self._llamar("GET", contenedor, reintentos=1, fields="status,status_code,video_status")
            except Exception as e2:
                estado = f"(no se pudo consultar el estado del contenedor: {e2})"
            raise ErrorInstagram("Instagram no aceptó la subida del vídeo.",
                                 tecnico=ocultar(f"HTTP {r.status_code} {cuerpo} · contenedor {contenedor} · uri {url} · bytes {len(contenido)} · estado: {estado}", self.token))

    def publicar_reel(self, ruta_video, caption, video_url=None, thumb_offset=3000):
        """Crea, sube, espera y publica un reel. Devuelve el id del contenido publicado."""
        try:
            d = self.crear_contenedor_reel(caption, resumable=True, thumb_offset=thumb_offset)
            contenedor = d["id"]
            self.subir_video(contenedor, ruta_video, d.get("uri"))
        except ErrorInstagram as e:
            if not video_url:
                raise
            print(f"AVISO: la subida directa del vídeo falló ({e.tecnico or e}); se usa la dirección pública.")
            contenedor = self.crear_contenedor_reel(caption, video_url=video_url, thumb_offset=thumb_offset)["id"]
        self.esperar_listo(contenedor, maximo_s=600, cada_s=15)
        return self.publicar(contenedor)
