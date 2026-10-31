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

Corrida del 30 de octubre de 2026. Muestra: 6 473 días de temporada (diciembre a abril, 1984 en adelante), 121 con huaico catalogado.

| Dato | Fuente | Licencia / uso |
|---|---|---|
| Lluvia horaria de Chosica y de la cuenca alta (1983 a hoy) | Open-Meteo (ERA5, `open_meteo_horario_estudio.json`) | CC BY 4.0; la API gratuita es solo no comercial. «Weather data by Open-Meteo.com» |
| TSM diaria de 3 cajas | NOAA OISST v2.1, vía ERDDAP de CoastWatch (`enso/oisst_diario.csv`) | Dominio público |
| Índices E y C mensuales (ERSSTv5) | IGP, `met.igp.gob.pe/datos/ecindex_ersstv5.txt` (`descargar-datos --solo igp-ec`) | Datos públicos del IGP **sin licencia explícita**: se citan y no van al espejo público. Takahashi et al. (2011), doi:10.1029/2011GL047364 |
| ICEN oficial | IGP/ENFEN (`--solo igp-icen`) | Igual que arriba |
| ONI | NOAA CPC | Dominio público |
| Resto del modelo base (puntos ERA5 de Matucana, Santa Eulalia alta y Ticlio; caudal GloFAS; humedad de selva y costa) | Capítulos 04 y 05 | Ver allí |
| Lluvia CHIRPS v3 (T28) | Climate Hazards Center, `data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/` (`--solo chirps-v3`) | Dominio público y CC BY 4.0. Funk et al. (2026), *Scientific Data* 13, 718, doi:10.1038/s41597-026-07096-4 |

**Con qué datos corrió cada cifra.** Modelo base con ERA5 completo en los seis puntos (capítulo 13), 150 fechas de huaico (121 días en temporadas de lluvia), mar NOAA, caudal GloFAS e ICEN, en la PC remota (commit `ddc70f0`). Modelo base de esta corrida: AP 0,289 (base 0,019), AUC 0,903, 53 % de los días con huaico con el 5 % de días en alarma.

## 4. T23 · Hora de la lluvia

**Método.** Entre los días lluviosos de cada punto (lluvia diaria de ERA5 ≥ 1 mm: 2 506 días y 104 con huaico en Chosica, 5 370 y 121 en la cuenca alta) se compara cada variable de forma entre días con huaico y sin huaico: AUC (0,5 = sin diferencia) con bootstrap de temporadas, y el mismo AUC solo entre los días de lluvia fuerte (percentil 90) para descartar que sea solo intensidad. También se calcula el AUC **dentro de cada mes de calendario** para quitar el ciclo estacional.

| Variable | Chosica: AUC [90 %] | Cuenca alta: AUC [90 %] | Lectura |
|---|---|---|---|
| Hora del pico | 0,517 [0,486; 0,550] | 0,538 [0,473; 0,591] | Mediana 14 h con y sin huaico: sin diferencia |
| Fracción entre 12 y 20 h | 0,531 [0,488; 0,576] | **0,364 [0,325; 0,406]** | En la cuenca alta los días con huaico tienen *menos* lluvia de tarde (mediana 0,67 contra 0,80) |
| Horas con lluvia | **0,686 [0,623; 0,739]** | **0,738 [0,696; 0,786]** | Más horas húmedas: 13,5 contra 9 (Chosica), 17 contra 11 (cuenca alta) |
| Racha húmeda más larga | **0,661 [0,608; 0,716]** | **0,725 [0,679; 0,773]** | Más continua |
| Fracción de la lluvia en 3 h | **0,403 [0,340; 0,457]** | **0,316 [0,255; 0,358]** | Menos concentrada |

Dentro de cada mes de calendario los resultados son los mismos (horas húmedas 0,751, racha 0,739 en Chosica; 0,739 y 0,725 en la cuenca alta). Solo en la cuenca alta la señal de duración sobrevive entre los días de lluvia fuerte (AUC 0,64 con 37 eventos); en Chosica baja a 0,53 con 27 eventos, sin poder estadístico.

**¿Mejoran el modelo diario?**

