# Disparador y vigilancia externos de JM TECH

Estado inicial: **desactivado** (`ENABLED=0`). No publica ni necesita credenciales
de Instagram. Las pruebas usan una API simulada.

## Activación

1. Entrar en una cuenta gratuita de Cloudflare Workers. La creación de cuenta,
   la aceptación de condiciones y el inicio de sesión los completa José.
2. Crear un token de GitHub limitado a `Xosu10/jmtech-instagram`, con Actions
   lectura/escritura y Contents lectura. Guardarlo **solo como secreto** del
   Worker, nombre `GITHUB_DISPATCH_TOKEN`; nunca en archivos, chat o Git.
   Esto requiere autorizar esta ubicación adicional para un secreto: la regla
   histórica del proyecto solo contempla GitHub Secrets.
3. Desplegar este directorio. Mantener `ENABLED=0` para revisar `/health`.
4. Ejecutar las pruebas de publicación en seco desde la rama revisada.
5. Cambiar `ENABLED=1` cuando estén publicados en `main` los nuevos inputs y
   comprobaciones. Nunca pasar `ignorar_hora=true` desde este servicio.
6. Conectar un monitor externo a `/health`, con notificación de fallo y de
   ausencia de respuesta. El registro de errores de Cloudflare no equivale por
   sí solo a un aviso entregado al usuario. Confirmar la recepción de un aviso
   simulado antes de dar por terminada la activación.

El cron revisa cada cinco minutos, con la fecha/hora de Europe/Madrid y sus
cambios de horario. Solo dispara lo pendiente, sin ampliar la ventana actual
de 90 minutos. No es una promesa de puntualidad de GitHub ni de Instagram.

## Recuperación y duplicados

Se consulta el registro persistente en GitHub. Si hay un trabajo activo del
mismo tipo, no se vuelve a disparar. Tras diez minutos se permite otro intento
si el trabajo anterior terminó y aún no hay publicación registrada. El
workflow revalida fecha y estado, conserva su bloqueo por tipo y comprueba
Instagram antes de publicar. Si esa comprobación falla, se detiene.

Después de 90 minutos no se publica tarde: `/health` pasa a HTTP 503 y el cron
registra fallo. Para permitir una recuperación más tardía se debe acordar
primero un límite; no se asume autorización para publicar contenido atrasado.

No se expone ningún endpoint público que permita disparar publicaciones:
`/health` es solo lectura. Se debe proteger contra exceso de consultas en la
configuración de despliegue antes de conectarlo a un dominio público.

## Reversión

`ENABLED=0` detiene el disparador externo. Los schedules de GitHub se mantienen
como respaldo. No borrar el estado de publicaciones: evita repetir contenidos.
