# WeatherNext (Google DeepMind): revisión de acceso y de los datos (3 de noviembre de 2026)

Acceso aprobado por el equipo de WeatherNext a la cuenta de la persona usuaria (datos históricos CC BY 4.0; datos en tiempo real con los términos de uso de DeepMind). Se miró solo el cubo de **estadísticas** de WeatherNext 3 en Cloud Storage (`gs://weathernext3_statistics_spatial/weathernext_3_0_0_statistics/zarr/`), que según la guía no tiene «Requester Pays». No se tocó el cubo del conjunto completo (sí cobra la salida al proyecto) ni BigQuery.

## Qué trae

- Lluvia horaria: `total_precipitation_1hr` con `_mean` y percentiles `_p10`, `_p25`, `_p50`, `_p75`, `_p90` del conjunto de 64 miembros. También `imerg_tp_1hr` y `experimental_tp_1hr` (sin revisar sus atributos), punto de rocío, presión, nubosidad y temperatura del mar.
- Rejilla de 0,1° (1 801 × 3 600) para lluvia; la de 0,05° es de temperatura de estaciones. Longitudes 0 a 360°.
- Histórico desde 2024: `2024/` y `2025/` con `6hr_inits.zarr` (una emisión cada 6 h, 360 plazos horarios) e `interim_inits.zarr`; `2026_to_present/` con un almacén por emisión horaria.

## Por qué no se usa para un backtest por Zarr

Cada bloque del cubo es un **campo global completo** (`chunks = (1, 1, 1801, 3600)`) y pesa unos **24 MB comprimidos** (no comprime). Para una serie de un punto hay que bajar un bloque por cada hora de cada emisión:

- un día de pronóstico a 24 h = 24 bloques ≈ 575 MB;
- el backtest equivalente al del capítulo 19 (unos 600 días) serían unos 345 GB para una sola variable.

Es viable para unos pocos días de prueba, no para una evaluación. Para series de un punto el diseño de Google apunta a Earth Engine o BigQuery (extracción en el servidor), con costos y registro propios que no se probaron.

## Cobertura y resolución

Solo 2024 en adelante en este cubo (unas 2 temporadas de lluvia completas en estadísticas), y 0,1° igual que UKMO: no resuelve una quebrada. Se deja como opción para la temporada 2026-27 (prueba prospectiva) en vez de un backtest.

## Lo que quedó montado

- La herramienta `gcloud` en la PC remota (`~/google-cloud-sdk`) con una sesión de credenciales de aplicación de la cuenta, sin proyecto de facturación asociado al uso, y la opción `weathernext` en `pyproject.toml` (obstore, zarr, xarray).
- La sesión se puede borrar con `gcloud auth application-default revoke`.
