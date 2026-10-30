# 05 · Modelo diario: ¿qué explica que un día haya huaico?

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide cuánto del catálogo de fechas se explica con el tiempo atmosférico, con los huecos del catálogo tal como están. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

Notebook: [`notebooks/05-modelo-diario.ipynb`](../notebooks/05-modelo-diario.ipynb). Código: [`src/illapa_research/modelo_diario.py`](../src/illapa_research/modelo_diario.py), con pruebas en `tests/test_modelo_diario.py`. Reutiliza `predictores.py` (variables) y `evaluacion_diaria.py` (etiquetas, pliegues, métricas y nula). Este capítulo se actualiza cada vez que llegan datos nuevos; las secciones «Con qué datos se corrió» y «Qué cambió frente a la corrida con 3 puntos de ERA5» dicen qué había en cada corrida.

## 1. Pregunta

Con la información disponible hasta *ayer* (humedad del suelo, lluvia previa, caudal, temperatura del mar, calor aguas arriba, estado de El Niño), ¿se puede decir mejor que con el calendario si hoy hay un día con huaico catalogado en Chosica, Chaclacayo, Santa Eulalia o Ricardo Palma? ¿Cuánto suma la lluvia del propio día? ¿Hay interacciones que un modelo lineal no ve?

Corresponde a las teorías T7 (los antecedentes definen un régimen favorable y la lluvia del día es el disparador) y T8 (interacciones no lineales) del capítulo 00. Dentro de este capítulo las alternativas se numeran de nuevo, y se escribieron antes de ver ningún puntaje:

| | Teoría | Variables |
|---|---|---|
| T1 | Solo la fecha | frecuencia por mes de calendario |
| T2 | Lluvia del día | lluvia de 1 y 3 días y picos horarios en Chosica, cuenca alta, Matucana, Santa Eulalia alta y Ticlio |
| T3 | Antecedentes («régimen favorable») | **todo** desplazado un día: suelo, lluvia previa de 7 y 30 días, caudal, temperatura del mar, calor y 0 °C aguas arriba, nieve, radiación |
| T4 | Lluvia + antecedentes | T2 y T3 juntos |
| T5 | T4 + Niño | T4 más el ICEN oficial del mes previo y la media de los tres meses previos. T5b (oráculo): más la marca de temporada Niño, que solo se conoce a posteriori |
| T6 | No lineal | gradient boosting con árboles de 4 hojas, 40-200 iteraciones, regularización L2 = 10, sobre las columnas de T5 |
| T7 | Dos etapas | P(día de lluvia fuerte \| antecedentes) × P(evento \| lluvia fuerte), esta última aprendida solo en las temporadas de entrenamiento |

Lluvia fuerte = lluvia de 3 días en Chosica sobre el percentil 90 del entrenamiento.

## 2. Datos y licencias

| Dato | Fuente | Licencia / uso |
|---|---|---|
| Fechas de huaico con día exacto y confianza no baja | `catalogo/` (INDECI, IGP, prensa; cada fila cita su fuente) | Hechos citados |
| Lluvia horaria y humedad del suelo, Chosica y cuenca alta, 1983 a hoy | Open-Meteo (ERA5) | CC BY 4.0; la API gratuita es solo no comercial. «Weather data by Open-Meteo.com» |
| Temperatura, nieve, radiación, humedad, presión y lluvia diarias en seis puntos (Ticlio, Santa Eulalia alta, Matucana, Chosica, costa de Lima, selva de Tarma) | Open-Meteo (ERA5): API para tres puntos y archivos de Open-Meteo en AWS Open Data para los otros tres (capítulo 13) | ídem |
| Caudal diario del Rímac y Santa Eulalia | Open-Meteo / GloFAS (modelo, no aforo) | ídem; GloFAS (Copernicus Emergency Management Service) |
| Temperatura diaria del mar (Niño 1+2, costa de Perú, costa de Lima) | NOAA OISST v2.1 vía ERDDAP de CoastWatch | Dominio público |
| ICEN oficial | IGP / ENFEN | Datos públicos del IGP, se citan |

