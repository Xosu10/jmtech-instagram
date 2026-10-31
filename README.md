# JM TECH · Publicador automático de Instagram

Sistema que genera y publica una imagen publicitaria en la cuenta de Instagram de **JM TECH — Servicio técnico y soluciones tecnológicas** (Murcia), de lunes a viernes a las 19:00 (hora de Madrid), usando la API oficial de Instagram y GitHub Actions.

Este repositorio es público porque Instagram necesita descargar cada imagen desde una dirección web pública. Solo contiene contenido publicitario: no hay claves, contraseñas ni datos personales. Las claves viven únicamente en *GitHub Secrets*.

## Estructura

| Carpeta | Contenido |
|---|---|
| `assets/` | Logo y tipografías (Poppins, licencia OFL). |
| `contenido/` | Temas y textos de las publicaciones. |
| `referencia/` | Diseño de referencia aprobado. |
| `config/` | Calendario y ajustes. |
| `estado/` | Registro de lo ya publicado (evita duplicados). |
| `publicaciones/` | Imágenes publicadas (`AAAA-MM-DD.jpg`). |
| `src/` | Código. |
| `tests/` | Pruebas automáticas. |
| `.github/workflows/` | Flujos automáticos de GitHub Actions. |
