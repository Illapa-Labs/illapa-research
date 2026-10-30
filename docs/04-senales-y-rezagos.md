# 04 · Señales y rezagos: ¿qué cambia días antes de un huaico?

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Es un análisis descriptivo con un catálogo de fechas incompleto. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

Notebook: [`notebooks/04-senales-y-rezagos.ipynb`](../notebooks/04-senales-y-rezagos.ipynb). Código: [`src/illapa_research/senales.py`](../src/illapa_research/senales.py), con pruebas en `tests/test_senales.py`. Este capítulo se actualiza cada vez que llegan datos nuevos; la sección «Con qué datos se corrió» dice qué había en cada corrida.

## 1. Pregunta e hipótesis

La lluvia del día separa los días de huaico del resto (AUC 0,82 en el notebook 02) pero da muchas falsas alarmas. ¿Hay algo que cambie **antes**? Cinco hipótesis, escritas antes de mirar los resultados:

| | Hipótesis | Datos |
|---|---|---|
| H1 | El mar (anomalía y alza de 3, 7 y 14 días) sube días antes del huaico. | NOAA OISST v2.1: Niño 1+2, costa de Perú y costa de Lima |
| H2 | El calor aguas arriba (temperatura, isoterma de 0 °C, nieve) precede al huaico o al aumento del caudal. | ERA5 en Ticlio, Santa Eulalia alta y Matucana |
| H3 | La humedad de la selva (punto de rocío, nubes) y el gradiente de presión selva-costa preceden al huaico. | ERA5 en Tarma (selva), Lima (costa) y Chosica |
| H4 | El caudal y la humedad del suelo señalan condiciones previas. | GloFAS, ERA5 |
| H5 | El efecto del mar es de régimen lento (entre temporadas), no un disparador diario. | lo anterior más ONI/ICEN |

**Qué cuenta como señal** (fijado de antemano):

- El rezago 0 es el propio día. Describe la tormenta y **no es un precursor**; solo cuenta el rezago ≥ 1 día.
- Una variable en un rezago es *señal* si su AUC supera una nula y pasa Benjamini-Hochberg con q = 0,10 sobre todas las pruebas. La nula mueve las etiquetas de huaico 7 a 25 días dentro de la misma temporada: conserva el número de eventos y su agrupamiento, y la fase del calendario, de modo que una variable que solo sigue la estación no pasa.
- Es *robusta* si además mantiene el signo con p < 0,10 en 2009+ y sin las temporadas 1983, 1998 y 2017 (las de más reporte).
- Benjamini-Hochberg controla la tasa de falsos descubrimientos; como referencia de azar se cuenta cuántas pruebas pasan p < 0,05 frente a `0,05 × pruebas`.

## 2. Datos y licencias

| Dato | Fuente | Licencia / uso | Cómo se obtiene |
|---|---|---|---|
| Fechas de huaico (día exacto, confianza no baja): 147 fechas, 118 en temporadas 1984-2026, 64 episodios | `catalogo/` (INDECI, IGP, prensa; cada fila cita su fuente) | Hechos citados | ya en el repositorio |
| Temperatura diaria del mar | NOAA OISST v2.1 vía ERDDAP de CoastWatch; promedios de la caja Niño 1+2 y de la costa de Perú (celdas de 1°) y de la costa de Lima (0,25°) | Dominio público | `descargar-datos --solo noaa-oisst` |
| Temperatura, humedad, presión, nubes, nieve, suelo, radiación en 6 puntos | Open-Meteo (ERA5), resúmenes diarios | CC BY 4.0; la API gratuita es solo no comercial | `descargar-datos --solo open-meteo-predictores` |
| Caudal diario | Open-Meteo (GloFAS v4), 3 puntos cerca de Chosica y Matucana | CC BY 4.0; modelo, no medición | `descargar-datos --solo open-meteo-caudal` |
| Lluvia horaria y suelo en Chosica y la cuenca alta | Open-Meteo (ERA5), de la primera fase | CC BY 4.0 | `descargar-datos --solo open-meteo-horario` |
| Temporadas Niño | ONI de NOAA e ICEN oficial del IGP/ENFEN | dominio público / público del IGP | `descargar-datos --solo noaa-enso igp-icen` |

Anomalías respecto de una climatología suavizada por día del año de 1991-2020. La isoterma de 0 °C se estima con la temperatura a 2 m y un gradiente estándar de 6,5 K/km (no se usó una variable de nivel de congelamiento: la API histórica no la entrega).