Todas entran por `descargar-datos` y están en `fuentes.py` y `DATOS.md`. Las anomalías se calculan contra la climatología 1991-2020 de cada serie (fija, sin mirar etiquetas). El número de días con huaico es **119 entre 6 473 días de temporada** (diciembre a abril, 1984 en adelante): 1,8 %.

## 3. Método

- **Etiqueta**: 1 si hay una fecha catalogada ese día. Variante: ese día o el anterior (202 días).
- **Sin mirar el futuro**: todos los antecedentes se desplazan un día antes de aplicar la máscara de temporada. El ICEN se toma del mes anterior.
- **Regularización anidada**: dentro de cada conjunto de entrenamiento se elige entre L2 (C = 0,003, 0,01, 0,03, 0,1) y L1 (C = 0,05, 0,15) con cuatro bloques internos de temporadas, por la pérdida logarítmica. El pliegue de prueba no se usa para elegir. **Todas las cifras principales usan esta validación de scikit-learn.**
- **Validación externa**: dejar fuera cada temporada (43 pliegues), cada episodio Niño completo (más bloques de tres temporadas no Niño) y bloques de cinco temporadas.
- **Referencia**: la climatología mensual (T1), aprendida también fuera de muestra.
- **Métricas**: precisión media (AP) frente a la tasa base (0,018), AUC, *Brier skill* y ganancia de log-loss contra T1, y qué parte de los días con huaico cae entre el 5 % y el 10 % de días de mayor probabilidad.
- **Intervalos**: remuestreo de temporadas completas (los días con huaico vienen en racimos: 23 en 2017).
- **Nula**: se desplazan cíclicamente los días con huaico dentro de cada temporada y se repite la validación dejando una temporada fuera. **2 000 mundos nulos** en la GPU (`gpu.ap_real_y_nulas`, regresión logística con la misma penalización que scikit-learn, C = 0,03 fijo), que reemplazan a los 30 de la primera versión. El AP «real» de esta tabla es el del mismo ajuste de C fijo, para comparar lo comparable.
- **Cálculo**: PC remota (24 hilos; `n_jobs=-1`; capítulo 12), sobre el commit `7188ef2` del repositorio. Todo en un solo proceso: las tres corridas (base, etiqueta del día anterior, Niño alterno) y la robustez.

## 4. Resultados (etiqueta del día; Niño por ICEN)

### 4.1 Las siete teorías, dejando fuera una temporada

| Teoría | AP | AUC | Brier skill | Log-loss ganado | Aciertos con 5 % de días | con 10 % |
|---|---|---|---|---|---|---|
| T1 fecha | 0,026 | 0,637 | 0 | 0 | — | — |
| T2 lluvia del día | 0,149 | 0,829 | 0,061 | 0,010 | 0,328 | 0,504 |
| T3 antecedentes | 0,199 | 0,878 | 0,088 | 0,016 | 0,437 | 0,597 |
| **T4 lluvia + antecedentes** | **0,281** | 0,904 | 0,144 | 0,022 | 0,529 | 0,714 |
| T5 + ICEN causal | 0,276 | 0,904 | 0,141 | 0,022 | 0,529 | 0,697 |
| T5b + marca de temporada Niño (oráculo) | 0,283 | 0,906 | 0,145 | 0,022 | 0,513 | 0,689 |
| T6 no lineal | 0,235 | 0,850 | 0,098 | 0,014 | 0,437 | 0,588 |
| T7 dos etapas | 0,057 | 0,707 | 0,019 | 0,003 | 0,227 | 0,420 |

(T1 es constante por mes: sus «aciertos» por orden no tienen sentido.)

Intervalos del 90 % por remuestreo de temporadas, AP: T2 0,08 a 0,23; T3 0,10 a 0,31; T4 0,16 a 0,39; T5 0,16 a 0,38; T6 0,14 a 0,34. El orden T2 < T3 < T4 es claro; **T4, T5 y T6 se solapan**: la diferencia entre ellos no se distingue del azar.

Con 5 % de días en alarma (324 días) T4 captura 53 % de los días con huaico: unos 63 aciertos y unos 260 días de alarma sin huaico catalogado, es decir **cuatro de cada cinco alarmas fallan**, y casi la mitad de los días con huaico queda sin alarma.

