# 19 · Backtest con el reforecast GEFSv12 (2000-2019)

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Es un banco de pruebas: mide cuánto de los días con huaico catalogados se anticipa con la **lluvia pronosticada** (no con la observada). Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/15-backtest-gefs-reforecast.ipynb`](../notebooks/15-backtest-gefs-reforecast.ipynb). Código: `src/illapa_research/gefs_reforecast.py` (lectura del reforecast) y `gefs_backtest.py` (backtest), con pruebas en `tests/test_gefs_reforecast.py`. Tablas: `catalogo/gefs_*.csv`. Antecedente: la revisión de métodos y fuentes del [capítulo 16](16-pronostico-a-probabilidad.md).

## 1. Pregunta y pre-registro

Los capítulos 05 y 15 dicen qué se puede acertar con la lluvia *correcta*. Aquí se pregunta qué pasa cuando esa lluvia es la que **un modelo de pronóstico había anunciado** a 24, 48 y 72 horas, a lo largo de 20 temporadas (2000-2019), con un único modelo (GEFSv12, misma versión todos los años). Hipótesis escritas antes de mirar ningún puntaje:

| | Hipótesis | Resultado |
|---|---|---|
| T40 | Con la lluvia del reforecast reescalada por cuantiles, el modelo entrenado con ERA5 (PP) conserva a 24 h al menos el 70 % de la ganancia sobre la climatología que tiene con lluvia ERA5 («techo»), y la fracción baja con el plazo | **Casi**: 67 % a 24 h, 45 % a 48 h, 39 % a 72 h (todas las temporadas). Sin 2017: 46 %, 38 %, 31 % |
| T41 | Un MOS entrenado dentro de 2000-2019 (solo 20 temporadas) no supera al PP | **Sí se cumple**: a 24 h el PP supera al MOS de ensamble por 0,18 de AP (intervalo −0,39 a −0,01); a 48 y 72 h no se distinguen |
| T42 | La probabilidad de excedencia y la dispersión del ensamble aportan sobre la media | **No**: el MOS con todo el ensamble rinde peor que el de la media (−0,03 de AP a 24 h; intervalo −0,07 a −0,00) |
| T43 | El resultado depende de 2017 (23 de los 55 días con huaico) | **Sí**: la precisión media del PP a 24 h baja de 0,254 a 0,102 |
| T44 (T29) | CAPE y agua precipitable del reforecast aportan sobre la lluvia | **No**: +0,000 de AP (intervalo −0,021 a +0,015) |

## 2. Datos y alineación

| Dato | Fuente | Detalle |
|---|---|---|
| Pronósticos | [NOAA GEFSv12 reforecast](https://registry.opendata.aws/noaa-gefs-reforecast/) (AWS Open Data, lectura anónima, sin cuenta) | `s3://noaa-gefs-retrospective`. Una corrida diaria de las 00 UTC con 5 miembros (`c00`, `p01` a `p04`), rejilla global de 0,25° (1440 × 721), pasos de 3 h. Archivos GRIB2 con `.idx`: se leen solo los mensajes necesarios por rangos de bytes. Datos abiertos de NOAA: atribuir, no insinuar respaldo |
| Variables | `apcp_sfc` (ventanas de 6 h `6-12`, `12-18`, …, `72-78`) de los 5 miembros; `cape_sfc` y `pwat_eatm` solo del miembro de control, a las 13:00 y 16:00 locales | Los crudos no se guardan: solo un CSV pequeño por corrida con medias por caja |
| Lluvia «verdad» y entradas del modelo | ERA5 (6 puntos), mar, caudal, ICEN | Los mismos del capítulo 05; días con huaico del catálogo de 148 fechas (55 en las 2 952 jornadas de prueba) |
| Comparación en mm | PISCOp v3.0 diario del SENAMHI (valle del Rímac, 6 celdas de 0,1°) | Sin redistribuir el archivo; solo la serie derivada local. «Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad.» |

