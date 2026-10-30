# 05 · Modelo diario: ¿qué explica que un día haya huaico?

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide cuánto del catálogo de fechas se explica con el tiempo atmosférico, con los huecos del catálogo tal como están. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

Notebook: [`notebooks/05-modelo-diario.ipynb`](../notebooks/05-modelo-diario.ipynb). Código: [`src/illapa_research/modelo_diario.py`](../src/illapa_research/modelo_diario.py), con pruebas en `tests/test_modelo_diario.py`. Reutiliza `predictores.py` (variables) y `evaluacion_diaria.py` (etiquetas, pliegues, métricas y nula). Este capítulo se actualiza cada vez que llegan datos nuevos; la sección «Con qué datos se corrió» dice qué había en cada corrida.

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
| Temperatura, nieve, radiación y lluvia diarias en Ticlio, Santa Eulalia alta y Matucana | Open-Meteo (ERA5) | ídem |
| Caudal diario del Rímac y Santa Eulalia | Open-Meteo / GloFAS (modelo, no aforo) | ídem; GloFAS (Copernicus Emergency Management Service) |
| Temperatura diaria del mar (Niño 1+2, costa de Perú, costa de Lima) | NOAA OISST v2.1 vía ERDDAP de CoastWatch | Dominio público |
| ICEN oficial | IGP / ENFEN | Datos públicos del IGP, se citan |

Todas entran por `descargar-datos` y están en `fuentes.py` y `DATOS.md`. Las anomalías se calculan contra la climatología 1991-2020 de cada serie (fija, sin mirar etiquetas). El número de días con huaico es 118 entre 6 473 días de temporada (diciembre a abril, 1984 en adelante): 1,8 %.

## 3. Método

- **Etiqueta**: 1 si hay una fecha catalogada ese día. Variante: ese día o el anterior.
- **Sin mirar el futuro**: todos los antecedentes se desplazan un día antes de aplicar la máscara de temporada. El ICEN se toma del mes anterior.
- **Regularización anidada**: dentro de cada conjunto de entrenamiento se elige entre L2 (C = 0,003, 0,01, 0,03, 0,1) y L1 (C = 0,05, 0,15) con cuatro bloques internos de temporadas, por la pérdida logarítmica. El pliegue de prueba no se usa para elegir. Quedó L2 con C = 0,03 en 42 de 43 pliegues; L1 no se eligió nunca.
- **Validación externa**: dejar fuera cada temporada (43 pliegues), cada episodio Niño completo (más bloques de tres temporadas no Niño) y bloques de cinco temporadas.
- **Referencia**: la climatología mensual (T1), aprendida también fuera de muestra.
- **Métricas**: precisión media (AP) frente a la tasa base (0,018), AUC, *Brier skill* y ganancia de log-loss contra T1, y qué parte de los días con huaico cae entre el 5 % y el 10 % de días de mayor probabilidad.
- **Intervalos**: remuestreo de temporadas completas (los días con huaico vienen en racimos: 23 en 2017).
- **Nula**: se desplazan cíclicamente los días con huaico dentro de cada temporada y se repite la validación (30 veces, con C = 0,1 fijo).

## 4. Resultados

### 4.1 Las siete teorías, dejando fuera una temporada

| Teoría | AP | AUC | Brier skill | Log-loss ganado | Aciertos con 5 % de días | con 10 % |
|---|---|---|---|---|---|---|
| T1 fecha | 0,026 | 0,638 | 0 | 0 | — | — |
| T2 lluvia del día | 0,120 | 0,819 | 0,040 | 0,008 | 0,288 | 0,508 |
| T3 antecedentes | 0,165 | 0,863 | 0,072 | 0,014 | 0,432 | 0,585 |
| **T4 lluvia + antecedentes** | **0,271** | 0,897 | 0,140 | 0,021 | 0,534 | 0,695 |
| T5 + ICEN causal | 0,269 | 0,900 | 0,137 | 0,021 | 0,534 | 0,703 |
| T5b + marca de temporada Niño (oráculo) | 0,276 | 0,903 | 0,142 | 0,022 | 0,517 | 0,720 |
| T6 no lineal | 0,175 | 0,855 | 0,074 | 0,013 | 0,398 | 0,576 |
| T7 dos etapas | 0,056 | 0,702 | 0,018 | 0,003 | 0,229 | 0,432 |