### 4.2 Otras validaciones (AP y aciertos con 5 % de alarmas)

| Teoría | Episodio Niño fuera | Bloque de 5 temporadas fuera |
|---|---|---|
| T2 lluvia | 0,141 · 0,33 | 0,153 · 0,33 |
| T3 antecedentes | 0,209 · 0,48 | 0,205 · 0,48 |
| T4 lluvia + antecedentes | 0,304 · 0,56 | 0,291 · 0,49 |
| T5 + ICEN | 0,300 · 0,58 | 0,283 · 0,50 |
| T6 no lineal | 0,249 · 0,41 | — |

Las cifras casi no cambian: el resultado no depende de cómo se cortan las temporadas.

### 4.3 ¿Es mejor que el azar? 2 000 mundos nulos

AP real frente a los mundos con las fechas desplazadas dentro de cada temporada (misma regresión, C = 0,03):

| Teoría | AP real | Nula, media | Nula, percentil 95 | Nula, máximo | p |
|---|---|---|---|---|---|
| T2 | 0,156 | 0,016 | 0,023 | 0,037 | 0,0005 |
| T3 | 0,207 | 0,026 | 0,046 | 0,105 | 0,0005 |
| T4 | 0,294 | 0,026 | 0,045 | 0,094 | 0,0005 |

Ninguno de los 2 000 mundos alcanza el AP real (p = 1/2 001 es el mínimo posible). La habilidad es real **respecto de un tiempo atmosférico sin relación con las fechas**; no dice que sirva como alerta. El mejor mundo nulo de T3 llega a 0,105: con fechas desplazadas, los antecedentes por sí solos pueden sacar «por casualidad» la mitad del AP real, un recordatorio de que T3 es la teoría con más varianza.

### 4.4 Qué familia aporta (ablación sobre T5)

| Se quita | AP | Cambio |
|---|---|---|
| nada (T5) | 0,276 | — |
| temperatura del mar | 0,230 | −0,046 |
| humedad y circulación (selva, costa, presión, nubes) | 0,263 | −0,013 |
| caudal | 0,275 | −0,001 |
| lluvia previa de 7 y 30 días | 0,275 | −0,001 |
| humedad del suelo | 0,279 | +0,003 |
| ICEN causal | 0,281 | +0,005 |
| calor y 0 °C aguas arriba, nieve, radiación | 0,286 | +0,010 |

Con los seis puntos de ERA5, **el mar es lo único que aporta con claridad**, y lo hace como régimen lento: los coeficientes más estables del mar son el nivel de 30 días en Niño 1+2 y el alza de 14 días en la costa de Lima, no el alza de pocos días. La humedad y circulación de selva y costa suma algo (−0,013 al quitarla) y entre los coeficientes más grandes aparecen el gradiente de presión Chosica-selva y el punto de rocío de la costa, de acuerdo con la hipótesis H3 del capítulo 04, que aquí por fin se pudo probar. El calor aguas arriba **ya no aporta** (+0,010 al quitarlo, dentro del ruido): lo que parecía aportar con tres puntos lo explican, muy probablemente, los puntos de Chosica, la costa y la selva (no se probó con un modelo que los quite de a uno). El ICEN no suma una vez que el mar de NOAA está en el modelo.

### 4.5 Niño y no Niño, calibración y estabilidad

| Régimen (ICEN) | Días | Días con huaico | AP (base) | AUC | Observado / predicho (T5) |
|---|---|---|---|---|---|
| Temporadas Niño | 3 177 | 89 | 0,306 (0,028) | 0,901 | 1,29 |
| No Niño | 3 296 | 30 | 0,220 (0,009) | 0,889 | 0,74 |

El modelo ordena los días igual de bien dentro y fuera de Niño (AUC 0,90 y 0,89), pero **se queda corto en Niño y se pasa fuera de Niño**: aun con el ICEN, los eventos observados son 29 % más que los predichos en Niño y 26 % menos fuera de él. Podría ser un efecto físico del régimen que el modelo no captura o más cobertura de prensa en años de Niño; el catálogo no permite separarlos.

