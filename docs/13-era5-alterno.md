# 13 · ERA5 sin la API de Open-Meteo

> Capítulo técnico de datos. No cambia ninguna hipótesis científica; resuelve un bloqueo de descarga.

## 1. Problema

Open-Meteo agotó la cuota diaria de su API gratuita (10 000 llamadas por día) antes de entregar tres de los seis puntos de predictores: Chosica, la costa de Lima y la selva de Tarma. Esperar al reinicio (19:00 hora Lima) era una opción; la otra era leer los mismos datos por otra vía.

## 2. Qué se probó

| Vía | Resultado |
|---|---|
| ARCO-ERA5 de Google (Zarr público, `gs://gcp-public-data-arco-era5/co/…`) | Se lee sin clave, pero **termina en agosto de 2021** (`single-level-*`) o en enero de 2023 (`ar/…`), y la malla del almacén `co` es una lista de 542 080 puntos gaussianos, no lat-lon. Sirve para 1983-2021, no para llegar a 2026. Descartada. |
| ERA5 en NCAR/AWS (`nsf-ncar-era5`) | Archivos globales de unos 100 MB por día y variable: una serie de 43 años exigiría leer decenas de miles de ellos. No se probó. |
| **Archivos de Open-Meteo en AWS Open Data** (`s3://openmeteo/data/copernicus_era5/…`, lectura anónima) | **Funciona.** Son los mismos datos que sirve la API, sin cuota. Se leen con `omfiles` y `s3fs` por rangos de bytes. |
| NASA POWER (MERRA-2) | Ya estaba como respaldo (capítulo 04); malla de 0,5° × 0,625°, demasiado gruesa (Chosica y la costa de Lima caen en la misma celda). Se sigue usando solo si falta ERA5. |

## 3. Cómo se leen los archivos de Open-Meteo

- Cada variable tiene `year_YYYY.om` (años completos) y `chunk_N.om` (504 horas cada uno) con una malla global (721 × 1440 a 0,25° para ERA5; 1801 × 3600 a 0,1° para ERA5-Land, solo temperatura, punto de rocío y humedad del suelo). Los archivos están troceados para series de un punto (1 × 6 × ~1000): una serie de un año son 8 lecturas pequeñas.
- El corte entre archivos anuales y de 504 horas **varía por variable**: temperatura, punto de rocío, presión y lluvia pasan a trozos en diciembre de 2021; la nubosidad, en diciembre de 2023. Se lee del listado del bucket.
- La orientación es latitud ascendente desde -90° y longitud desde -180° (comprobada con Matucana: 6,4 °C en la celda, 13,8 °C a la altura del punto en la API).
- Las horas están en UTC; las cachés de `descargar-datos` están en hora de Lima (UTC-5): se desplazan.
- La presión viene en Pa (se divide por 100).
- Humedad relativa y déficit de presión de vapor se derivan de temperatura y punto de rocío (fórmula de Magnus).
- La API devuelve la temperatura **a la altura del punto** (modelo digital de elevación) y no a la de la celda de ERA5. Aquí se hace una corrección con gradiente: `T + 0,0065 · (z_celda − z_punto)` y `Td + 0,0020 · (z_celda − z_punto)`, con la altura del punto leída del Copernicus GLO-30 y la de la celda de `static/HSURF.om` (ERA5-Land para temperatura y punto de rocío, como la API).

Código: `src/illapa_research/era5_alterno.py`. Fuente `era5-aws` (opt-in): `uv run --extra era5 descargar-datos --solo era5-aws` rellena en `datos/predictores_cache/` los puntos que no tengan caché, con el mismo formato de `descargar-datos`, así que `predictores.cargar_con_respaldo` los usa sin cambios.

## 4. Equivalencia medida

