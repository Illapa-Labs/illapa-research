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

- Fechas: `catalogo/eventos*.csv` (9 archivos, incluido `eventos_hemeroteca_2026.csv`, que nace de este capítulo: §5, T15). Se usan las filas con día exacto y confianza por encima de `baja` (las mismas que el capítulo 05): 150 fechas, 143 desde 1983, **121 en temporadas de lluvias desde 1984**.
- Variables diarias: las del capítulo 05 (`predictores.construir`), **con ERA5 completo en los seis puntos** (Matucana, Santa Eulalia alta y Ticlio por la API de Open-Meteo; Chosica, costa de Lima y selva de Tarma por los archivos de Open-Meteo en AWS, capítulo 13), temperatura del mar NOAA OISST (3 cajas), caudal GloFAS y lluvia horaria ERA5, hasta el 24 de octubre de 2026. Corrida del **30 de octubre de 2026 en la PC remota** (GPU RTX 4080 SUPER): commit `ddc70f0`, **5 000 remuestreos** de temporadas y **2 000 mundos nulos** por etiqueta con `gpu.py`.
- Tipos de fuente (heurística de palabras clave sobre la columna `fuente`): instituciones (INDECI, COEN, SINPAD, Defensa Civil, CENEPRED), ciencia (IGP, INGEMMET, Valverde, UNFV, PREDES), DesInventar, prensa de Lima y televisión. Una fecha sin ninguna palabra reconocida cuenta 0 tipos.

## 4. Método

Una sola probabilidad por día: el modelo `lluvia+antecedentes` del capítulo 05 (regularización elegida dentro de cada pliegue), dejando fuera una temporada cada vez, entrenado con la etiqueta base. Se mide contra cada etiqueta alternativa (T12) y por era (T13). Para T12 se **reentrena** además con A, B, D y E.

Métricas: AP, *lift* = AP / tasa base de esa etiqueta, AUC, y aciertos con 5 % de días en alarma. Intervalo de 90 % por bootstrap sobre temporadas completas (5 000 remuestreos, `gpu.auc_ap_lote`); todas las etiquetas usan **los mismos remuestreos**, así que la diferencia contra la base es pareada (columnas `d_*`; si su intervalo excluye 0, la diferencia es real). **Habilidad real:** AP fuera de muestra frente a 2 000 mundos con las fechas desplazadas cíclicamente dentro de cada temporada (mismos eventos por temporada y mismo agrupamiento, sin relación con el tiempo), con ajuste logístico L2 de C fijo (`gpu.ap_real_y_nulas`). El Brier skill de etiquetas raras sale negativo si la probabilidad está calibrada a la base, así que para comparar etiquetas se usan *lift* y AUC.

## 5. Resultados

### T12 · Días mejor documentados (probabilidad entrenada con la base)

| Etiqueta | Fechas en temporada | AP | Lift (90 %) | AUC (90 %) | Aciertos con 5 % de alarmas | Δ lift vs base (90 %) | Δ AUC vs base (90 %) |
|---|---|---|---|---|---|---|---|
| base | 121 | 0,29 | 15,5 (9,9 a 22,9) | 0,903 (0,860 a 0,934) | 53 % | — | — |
| A corroborada | 45 | 0,18 | 25,6 (9,2 a 50,5) | 0,930 (0,892 a 0,956) | 62 % | −3,4 a +30,6 | −0,006 a +0,061 |
| **B severa** | 24 | 0,10 | 26,7 (12,5 a 68,6) | **0,948 (0,912 a 0,974)** | 71 % | −0,1 a +50,0 | **+0,011 a +0,084** |
| C prensa (3+ tipos) | 12 | 0,20 | 107 (3,7 a 205) | 0,952 (0,816 a 0,985) | 67 % | −10,7 a +190 | −0,076 a +0,096 |
| D ampliada (+1 día) | 206 | 0,32 | 10,0 (6,9 a 14,0) | 0,881 (0,832 a 0,918) | 45 % | **−9,2 a −2,8** | **−0,033 a −0,012** |
| E sin solo-inundación | 119 | 0,27 | 14,7 (9,2 a 20,9) | 0,901 (0,857 a 0,933) | 52 % | −3,7 a +0,1 | −0,004 a 0,000 |
| E2 sin mención de inundación | 97 | 0,15 | 10,2 (6,3 a 18,2) | 0,884 (0,839 a 0,921) | 49 % | −9,7 a +0,3 | −0,048 a 0,000 |

