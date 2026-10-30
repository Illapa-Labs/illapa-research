# 10 · Hipótesis de la literatura: hora de la lluvia, mar absoluto, índices E y C, lluvia satelital

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide qué señales adicionales explican las fechas catalogadas. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

Notebook: [`notebooks/10-hipotesis-de-la-literatura.ipynb`](../notebooks/10-hipotesis-de-la-literatura.ipynb). Código: [`src/illapa_research/hipotesis_literatura.py`](../src/illapa_research/hipotesis_literatura.py), con pruebas en `tests/test_hipotesis_literatura.py`. Reutiliza `modelo_diario.py` (capítulo 05) sin modificarlo.

## 1. Pregunta

El capítulo 09 propuso hipótesis nuevas a partir de la literatura. Este capítulo prueba cuatro: T23 (la hora de la lluvia), T24 (la temperatura **absoluta** del mar y sus umbrales de convección), T25 (los índices E y C en lugar del ICEN o el ONI) y T28 (lluvia satelital en lugar de la de reanálisis). Se numeran como en el capítulo 09.

## 2. Pre-registro

Se escribió antes de ver ninguna cifra (está también en la primera celda del notebook).

| | Hipótesis | Variable fijada de antemano |
|---|---|---|
| T23 | Los días con huaico tienen la lluvia de la tarde y corta e intensa | hora del pico; fracción de la lluvia entre 12 y 20 h locales; horas con ≥ 0,1 mm; racha continua más larga; fracción de la lluvia del día en 3 h |
| T24 | La convección responde a la TSM absoluta por umbral, no solo a la anomalía | grados-día sobre 25, 26, 27 y 28 °C en 7, 14 y 30 días hasta ayer; días seguidos sobre cada umbral; nivel de ayer; cajas Niño 1+2, costa de Perú y costa de Lima |
| T25 | E y C explican la frecuencia por temporada mejor que el ICEN y el ONI | media de enero a abril de E, C, ICEN y ONI; E y C del mes previo (y su cambio) en el modelo diario |
| T28 | La lluvia de CHIRPS v3 (tiempo de IMERG) mejora o complementa la de ERA5 | lluvia de 1 y 3 días y de los 7 días previos, en cajas de 0,2° alrededor de Chosica, Santa Eulalia alta, Matucana, Ticlio y la selva de Tarma |

Criterios (iguales a los del capítulo 05): dejar fuera una temporada cada vez; cambio de la precisión media (AP) frente al mejor modelo del capítulo 05 (lluvia + condiciones de ayer), con intervalo del 90 % por bootstrap de temporadas; una nula en que **el bloque nuevo** se desplaza cíclicamente dentro de cada temporada (8 repeticiones; conserva su distribución y su autocorrelación, rompe su relación con el día). Las variables del propio día solo valen como nowcast (lag 0): se separan de las de ayer.

## 3. Datos y licencias

Corrida del 30 de octubre de 2026. Muestra: 6 473 días de temporada (diciembre a abril, 1984 en adelante), 118 con huaico catalogado.

| Dato | Fuente | Licencia / uso |
|---|---|---|
| Lluvia horaria de Chosica y de la cuenca alta (1983 a hoy) | Open-Meteo (ERA5, `open_meteo_horario_estudio.json`) | CC BY 4.0; la API gratuita es solo no comercial. «Weather data by Open-Meteo.com» |
| TSM diaria de 3 cajas | NOAA OISST v2.1, vía ERDDAP de CoastWatch (`enso/oisst_diario.csv`) | Dominio público |
| Índices E y C mensuales (ERSSTv5) | IGP, `met.igp.gob.pe/datos/ecindex_ersstv5.txt` (`descargar-datos --solo igp-ec`) | Datos públicos del IGP **sin licencia explícita**: se citan y no van al espejo público. Takahashi et al. (2011), doi:10.1029/2011GL047364 |
| ICEN oficial | IGP/ENFEN (`--solo igp-icen`) | Igual que arriba |
| ONI | NOAA CPC | Dominio público |
| Resto del modelo base (puntos ERA5 de Matucana, Santa Eulalia alta y Ticlio; caudal GloFAS; humedad de selva y costa) | Capítulos 04 y 05 | Ver allí |
| Lluvia CHIRPS v3 (T28) | Climate Hazards Center, `data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/` (`--solo chirps-v3`) | Dominio público y CC BY 4.0. Funk et al. (2026), *Scientific Data* 13, 718, doi:10.1038/s41597-026-07096-4 |