Calibración (T5, ocho cuantiles de probabilidad): en el cuantil más alto el modelo da 0,102 y se observa 0,109 (88 eventos en 809 días); en los demás la diferencia es de unos pocos eventos por cuantil. Está razonablemente calibrado en conjunto.

Estabilidad: 109 de 116 coeficientes de T4 están activos y con el mismo signo en al menos 80 % de los pliegues (la regularización elegida fue L2 con C = 0,03 en 42 de 43 pliegues; L1 solo una vez). **No se interpretan como causas**: con más de cien columnas muy correlacionadas el signo de una puede compensar el de otra (por ejemplo, la temperatura de Matucana de los 7 días previos entra con signo positivo aunque sola no separa).

### 4.6 Robustez (mismo commit; AP y, entre paréntesis, días con huaico)

| Escenario | T1 | T2 | T3 | T4 | T5 |
|---|---|---|---|---|---|
| Base: 1984 en adelante (119) | 0,026 | 0,149 | 0,199 | 0,281 | 0,276 |
| Etiqueta del día y el anterior (202) | 0,043 | 0,162 | 0,232 | 0,283 | 0,290 |
| Solo 2009 en adelante (64) | 0,030 | 0,229 | 0,274 | 0,361 | 0,357 |
| Sin 1983, 1998 y 2017 (80) | 0,022 | 0,127 | 0,132 | 0,185 | 0,185 |

El orden T2 < T3 < T4 se mantiene en los cuatro escenarios. **Sin los tres mayores racimos el AP de T4 baja de 0,28 a 0,19**: buena parte de la habilidad viene de las temporadas con más eventos. Desde 2009 (registro más consistente) sube a 0,36. Con la etiqueta ampliada al día anterior los aciertos con 5 % de días bajan (0,53 a 0,41): las fechas del catálogo no siempre coinciden con el día de la lluvia.

### 4.7 Etiqueta del día anterior en todos los pasos

Misma batería con la etiqueta «el día y el anterior» (202 días positivos):

| Teoría | AP | AUC | Aciertos con 5 % | Nula (máx., 2 000 mundos) |
|---|---|---|---|---|
| T1 fecha | 0,043 | 0,616 | — | — |
| T2 lluvia | 0,162 | 0,815 | 0,297 | 0,052 (real 0,166) |
| T3 antecedentes | 0,232 | 0,847 | 0,376 | 0,132 (real 0,242) |
| T4 lluvia + antecedentes | 0,283 | 0,874 | 0,411 | 0,127 (real 0,307) |
| T5 + ICEN | 0,290 | 0,880 | 0,401 | — |
| T6 no lineal | 0,180 | 0,814 | 0,297 | — |
| T7 dos etapas | 0,083 | 0,669 | 0,208 | — |

Episodio Niño fuera: T4 0,301 (0,42); bloques de 5: T4 0,315 (0,41). Ablación: sin mar −0,031; sin humedad y circulación −0,018; sin ICEN −0,007; el resto, dentro del ruido. En Niño el AP de T5 es 0,345 (base 0,047, observado/predicho 1,30) y fuera 0,189 (base 0,016, 0,72). Conclusiones iguales al caso del día exacto, con dos diferencias: el AP sube (la etiqueta es menos exigente) pero los aciertos con 5 % de alarmas bajan, y los coeficientes son **mucho menos estables** (52 de 116 estables, y la regularización cambia de un pliegue a otro: L2 C = 0,01 en 17, C = 0,03 en 13 y L1 en 13), señal de que el ruido de la etiqueta es mayor.

### 4.8 Definición alterna de temporada Niño (Niño 1+2 en lugar del ICEN)

Los modelos de T1 a T4, T6 y T7 no usan la marca de temporada, así que sus cifras son las mismas. Cambian solo T5b, los episodios de la validación y la separación Niño / no Niño:

| | ICEN (22 temporadas Niño) | Niño 1+2 (15 temporadas) |
|---|---|---|
| T5b oráculo, AP | 0,283 | 0,283 |
| Episodio Niño fuera, T4 / T5, AP | 0,304 / 0,300 | 0,302 / 0,298 |
| Días en Niño · con huaico | 3 177 · 89 | 2 118 · 69 |
| AP en Niño de T5 (base) | 0,306 (0,028) | 0,349 (0,033) |
| Observado / predicho, Niño · no Niño | 1,29 · 0,74 | 1,34 · 0,86 |

Con la definición más estrecha el sesgo del modelo es parecido pero algo menor fuera de Niño (0,86), porque las temporadas «Niño débil» que cuenta el ICEN pasan a ser no Niño y con ellas sus huaicos. El resultado no depende de qué definición se use.

### 4.9 ¿Cuánto es sobreajuste?

T5 tiene 118 columnas para 119 días con huaico. Ajustado sobre todo el conjunto, el AP dentro de muestra es **0,452**; dejando temporadas fuera es **0,276**: cerca de dos quintos de lo que «se ve» en la muestra es sobreajuste, y por eso solo se reportan cifras fuera de muestra. Un modelo con 11 variables elegidas por conocimiento previo (lluvia de 1 y 3 días y pico horario en Chosica, lluvia de Matucana, suelo y lluvia de 7 días de ayer, mar Niño 1+2 de 30 días, temperatura y radiación de Santa Eulalia alta de ayer, caudal de 7 días y ICEN) conserva casi todo: AP 0,260, 50 % de los días con huaico en el 5 % de alarmas. Esa selección se hizo después de ver los resultados de las familias, así que es un análisis posterior y no una teoría pre-registrada.

### 4.10 T6 y T7

Con seis puntos de ERA5 el modelo no lineal (AP 0,235; intervalo 0,14 a 0,34) ya **no se distingue** del lineal (0,281): con 119 positivos los árboles pequeños no encuentran interacciones que el modelo lineal regularizado no capture. T7 funciona mal (AP 0,057) porque el cuello de botella es la segunda etapa: la lluvia fuerte de Chosica en reanálisis deja pasar demasiados días sin huaico (ver capítulo 02). Con cortes en el percentil 80, 90 y 95 el AP es 0,046, 0,057 y 0,066.

## 5. Qué se puede decir

1. Los antecedentes de ayer ordenan los días mucho mejor que el calendario (AP 0,199 frente a 0,026) y la lluvia de hoy los ordena a otro nivel (0,149). **Juntos** llegan a 0,281, más que la suma de cada parte. La teoría T7 del capítulo 00 se sostiene.
2. El orden se sostiene dejando fuera temporadas, episodios Niño y bloques de años, y con otra etiqueta y otra definición de Niño; es muy distinto de 2 000 nulas con las fechas desplazadas.
3. De las familias de antecedentes, **solo el mar aporta claramente**, como régimen lento; la humedad y circulación de selva y costa suma un poco. El estado de El Niño ya está casi todo en el mar de NOAA: el ICEN no suma.
4. No hay interacciones no lineales detectables con estos datos (T8 no se sostiene).

## 6. Límites

- **No es una alerta.** Aun con la mejor teoría, cuatro de cada cinco alarmas en el 5 % de días más probables no coinciden con un huaico catalogado, y casi la mitad de los días con huaico no se anuncian.
- El catálogo es de prensa e instituciones: un día sin huaico catalogado no es un día sin huaico, y cuando el evento fue de noche la fecha puede estar corrida un día.
- La lluvia y el calor son de reanálisis (ERA5, unos 25 km), no de pluviómetros en las cabeceras; el caudal es de modelo. Tres de los seis puntos vienen de los archivos de Open-Meteo con corrección de altura por gradiente (capítulo 13), no de la API.
- Gran parte de la habilidad viene de pocas temporadas con muchos eventos (2015, 2017, 2019, 2023); sin 1983, 1998 y 2017 el AP de T4 baja a 0,19.
- El modelo se queda corto en Niño y se pasa fuera de Niño (observado/predicho 1,29 y 0,74).
- Las cifras son de reanálisis y catálogo; no se probaron con eventos futuros reales.

## 7. Con qué datos se corrió