| Bloque añadido al modelo base | ΔAP [90 %] | Prob. de mejora | Nula p95 |
|---|---|---|---|
| Timing del día, 10 columnas (nowcast) | +0,002 [−0,026; +0,025] | 0,55 | −0,005 |
| Duración y concentración del día, 6 columnas (nowcast) | +0,003 [−0,023; +0,027] | 0,59 | −0,001 |
| Timing de ayer, 10 columnas (antecedente) | +0,025 [−0,005; +0,042] | 0,92 | −0,007 |

**Conclusión T23: no se confirma como se planteó, y aparece la contraria.** La hipótesis era «tarde, corta e intensa»; los datos dicen que la hora del pico no distingue y que los días con huaico tienen lluvia **más prolongada y menos concentrada**. Esto coincide con que lo que ordena el modelo son los antecedentes y la lluvia acumulada (capítulos 04 y 05). La mejora del modelo es pequeña y los tres intervalos incluyen el cero; el timing de ayer es el que más sube (+0,025, probabilidad de mejora 0,92) y habría que repetirlo con más temporadas antes de interpretarlo.

**Límites.** ERA5 suaviza el ciclo diurno de la lluvia en terreno complejo: una hora de pico que no discrimina en ERA5 no prueba que no discrimine en la realidad. Las únicas horas documentadas (Chosica 2012: 16 a 18 h; 2015: 14:30) son de tarde y también están en la mediana de 14 h de los días sin huaico. Para probar la hipótesis hacen falta pluviógrafos o radar.

## 5. T24 · Temperatura absoluta del mar

**Método.** Desde NOAA OISST (cajas `nino12`, `costa_peru`, `costa_lima`): temperatura de ayer, grados-día sobre 25, 26, 27 y 28 °C en los 7, 14 y 30 días hasta ayer (51 columnas) y días seguidos sobre cada umbral. Días con racha activa de 6 473: Niño 1+2 3 456 (25 °C), 1 855 (26), 648 (27), 122 (28); costa de Perú 770, 265, 30, 0; costa de Lima 139, 37, 0, 0 (la costa de Lima casi nunca pasa de 26 °C).

**Resultado univariado.** La temperatura absoluta separa los días, pero el mar se calienta de diciembre a marzo, igual que la frecuencia de huaicos; por eso se repite **dentro de cada mes de calendario**: 0,739 [0,649; 0,806] (costa de Perú), 0,722 [0,618; 0,792] (Niño 1+2) y 0,714 [0,643; 0,778] (costa de Lima). Los grados-día sobre 25 °C llegan a 0,71, y los de 26 °C a 0,69: **no mejoran el simple nivel**. 29 de las 51 columnas separan, pero comparten la misma señal de régimen (un mar cálido en un año de El Niño).

**¿Mejora el modelo?** No de forma clara: el modelo base ya incluye la anomalía de la TSM. El nivel de las tres cajas suma +0,018, pero queda por debajo del percentil 95 de la nula (+0,023).

| Bloque añadido | ΔAP [90 %] | Prob. de mejora |
|---|---|---|
| Nivel de las 3 cajas (3 columnas) | +0,018 [+0,004; +0,028] | 0,99 |
| Grados-día y rachas sobre 26-28 °C, Niño 1+2 y costa de Perú (24) | −0,032 [−0,051; −0,012] | 0,00 |
| Todo (51) | −0,086 [−0,124; −0,032] | 0,00 |

**Conclusión T24: no se confirma el umbral.** El nivel absoluto es un buen indicador del régimen (interanual), pero no aporta nada que la anomalía no tenga ya, y los umbrales de convección no mejoran sobre una relación lineal. Con 51 columnas el modelo empeora (sobreajuste; ver capítulo 05).

## 6. T25 · Índices E y C

**Método.** Una cifra por temporada (desde 1984, 43 temporadas): media de enero a abril de E, C, ICEN y ONI. Se correlaciona (Spearman, valor p por permutación de 2 000 sorteos) con el número de quebradas ubicadas activas y con los días con huaico, y se compara la deviance de Poisson dejando una temporada fuera. Los índices se parecen por pares: E con ICEN 0,88 y C con ONI 0,87, mientras E y C entre sí no se correlacionan (−0,06), como dice Takahashi et al. (2011).