**Con qué datos corrió cada cifra.** Los puntos Chosica, costa de Lima y selva de Tarma del modelo base **no son ERA5** todavía: Open-Meteo agotó su cuota diaria y esos tres puntos vienen de NASA POWER (MERRA-2, malla gruesa; ver capítulo 05). Matucana, Santa Eulalia alta y Ticlio sí son ERA5. La lluvia horaria de T23 sí es ERA5 completa. **Cuando llegue la descarga ERA5 de los tres puntos (programada para las 19:05 hora de Lima) hay que re-ejecutar el notebook**; el modelo base cambiará un poco y con él los ΔAP de abajo. Modelo base de esta corrida: AP 0,282 (base 0,018), AUC 0,903, 56 % de los días con huaico con el 5 % de días en alarma.

## 4. T23 · Hora de la lluvia

**Método.** Entre los días lluviosos de cada punto (lluvia diaria de ERA5 ≥ 1 mm: 2 506 días y 102 con huaico en Chosica, 5 370 y 118 en la cuenca alta) se compara cada variable de forma entre días con huaico y sin huaico: AUC (0,5 = sin diferencia) con bootstrap de temporadas, y el mismo AUC solo entre los días de lluvia fuerte (percentil 90) para descartar que sea solo intensidad. También se calcula el AUC **dentro de cada mes de calendario** para quitar el ciclo estacional.

| Variable | Chosica: AUC [90 %] | Cuenca alta: AUC [90 %] | Lectura |
|---|---|---|---|
| Hora del pico | 0,510 [0,481; 0,541] | 0,528 [0,467; 0,581] | Mediana 14 h con y sin huaico: sin diferencia |
| Fracción entre 12 y 20 h | 0,532 [0,490; 0,579] | **0,363 [0,323; 0,407]** | En la cuenca alta los días con huaico tienen *menos* lluvia de tarde (mediana 0,67 contra 0,80) |
| Horas con lluvia | **0,688 [0,629; 0,741]** | **0,740 [0,699; 0,787]** | Más horas húmedas: 13,5 contra 9 (Chosica), 17 contra 11 (cuenca alta) |
| Racha húmeda más larga | **0,660 [0,604; 0,718]** | **0,732 [0,690; 0,773]** | Más continua |
| Fracción de la lluvia en 3 h | **0,398 [0,334; 0,449]** | **0,311 [0,250; 0,355]** | Menos concentrada |

Dentro de cada mes de calendario los resultados son los mismos (horas húmedas 0,756, racha 0,741 en Chosica; 0,743 y 0,732 en la cuenca alta). Solo en la cuenca alta la señal de duración sobrevive entre los días de lluvia fuerte (AUC 0,65 con 36 eventos); en Chosica baja a 0,55 con 26 eventos, sin poder estadístico.

**¿Mejoran el modelo diario?**

| Bloque añadido al modelo base | ΔAP [90 %] | Prob. de mejora | Nula p95 |
|---|---|---|---|
| Timing del día, 10 columnas (nowcast) | +0,011 [−0,014; +0,031] | 0,79 | +0,006 |
| Duración y concentración del día, 6 columnas (nowcast) | +0,016 [−0,007; +0,034] | 0,87 | −0,001 |
| Timing de ayer, 10 columnas (antecedente) | −0,008 [−0,027; +0,009] | 0,23 | 0,000 |

**Conclusión T23: no se confirma como se planteó, y aparece la contraria.** La hipótesis era «tarde, corta e intensa»; los datos dicen que la hora del pico no distingue y que los días con huaico tienen lluvia **más prolongada y menos concentrada**. Esto coincide con que lo que ordena el modelo son los antecedentes y la lluvia acumulada (capítulos 04 y 05). La mejora del modelo es pequeña (supera la nula, pero el intervalo incluye el cero); no se puede afirmar. Ninguna variable de ayer ayuda.

**Límites.** ERA5 suaviza el ciclo diurno de la lluvia en terreno complejo: una hora de pico que no discrimina en ERA5 no prueba que no discrimine en la realidad. Las únicas horas documentadas (Chosica 2012: 16 a 18 h; 2015: 14:30) son de tarde y también están en la mediana de 14 h de los días sin huaico. Para probar la hipótesis hacen falta pluviógrafos o radar; los datos horarios del SENAMHI no se usan hasta tener autorización por escrito.

## 5. T24 · Temperatura absoluta del mar

