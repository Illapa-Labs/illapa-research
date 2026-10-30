# 07 · Calidad de la etiqueta, era y severidad

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide qué tan bien el tiempo atmosférico explica las fechas que alguien registró, con los huecos del catálogo tal como están. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

Notebook: [`notebooks/07-calidad-de-etiquetas.ipynb`](../notebooks/07-calidad-de-etiquetas.ipynb). Código: [`src/illapa_research/etiquetas_calidad.py`](../src/illapa_research/etiquetas_calidad.py), con pruebas en `tests/test_etiquetas_calidad.py`. Usa el modelo y la validación del [capítulo 05](05-modelo-diario.md) sin tocarlos.

## 1. Pregunta

El modelo diario se entrena con «hay una fecha de huaico catalogada». Pero (a) no todas las fechas están igual de corroboradas, (b) el catálogo describe distinto cada época, y (c) mezcla huaicos con inundaciones. ¿Cuánto de la habilidad del modelo, y de sus errores, depende de cómo se hizo la etiqueta?

## 2. Teorías (escritas antes de mirar ningún puntaje)

| | Teoría | Se confirma si |
|---|---|---|
| T12 | El modelo predice mejor los días mejor documentados | las etiquetas A (fecha en 2 o más archivos del catálogo o confianza alta), B (2 o más quebradas ubicadas activas el mismo día) y C (citada por 3 o más tipos de fuente) tienen más *lift* y AUC que la base, con intervalos que no se solapan |
| T13 | El sesgo de reporte cambia por era | la habilidad y las fechas por día de lluvia extrema cambian entre 1984-1998, 1999-2008 y 2009-2026, y un control de era cambia el resultado |
| T14 | Las inundaciones mezcladas con huaicos degradan la etiqueta | quitar las fechas que solo hablan de inundación (o que la mencionan) sube la habilidad |
| T15 | Los falsos positivos de mayor probabilidad son en parte huaicos sin registrar | la web o los informes confirman huaicos en esos días |

## 3. Datos y versión

- Fechas: `catalogo/eventos*.csv` (8 archivos). Se usan las filas con día exacto y confianza por encima de `baja` (las mismas que el capítulo 05): 147 fechas, 140 desde 1983, 118 en temporadas de lluvias desde 1984.
- Variables diarias: las del capítulo 05 (`predictores.construir`). **Corrida del 30 de octubre de 2026**, con: ERA5 (Open-Meteo) en Matucana, Santa Eulalia alta y Ticlio; **MERRA-2 (NASA POWER, malla gruesa) en Chosica, costa de Lima y selva de Tarma**, porque Open-Meteo agotó su cuota diaria; temperatura del mar NOAA OISST (3 cajas) hasta el 14 de octubre; caudal GloFAS y lluvia horaria de Chosica y cuenca alta (ERA5) hasta el 29 de octubre. **Todas las cifras de abajo salen de esa versión**; hay que repetirlas cuando llegue ERA5 en los tres puntos que faltan (pendiente, ver §8).
- Tipos de fuente (heurística de palabras clave sobre la columna `fuente`): instituciones (INDECI, COEN, SINPAD, Defensa Civil, CENEPRED), ciencia (IGP, INGEMMET, Valverde, UNFV, PREDES), DesInventar, prensa de Lima y televisión. Una fecha sin ninguna palabra reconocida cuenta 0 tipos.

## 4. Método

Una sola probabilidad por día: el modelo `lluvia+antecedentes` del capítulo 05 (regularización elegida dentro de cada pliegue), dejando fuera una temporada cada vez, entrenado con la etiqueta base. Se mide contra cada etiqueta alternativa (T12) y por era (T13). Para T12 se **reentrena** además con A, B, D y E. Métricas: AP, *lift* = AP / tasa base de esa etiqueta, AUC, Brier skill contra la climatología por mes y aciertos con 5 % de días en alarma; intervalo de 90 % por bootstrap sobre temporadas completas (200 remuestreos). El Brier skill de etiquetas raras sale negativo porque la probabilidad está calibrada a la tasa de la base: para comparar etiquetas se usan *lift* y AUC.

## 5. Resultados

### T12 · Días mejor documentados (probabilidad entrenada con la base)