| Índice (ene-abr) | ρ con quebradas activas (p) | ρ con días con huaico (p) |
|---|---|---|
| E | 0,400 (0,010) | 0,450 (0,002) |
| C | −0,010 (0,95) | −0,130 (0,41) |
| **ICEN** | **0,489 (0,002)** | **0,500 (0,002)** |
| ONI | 0,145 (0,36) | 0,028 (0,85) |

Deviance de Poisson dejando una temporada fuera (más baja es mejor):

| Modelo | Quebradas activas | Días con huaico |
|---|---|---|
| Media | 207,6 | 232,5 |
| **ICEN** | **159,0** | 157,7 |
| ONI | 203,3 | 243,2 |
| E | 176,4 | 173,4 |
| C | 213,5 | 231,7 |
| E + C | 183,1 | 172,6 |
| ICEN + C | 167,0 | 152,3 |
| ICEN + ONI | 162,6 | **136,6** |
| E + C + ICEN + ONI | 176,7 | 158,8 |

En el modelo diario, E y C del mes previo (y su cambio) no suman: ΔAP −0,005 [−0,027; +0,014].

**Conclusión T25: no se confirma.** E y C no explican mejor que el ICEN: el ICEN gana en ambas medidas. Lo que se ve es consistente con que el efecto es **costero** (E, ICEN) y no del Pacífico central (C, ONI): C y ONI solos no se distinguen de la media. Lo único que mejora a ICEN es sumarle el ONI en los días con huaico (136,6 contra 157,7), una señal que habría que repetir con más temporadas antes de interpretarla. **Contexto del 2026:** E llega a 4,26 en septiembre de 2026 y el ICEN supera 3,9, valores de El Niño extraordinario; los archivos del IGP terminan en septiembre. Esto no es una predicción de huaicos: es la razón por la cual el contraste por temporada seguirá actualizándose.

## 7. T28 · Lluvia independiente de ERA5 (PERSIANN-CDR y CPC; CHIRPS no se pudo)

**Qué se hizo.** CHIRPS v3 no se pudo bajar: `data.chc.ucsb.edu` dejó de responder (una sola petición de comprobación más, también agotó el tiempo) y el IRI Data Library pide login (redirige a `/auth/login`, no se usó). Se probaron entonces dos series públicas de NOAA, independientes de ERA5 (`src/illapa_research/lluvia_satelital.py`, `descargar-datos --solo persiann-cdr cpc-lluvia`; ambas no se bajan por defecto):

- **PERSIANN-CDR** (NCEI, 0,25°, doi:10.7289/V51V5BWQ): lluvia satelital infrarroja ajustada a totales mensuales de pluviómetros (GPCP). Archivos diarios globales de 1,3 MB; se leyeron 181 días (noviembre a abril) por temporada, 1984 a 2026, con 3 conexiones y pausas (unos 30 minutos desde la PC remota).
- **CPC Global Unified Gauge-Based Analysis** (PSL, 0,5°): solo pluviómetros interpolados; archivos anuales de 63 MB. Con pocos pluviómetros en la sierra de Lima, casi siempre da 0 mm.

La celda de cada serie que contiene el centro de cada punto se fijó antes de mirar (los centros de las cajas de CHIRPS: Chosica, Santa Eulalia alta, Matucana y Ticlio; la selva de Tarma se descargó pero no se comparó porque ERA5 no tiene allí lluvia diaria equivalente).

**Datos de esta corrida (30 de octubre de 2026, tarde).** Modelo base con **ERA5 completo en los 6 puntos** (caché de `descargar-datos` más la lectura de los archivos de Open-Meteo en AWS, capítulo 13), lluvia horaria ERA5 de Chosica y cuenca alta, mar NOAA, caudal GloFAS e ICEN. 6 473 días de temporada (121 con huaico) para CPC y 6 372 (113) para PERSIANN-CDR (empieza en la temporada 1984). Nulas: 2 000 mundos en GPU (RTX 4080 SUPER).

**Resultados** (tablas en `catalogo/t28_*.csv`):