**Cajas** (fijadas antes de mirar resultados; promedio de las celdas de 0,25° cuyo cuadrado cruza la caja): `valle` = las 6 celdas de PISCOp del capítulo 14 (lon −76,80 a −76,50; lat −12,00 a −11,80; 4 celdas del reforecast); y las del capítulo 10 (`fuentes.CAJAS_CHIRPS`): `chosica`, `santa-eulalia-alta`, `matucana`, `ticlio`. La lluvia de ERA5 `ch_*`/`chosica_h_*` se asocia a la caja `chosica`; `sea_*` a `santa-eulalia-alta`; `mat_*` y `cuenca-alta_h_*` a `matucana`; `tic_*` a `ticlio`.

**Alineación con el día local de Lima (UTC−5).** La corrida del día `r` empieza a las 00 UTC = 19:00 del día `r−1`. El día local `d` va de 05 UTC de `d` a 05 UTC de `d+1`; su bloque de ventanas más cercano son las horas 6 a 30 de la corrida de `d` (de 01:00 a 01:00 hora local: desfase de 1 hora, documentado y no corregido). El **plazo k** usa la corrida emitida k−1 días antes, de modo que cada plazo solo usa información disponible antes de que empiece el día:

- plazo 1 (0-24 h): corrida de `d`, horas 6-30;
- plazo 2 (24-48 h): corrida de `d−1`, horas 30-54;
- plazo 3 (48-72 h): corrida de `d−2`, horas 54-78.

Los antecedentes del modelo (suelo, lluvia previa, caudal, mar, calor en altura…) son los observados **desplazados k días**.

**Tamaño y tiempos reales.** Se procesaron 3 032 de las 3 065 corridas posibles de diciembre a abril: faltan solo las de **1 de noviembre a 31 de diciembre de 1999**, que el archivo no tiene (empieza el 1 de enero de 2000); por eso la temporada 2000 solo tiene enero a abril. Una corrida (5 miembros de lluvia, 6 pasos de CAPE y de agua precipitable del control) lee unos **36,7 MB** (medido en la corrida del 10 de febrero de 2010), es decir **unos 111 GB** en total (extrapolado de esa corrida, no medido en conjunto). La descarga y reducción duró unos 40 minutos en la PC remota con 20 procesos (la primera versión con hilos hacía unas 10 corridas por minuto: la decodificación GRIB2 mantiene el intérprete). Quedó en 60 MB de CSV (1,09 millones de filas). Fuente opt-in: `descargar-datos --solo gefs-reforecast`.

## 3. Método

1. **PP (perfect prognosis).** Regresión logística con penalización L2 (C = 0,03, la del capítulo 05) entrenada con entradas hechas con ERA5 de todas las demás temporadas (1984-2026), dejando una temporada fuera; en la temporada retenida la lluvia del día se **sustituye** por la pronosticada (1 y 3 días, 6 columnas cada una). Variantes: `techo` (lluvia ERA5), `pp_qm` (lluvia GEFS reescalada al ERA5 por cuantiles empíricos, ajustados en las otras temporadas de prueba) y `pp_crudo` (sin reescalar). Las variables de hora pico y de 3 h máximas (el reforecast no las da) quedan fuera de este modelo. Variante `pp_qm_sin2017_ent`: sin 2017 también en el entrenamiento.
2. **MOS dentro de 2000-2019**, dejando una temporada fuera, con regularización fija elegida antes de mirar: `mos_media` (media del ensamble y suma de 3 días, 5 cajas; C = 0,3), `mos_ens` (+ máximo, dispersión y probabilidades de superar 1, 5 y 10 mm; C = 0,1), `mos_ant` (+ antecedentes; C = 0,03) y `mos_ens_conv` (+ CAPE y agua precipitable).
3. **Referencias.** El ranking directo del pronóstico (`gefs_media`: media del ensamble en la caja del valle; un umbral solo corta ese ranking) y la climatología mensual fuera de temporada.
4. **Métricas por plazo** (AP = precisión media, AUC, Brier de habilidad frente a la climatología, aciertos con el 5 % y el 10 % de los días en alarma, razón observado/predicho), con y sin 2017, y por subventanas (2000-2008, 2009-2019). Intervalos por remuestreo de temporadas (1 000), diferencias pareadas (2 000) y **2 000 mundos nulos en la GPU** que desplazan las etiquetas dentro de cada temporada y repiten todo el procedimiento.