Corrida del **30 de octubre de 2026** en la PC remota, repositorio en el commit `7188ef2` (que incluye el evento del 12 de marzo de 2023 del informe 599 de INDECI-COEN, de ahí los 119 días), último día de datos el 24 de octubre de 2026:

- ERA5 de **los seis puntos**: Matucana, Santa Eulalia alta y Ticlio (API de Open-Meteo); Chosica, costa de Lima y selva de Tarma (archivos de Open-Meteo en AWS, capítulo 13).
- Lluvia horaria y suelo de Chosica y cuenca alta (`open_meteo_horario_estudio.json`).
- Temperatura del mar: las tres cajas (Niño 1+2, costa de Perú, costa de Lima), `enso/oisst_diario.csv` consolidado.
- Caudal: GloFAS en tres puntos (los del Rímac en Chosica y del Santa Eulalia caen casi en la misma celda).
- ICEN: `enso/igp_icen.txt`; temporadas Niño: `nino.cargar_temporadas` (22 temporadas Niño de 45 con el ICEN; 15 con el proxy Niño 1+2).
- Catálogo: 147 fechas con día exacto en el commit anterior y una más en este; 119 días en temporadas 1984 a 2026.

## 8. Qué cambió frente a la corrida con 3 puntos de ERA5

La primera versión de este capítulo (30 de octubre, caché parcial con Matucana, Santa Eulalia alta y Ticlio) dio:

| | 3 puntos | 6 puntos |
|---|---|---|
| Días con huaico | 118 | 119 (un evento nuevo) |
| Columnas de T5 | 93 | 118 |
| T2 lluvia, AP | 0,120 | 0,149 |
| T3 antecedentes, AP | 0,165 | 0,199 |
| T4, AP · aciertos con 5 % | 0,271 · 0,534 | 0,281 · 0,529 |
| T5, AP | 0,269 | 0,276 |
| T6 no lineal, AP (¿distinto de T4?) | 0,175 (sí) | 0,235 (no se distingue) |
| Ablación: calor aguas arriba | −0,065 | +0,010 |
| Ablación: humedad y circulación | 0 (familia vacía) | −0,013 |
| Ablación: mar | −0,041 | −0,046 |
| Sobreajuste: AP dentro / fuera | 0,414 / 0,269 | 0,452 / 0,276 |
| Coeficientes estables | 88 de 96 | 109 de 116 |
| Sin 1983, 1998 y 2017, AP de T4 | 0,173 | 0,185 |
| Pruebas nulas | 30 mundos (p < 0,034) | 2 000 mundos (p = 0,0005) |
| Observado / predicho, Niño · no Niño | 1,30 · 0,72 | 1,29 · 0,74 |

Lo que se confirma: el orden T2 < T3 < T4, la habilidad frente a la nula, el peso del mar, el sesgo Niño / no Niño y la dependencia de los racimos. Lo que cambia: el punto de Chosica mejora la lluvia del día (AP 0,12 a 0,15), **el calor aguas arriba deja de aportar** (probable explicación: con tres puntos el modelo lo usaba para suplir lo que faltaba de la costa, la selva y Chosica) y el modelo no lineal deja de ser peor que el lineal. Dos efectos no atribuibles a ERA5: el cambio de 90 a 2 000 mundos nulos y el evento nuevo del catálogo.

## 9. Qué falta

- Un registro de huaicos con hora (INDECI/COEN) para separar eventos de noche y de día; sin él el rezago de un día es ambiguo.
- Pluviómetros o radar en las cabeceras (SENAMHI, sujeto a autorización por escrito).
- Una sugerencia para `predictores.construir`: incluir el ICEN causal (hoy lo agrega `modelo_diario.cargar_datos`) para que todos los capítulos usen la misma tabla, y reemplazar `DatetimeIndex.dayofyear` por `day_of_year` (aviso de pandas).
- El `PerformanceWarning` de pandas que sale al construir la tabla (por añadir cientos de columnas una a una en `predictores.construir`) se evita aquí defragmentando el marco con `.copy()`; la corrección de fondo sería construir las columnas en un diccionario y concatenar una vez.
