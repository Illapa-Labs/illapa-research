# 26 · Lluvia corregida para el mapa de alerta

> **No es una alerta ni una predicción para decidir evacuaciones.** Es investigación sobre cómo mostrar mejor la lluvia pronosticada en el mapa de Illapa. Ante una emergencia llama al 115 (INDECI).

Plan completo, con cuatro etapas y una compuerta por etapa, en el registro de la sesión. Este capítulo se llena etapa por etapa.

## 1. Pregunta

El mapa (`peru-alerta-lluvia`) dibuja la lluvia hora por hora del UK Met Office de 10 km que sirve `illapa-engine`. Usa una malla de 0,2° sobre el Perú y otra de 0,1° en cinco zonas con quebradas (`catalogo/zonas_pronostico.json`). El capítulo 14 midió que sobre el valle del Rímac ese modelo marca unas 2,6 veces más lluvia que PISCOp. ¿Se puede mostrar **la cantidad correcta**, **con más detalle** y **con su probabilidad**, entrenando en la RTX 4080 y sirviendo sin depender de ella?

## 2. Datos

| Dato | Fuente | Detalle |
|---|---|---|
| Lluvia observada | PISCOp v3.0 diario completo (SENAMHI, [Figshare](https://figshare.com/articles/dataset/High-resolution_grids_of_rainfall_for_Peru_-_PISCOp_v3_0_dataset/32411886), GPL-3.0) | 1981-2025, 0,1°. El tiempo es un contador `Z1` (1 = 1981-01-01) con unidades «unknown» |
| Pronóstico | Archivo de `ukmo_global_deterministic_10km` en el bucket público de Open-Meteo (`s3://openmeteo/data/ukmo_global_deterministic_10km/precipitation/chunk_N.om`, CC BY-SA 4.0) | Desde febrero de 2022, archivos de 193 horas en la malla nativa de 0,140625° × 0,09375°. Hay dos formatos: los viejos son planos (lat·lon, tiempo) y los nuevos 3D |
| Lluvia fina | CHIRPS v3 diario `rnl` (tiempo de ERA5) en su malla de 0,05° sobre las cinco zonas (`descargar-datos --solo chirps-malla`) | En descarga en la PC remota desde 1981 (sección 3) |

**Cómo se lee el pronóstico sin cuota.** El bucket da **exactamente** los valores horarios de la API de pronósticos pasados en la celda que la API elige (diferencia 0,0 mm en las 6 celdas del capítulo 14, febrero de 2024). Pero la API no toma la celda más cercana: toma una vecina con una elevación más parecida y devuelve su centro. Por eso `correccion_malla.celdas_api` pregunta una vez a la API qué celda usa para cada nodo del mapa (2 peticiones para los 154 nodos de Lima Este, que caen en 96 celdas nativas). Después `ukmo_bucket` lee toda la historia del bucket, un rectángulo por archivo.

## 3. Etapa 0: CHIRPS en malla (en curso)

- **Servidor.** El del Climate Hazards Center responde desde la PC (4 de noviembre de 2026). `rnl` va de 1981 a hoy; `sat` (tiempo de IMERG), de 1998 a hoy.
- **Formato.** Cada día es un GeoTIFF global de unos 16 MB, LZW, guardado en tiras de una fila (no en teselas), 7 200 × 2 400 celdas de 60° N a 60° S. El mar vale −9999 y no hay marca de «sin dato». La resolución viene guardada en float32 (0,05000000074°); con ese valor la ventana salía una fila más grande, así que se usa la nominal (hay una prueba).
- **Costo.** Leer solo las filas de la ventana toma unos 25 a 45 s por mes para las cinco zonas: unas 4 horas desde 1981.
- **Lo que es el dato diario** (readme del CHC). CHIRPS es un producto de péntadas y meses: estaciones más el satélite CHIRP. El valor diario reparte cada péntada entre sus días con el tiempo de ERA5 o de IMERG, interpolado bilinealmente a 0,05°, en días UTC. **El detalle de 0,05° es real a escala de péntada y mes, no de día.** `chirps_malla.pentadas` recupera la péntada.

**Lo que ya dice el SENAMHI.** Túpac Yupanqui (2015), *Validación de los datos CHIRPS de precipitación para monitoreo de periodos secos y húmedos del Perú* (SENAMHI, Dirección de Hidrología; [PDF en SIGRID](https://sigrid.cenepred.gob.pe/sigridv3/storage/docs/PARA%20PUBLICAR/SENAMHI/Validacion%20de%20datos%20CHIRPS%20de%20Precipitacion%20para%20Monitoreo%20de%20Periodos%20Secos%20y%20Humedos%20en%20el%20Peru.pdf)), comparó 11 índices de lluvia extrema de CHIRPS **v2** diario a 0,05° con estaciones del SENAMHI, entre 1983 y 2014.
- **Estaciones de la zona.** Entre ellas están varias del Rímac: Autisha, Carampoma, Matucana, Ñaña, Santa Eulalia y Huarochirí.
- **Lo que funciona.** La lluvia total, los días con más de 10 y 20 mm (`R10MM`, `R20MM` y sus totales), la intensidad media de los días húmedos (`SDII`) y los días húmedos seguidos (`CDW`).
- **Lo que falla.** Los días de lluvia ligera o nula, sobre todo en toda la costa.
- **Sesgo.** Los índices de las estaciones salen más altos que los de CHIRPS: subestima los extremos.
- **Andes centrales.** Ahí el índice con más estaciones significativas es `SDII`.
- **Qué implica aquí.** Los umbrales de lluvia fuerte en los nodos del valle son bajos (percentil 95 de unos 7 mm), así que caen justo en el rango donde CHIRPS es menos confiable. Además, esas estaciones probablemente entraron en CHIRPS, así que la comparación no es independiente. La comprobación de la etapa 0 agrega estos mismos índices (`R10MM`, `R20MM`, `SDII`, `CDW`) para poder contrastar con ese estudio.

Las comprobaciones contra PISCOp y los pluviómetros se agregan cuando termine la descarga.

## 4. Etapa 1: la cantidad correcta en Lima Este

**Método** (`src/illapa_research/correccion_malla.py`, 10 pruebas):
- **Nodos.** Son los mismos que pide el engine: latitud `north − fila·paso`, longitud `west + col·paso`. Cada nodo es la esquina común de cuatro celdas de PISCOp y toma su media.
- **Día de lluvia.** De 7 a. m. a 7 a. m. de Lima (de 12 a 12 UTC), solo días completos.
- **Correcciones.** Un factor (lluvia observada total sobre la modelada) o un mapeo de 21 cuantiles. Cada una se ajusta por separado en lluvias (diciembre a abril) y en seca, por nodo. El mapeo se hace en dos versiones: con los días de la ventana de 3 × 3 nodos vecinos, o solo con los del propio nodo.
- **Validación.** Cada año hidrológico (julio a junio) se corrige con lo aprendido de los otros años. Se evalúa en los meses de lluvia: 546 días entre febrero de 2022 y diciembre de 2025.
- **Umbrales.** Percentiles 90, 95 y 99 de PISCOp en cada nodo; la mediana sobre nodos es de 5,1, 6,8 y 11,6 mm.

**Resultados** (mediana sobre los 154 nodos; tablas en `catalogo/correccion_lima-este_metricas.csv` y `_resumen.csv`):

| Versión | Sesgo (modelo/obs) | Rango del sesgo entre nodos | Error medio (mm/día) | r diario | Aciertos P90 | Falsas alarmas P90 | CSI P90 | CSI P95 |
|---|---|---|---|---|---|---|---|---|
| Crudo (lo que muestra hoy el mapa) | **2,06** | 0,55 a 27,4 | 3,58 | 0,38 | 0,53 | 0,77 | **0,18** | **0,11** |
| Factor | 0,95 | 0,23 a 3,32 | 1,81 | 0,36 | 0,24 | 0,74 | 0,14 | 0,10 |
| Cuantiles, 3 × 3 vecinos | 0,93 | 0,35 a 3,23 | 1,81 | 0,38 | 0,24 | 0,74 | 0,14 | 0,08 |
| Cuantiles, sin vecinos | **0,99** | **0,68 a 1,39** | **1,71** | 0,37 | 0,27 | 0,74 | 0,15 | 0,08 |

El CSI se calcula por nodo a partir de los aciertos y las falsas alarmas.

**Qué se aprende:**
1. **El sesgo se corrige.** El mapa marca hoy el doble de lluvia en el nodo típico, y hasta 27 veces más en nodos de la costa desértica. Corregido sin vecinos, queda entre 0,68 y 1,39, y el error medio baja a la mitad.
2. **Pero corregir los mm no ayuda a ver la lluvia fuerte; la empeora.** La correlación diaria del modelo con PISCOp es baja (r ≈ 0,38 en un nodo de 10 km). Con eso, los días en que el modelo exagera no son los días en que llueve fuerte. El mapa crudo «acierta» más días fuertes (0,53) porque los marca casi siempre (77 % de falsas alarmas). Una vez corregido, casi nunca llega al umbral: los aciertos bajan a 0,24 y el CSI de 0,18 a 0,14–0,15. En el percentil 99 no acierta ninguno.
3. **La compuerta 1 no pasa tal como se escribió.** El sesgo sí baja a ≈ 1, pero los aciertos empeoran.
4. **El mapeo no gana a un factor.** El mapeo con vecinos no gana al factor. Sin vecinos sí da el sesgo más parejo entre nodos y el menor error medio, pero queda igual que el factor en aciertos.

**Lo que esto implica para la web.** Un mapa de mm corregidos sería más honesto con los totales, pero mostraría menos los días fuertes. La forma de comunicar «puede llover fuerte» con un pronóstico de tan poca habilidad diaria es una **probabilidad** (etapa 3), no un número de mm.

**Límites:**
- 3,5 temporadas de lluvia; PISCOp termina en diciembre de 2025.
- PISCOp es una malla interpolada de estaciones: en la sierra alta tiene pocas.
- Solo Lima Este.
- Solo plazo 0: el archivo guarda la primera parte de cada corrida.

## 5. Etapa 3: probabilidad de lluvia fuerte en Lima Este

**Pregunta.** Para cada nodo y cada día, ¿qué probabilidad hay de que la lluvia del día (7 a. m. a 7 a. m.) pase el percentil 95 de PISCOp en ese nodo?

**Método** (`src/illapa_research/probabilidad_malla.py`, 5 pruebas):
- **Pronóstico.** GEFSv12 reforecast 2000-2019 (NOAA, dominio público): corrida de 00 UTC, miembros c00 y p01-p04, 0,25°. Se lee por rangos de bytes, como en el capítulo 19, pero guardando un rectángulo de 8 × 9 celdas sobre Lima Este. Son 3 065 corridas, unos 33 minutos con 12 procesos en la PC.
- **Día.** Las horas 12 a 36 de la corrida del día `d` son exactamente el día de PISCOp (lead 1, emitido a las 19:00 del día anterior). Las horas 36 a 60 de la corrida `d−1` dan el lead 2.
- **Valor en el nodo.** Interpolación bilineal de cada miembro al nodo.
- **Calibración por nodo.** Regresión logística sobre dos resúmenes del conjunto: la raíz de la media del conjunto, y la fracción de miembros sobre el percentil 95 del propio modelo en ese nodo.
- **Validación.** Dejando una temporada fuera. Los umbrales, el ajuste y la climatología salen solo de las otras temporadas.
- **Comparadores.** La «fracción cruda» (miembros sobre el umbral de PISCOp, lo que daría mostrar el conjunto tal cual) y la climatología del nodo.

**Resultados** (todos los nodos y días de lluvia de 20 temporadas: unos 461 000 pares nodo-día; frecuencia del evento 5,1 %; `catalogo/probabilidad_lima-este_metricas.csv`):

| Versión | Plazo | Brier | Mejora sobre la climatología | AUC | Probabilidad media |
|---|---|---|---|---|---|
| Calibrada | 1 día | 0,0457 | **+6,0 %** | **0,78** | 0,050 |
| Calibrada | 2 días | 0,0456 | +6,2 % | 0,78 | 0,050 |
| Fracción cruda del conjunto | 1 día | 0,200 | −312 % | 0,73 | 0,282 |
| Climatología | — | 0,0486 | 0 | 0,50 | 0,050 |

**Fiabilidad de la calibrada, plazo 1** (`catalogo/probabilidad_lima-este_fiabilidad.csv`):

| Probabilidad dicha | Pares nodo-día | Probabilidad media dicha | Frecuencia observada |
|---|---|---|---|
| < 5 % | 310 732 | 2,3 % | 2,1 % |
| 5 a 10 % | 89 639 | 7,1 % | 8,1 % |
| 10 a 20 % | 50 297 | 13,5 % | 14,3 % |
| 20 a 30 % | 7 330 | 23,6 % | 22,1 % |
| 30 a 50 % | 2 408 | 37,2 % | 31,2 % |
| ≥ 50 % | 670 | 62,5 % | **44,3 %** |

**Qué se aprende:**
1. **Calibrada y con señal.** Hasta el 30 % la probabilidad dice lo que pasa. Por encima exagera un poco: cuando dice 62 %, ocurre 44 %. Los días con 20 % o más son el 2,3 % de los pares nodo-día, y en ellos la lluvia fuerte ocurre entre 4 y 9 veces más que en un día cualquiera.
2. **El conjunto crudo engaña.** Mostrar «cuántos miembros pasan el umbral» diría 80 % cuando ocurre 11 %: el GEFS a 25 km sobrestima la lluvia de la sierra, igual que el UKMO. Sin calibración no sirve para el mapa.
3. **La mejora es modesta.** El Brier mejora un 6 % sobre la climatología. La probabilidad separa días (AUC 0,78), pero casi siempre se queda baja, porque el evento es raro y el pronóstico de lluvia en la sierra es difícil.
4. **El plazo 2 vale lo mismo que el 1.** Cubre las 36 horas del mapa.
5. **Compuerta 3: pasa,** con la salvedad de la banda alta, que se agrupa como «≥ 30 %».

**Para la web.** Tres bandas de probabilidad («normal» < 10 %, «elevada» 10 a 30 %, «alta» ≥ 30 %), calculadas en el engine con la tabla `catalogo/probabilidad_lima-este_lead{1,2}.json`. La tabla da, por nodo, los dos umbrales y los tres coeficientes de la fórmula, sobre los mismos 5 miembros (c00, p01-p04) del GEFS operativo. **Falta verificar** la fuente del GEFS operativo con esos miembros (API de conjuntos de Open-Meteo o NOMADS) y que el GEFS operativo se comporte como el reforecast: son el mismo modelo, pero el reforecast tiene otra asimilación inicial.

**Límites:**
- PISCOp tiene pocas estaciones en la sierra alta.
- El umbral es por nodo y relativo: no es un umbral de peligro.
- Solo Lima Este.
- 2000-2019: el reforecast no llega más allá.

## 6. Reproducir

```bash
uv run descargar-datos --solo chirps-malla     # etapa 0, en la PC remota (unas 4 h)
```

```python
from illapa_research import correccion_malla as M
M.principal("lima-este")    # necesita datos/pisco/PISCOp_d.nc y el extra era5 (s3fs, omfiles); unos 3 min

from illapa_research import probabilidad_malla as P
P.principal("lima-este", procesos=12)   # extra gefs (eccodes); unos 33 min, después de la etapa 1
```