## 4. Resultados

### 4.1 Precisión media y aciertos por plazo (todas las temporadas: 2 952 días, 55 con huaico; base 0,019)

| Plazo | Modelo | AP | AUC | Aciertos con 5 % de alarmas | Brier de habilidad | Obs/pred |
|---|---|---|---|---|---|---|
| 24 h | Climatología | 0,026 | 0,62 | 0 % | 0 | 0,98 |
| 24 h | **Techo (lluvia ERA5)** | **0,366** | 0,91 | 56 % | +0,20 | 1,12 |
| 24 h | **PP con GEFS reescalado** | **0,254** | 0,90 | 56 % | +0,08 | 0,78 |
| 24 h | PP con GEFS crudo | 0,252 | 0,90 | 56 % | +0,07 | 0,73 |
| 24 h | MOS media | 0,111 | 0,82 | 27 % | +0,03 | 1,03 |
| 24 h | MOS ensamble | 0,076 | 0,82 | 22 % | +0,02 | 1,02 |
| 24 h | MOS + antecedentes | 0,239 | 0,88 | 45 % | +0,12 | 1,23 |
| 24 h | GEFS crudo (ranking) | 0,116 | 0,81 | 25 % | — | — |
| 48 h | Techo | 0,345 | 0,91 | 58 % | +0,19 | 1,08 |
| 48 h | PP con GEFS reescalado | 0,169 | 0,88 | 44 % | −0,07 | 0,66 |
| 48 h | MOS media | 0,128 | 0,81 | 25 % | +0,03 | 1,02 |
| 72 h | Techo | 0,297 | 0,90 | 56 % | +0,15 | 1,05 |
| 72 h | PP con GEFS reescalado | 0,131 | 0,87 | 47 % | −0,13 | 0,66 |
| 72 h | MOS media | 0,094 | 0,79 | 24 % | +0,02 | 1,01 |

(Todas las filas por plazo y modelo, con y sin 2017 y por subventana, en `catalogo/gefs_metricas.csv`.)

**Lectura.** Con la lluvia pronosticada a 24 h, el PP recupera dos tercios de la ganancia que daría la lluvia perfecta y deja el 56 % de los días con huaico dentro del 5 % de días de mayor puntaje, igual que el techo. El **orden** de los días se conserva (AUC 0,87-0,90 a los tres plazos). Lo que se pierde con el plazo es la **precisión media** (de 0,254 a 0,131), y sobre todo la **calibración**: el PP con GEFS sobreestima (observado/predicho 0,66 a 0,78), su Brier de habilidad es negativo a 48 y 72 h, y por eso sus «probabilidades» no son confiables sin recalibrar. El MOS entrenado dentro de 2000-2019 sí queda calibrado (observado/predicho ≈ 1), pero casi no mejora el ranking directo del pronóstico (24 h: 0,111 contra 0,116).

### 4.2 Sin 2017 (32 días con huaico; base 0,011)

| Plazo | Techo | PP reescalado | MOS media | MOS + antecedentes | GEFS crudo |
|---|---|---|---|---|---|
| 24 h | 0,198 | **0,102** | 0,112 | 0,119 | 0,052 |
| 48 h | 0,166 | 0,076 | 0,149 | 0,065 | 0,071 |
| 72 h | 0,145 | 0,060 | 0,105 | 0,072 | 0,078 |