| | PERSIANN-CDR | CPC |
|---|---|---|
| Correlación diaria con ERA5 (Spearman, 4 puntos) | 0,26 a 0,36 | 0,15 a 0,20 |
| Media del 5 % de días más lluviosos de ERA5 (mm) | 4,4 a 5,1 contra 11,9 a 20,8 de ERA5 | 0,15 a 0,21 contra 12,2 a 21,2 |
| AUC de la lluvia de 3 días para separar días con huaico, Chosica | 0,72 [0,68; 0,77] contra 0,83 [0,77; 0,89] de ERA5 | 0,60 [0,53; 0,66] |
| Lo mismo, tres puntos de la cuenca alta | 0,68 a 0,70 contra 0,68 a 0,76 de ERA5 | 0,60 (todos los puntos casi iguales) |
| Añadir las columnas al modelo `lluvia+antecedentes` (ΔAP, IC 90 % por bootstrap de temporadas) | −0,004 [−0,019; 0,008] | −0,017 [−0,042; 0,004] |
| Sustituir la lluvia ERA5 de la cuenca alta | −0,021 [−0,050; 0,006] | −0,016 [−0,054; 0,009] |
| Nula en GPU con regularización fija (2 000 mundos, bloque desplazado dentro de cada temporada): ΔAP real; p95 nula; p | −0,006; +0,004; 0,30 | −0,007; +0,013; 0,74 |

**Conclusión T28: no se confirma.** Ninguna de las dos series independientes mejora ni sustituye la lluvia de ERA5. En Chosica, ERA5 separa claramente mejor los días con huaico (AUC 0,83 contra 0,72); en la cuenca alta los AUC se parecen. La versión de GPU con 2 000 mundos nulos coincide con la anidada: añadir cualquiera de las dos no se distingue de ruido. PERSIANN-CDR da entre un cuarto y un tercio de la lluvia de ERA5 en los días más lluviosos; es consistente con que el infrarrojo y el ajuste mensual subestiman la lluvia convectiva corta, pero no dice qué serie se acerca más a la lluvia real (el capítulo 11 encuentra que ERA5 da hasta el doble de lluvia que los pluviómetros en extremos).

**Qué no se probó.** CHIRPS v3 (mezcla estaciones y satélite con tiempo de IMERG y 0,05°) y IMERG (piden servidores o cuentas que no se usaron). Los pluviómetros reales del SENAMHI sí ayudaron antes de 2014 (capítulo 11); la limitación parece ser la resolución de las series gruesas en una cuenca de relieve fuerte, no la falta de una segunda fuente.

## 8. Qué se concluye

| | Hipótesis | Resultado |
|---|---|---|
| T23 | tarde, corta e intensa | **No.** Hora del pico sin diferencia; los días con huaico tienen más horas húmedas y rachas más largas, y la lluvia menos concentrada. Mejora del modelo pequeña y con intervalo que incluye el cero |
| T24 | TSM absoluta con umbral | **No como umbral.** El nivel separa (AUC por mes 0,71–0,74) pero ya está en el modelo vía la anomalía; ΔAP ≈ 0 |
| T25 | E y C mejor que ICEN | **No.** El ICEN gana; el efecto es costero (E ≈ ICEN) y C/ONI no distinguen de la media |
| T28 | Lluvia independiente de ERA5 | **No.** CHIRPS no se pudo bajar; PERSIANN-CDR y CPC no mejoran ni sustituyen ERA5 (ΔAP −0,004 a −0,021); ERA5 separa mejor en Chosica |

## 9. Límites

- 121 días con huaico, agrupados en pocas temporadas; las diferencias de AP de ±0,01 están dentro del ruido.
- Los índices del IGP (E, C, ICEN) no traen licencia explícita: se descargan con `descargar-datos` y no se redistribuyen en el espejo público.

## 10. Reproducir

```bash
uv run descargar-datos --solo noaa-oisst igp-icen igp-ec noaa-enso nasa-power   # ERA5 y CHIRPS aparte
uv run descargar-datos --solo cpc-lluvia persiann-cdr                            # T28 (PERSIANN ~30 min)
uv run jupyter lab notebooks/10-hipotesis-de-la-literatura.ipynb                  # ~15 minutos
```
