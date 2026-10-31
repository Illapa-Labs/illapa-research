# 25 · Etiquetas objetivas con satélite: piloto de cambio por temporada

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Prueba si una imagen de satélite puede decir qué quebradas se activaron en una temporada sin depender de que alguien lo haya reportado. Ante una emergencia llama al 115 (INDECI).

Código: [`src/illapa_research/satelite.py`](../src/illapa_research/satelite.py) y [`satelite_piloto.py`](../src/illapa_research/satelite_piloto.py), con pruebas en `tests/test_satelite.py`. Resultados: `catalogo/satelite_cambio_temporadas.csv` y `catalogo/satelite_validacion.csv`. Se ejecuta en la PC remota con `uv run --extra satelite python -m illapa_research.satelite_piloto`.

## 1. Pregunta

Todas las etiquetas del catálogo existen porque alguien las reportó, y los reportes siguen a la gente (capítulo 03). Un flujo de detritos deja una cicatriz (cauce socavado, sedimento nuevo en el abanico y la carretera) se reporte o no. ¿Se ve en imágenes abiertas de 20 m, y sirve como etiqueta independiente?

## 2. Datos y acceso

- Sentinel-2 L2A (2018 en adelante sobre esta zona) desde el catálogo abierto de Microsoft Planetary Computer: lectura anónima, sin cuenta (el cliente solo pide al endpoint público que firme las direcciones de los archivos). Lecturas recortadas, a 20 m, de las bandas B04, B08, B11, B12 y la clasificación de escena SCL (nubes y sombras).
- Landsat colección 2 (1982 en adelante) está en el mismo catálogo y no se usó todavía.
- Con Sentinel-2 no se puede ver un evento día por día: en marzo de 2017 todas las escenas posteriores al gran evento (22 de marzo, 1 y 11 de abril) están cubiertas de nubes sobre las quebradas. Sí se ve la temporada completa comparando una escena antes y otra después, que es la unidad del modelo por quebrada.

## 3. Diseño (fijado antes de ver los resultados de las ocho temporadas)

- Unidad: cuenca × temporada, 24 cuencas con historial, temporadas 2019 a 2026.
- Escena «antes»: la más limpia entre el 15 de octubre y el 15 de diciembre del año anterior; «después»: la más limpia entre el 1 de mayo y el 31 de agosto (estación seca). Limpieza medida con SCL en el disco de cada salida.
- Medida: cambio (después menos antes) del índice dentro de un disco de 700 m alrededor de la salida de cada cuenca, donde está el abanico y la carretera; se exige 80 % de píxeles válidos.
- **Principal:** NBR, que se espera **baje** donde hubo flujo. Secundarias: NDVI (baja) y SWIR (sube).
- Prueba: AUC entre la evidencia (índice estandarizado dentro de cada temporada, con el signo esperado) y la activación del catálogo en esa temporada; p por permutaciones de las etiquetas dentro de cada temporada (2 000).
- Las escenas elegidas por temporada están en el CSV (`antes`, `despues`).

## 4. Resultados

110 pares cuenca-temporada con datos válidos (22 de 24 cuencas; las dos restantes no tienen píxeles válidos en el disco), 20 de ellos con activación en el catálogo. Las temporadas 2021, 2022 y 2025 no tienen activaciones ubicadas y no aportan a la prueba.

| Índice | Signo esperado | AUC | p |
|---|---|---|---|
| **NBR (principal)** | baja | **0,61** | 0,17 |
| NDVI | baja | 0,61 | 0,054 |
| SWIR | sube | 0,52 | 0,35 |

Exploratorio, quitando el efecto de cuenca y el de temporada (estandarización de dos vías, no pre-registrado): NBR 0,55 (p = 0,54), NDVI 0,63 (p = 0,053), SWIR 0,58 (p = 0,078).

## 5. Lectura

- **No hay una señal utilizable como etiqueta.** El AUC va de 0,52 a 0,63 con el signo esperado, pero ninguna medida pasa el 5 % y la principal pre-registrada queda en p = 0,17. Con 20 positivos esto no distingue un efecto pequeño de ruido.
- **Un caso previo a mano (temporada 2019, 22 cuencas) dio el signo contrario** con el NBR, un recordatorio de por qué se fijó el diseño antes: mirando índices uno por uno aparece cualquier cosa.
- **Por qué es difícil con esta medida:** el disco de 700 m mezcla abanico, urbanización y cultivos; el verdor cambia entre octubre y junio por la lluvia misma (los píxeles de ladera «reverdecen» más donde llovió más, sin que haya flujo); y 20 m no resuelven un cauce de 10 a 30 m de ancho.
- **Los negativos del catálogo no son negativos confirmados.** Una cuenca sin activación registrada puede haberse activado sin reporte; ese ruido de etiqueta baja el AUC máximo alcanzable.

## 6. Límites

- Solo 2019 a 2026 (Sentinel-2 sobre la zona); la temporada 2017, la más grande, no tiene escena limpia posterior en el período de lluvias y la estación seca siguiente no se probó.
- Se usó una escena por fecha, sin compuestos. Un compuesto (mediana de varias escenas limpias) reduce el ruido.
- No se separó el cauce del resto: una máscara del cauce a partir del DEM (acumulación de flujo) y bandas de 10 m son el siguiente paso lógico.

## 7. Qué sigue

Un segundo diseño, pre-registrado antes de correrlo: máscara de cauce y abanico a partir del DEM en vez del disco; NDVI y NBR a 10 m; compuestos de mediana para «antes» y «después»; línea base por cuenca; y un control positivo con un evento muy grande y bien documentado (2017) usando Landsat de la estación seca. Si tampoco separa, se descarta esta vía y se deja como resultado negativo.