### Con qué datos se corrió

**Corrida actual (30 de octubre de 2026, PC remota con GPU, 10 000 réplicas de la nula por prueba):**

- ERA5 en **los 6 puntos**. Tres vienen de la API de Open-Meteo (Matucana, Santa Eulalia alta, Ticlio) y tres de los archivos de Open-Meteo en AWS, con corrección de altura (Chosica, costa de Lima, selva de Tarma; ver [`13-era5-alterno.md`](13-era5-alterno.md)). Los de AWS coinciden bien con la API en punto de rocío, presión, nubosidad y suelo (correlación diaria 0,85-0,90), peor en lluvia y temperatura media; por eso H3 usa solo punto de rocío, presión y nubosidad, y la lluvia sale de la serie horaria del primer estudio. Último día con datos: 24 de octubre de 2026.
- Mar: las tres cajas (Niño 1+2, costa de Perú y costa de Lima), 1982 a octubre de 2026.
- Caudal GloFAS, 3 puntos, 1984-2026 (los de «Rímac Chosica» y «Santa Eulalia» caen en casi la misma celda y se comportan igual). Lluvia horaria y suelo de Chosica y la cuenca alta de la primera fase.

**Corrida anterior (30 de octubre, portátil, 3 de 6 puntos de ERA5, 1 000 réplicas):** sin Chosica, costa de Lima ni selva de Tarma, así que H3 no se pudo probar. Las cifras de esa corrida se conservan en el historial de git (`23ae47a`, `424583e`).

**Qué cambió al pasar a los 6 puntos y 10 000 réplicas**

| | 3 puntos, 1 000 réplicas | 6 puntos, 10 000 réplicas |
|---|---|---|
| Pruebas (variable × rezago 0-14) | 735 | 825 |
| Pasan Benjamini-Hochberg (crudo / sin la media de la temporada) | 121 / 121 | 153 / 132 |
| p < 0,05 (crudo) contra el azar | 165 contra 37 | 182 contra 41 |
| Robustas (rezago ≥ 1) | 56 de 686 | 68 de 770 |
| Por hipótesis (robustas) | H1 14, H2 21, H3 sin datos, H4 21 | H1 16, H2 22, H3 7, H4 23 |

Todo lo que ya estaba (suelo, caudal, alza del mar en 14 días, frío del día anterior) **se mantiene con las mismas cifras redondeadas**. Lo nuevo es H3 y que la anomalía de la costa de Lima se suma a la lista de robustas de H1. Los cambios de H2 son un rezago más (Matucana 5 días) y no alteran la lectura.

## 3. Método

1. **Rezagos.** Para cada variable `x` y cada rezago `k` de 0 a 14 días se calcula el AUC de `x(t-k)` para separar los días con huaico de los demás, en días de temporada de lluvias (diciembre a abril) desde 1984. Se calcula con rangos y se compara con las réplicas de la nula (10 000 en la PC con GPU, `ILLAPA_N_NULL` y `ILLAPA_GPU=1`; el AUC de todas las réplicas es un solo producto de matrices).
2. **Sin la media de cada temporada.** Se resta a cada variable la media de su temporada: queda solo el momento dentro de la temporada.
3. **Entre temporadas.** Correlación de Spearman entre la media de cada variable en la temporada y el número de días con huaico de esa temporada (un punto por temporada, p por permutación de los conteos).
4. **Composites.** Promedio del puntaje z de la variable de 14 días antes a 3 después del inicio de cada episodio (días con huaico a 3 días o menos cuentan como uno: 2017 cuenta una vez), contra una nula que mueve cada episodio a un día cualquiera de la misma temporada.
5. **Robustez.** Ventanas 1984+, 2009+, sin 1983-1998-2017, y solo temporadas Niño o sin Niño (ICEN oficial o ONI ≥ +0,5).

## 4. Resultados

Todas las cifras de esta sección salen de la corrida descrita arriba.

### Visión general

- **825 pruebas** (variable × rezago 0 a 14) en el período completo: 153 pasan Benjamini-Hochberg; 182 tienen p < 0,05 contra 41 esperadas por azar. Sin la media de cada temporada: 132 y 185. Es decir, **hay estructura de verdad**, pero buena parte es persistencia: variables muy autocorrelacionadas (suelo, caudal) dan el mismo hallazgo en rezagos vecinos, que no son pruebas independientes.
- **68 de 770** combinaciones con rezago ≥ 1 son robustas. Por hipótesis: H4, 23 de 182; H2, 22 de 294; H1, 16 de 210; H3, 7 de 84.

