# WeatherNext (Google DeepMind): acceso, datos y costos (3 de noviembre de 2026)

> Nota de trabajo, no es un capítulo. Lo que dice «según Google» sale de las guías oficiales de WeatherNext 3 ([acceso](https://developers.google.com/weathernext/guides/access-forecast), [Cloud Storage](https://developers.google.com/weathernext/guides/gcs), [Earth Engine](https://developers.google.com/weathernext/guides/earth-engine), [BigQuery](https://developers.google.com/weathernext/guides/bigquery)); lo que dice «no verificado» no se probó.

Acceso aprobado por el equipo de WeatherNext a la cuenta de la persona usuaria. Datos históricos (de hace una hora o más) con licencia CC BY 4.0; datos en tiempo real con los términos de uso de DeepMind. Los tres caminos de acceso comparten una sola aprobación.

## Qué contiene (WeatherNext 3, 0,1° y 0,05°)

- **Lluvia horaria:** `total_precipitation_1hr` con media y percentiles 10, 25, 50, 75 y 90 del conjunto de 64 miembros (en metros; ×1000 para mm). También punto de rocío, presión al nivel del mar, nubosidad baja, media y alta, temperatura del mar, viento y radiación solar. No trae humedad del suelo ni caudal.
- **Rejillas:** 0,1° (unos 10 km) para las variables de superficie; 0,05° solo para temperatura y punto de rocío de 2 m en estaciones. Es la misma escala de UKMO y no resuelve una quebrada.
- **Histórico:** de 2024 en adelante. En 2024 y 2025, 8 emisiones por día con 360 plazos horarios (más emisiones intermedias de 48 h); desde 2026, 24 emisiones por día.
- Los miembros individuales del conjunto solo están en Cloud Storage (Zarr, cubo del conjunto completo). BigQuery y Earth Engine traen solo estadísticas.

## Cuatro caminos, con lo que cuesta cada uno

| Camino | Cómo extrae un punto | Costo | Veredicto |
|---|---|---|---|
| **Cloud Storage, estadísticas** (`gs://weathernext3_statistics_spatial/...`) | Hay que bajar un campo global por hora y emisión (`chunks = (1, 1, 1801, 3600)`, unos **24 MB** por bloque comprimido). Un día de pronóstico a 24 h son unos 575 MB. | Sin «Requester Pays» (según Google), pero el volumen es enorme: unos 345 GB para un backtest de 600 días. | Solo para pocas pruebas puntuales. |
| **Cloud Storage, conjunto completo** (`gs://weathernext3_spatial/...`) | Igual, con 64 miembros. | «Requester Pays» activado: la salida **se cobra al proyecto**. | No usar. |
| **Earth Engine** (`projects/gcp-public-data-weathernext/assets/weathernext_3_0_0_0p1deg`) | Una imagen por emisión y plazo, con las propiedades `start_time`, `end_time` y `forecast_hour`; `reduceRegion` sobre un punto, filtrando antes por `start_time`, `forecast_hour` y `filterBounds`. | **Gratis para uso no comercial**: no se cobra Earth Engine, pero desde el 27 de abril de 2026 cada proyecto tiene una cuota mensual de cómputo (nivel Comunidad: 150 horas-EECU según las fuentes que revisé; la página oficial solo confirma esa cifra). Hay que registrar el proyecto como no comercial y revalidarlo cada año. | Posible, pero una llamada por imagen: un día de 24 h son 24 llamadas. |
| **BigQuery** (listado de Analytics Hub `weathernext_3_1a067c1e929`, proyecto `gcp-public-data-weathernext`, región `us`) | SQL: tabla `weathernext_3_0_0_0p1deg`, particionada por `init_time` y agrupada por `geography`. Un filtro sobre ambas deja leer pocos bloques. | **1 TiB de consultas gratis al mes y 10 GiB de almacenamiento** (según guías de terceros; el precio de lista es 6,25 USD por TiB, a confirmar en [la página de Google](https://cloud.google.com/bigquery/pricing)). Existe un modo «sandbox» sin cuenta de facturación con los mismos límites. | **La mejor opción para un backtest.** |

## Por qué BigQuery es el camino

Una consulta de un punto filtra por `init_time` (partición) y por `geography` (agrupación) y selecciona solo la columna de lluvia, así que se leen megabytes y no gigabytes. La guía recuerda que `LIMIT` no reduce los bytes cobrados y que no conviene usar `SELECT *`. Ejemplo para Chosica (lon −76,70, lat −11,95), lluvia horaria de las 24 primeras horas de una emisión:

```sql
SELECT t.init_time, f.time, f.hours,
       f.total_precipitation_1hr_mean * 1000 AS lluvia_mm
FROM `PROYECTO.DATASET.weathernext_3_0_0_0p1deg` AS t, t.forecast AS f
WHERE t.init_time = TIMESTAMP('2026-02-24 12:00:00 UTC')
  AND ST_DWITHIN(t.geography, ST_GEOGPOINT(-76.70, -11.95), 8000)
  AND f.hours <= 24
ORDER BY f.time;
```

Antes de correr nada en serio se hace una **ejecución en seco** (`--dry_run`), que dice los bytes exactos que se leerían sin cobrar. El backtest equivalente al del capítulo 19 serían unas 300 consultas de un día (dos temporadas) y, con partición y agrupación, debería caber de sobra en el 1 TiB gratuito. Es una estimación, no una medida.

## Cobertura y valor para el proyecto

- Solo 2024 en adelante: dos temporadas de lluvia completas (2024 y 2025) más 2026 hasta hoy, con muy pocos huaicos catalogados. Un backtest así es orientativo, igual que el de UKMO (capítulo 17).
- 0,1°: no distingue una quebrada de otra.
- Lo más útil sería la **prueba prospectiva en la temporada 2026-27**: guardar cada día el pronóstico de WeatherNext y comparar después con los huaicos que se reporten.

## Lo que quedó montado en la PC remota

- `gcloud` en `~/google-cloud-sdk` y una sesión de credenciales de aplicación de la cuenta (para librerías; la CLI no tiene cuenta iniciada). Se borra con `gcloud auth application-default revoke`.
- El proyecto de cuota de esa sesión es `illapa-weather`; tiene asociada la cuenta de facturación «My Maps Billing Account» y una alerta de presupuesto de 1 USD creada por la persona usuaria.
- La opción `weathernext` de `pyproject.toml` (obstore, zarr, xarray) para leer Zarr; hay que añadir `dask` si se abre con `chunks={}`.

## Si se sigue por BigQuery (pasos)

1. Con la cuenta aprobada, abrir «Analytics Hub» en la consola de Google Cloud y suscribirse al listado `weathernext_3_1a067c1e929` (región `us`); queda vinculado como un conjunto de datos del proyecto.
2. Instalar `google-cloud-bigquery` en la PC remota y consultar con la sesión ya guardada.
3. Ejecución en seco de la consulta de un día; si lee unos pocos MB, seguir con el lote.
4. Guardar solo resultados pequeños (CSV) en `datos/`; no copiar tablas completas.

**No verificado:** si la suscripción de Analytics Hub exige facturación activa; cuántos bytes lee en realidad una consulta de un punto; si `imerg_tp_1hr` y `experimental_tp_1hr` son útiles.