Aciertos con el 5 % de alarmas del PP sin 2017: 34 %, 38 % y 34 % (contra 56 %, 44 % y 47 % con 2017). Sin 2017 el PP y el MOS de media **quedan empatados** y a 48-72 h el MOS de media es mejor. El Brier de habilidad del PP sin 2017 es negativo a los tres plazos (−0,13, −0,26, −0,32): sobreestima. **El resultado que más importa de este capítulo es esa dependencia**: una parte grande del buen desempeño del PP viene de 2017 (23 de los 55 días con huaico).

### 4.3 Intervalos y diferencias pareadas (remuestreo de 20 temporadas)

Intervalos del 90 % de la precisión media a 24 h (todas las temporadas): techo 0,10 a 0,53; PP reescalado 0,06 a 0,49; MOS ensamble 0,04 a 0,14; GEFS crudo 0,03 a 0,19; climatología 0,01 a 0,05. Son anchos: con 20 temporadas y 55 eventos agrupados, **un intervalo así no separa al PP del techo**.

| Diferencia de AP (a − b) | Plazo | Todas | Sin 2017 |
|---|---|---|---|
| PP reescalado − techo | 24 h | −0,081 [−0,160; 0,006] | −0,071 [−0,151; 0,002] |
| PP reescalado − techo | 48 h | −0,145 [−0,224; −0,021] | −0,085 [−0,192; 0,006] |
| PP reescalado − techo | 72 h | −0,144 [−0,235; −0,009] | −0,077 [−0,178; 0,009] |
| PP reescalado − PP crudo | 24-72 h | ≈ 0 (±0,03) | ≈ 0 |
| MOS ensamble − MOS media | 24 h | −0,031 [−0,070; −0,002] | −0,038 [−0,085; 0,000] |
| MOS ensamble − PP reescalado | 24 h | −0,176 [−0,385; −0,009] | −0,062 [−0,190; 0,001] |
| MOS + antecedentes − MOS ensamble | 24 h | +0,152 [0,016; 0,290] | +0,061 [−0,002; 0,119] |
| MOS + CAPE/agua precipitable − MOS ensamble | 24 h | 0,000 [−0,021; 0,015] | −0,002 [−0,029; 0,018] |

Sin 2017 casi todas las diferencias tocan el cero. Los antecedentes (suelo, lluvia previa, caudal, mar) ayudan al MOS a 24 h (con 2017), no de forma demostrable sin él. La **reescala por cuantiles no cambia el orden** de los días (diferencia ≈ 0), solo la calibración.

### 4.4 Mundos nulos (2 000, GPU)

| Plazo | Modelo | AP real | AP nula media / p95 / máx | p |
|---|---|---|---|---|
| 24 h | PP reescalado | 0,254 | 0,030 / 0,056 / 0,145 | 0,0005 |
| 24 h | MOS ensamble | 0,076 | 0,018 / 0,026 / 0,066 | 0,0005 |
| 48 h | PP reescalado | 0,169 | 0,030 / 0,058 / 0,134 | 0,0005 |
| 48 h | MOS ensamble | 0,108 | 0,018 / 0,026 / 0,053 | 0,0005 |
| 72 h | PP reescalado | 0,131 | 0,030 / 0,058 / 0,133 | 0,0010 |
| 72 h | MOS ensamble | 0,060 | 0,017 / 0,024 / 0,056 | 0,0005 |

Ningún mundo nulo alcanza a los modelos reales (el mínimo posible con 2 000 mundos es 0,0005): **hay habilidad real a 24, 48 y 72 h**. Otra cosa es cuánta, y si vale como probabilidad: ver §4.5.

### 4.5 Fiabilidad y valor económico

Bandas de probabilidad del PP reescalado a 24 h: de 2 462 días con probabilidad 0-2 %, 11 tuvieron huaico (0,4 %); de 343 días con 2-10 %, 13 (3,8 %); de 84 con 10-25 %, 13 (15,5 %); de 63 con 25 % o más, 18 (28,6 %; predicho medio 51,7 %). Es decir, **la banda alta sobreestima casi al doble** y la misma banda a 48 y 72 h tiene 21,7 % y 17,9 % de huaicos con un predicho de 48 % a 49 %. El MOS de ensamble casi nunca pasa del 25 % (0, 6 y 0 días).