### H4 · Suelo y caudal: la señal más fuerte, y lo más obvio

- **Humedad del suelo en Chosica**, AUC **0,75** un día antes, **0,73** a tres días (0,79 desde 2009) y robusta en rezagos 1 a 3. Es la lluvia acumulada de los días anteriores, no un fenómeno aparte.
- **Alza del caudal en 3 días** (GloFAS): AUC 0,64-0,65 con 5 a 7 días de antelación, robusta; más fuerte en temporadas sin Niño (AUC 0,82) que en temporadas Niño (0,62), aunque con pocos eventos.
- Suelo de ERA5 en Matucana y Santa Eulalia alta: AUC 0,59-0,62 con 1 a 4 días.
- Con 10 000 réplicas el alza del caudal en Chosica añade el rezago de 4 días (AUC 0,63) a los de 5 a 7.

### H1 · El mar: sí en régimen y también una señal diaria débil (H5)

- Anomalía del mar en Niño 1+2 y costa de Perú, un día antes: **AUC 0,71** (0,66 a 14 días). Es sobre todo **entre temporadas**: al quitar la media de cada temporada baja a **0,59-0,60**, y la anomalía de 30 días a 0,51-0,53.
- Correlación entre temporadas (43): alza del mar de la costa de Perú en 14 días **ρ = 0,41** (p = 0,007), anomalía Niño 1+2 **0,39** (p = 0,008), anomalía de 7 días 0,38 (p = 0,013). Pasan la corrección 8 de 25 variables probadas (cinco del mar, el suelo de Chosica y dos de caudal; esperadas por azar a p < 0,05: 1,2).
- **Lo que queda dentro de la temporada** es el **alza del mar en 14 días**: AUC centrado **0,66** (costa de Lima) y **0,64** (costa de Perú) con 1 a 3 días de antelación; robusta en las dos cajas (0,66 y 0,65 desde 2009; 0,64-0,66 en temporadas Niño y 0,59-0,66 en las que no). La anomalía de la costa de Lima el día anterior también (0,64 centrada, robusta en rezagos 1 y 2). En el composite, de los 14 días previos al inicio del episodio, 7 (costa de Perú) y 4 (costa de Lima) quedan por encima de la banda nula; ninguno por debajo. El alza de 7 días en Niño 1+2 pasa solo con rezago de 1 día (0,59).
- Lectura: H5 se confirma en lo grueso (el mar marca el régimen; la anomalía de largo plazo pierde toda la señal al centrar), pero hay una señal diaria débil de **calentamiento rápido de la costa en las dos semanas previas**, consistente en tres cajas y en las ventanas de cobertura. No se sabe si es causa, es consecuencia de un patrón de circulación común (menos viento costero y más nubosidad antes de un evento) o es coincidencia con pocos episodios; con 64 episodios y muchas pruebas, se trata como hipótesis para probar con datos nuevos, no como mecanismo.

### H2 · Calor aguas arriba: no hay precursor de calor; hay frío y nubes el día anterior

- Ticlio y Santa Eulalia alta: la anomalía de temperatura y de la isoterma de 0 °C es **negativa** el día antes (AUC 0,35-0,38) y el mismo día (0,28-0,31): la firma de la tormenta (nubes y frío), no calor. No hay señal con rezago de 2 días o más.
- **Matucana** (única en mostrar algo del lado cálido): la anomalía cálida **8 a 11 días antes** tiene AUC 0,61-0,64 (0,60 desde 2009), es robusta y aparece tanto con Niño (0,57) como sin él (0,60). Seguida de enfriamiento el día anterior (AUC 0,37). Podría ser el ciclo sinóptico «tiempo cálido y seco → sistema frío y húmedo»; solo la ve un punto de tres, así que se trata como hallazgo a repetir con más puntos y no como precursor.
- Nieve acumulada: sin señal robusta.
- Conclusión para H2: **no se sostiene** la idea de que el calor en las cabeceras en los días inmediatos suba el río o dispare el huaico. La temperatura aporta solo como firma de la propia tormenta.

### H3 · Selva y gradiente de presión: la humedad de la selva **no** precede; la de la costa sí, poco