(T1 es constante por mes: sus «aciertos» por orden no tienen sentido.)

Intervalos del 90 % por remuestreo de temporadas, AP: T2 0,08 a 0,18; T3 0,09 a 0,26; T4 0,16 a 0,39; T5 0,16 a 0,39; T6 0,11 a 0,26. Los intervalos de T4 y T2 se tocan apenas; el orden T2 < T3 < T4 es claro, pero la diferencia entre T4 y T5 no se distingue del azar.

Con 5 % de días en alarma (324 días) T4 captura 53 % de los días con huaico: unos 63 aciertos y unos 260 días de alarma sin huaico catalogado, es decir **cuatro de cada cinco alarmas fallan**, y casi la mitad de los días con huaico queda sin alarma.

### 4.2 Otras validaciones

| Teoría | AP, episodio Niño fuera | AP, bloque de 5 temporadas fuera |
|---|---|---|
| T2 lluvia | 0,114 | 0,116 |
| T3 antecedentes | 0,195 | 0,180 |
| T4 lluvia + antecedentes | 0,275 | 0,269 |
| T5 + ICEN | 0,258 | 0,262 |

Las cifras casi no cambian: el resultado no depende de cómo se cortan las temporadas.

### 4.3 ¿Es mejor que el azar?

AP real frente a la nula de etiquetas desplazadas dentro de cada temporada (30 repeticiones):

| Teoría | AP real | AP nula, mediana | AP nula, máximo | p empírico |
|---|---|---|---|---|
| T2 | 0,122 | 0,015 | 0,023 | < 0,034 |
| T3 | 0,196 | 0,020 | 0,056 | < 0,034 |
| T4 | 0,272 | 0,020 | 0,058 | < 0,034 |

Ninguna de las 90 corridas nulas se acerca al valor real. La habilidad es real **respecto de un tiempo atmosférico sin relación con las fechas**; no dice que sirva como alerta.

### 4.4 Qué familia aporta (ablación sobre T5)

| Se quita | AP | Caída |
|---|---|---|
| nada (T5) | 0,269 | — |
| calor y 0 °C aguas arriba, nieve, radiación (de ayer) | 0,204 | −0,065 |
| temperatura del mar | 0,228 | −0,041 |
| caudal | 0,243 | −0,026 |
| lluvia previa de 7 y 30 días | 0,260 | −0,009 |
| humedad del suelo | 0,267 | −0,002 |
| ICEN causal | 0,271 | +0,002 |
| humedad y circulación (selva, costa, presión) | 0,269 | 0 (la familia está vacía, ver §6) |

El calor aguas arriba es lo que más aporta, pero **no como calor**: el capítulo 04 muestra que la anomalía de temperatura de los días 2 a 10 antes no separa los días con huaico, y que el día mismo la señal es de *frío* y poca radiación (nubosidad de la tormenta). Lo que aporta aquí es la temperatura y la radiación *de ayer*, es decir, persistencia de una situación nublada y fría de varios días, no un precursor de calentamiento. El mar aporta como régimen lento (nivel y alza de 14-30 días), no como disparador. El ICEN no suma una vez que el mar de NOAA está en el modelo.

### 4.5 Niño y no Niño, calibración y estabilidad

| Régimen | Días | Días con huaico | AP (base) | AUC | Observado / predicho (T5) |
|---|---|---|---|---|---|
| Temporadas Niño | 3 177 | 88 | 0,315 (0,028) | 0,897 | 1,30 |
| No Niño | 3 296 | 30 | 0,177 (0,009) | 0,884 | 0,72 |