**Método.** Desde NOAA OISST (cajas `nino12`, `costa_peru`, `costa_lima`): temperatura de ayer, grados-día sobre 25, 26, 27 y 28 °C en los 7, 14 y 30 días hasta ayer (51 columnas) y días seguidos sobre cada umbral. Días con racha activa de 6 473: Niño 1+2 3 456 (25 °C), 1 855 (26), 648 (27), 122 (28); costa de Perú 770, 265, 30, 0; costa de Lima 139, 37, 0, 0 (la costa de Lima casi nunca pasa de 26 °C).

**Resultado univariado.** La temperatura absoluta separa los días: AUC 0,82 (costa de Perú), 0,81 (costa de Lima), 0,78 (Niño 1+2). Pero el mar se calienta de diciembre a marzo, igual que la frecuencia de huaicos; por eso se repite **dentro de cada mes de calendario**: 0,736 [0,646; 0,803] (costa de Perú), 0,718 [0,613; 0,792] (Niño 1+2) y 0,713 [0,641; 0,778] (costa de Lima). Los grados-día sobre 25 °C llegan a 0,70, y los de 26 °C a 0,68: **no mejoran el simple nivel**. 29 de las 51 columnas separan, pero comparten la misma señal de régimen (un mar cálido en un año de El Niño).

**¿Mejora el modelo?** No: el modelo base ya incluye la anomalía de la TSM.

| Bloque añadido | ΔAP [90 %] | Prob. de mejora |
|---|---|---|
| Nivel de las 3 cajas (3 columnas) | −0,005 [−0,024; +0,014] | 0,38 |
| Grados-día y rachas sobre 26-28 °C, Niño 1+2 y costa de Perú (24) | −0,017 [−0,054; +0,034] | 0,31 |
| Todo (51) | −0,081 [−0,132; −0,016] | 0,02 |

**Conclusión T24: no se confirma el umbral.** El nivel absoluto es un buen indicador del régimen (interanual), pero no aporta nada que la anomalía no tenga ya, y los umbrales de convección no mejoran sobre una relación lineal. Con 51 columnas el modelo empeora (sobreajuste; ver capítulo 05).

## 6. T25 · Índices E y C

**Método.** Una cifra por temporada (desde 1984, 43 temporadas): media de enero a abril de E, C, ICEN y ONI. Se correlaciona (Spearman, valor p por permutación de 2 000 sorteos) con el número de quebradas ubicadas activas y con los días con huaico, y se compara la deviance de Poisson dejando una temporada fuera. Los índices se parecen por pares: E con ICEN 0,88 y C con ONI 0,87, mientras E y C entre sí no se correlacionan (−0,06), como dice Takahashi et al. (2011).

| Índice (ene-abr) | ρ con quebradas activas (p) | ρ con días con huaico (p) |
|---|---|---|
| E | 0,402 (0,009) | 0,438 (0,002) |
| C | −0,010 (0,95) | −0,119 (0,45) |
| **ICEN** | **0,489 (0,002)** | **0,491 (0,002)** |
| ONI | 0,145 (0,35) | 0,035 (0,81) |

Desde 2009 (18 temporadas) solo el ICEN pasa el 5 % (ρ = 0,53, p = 0,028; E 0,33, p = 0,19).

Deviance de Poisson dejando una temporada fuera (más baja es mejor):

| Modelo | Quebradas activas | Días con huaico |
|---|---|---|
| Media | 200,4 | 230,6 |
| **ICEN** | **151,7** | 156,3 |
| ONI | 195,9 | 241,2 |
| E | 168,2 | 170,6 |
| C | 205,6 | 230,0 |
| E + C | 174,3 | 170,0 |
| ICEN + C | 158,7 | 150,1 |
| ICEN + ONI | 155,0 | **137,5** |
| E + C + ICEN + ONI | 168,5 | 157,6 |

En el modelo diario, E y C del mes previo (y su cambio) no suman: ΔAP −0,002 [−0,016; +0,010].

**Conclusión T25: no se confirma.** E y C no explican mejor que el ICEN: el ICEN gana en ambas medidas. Lo que se ve es consistente con que el efecto es **costero** (E, ICEN) y no del Pacífico central (C, ONI): C y ONI solos no se distinguen de la media. Lo único que mejora a ICEN es sumarle el ONI en los días con huaico (137,5 contra 156,3), una señal que habría que repetir con más temporadas antes de interpretarla. **Contexto del 2026:** E llega a 4,26 en septiembre de 2026 y el ICEN supera 3,9, valores de El Niño extraordinario; los archivos del IGP terminan en septiembre. Esto no es una predicción de huaicos: es la razón por la cual el contraste por temporada seguirá actualizándose.