Para probar que es lo mismo, se bajaron con este método los tres puntos que **sí** tenemos de la API (Matucana, Santa Eulalia alta y Ticlio) para el año 2021 y se compararon hora a hora y día a día (`catalogo/validacion_era5_alterno.csv`, con todas las variantes probadas: sin corrección, gradiente 6,5 y 6,5 K/km, ERA5 sin ERA5-Land). Promedio de los tres puntos con la configuración elegida (ERA5-Land, gradiente 6,5 K/km en temperatura y 2 K/km en el punto de rocío):

| Variable | Correlación horaria | Correlación diaria | Sesgo diario |
|---|---|---|---|
| Temperatura | 0,89 | 0,61 | +0,8 °C |
| Punto de rocío | 0,79 | 0,90 | +0,4 °C |
| Humedad relativa | 0,79 | 0,85 | -1,3 % |
| Déficit de presión de vapor | 0,81 | 0,83 | +0,07 kPa |
| Presión a nivel del mar | 0,86 | 0,89 | -1,0 hPa |
| Nubosidad | 0,66 | 0,89 | +4,2 % |
| Lluvia | 0,42 | 0,64 | +2,2 mm por día |
| Humedad del suelo | 0,84 | 0,85 | +0,02 |

- **Lo que coincide bien**: punto de rocío, presión, nubosidad y humedad del suelo (correlación diaria 0,85-0,90). Son las variables que usan los tres puntos nuevos (Tarma: punto de rocío, presión, nubosidad, lluvia; costa de Lima: punto de rocío, nubosidad, presión; Chosica: temperatura, humedad relativa, presión, nubosidad, lluvia, déficit).
- **Lo que no coincide**: la lluvia (+2,2 mm por día, correlación diaria 0,64) y la temperatura media diaria (0,61). La API sirve para estos dos campos algo distinto del ERA5 de 0,25° (probablemente ERA5-Land y/o ajustes propios); el archivo de lluvia que sí está en el bucket es el ERA5 crudo. Las características del modelo diario usan la lluvia de Chosica de la caché horaria del primer estudio (ERA5-Land vía API), no esta; y la temperatura entra solo como anomalía, donde un sesgo constante no importa.
- El sesgo de temperatura (+0,8 °C) depende de las alturas de celda y punto; no se ajustó el gradiente al sesgo para no sobreajustar.

## 5. Resultado de la descarga

Tiempos medidos en la PC remota (WSL2, 24 hilos, 4 hilos de red, lectura por rangos): **unos 8 minutos** para los tres puntos de 1983 a hoy (Chosica 5 variables, costa de Lima 3, selva de Tarma 4; ~70 MB de JSON). La última hora disponible en el bucket el 30 de octubre de 2026 era el 24 de octubre.

Alturas del punto (Copernicus GLO-30): Chosica 1 069 m, costa de Lima 23,5 m, selva de Tarma 3 058 m.

Comprobación cruzada con MERRA-2 (anomalías diarias, 1983-2026): presión 0,76-0,88, punto de rocío 0,59-0,64, nubosidad 0,30-0,58, lluvia de Tarma 0,26. Más bajo que contra la propia API porque MERRA-2 es mucho más gruesa; solo confirma que las series tienen la misma señal.

Efecto en el modelo diario (`modelo_diario`, una temporada fuera, lluvia + antecedentes): precisión media 0,289 con los seis puntos ERA5; quitar el bloque de humedad y circulación la baja a 0,269 (−0,017). Es decir, la humedad de la selva sí aporta un poco con datos de buena calidad, pero poco.

## 6. Licencia y atribución

ERA5 es un producto del Servicio de Cambio Climático de Copernicus (uso libre con atribución); los archivos los distribuye Open-Meteo bajo CC BY 4.0: «Weather data by Open-Meteo.com; contains modified Copernicus Climate Change Service information». Está en `DATOS.md` y en la tarjeta del espejo de Hugging Face, y se publicó en el espejo público.

## 7. Límites

- La corrección con gradiente es una aproximación. La API usa su propio modelo de elevación y un trato de la humedad que no es público en detalle.
- Es la celda ERA5 más cercana, sin interpolar entre celdas.
- `omfiles` y `s3fs` son dependencias opcionales (`--extra era5`).