| Etiqueta | Fechas en temporada | AP | Lift (90 %) | AUC | Aciertos con 5 % de alarmas |
|---|---|---|---|---|---|
| base | 118 | 0,28 | 15,5 (10,1 a 21,5) | 0,90 | 56 % |
| A corroborada | 42 | 0,15 | 22,9 (7,6 a 42,8) | 0,93 | 57 % |
| B severa | 24 | 0,09 | 23,9 (12,3 a 50,0) | 0,945 | 67 % |
| C prensa (3+ tipos) | 12 | 0,18 | 99 (16 a 147) | 0,96 | 75 % |
| D ampliada (+1 día) | 200 | 0,31 | 10,2 (7,2 a 13,6) | 0,88 | 48 % |

La dirección es la esperada (más corroboración, más *lift* y más AUC), pero los intervalos de A, B y C **se solapan con el de la base**: con 12 a 42 fechas no se puede afirmar. Ampliar con el día anterior (D) empeora, no ayuda: el evento se ubica en el día catalogado y no en el anterior.

**Reentrenando con la etiqueta alternativa** no se gana nada: A *lift* 12,3 (AUC 0,93), B 12,7 (0,90), D 9,9, E 15,0 (0,905). Es decir, las fechas bien documentadas son más fáciles de reconocer cuando el modelo se entrenó con *todas*, no cuando se entrena solo con ellas (pocos positivos).

### T13 · Era y detección

| Era | Fechas en temporada | AP | Lift | AUC | Archivos / tipos de fuente por temporada | Fechas por día de lluvia extrema |
|---|---|---|---|---|---|---|
| 1984-1998 | 43 | 0,21 | 11,1 | 0,88 | 2,4 / 2,1 | 1,30 |
| 1999-2008 | 12 | 0,15 | 18,6 | 0,85 | **1,0 / 1,0** | 1,50 |
| 2009-2026 | 63 | 0,40 | 17,2 | 0,93 | 2,4 / 2,9 | **2,62** |

- Entre 1999 y 2008 **un solo archivo** del catálogo aporta fechas (2,4 por temporada). Desde 2009 se registran el doble de fechas por cada día de lluvia extrema (índice de detección 2,6 contra 1,3). La lluvia extrema es el percentil 99 de la lluvia diaria de Chosica (ERA5), el mismo umbral para todos los años.
- La AP sube de 0,21 a 0,40 en 2009-2026, pero casi todo es tasa base (hay más fechas): el *lift* queda en 11 a 19 con intervalos amplios. La habilidad relativa no cambia de forma demostrable entre eras.
- Control de era: con variables ficticias de era la AP pasa de 0,282 a 0,293 y el *lift* de 15,5 a 16,1; recalibrando con la tasa de cada era (un techo, usa las etiquetas) llega a 0,302. Son diferencias dentro del ruido.

### T14 · Inundaciones

Solo 6 fechas del catálogo hablan únicamente de inundación (sin mencionar huaico ni nombrar una quebrada), 2 en temporadas de lluvias. Quitarlas no cambia nada (AP 0,282 → 0,268; AUC 0,903 → 0,902). Si se quitan todas las fechas que **mencionan** inundación o desborde en cualquier fila (24 filas en temporada), la AP baja de 0,282 a 0,176 y el AUC de 0,903 a 0,883; esas 24 fechas son las **más** predecibles (AUC 0,98, 92 % acertadas con 5 % de alarmas) porque son los eventos grandes (1983, 1998, 2017) donde el huaico vino con desborde del Rímac. La teoría T14 **no se confirma**: lo que mezcla inundación no ensucia la etiqueta, la define.

### T15 · Los 20 mayores falsos positivos fuera de muestra

Días con la probabilidad más alta sin fecha ese día ni los vecinos (uno por racimo de 3 días). Primeros diez:

| Día | Prob. | Lluvia 1 d / 3 d en Chosica (mm) | Temporada Niño |
|---|---|---|---|
| 1989-02-11 | 0,74 | 29,7 / 47,1 | no |
| 2008-04-03 | 0,73 | 6,3 / 40,3 | sí |
| 2004-02-11 | 0,70 | 6,8 / 22,6 | no |
| 1997-12-09 | 0,49 | 0,6 / 0,8 | sí |
| 1999-02-17 | 0,43 | 15,1 / 35,8 | no |
| 1998-02-07 | 0,37 | 2,3 / 16,1 | sí |
| 1998-02-11 | 0,36 | 1,0 / 18,6 | sí |
| 2013-03-07 | 0,35 | 2,6 / 25,0 | no |
| 1989-02-20 | 0,35 | 13,2 / 35,7 | no |
| 1998-01-22 | 0,34 | 4,4 / 6,5 | sí |