El modelo ordena los días igual de bien dentro y fuera de Niño (AUC 0,90 y 0,88), pero **se queda corto en Niño y se pasa fuera de Niño**: aun con el ICEN, los eventos observados son 30 % más que los predichos en Niño y 28 % menos fuera de él. Podría ser un efecto físico del régimen que el modelo no captura o más cobertura de prensa en años de Niño; el catálogo no permite separarlos.

Calibración (T5, ocho cuantiles de probabilidad): en el cuantil más alto el modelo da 0,099 y se observa 0,108 (87 eventos en 809 días); en los demás la diferencia es de unos pocos eventos por cuantil. Está razonablemente calibrado en conjunto.

Estabilidad: 88 de 96 coeficientes de T4 están activos y con el mismo signo en al menos 80 % de los pliegues. **No se interpretan como causas**: con casi cien columnas muy correlacionadas el signo de una puede compensar el de otra (por ejemplo, la temperatura de Matucana de los 7 días previos entra con signo positivo aunque sola no separa).

### 4.6 Robustez

AP de cada teoría bajo otras etiquetas y ventanas:

| Escenario (días con huaico) | T1 | T2 | T3 | T4 | T5 |
|---|---|---|---|---|---|
| Base: 1984 en adelante (118) | 0,026 | 0,120 | 0,165 | 0,271 | 0,269 |
| Etiqueta del día y el anterior (200) | 0,043 | 0,138 | 0,210 | 0,281 | 0,279 |
| Solo 2009 en adelante (63) | 0,030 | 0,172 | 0,253 | 0,363 | 0,370 |
| Sin 1983, 1998 y 2017 (79) | 0,021 | 0,110 | 0,129 | 0,173 | 0,168 |

El orden T2 < T3 < T4 se mantiene en los cuatro escenarios. **Sin los tres mayores racimos el AP de T4 baja de 0,27 a 0,17**: buena parte de la habilidad viene de las temporadas con más eventos. Desde 2009 (registro más consistente) sube a 0,36. Con la etiqueta ampliada a «el día anterior» los aciertos con 5 % de días bajan (0,53 a 0,45), señal de que las fechas del catálogo no siempre coinciden con el día de la lluvia.

### 4.7 ¿Cuánto es sobreajuste?

T5 tiene 98 columnas para 118 días con huaico. Ajustado sobre todo el conjunto, el AP dentro de muestra es **0,414**; dejando temporadas fuera es **0,269**: más de un tercio de lo que «se ve» en la muestra es sobreajuste, y por eso solo se reportan cifras fuera de muestra. Un modelo con 11 variables elegidas por conocimiento previo (lluvia de 1 y 3 días y pico horario en Chosica, lluvia de Matucana, suelo y lluvia de 7 días de ayer, mar Niño 1+2 de 30 días, temperatura y radiación de Santa Eulalia alta de ayer, caudal de 7 días y ICEN) conserva casi todo: AP 0,248 (intervalo del 90 % 0,14 a 0,37), 50 % de los días con huaico en el 5 % de alarmas. Esa selección se hizo después de ver los resultados de las familias, así que es un análisis posterior y no una teoría pre-registrada.

### 4.8 T6 y T7

El modelo no lineal no mejora al lineal (AP 0,175 frente a 0,271; intervalo 0,11 a 0,26, que no contiene al lineal): con 118 positivos los árboles no encuentran interacciones que el modelo lineal con regularización no capture. T7 funciona mal (AP 0,056) porque el cuello de botella es la segunda etapa: la lluvia fuerte de Chosica en reanálisis deja pasar demasiados días sin huaico (ver capítulo 02). Con cortes en el percentil 80 y 95 (corrida anterior, con menos cajas de mar) el AP fue 0,046 y 0,064.

## 5. Qué se puede decir