- **Hay habilidad real en cada etiqueta.** Contra 2 000 mundos nulos, el AP real supera el percentil 95 de los nulos en todas (base 0,303 contra 0,046; B 0,054 contra 0,023; C 0,125 contra 0,008), con p entre 0,0005 y 0,006.
- **Las fechas más severas (B: 2 o más quebradas activas) se reconocen mejor**: su AUC es 0,045 más alto y la diferencia pareada excluye 0. Las corroboradas por 2 o más archivos (A) y las citadas por 3 tipos de fuente (C) apuntan en la misma dirección, pero con 45 y 12 fechas sus intervalos incluyen 0. T12 se confirma solo para la severidad.
- **Ampliar con el día anterior (D) empeora de forma demostrable:** el evento está en el día catalogado.
- **Reentrenando con la etiqueta alternativa:** A lift 24,8 (AUC 0,937), B 15,5 (0,923), D 9,5 (0,874), E 14,4 (0,900). Con A el modelo entrenado solo con fechas corroboradas es tan bueno como el entrenado con todas; con B (24 fechas) pierde poder.

### T13 · Era y detección

| Era | Fechas en temporada | AP (90 %) | Lift (90 %) | AUC (90 %) | Archivos / tipos de fuente por temporada | Fechas por día de lluvia extrema |
|---|---|---|---|---|---|---|
| 1984-1998 | 43 | 0,22 (0,10 a 0,38) | 11,2 (4,8 a 32,2) | 0,881 (0,816 a 0,930) | 2,4 / 2,1 | 1,30 |
| 1999-2008 | 12 | 0,20 (0,05 a 0,53) | 25,2 (6,3 a 100) | 0,849 (0,643 a 0,988) | **1,0 / 1,0** | 1,50 |
| 2009-2026 | 66 | 0,38 (0,16 a 0,52) | 15,6 (10,2 a 22,7) | 0,921 (0,866 a 0,952) | 2,7 / 3,2 | **2,75** |

- Entre 1999 y 2008 **un solo archivo** del catálogo aporta fechas (2,4 por temporada). Desde 2009 se registran el doble de fechas por cada día de lluvia extrema (índice de detección 2,7 contra 1,3). La lluvia extrema es el percentil 99 de la lluvia diaria de Chosica (ERA5), el mismo umbral para todos los años.
- La AP sube de 0,22 a 0,38, pero casi todo es tasa base (hay más fechas): el *lift* y el AUC tienen intervalos que se solapan entre eras. La habilidad relativa no cambia de forma demostrable, y la época 1999-2008 es demasiado pequeña (12 fechas) para decir nada.
- Control de era: con variables ficticias de era la AP pasa de 0,289 a 0,310 (lift 15,5 a 16,6); recalibrando con la tasa de cada era (un techo, usa las etiquetas) llega a 0,298. Todo dentro del intervalo (0,167 a 0,402).

### T14 · Inundaciones

Solo 2 fechas del catálogo hablan únicamente de inundación (sin mencionar huaico ni nombrar una quebrada), las dos en temporadas de lluvias. Quitarlas no cambia nada (AP 0,289 → 0,277; AUC 0,903 → 0,902). Si se quitan todas las fechas que **mencionan** inundación o desborde en cualquier fila (24 fechas en temporada), la AP baja de 0,289 a 0,198 y el AUC de 0,903 a 0,886; esas 24 fechas son las **más** predecibles (AUC 0,97, 79 % acertadas con 5 % de alarmas) porque son los eventos grandes (1983, 1998, 2017) donde el huaico vino con desborde del Rímac. La teoría T14 **no se confirma**: lo que mezcla inundación no ensucia la etiqueta, la define.

### T15 · Los 20 mayores falsos positivos fuera de muestra

Días con la probabilidad más alta sin fecha ese día ni los vecinos (uno por racimo de 3 días). Primeros diez:

| Día | Prob. | Lluvia 1 d / 3 d en Chosica (mm) | Temporada Niño |
|---|---|---|---|
| 1989-02-11 | 0,61 | 29,7 / 47,1 | no |
| 2008-04-03 | 0,58 | 6,3 / 40,3 | sí |
| 2019-02-09 | 0,54 | 6,8 / 17,3 | sí |
| 1984-02-15 | 0,42 | 9,8 / 34,5 | no |
| 1998-02-07 | 0,37 | 2,3 / 16,1 | sí |
| 2019-01-29 | 0,36 | 5,6 / 12,6 | sí |
| 1998-02-11 | 0,36 | 1,0 / 18,6 | sí |
| 2004-02-11 | 0,35 | 6,8 / 22,6 | no |
| 2025-02-05 | 0,32 | 19,3 / 19,8 | sí |
| 2019-02-17 | 0,28 | 1,3 / 5,7 | sí |