Valor económico relativo (coste/pérdida, alarma si p ≥ C/L; 1 = pronóstico perfecto, 0 = climatología):

| C/L | Techo 24 h | PP 24 h | MOS 24 h | PP 48 h | PP 72 h |
|---|---|---|---|---|---|
| 0,02 | 0,64 | 0,64 | 0,51 | 0,57 | 0,60 |
| 0,05 | 0,56 | 0,45 | 0,11 | 0,35 | 0,30 |
| 0,10 | 0,32 | 0,33 | −0,01 | 0,18 | 0,18 |
| 0,20 | 0,18 | 0,13 | 0,01 | −0,05 | 0,01 |
| 0,50 | 0,09 | 0,06 | 0,00 | −0,26 | −0,36 |

El valor se concentra en coste/pérdida bajos (alarma barata frente a lo que se pierde): a 0,02 el PP a 24 h es igual al techo (0,64). Cuanto más caro es actuar, menos valor, y a 48-72 h el PP tiene valor negativo por su sobreestimación.

### 4.6 Umbrales en mm: GEFS frente a PISCOp (SENAMHI)

La media del ensamble en la caja del valle marca **entre 3,4 y 4,2 veces** la lluvia de PISCOp (correlación 0,46-0,50 con ella). Con umbrales de percentiles de PISCOp (2,7; 3,8 y 7,7 mm):

| Plazo | Umbral | Sin corregir: POD / FAR / alarmas en otros días | Con cuantiles: POD / FAR / alarmas en otros días |
|---|---|---|---|
| 24 h | p90 (2,7 mm) | 0,91 / 0,84 / 55 % (55 de 55 huaicos) | 0,31 / 0,70 / 9 % (28 de 55) |
| 24 h | p95 (3,8 mm) | 0,89 / 0,89 / 42 % (55 de 55) | 0,27 / 0,74 / 5 % (21 de 55) |
| 72 h | p90 | 0,88 / 0,83 / 51 % (55 de 55) | 0,32 / 0,68 / 9 % (26 de 55) |

(Los POD y FAR son sobre días de lluvia observada ≥ umbral; los huaicos capturados, sobre los 55 del catálogo, con el día o el anterior.) **Sin corregir, el umbral pasa casi todos los huaicos con la mitad de los días del año en alarma** (útil para nada). Corrigiendo el sesgo, la tasa de alarma cae a un 5-9 % pero se captura solo el 20-50 % de los huaicos: una corrección monótona no mejora la detección, solo la calibración (coincide con el capítulo 14). Un umbral en mm no es una buena regla de decisión.

### 4.7 ¿Qué quebrada?

`P(día) × participación` (capítulo 06) con el MOS de ensamble: precisión media por par (quebrada, día) 0,0070, 0,0103 y 0,0075 a 24, 48 y 72 h, contra 0,0054, 0,0096 y 0,0072 de solo el día (base 0,0008). **Sin 2017 la ventaja desaparece** (a 48 y 72 h solo el día queda mejor: 0,0096 contra 0,0081 y 0,0074 contra 0,0053). Lo que sí funciona es ordenar las quebradas por su historial: de 61 pares (quebrada, día) con huaico y quebrada ubicada en 21 días con huaico de 2000-2019, **26 (43 %) cayeron entre las 5 quebradas de mayor participación**, contra el 21 % (5 de 24) de una elección al azar; participación aprendida sin la temporada del día. Es lo ya visto en el capítulo 03: el historial se concentra en las quebradas más reportadas.

### 4.8 Potencia y sesgo del catálogo (por subventana)

| Subventana | Temporadas | Días | Días con huaico |
|---|---|---|---|
| 2000-2008 | 9 | 1 311 | 8 |
| 2009-2013 | 5 | 746 | 12 |
| 2014-2019 | 6 | 895 | 35 (23 en 2017) |