Con ERA5 de los 6 puntos (6 variables, 84 pruebas con rezago ≥ 1; 13 pasan BH, 7 son robustas):

- **Punto de rocío de la selva (Tarma)**: AUC 0,50 el día antes (crudo) y **0,45 centrado**, sin señal en ningún rezago. Si algo, la selva está un poco más seca de lo normal el día antes. **H3 no se sostiene en su parte de humedad de la selva**: el aire húmedo amazónico no se ve días antes en este punto.
- **Nubes de la selva**: AUC 0,64 (crudo) y 0,60 (centrado) con 1 a 2 días de antelación; es cubierta nubosa en los días inmediatos, no humedad acumulada, y no es robusta.
- **Costa de Lima**: anomalía del punto de rocío de los 3 días previos, **AUC 0,74 (crudo) y 0,63 (centrado)** el día antes, robusta solo en el rezago 1 (0,62 desde 2009; 0,61 en temporadas Niño y 0,71 en las que no); nubes de la costa 0,63-0,66 (crudo), robustas en los rezagos 1, 3 y 6 (0,62-0,63 desde 2009). Va junto con el mar cálido de la costa de Lima (H1): son la misma señal costera (más humedad y nubosidad cuando el mar está más cálido), no dos independientes.
- **Gradiente de presión Chosica menos Tarma**: AUC centrado 0,62 el día antes y 0,64 el mismo día, y señales sueltas con signo cambiante en rezagos 8 a 13 (0,36 a 0,62): no se interpreta; en el composite 6 de los 14 días previos quedan por debajo de la banda.
- Lectura: lo que acompaña al huaico por el lado de la humedad es **costero** (nubosidad y punto de rocío de la costa de Lima, con el mar cálido), no un pulso de humedad de la selva. Es un indicio, no un mecanismo.

## 5. Lo concurrente frente a lo antecedente

Los valores a rezago 0 son más extremos que a rezago 1 en las variables de temperatura (por ejemplo, Santa Eulalia alta: AUC 0,28 el día contra 0,35 el día anterior). Un modelo que use esas variables el mismo día **no es un aviso**: ya está lloviendo.

## 6. Límites

- El catálogo trae 118 días con huaico en la temporada de lluvias desde 1984, agrupados en 64 episodios y en 43 temporadas; 2017 solo aporta 23 días. La fecha publicada puede ser la del día siguiente a un evento nocturno.
- Los datos de reanálisis (ERA5) no ven bien la lluvia convectiva de las quebradas y el caudal de GloFAS es un modelo, no una medición.
- Cientos de pruebas autocorrelacionadas: la corrección de Benjamini-Hochberg asume dependencia positiva, que es lo razonable aquí, pero las pruebas no son independientes y los hallazgos en rezagos vecinos son una sola cosa.
- Se mantuvo una regla única de robustez; otras reglas darían listas algo distintas.
- Un AUC de 0,65 a 0,75 con rezago ≥ 1 no es una alarma: en 6 473 días de temporada con 118 días de huaico casi cualquier umbral sobre estas variables da muchas falsas alarmas.

## 7. Qué falta y qué se pide a otros módulos

- Repetir H2 con más puntos de altura (solo hay tres: Ticlio, Santa Eulalia alta y Matucana). La anomalía cálida de Matucana a 8-11 días sigue siendo un hallazgo de un solo punto.
- Probar H3 con otra variable de la selva (viento a 700 hPa u OLR; hay un archivo de OLR en `datos/circulacion/`): el punto de rocío a 2 m de un solo punto de la selva es una medida pobre de la humedad que entra.
- Repetir la prueba con **lluvia como control** (efecto de la variable una vez descontada la lluvia del día y de los días previos), en un modelo multivariable validado dejando temporadas fuera; esto lo cubre el notebook 05, no este.
- Cambios sugeridos en otros archivos (no hechos aquí, por ser de otro dueño):
  - `predictores.construir`: añadir el flag `rezago_minimo` por familia, para que el modelo diario solo use información de ≥ 1 día antes.
  - `datos/enso/oisst_diario.csv` trae fechas duplicadas en los límites de año; `senales.cargar_matriz` las quita, pero conviene corregir el consolidado en `fuentes.py`.
  - `evaluacion_diaria.rezagos` (bootstrap por temporadas) se usó solo como comprobación; el notebook 04 usa los rangos y la nula de `senales.py`, mucho más rápidos.