Los otros diez (probabilidades 0,24 a 0,28): 1989-02-20, 1998-03-24, 2026-02-02, 1997-12-10, 1999-02-17, 1984-02-04, 1984-03-09, 2025-02-27, 1985-04-03 y 1984-02-08. Trece de los 20 caen antes de 2015 (épocas con pocas fuentes), 4 en 1997-1998 (Niño extraordinario: pesan más los antecedentes que la lluvia del día) y 6 desde 2019.

**Verificación en la web (30 de octubre de 2026).** El 12 de marzo de 2023, que el modelo marcaba como falso positivo, **sí fue un día con activaciones**. El [Informe de Emergencia N° 599 del INDECI-COEN](https://portal.indeci.gob.pe/wp-content/uploads/2023/03/INFORME-DE-EMERGENCIA-N%C2%BA-599-19MAR2023-LLUVIAS-INTENSAS-EN-EL-DEPARTAMENTO-DE-LIMA-11-DEE.pdf) (19/03/2023, leído completo) dice que «el 12 de marzo de 2023, a las 17:44 horas, se registraron lluvias intensas que causaron la activación de la quebrada Huaycoloro 1, Huaycoloro 2 y Rio Seco 2 en los distritos de Chaclacayo, Cieneguilla, Lurigancho-Chosica y San Juan de Lurigancho». Se agregó como fila de confianza alta a `catalogo/eventos_hemeroteca_2026.csv` (una fila). La prensa de esos días (resultados de búsqueda de El Comercio y La República) menciona además Los Laureles (km 21) y Chacrasana, pero solo se leyó el informe del INDECI, y las quebradas de esa fila no pertenecen a las cuencas de Chosica.

Se buscaron sin éxito 2019-02-09, 2025-02-05 y 2026-02-02 (prensa e informes: solo aparecen eventos cercanos, como el 12 y el 25 de febrero de 2019, las alertas del 10 al 13 de febrero de 2025 con huaico en Matucana, y las activaciones del 24 y 25 de febrero de 2026, que ya están en el catálogo). Antes se habían buscado 1989-02-11, 2008-04-03, 2004-02-11, 1999-02-17 y 2013-03-07, sin hallazgos. **«Sin fuente» no es «no hubo»**: la prensa anterior a 2010 casi no está indexada, y para los años recientes los días con lluvia moderada rara vez salen en un titular.

## 6. Qué se concluye

1. Las fechas más severas (2 o más quebradas activas) se reconocen mejor que la base, y la diferencia es real (AUC +0,045). Las corroboradas por 2 o más archivos o citadas por 3 tipos de fuente tienen la misma dirección sin significancia. Ampliar la etiqueta con el día anterior es peor, de forma demostrable.
2. El catálogo cambia mucho por época: entre 1999 y 2008 hay una sola fuente y casi no hay fechas; desde 2009 se registra más del doble por cada día de lluvia extrema. La habilidad relativa (*lift*, AUC) no cambia de forma demostrable, pero cualquier AP que cruce eras mezcla habilidad con tasa de reporte.
3. Las inundaciones puras son 2 fechas y no pesan. Las fechas que mezclan huaico con desborde son los eventos grandes y son los más fáciles: quitarlas bajaría la habilidad.
4. De los falsos positivos, uno (2023-03-12) resultó ser un día con activaciones oficiales: el catálogo tiene huecos, y el modelo a veces los señala. Los demás siguen sin verificarse.

## 7. Límites

- La corroboración se mide con archivos y tipos de fuente del propio catálogo, que se alimenta en parte de las mismas fuentes originales (varios archivos citan INDECI o a Valverde): «2 archivos» no siempre son dos observaciones independientes. El conteo de tipos usa palabras clave y puede equivocarse.
- C tiene 12 fechas: su intervalo (lift 3,6 a 232) no dice nada.
- El índice de detección usa una sola serie de lluvia (Chosica, ERA5) y supone que la lluvia extrema es igual de peligrosa cada año; la humedad previa y el Niño la modifican.

## 8. Pendientes

- Revisar en hemeroteca (El Comercio, La República) o en los informes del INDECI/COEN de cada fecha los candidatos de T15 que siguen sin fuente (1989-02-11, 2008-04-03, 2004-02-11, 1999-02-17; y 2019-02-09, 2025-02-05, 2026-02-02), y agregar los que se confirmen a `catalogo/eventos_hemeroteca_2026.csv`.

## Reproducir

```bash
uv run descargar-datos --solo open-meteo-predictores noaa-oisst open-meteo-caudal igp-icen
# con GPU: unos 10 minutos (5 000 remuestreos y 2 000 mundos nulos por etiqueta)
uv run --extra gpu --extra notebooks jupyter lab notebooks/07-calidad-de-etiquetas.ipynb
# prueba rápida en el portátil: ILLAPA_B=200 ILLAPA_NULAS=10
```
