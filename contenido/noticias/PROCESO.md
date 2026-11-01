# Las noticias de la semana (domingos, 19:00)

Vídeo extra semanal, semiautomático: se prepara el domingo por la mañana, José lo aprueba y sale solo a las 19:00 (hora de Madrid).

1. **Barrido.** Portadas con fecha de MuyComputer, HardZone, Genbeta, Xataka y los canales oficiales de las marcas. La búsqueda por fechas devuelve resultados viejos: mejor abrir las portadas.
2. **Verificar.** Cada noticia debe estar confirmada por al menos otra fuente. Lo no confirmado se cuenta como rumor («según filtraciones…»). Se descarta lo que sea anterior a la semana o no se confirme (en la prueba del 1-nov-2026 cayeron 3 de 6).
3. **Guion.** Copiar `noticias_2026_11_01.json` como `noticias_AAAA_MM_DD.json`: rótulo de apertura, 3 noticias en tarjetas, consejo de la semana y cierre. Máximo 175 palabras (`max_palabras`). Sin porcentajes con el símbolo %: «un 13 por ciento».
4. **Imágenes.** Normalmente no hacen falta (tarjetas del propio sistema). Si alguna noticia pide imagen, se piden a GPT en `PETICIONES.md` con el proceso habitual.
5. **Vídeo.** `python -m jmtech.curiosidad render contenido/noticias/<id>.json --salida <id>.mp4 --musica <mp3>`; se envía a José para su OK.
6. **Cola.** Con el OK, copiar el mp4 a `jmtech-musica/curiosidades/noticias/` y añadir su entrada a `cola.json` (fecha del domingo, id, video, pie con `construir_descripcion`). Subir `jmtech-musica`.
7. **TikTok.** `python -m jmtech.tiktok preparar --carpeta C:\Users\xosu1\Documents\TikTok --hasta 2027-10-31`.

Workflow: `.github/workflows/publicar-noticias.yml` (domingos 17:00 y 18:00 UTC). Pausar: `"noticias": false` en `config/calendario.json`.