1. Los antecedentes de ayer ordenan los días mucho mejor que el calendario (AP 0,165 frente a 0,026) y la lluvia de hoy los ordena a otro nivel (0,120). **Juntos** llegan a 0,271, más que la suma de cada parte. La teoría T7 del capítulo 00 se sostiene.
2. El orden se sostiene dejando fuera temporadas, episodios Niño y bloques de años; es muy distinto de una nula con las fechas desplazadas.
3. El estado de El Niño ya está casi todo en el mar de NOAA: el ICEN no suma, y la marca de temporada Niño a posteriori suma poco (0,276 frente a 0,269).
4. No hay interacciones no lineales detectables con estos datos (T8 no se sostiene).

## 6. Límites

- **No es una alerta.** Aun con la mejor teoría, cuatro de cada cinco alarmas en el 5 % de días más probables no coinciden con un huaico catalogado, y casi la mitad de los días con huaico no se anuncian.
- El catálogo es de prensa e instituciones: un día sin huaico catalogado no es un día sin huaico, y cuando el evento fue de noche la fecha puede estar corrida un día.
- La lluvia y el calor son de reanálisis (ERA5, unos 25 km), no de pluviómetros en las cabeceras; el caudal es de modelo.
- Gran parte de la habilidad viene de pocas temporadas con muchos eventos (2015, 2017, 2019, 2023); sin 1983, 1998 y 2017 el AP de T4 baja a 0,17.
- El modelo se queda corto en Niño y se pasa fuera de Niño (observado/predicho 1,30 y 0,72).
- Las cifras son de reanálisis y catálogo; no se probaron con eventos futuros reales.

## 7. Con qué datos se corrió

Corrida del **30 de octubre de 2026**, con el último día de datos al 29 de octubre de 2026:

- ERA5 (Open-Meteo): solo **3 de 6 puntos** (Matucana, Santa Eulalia alta, Ticlio) de la caché parcial de `datos/predictores_cache/`. **Faltan** Chosica, costa de Lima y selva de Tarma. Por eso **la familia «humedad y circulación» (punto de rocío de la selva, nubes de la selva y la costa, gradiente de presión selva-costa, humedad relativa y déficit de presión de vapor de Chosica) no se probó**: está vacía y su ablación da lo mismo que el modelo completo. La hipótesis H3 del capítulo 04 queda sin evaluar en el modelo diario.
- Lluvia horaria y suelo de Chosica y cuenca alta (`open_meteo_horario_estudio.json`), sí.
- Temperatura del mar: las tres cajas (Niño 1+2, costa de Perú, costa de Lima), `enso/oisst_diario.csv` consolidado.
- Caudal: GloFAS en tres puntos (los puntos del Rímac en Chosica y del Santa Eulalia caen casi en la misma celda).
- ICEN: `enso/igp_icen.txt`; temporadas Niño: `nino.cargar_temporadas` (22 temporadas Niño de 45).
- Catálogo: 147 fechas con día exacto, 118 en temporadas 1984 a 2026.

## 8. Qué falta

- Re-ejecutar el notebook cuando llegue `datos/open_meteo_predictores_diarios.json` (Chosica, costa de Lima y selva): probará H3 y la familia vacía, y puede cambiar el AP de T4/T5.
- Repetir con la etiqueta ampliada a ±1 día para todos los pasos (hoy solo T1 a T5 en la tabla de robustez) y con una definición de «temporada Niño» alterna (proxy Niño 1+2).
- Un registro de huaicos con hora (INDECI/COEN) para separar eventos de noche y de día; sin él el rezago de un día es ambiguo.
- Pluviómetros o radar en las cabeceras (SENAMHI, sujeto a autorización por escrito).
- Cambios en otros archivos: ninguno bloqueante. Una sugerencia para `predictores.construir`: incluir el ICEN causal (hoy lo agrega `modelo_diario.cargar_datos`) para que todos los capítulos usen la misma tabla.
