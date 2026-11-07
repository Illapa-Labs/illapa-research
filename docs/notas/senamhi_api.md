# API de interoperabilidad del SENAMHI: cómo se usa aquí

Guía oficial: <https://observatorio.senamhi.gob.pe/investigadores/interoperabilidad/apis> (23 endpoints, solo GET, JSON).

- **Base:** `https://interoperabilidad.senamhi.gob.pe/api`. **Autenticación:** cabecera `apikey` con la clave que entrega el SENAMHI al aprobar la cuenta; la llamada debe salir de una **IP registrada** en la cuenta. Respuestas 401 (sin clave), 403 (IP no registrada o grupo no autorizado), 429 (límite).
- **Límites de la cuenta:** 1 000 consultas por día y 60 por minuto. El cliente (`src/illapa_research/senamhi_api.py`) usa un tope propio de 800 al día, 1,5 s de pausa entre llamadas, caché en disco y se detiene ante cualquier 401, 403 o 429.
- **Clave:** el cliente la lee de la variable `SENAMHI_APIKEY` o del archivo `~/.senamhi_env` (una línea `export SENAMHI_APIKEY=...`, permiso 600, fuera del repositorio). Nunca se imprime ni se guarda en la caché. Para crear el archivo sin que se vea en pantalla ni en el historial, en la PC remota:
  `read -s "?API key: " K; echo; umask 077; printf 'export SENAMHI_APIKEY=%q\n' "$K" > ~/.senamhi_env; unset K`
- **Endpoints:** estaciones (`/stations`, `/stations/{id}/readings`, `/stations/{id}/time-series`, …), avisos meteorológicos por provincia (`/weather-warnings`, filtros `ubigeo` y `year`), avisos de lluvia a corto plazo por distrito (`/short-term-warnings`, filtro `ubigeo`) y ubigeo (`/locations/...`).
- **Lo que NO ofrece:** humedad del suelo (SMI), SPI, SILVIA, el pronóstico ETA ni el WRF de 1 km. Los issues #2, #3, #4 y la parte de WRF del #1 siguen abiertos.
- **Qué se usó (7 de noviembre de 2026, unas 40 llamadas):** catálogos de provincias, distritos y estaciones (3 llamadas, 2 984 estaciones); avisos meteorológicos de Lima y Huarochirí de 2014 a 2026 (26 llamadas; solo hay datos desde 2021); avisos de lluvia a corto plazo de 5 distritos (solo 2025 y 2026). Capítulo [27](../27-avisos-senamhi.md).
- **Términos:** la información lleva la leyenda del SENAMHI (`senamhi.LEYENDA`) y no se presenta como producto oficial. Las condiciones de redistribución propias de esta cuenta no se conocen: los datos crudos de la API quedan en `datos/` (fuera de git y del espejo público); en `catalogo/` solo van resúmenes agregados.