Con **8 eventos en 2000-2008** y **35 en 2014-2019**, el catálogo no pesa igual en todos los años: la cobertura de 1999-2008 es pobre (capítulo 07) y la reciente es mucho más completa. Por subventana (24 h): en 2000-2008 el PP da 0,213 y el techo 0,247 (8 eventos); en 2009-2019, 0,272 y 0,397 (47 eventos). La mitad de lo que mide el backtest sale de 2014-2019. Con 55 eventos agrupados en pocas tormentas, **se pueden detectar diferencias grandes** (modelo contra nulo, PP contra climatología) **y no las finas** (PP contra techo a 24 h, MOS contra PP a 48-72 h, cualquier efecto de las variables del ensamble o convectivas).

## 5. Conclusiones

1. **El backtest con pronóstico real se puede hacer a escala de 20 años** con datos abiertos y sin cuenta: el reforecast GEFSv12 lo permite, y queda reproducible (`--solo gefs-reforecast`).
2. **El PP con GEFS conserva a 24 h dos tercios de la ganancia de la lluvia perfecta** (T40 casi se cumple) y el mismo 56 % de huaicos en el 5 % de días de mayor puntaje. A 48 y 72 h la precisión media cae a un 45 % y 39 % de esa ganancia.
3. **Dependencia fuerte de 2017**: sin ese año el PP y un MOS simple de la media quedan empatados y la precisión media cae a la mitad.
4. **La probabilidad no es confiable sin recalibrar**: el PP sobreestima (observado/predicho 0,66-0,78; negativo en Brier de habilidad a 48-72 h y sin 2017). El MOS sí está calibrado pero casi no mejora el ranking del pronóstico crudo.
5. **Lo que no aporta**: las estadísticas de ensamble (dispersión, probabilidades de excedencia) con 20 temporadas, y CAPE y agua precipitable del miembro de control (T29/T44: +0,000).
6. **Un umbral en mm no sirve de regla**: sin corregir alarma la mitad del año; corregido, captura entre el 20 % y el 50 % de los huaicos.

## 6. Límites

- **Resolución y miembros.** El reforecast tiene 5 miembros y una rejilla de 0,25° (~28 km); la lluvia de una quebrada de 10 km² en la sierra se promedia en 1 a 4 celdas muy suavizadas. La correlación diaria con PISCOp es ≈ 0,5.
- **Alineación.** Desfase de 1 hora entre el día local y las ventanas de 6 h; no corregido.
- **Catálogo.** 55 días con huaico en 20 temporadas (23 en 2017; solo 8 en 2000-2008); sesgo de reporte y de cobertura por era.
- **MOS con 20 temporadas.** Muy poco para ajustar 30 a 130 variables; la regularización fija se eligió antes y no se afinó.
- **Reescala por cuantiles** ajustada solo con las otras temporadas de prueba (hasta 19), no con una serie larga.
- **Modelo PP único** (regresión logística con L2): no se probó otro tipo de modelo con pronóstico.
- **Faltan las corridas de diciembre de 1999** (no existen en el archivo).
- La lluvia de ERA5 («techo») no es la lluvia real: el techo es el de «tener ERA5 perfecto», no el de tener pluviómetros.

## 7. Reproducir

```bash
uv sync --extra gefs --extra gpu --extra dev --extra notebooks
uv run descargar-datos --solo gefs-reforecast      # ~111 GB leídos por rangos de bytes, ~40 min con 20 procesos, deja 60 MB
uv run python -m illapa_research.gefs_backtest --nulas 2000   # escribe catalogo/gefs_*.csv (en la PC remota con GPU)
uv run jupyter lab notebooks/15-backtest-gefs-reforecast.ipynb
```

Los crudos GRIB nunca se guardan. Las probabilidades fuera de muestra de todos los modelos y plazos quedan en `catalogo/gefs_probabilidades_fuera_de_muestra.csv.gz`.