Los otros diez (probabilidades 0,26 a 0,32) son de 1984, 1998, 1999, 2017, 2019, 2024 y 2025. Se ve un patrón: 6 de los 20 caen en 1997-1998 (Niño extraordinario, con más antecedentes que lluvia del día) y 14 en 1984-2008, las épocas con menos fuentes. Los candidatos con más lluvia (1989-02-11 con 47 mm en 3 días, 2008-04-03 con 40 mm, 1989-02-20, 1999-02-17) son los que más valdría revisar en la hemeroteca.

**Verificación en la web (30 de octubre de 2026).** Se buscaron 1989-02-11, 2008-04-03, 2004-02-11, 1999-02-17 y 2013-03-07 en prensa y repositorios. **No se encontró confirmación ni refutación**: los resultados fueron de otros años (1998, 2015, 2017, 2019, 2023) o no mencionaron esas fechas. Tampoco aparecen en la cronología del IGP (2023) ni en el cuadro de eventos históricos del informe INGEMMET A7458. La prensa anterior a 2010 casi no está indexada; la prueba requiere la hemeroteca (El Comercio, La República) o los archivos de INDECI. **No se agregó ninguna fecha nueva al catálogo**; no se creó `catalogo/eventos_hemeroteca_2026.csv` porque no hay nada verificado que poner.

## 6. Qué se concluye

1. Las fechas mejor documentadas son algo más fáciles de reconocer (*lift* y AUC más altos), pero con 12 a 42 fechas la diferencia no es significativa, y reentrenar con ellas no mejora.
2. El catálogo cambia mucho por época: entre 1999 y 2008 hay una sola fuente y casi no hay fechas; desde 2009 se registra el doble por cada día de lluvia extrema. La habilidad relativa (*lift*) no cambia de forma demostrable, pero cualquier AP que cruce eras mezcla habilidad con tasa de reporte.
3. Las inundaciones puras son 6 fechas y no pesan. Las fechas que mezclan huaico con desborde son los eventos grandes y son los más fáciles.
4. Los falsos positivos más fuertes son, en su mayoría, épocas con pocas fuentes o con Niño extraordinario; no se pudo comprobar que sean huaicos sin registrar.

## 7. Límites

- La corroboración se mide con archivos y tipos de fuente del propio catálogo, que se alimenta en parte de las mismas fuentes originales (varios archivos citan INDECI o a Valverde): «2 archivos» no siempre son dos observaciones independientes. El conteo de tipos usa palabras clave y puede equivocarse.
- C tiene 12 fechas: su intervalo (lift 16 a 147) no dice nada.
- El índice de detección usa una sola serie de lluvia (Chosica, ERA5) y supone que la lluvia extrema es igual de peligrosa cada año; la humedad previa y el Niño la modifican.
- Las cifras salen de la versión de datos de §3, con tres puntos de MERRA-2.

## 8. Pendientes

- Repetir con ERA5 en Chosica, costa de Lima y selva de Tarma cuando termine la descarga programada de Open-Meteo (tras la renovación diaria de la cuota). `modelo_diario.cargar_datos` ya lee el archivo consolidado cuando existe, así que basta volver a ejecutar el notebook; hay que actualizar las cifras de §5.
- Revisar en hemeroteca los candidatos de T15 y, si se confirman, agregarlos en `catalogo/eventos_hemeroteca_2026.csv` con el mismo esquema que los otros archivos.
- Sugerencia para el módulo de otro worker (no se tocó): `modelo_diario.matrices` produce un `PerformanceWarning` por fragmentación de marcos; basta construir las columnas con `pd.concat` de una vez.

## Reproducir

```bash
uv run descargar-datos --solo open-meteo-predictores noaa-oisst open-meteo-caudal igp-icen
uv run jupyter lab notebooks/07-calidad-de-etiquetas.ipynb   # unos 80 segundos
```