## 7. T28 · Lluvia satelital (CHIRPS v3): **no probada en esta corrida**

**Qué se hizo.**
- Se encontró la fuente: CHIRPS v3 diario (`sat`, tiempo de NASA IMERG, desde 1998) en el Climate Hazards Center, sin clave y con licencia de dominio público y CC BY 4.0. El readme del producto es explícito en que CHIRPS diario **reparte los totales de cada pentada entre los días con el tiempo de IMERG o de ERA5**; la versión `sat` usa IMERG, así que su reparto entre días es independiente de ERA5 (el total de la pentada no es una medida diaria).
- Se probó la lectura por ventanas de un GeoTIFF de 11 MB (rasterio sobre HTTP: ~1,5 s por día y por las 5 cajas, unos kilobytes transferidos) y se escribió `descargar-datos --solo chirps-v3`, que guarda la media de cajas de 4 × 4 celdas (0,2°) para noviembre a abril, de 1998 a hoy, con caché por temporada. Las cajas se fijaron antes de mirar cualquier resultado: Chosica (−76,80 a −76,60; −12,03 a −11,83), Santa Eulalia alta (−76,50 a −76,30; −11,80 a −11,60), Matucana (−76,48 a −76,28; −11,94 a −11,74), Ticlio (−76,30 a −76,10; −11,70 a −11,50) y selva de Tarma (−75,79 a −75,59; −11,52 a −11,32).
- Se escribieron las pruebas de complemento y sustitución (`evaluar_chirps`: ERA5, ERA5 + CHIRPS y CHIRPS en vez de ERA5 en las temporadas 1998 en adelante, con los mismos pliegues) y la comparación diaria con ERA5 (correlación y sesgo en el 5 % de días más lluviosos).

**Qué falló.** El 30 de octubre de 2026, desde las ~12:00 hora de Lima, `data.chc.ucsb.edu` dejó de responder a esta máquina (las conexiones agotan el tiempo; `www.chc.ucsb.edu` sí responde). Pasó después de un primer intento con 12 hilos en paralelo; no sé si fue un límite por IP o una caída del servidor. La alternativa del Data Library del IRI (CHIRPS v2) sí responde, pero tarda de 1 a 4 minutos por unos pocos días y 1998-2026 sería inviable. Se dejó un proceso que prueba el servidor cada 5 minutos (hasta unas 7 horas) y, cuando responda, descarga con 4 hilos. **Cuando exista `datos/chirps_v3_sat_diario.csv` basta re-ejecutar el notebook**; las celdas de T28 ya están escritas y se activan solas.

**Expectativa honesta.** Como el reparto diario de CHIRPS es el de IMERG y el total es el de la pentada, la comparación con ERA5 mide sobre todo cuánto de la mala lluvia de ERA5 en terreno complejo (capítulo 09: correlaciones de ~0,1 con MERRA-2) se corrige. Si no aparece mejora, el techo no estaría en la fuente de la lluvia.

## 8. Qué se concluye

| | Hipótesis | Resultado |
|---|---|---|
| T23 | tarde, corta e intensa | **No.** Hora del pico sin diferencia; los días con huaico tienen más horas húmedas y rachas más largas, y la lluvia menos concentrada. Mejora del modelo pequeña y con intervalo que incluye el cero |
| T24 | TSM absoluta con umbral | **No como umbral.** El nivel separa (AUC por mes 0,71–0,74) pero ya está en el modelo vía la anomalía; ΔAP ≈ 0 |
| T25 | E y C mejor que ICEN | **No.** El ICEN gana; el efecto es costero (E ≈ ICEN) y C/ONI no distinguen de la media |
| T28 | CHIRPS | **Sin probar** (servidor del CHC inaccesible); código, fuente y cajas listos |

## 9. Límites

- 118 días con huaico, agrupados en pocas temporadas; las diferencias de AP de ±0,01 están dentro del ruido.
- Las nulas son de 8 repeticiones, suficientes para ver si el cambio supera el azar pero no para estimar p-valores finos.
- Las cifras del modelo base dependen de tres puntos MERRA-2 de respaldo hasta que llegue ERA5.
- Los índices del IGP (E, C, ICEN) no traen licencia explícita: se descargan con `descargar-datos` y no se redistribuyen en el espejo público.

## 10. Reproducir

```bash
uv run descargar-datos --solo noaa-oisst igp-icen igp-ec noaa-enso nasa-power   # ERA5 y CHIRPS aparte
uv run jupyter lab notebooks/10-hipotesis-de-la-literatura.ipynb                  # ~15 minutos
```
