"""Guardas y comprobación del resultado real, sin llamar a Instagram."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TIPOS = {
    "reel": ("reels", "hora_reel"),
    "curiosidad": ("curiosidades", "hora_curiosidad"),
    "noticias": ("noticias", "hora_noticias"),
}


def comprobar_fecha(fecha: str, ahora: datetime | None = None) -> None:
    hoy = (ahora or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Madrid")).date()
    if fecha and fecha != hoy.isoformat():
        raise ValueError("El disparo corresponde a otra fecha; se cancela para no publicar el contenido de otro día.")


def falta_publicacion(tipo: str, cfg: dict, estado: dict, ahora: datetime | None = None) -> bool:
    from .calendario import es_dia_publicable
    from .estado import publicado_el
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Madrid"))
    dia = ahora.date()
    activo, hora = TIPOS[tipo]
    if cfg.get("pausado") or not cfg.get(activo, True):
        return False
    if tipo == "reel" and not es_dia_publicable(dia, cfg):
        return False
    if tipo == "noticias" and dia.weekday() != 6:
        return False
    if ahora.strftime("%H:%M") < cfg[hora]:
        return False
    return not publicado_el(estado, dia, tipo)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("orden", choices=["fecha", "resultado"])
    parser.add_argument("valor")
    args = parser.parse_args()
    if args.orden == "fecha":
        comprobar_fecha(args.valor)
    else:
        from .calendario import cargar_config
        from .estado import cargar
        if falta_publicacion(args.valor, cargar_config(), cargar()):
            raise SystemExit("::error::La publicación prevista no figura como publicada. Revisar horario, cola y ejecución; un script sin errores no basta.")


if __name__ == "__main__":
    main()
