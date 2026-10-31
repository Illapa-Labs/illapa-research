# 17 · Backtest con pronósticos de lluvia: del pronóstico a la probabilidad del día

> **No es una alerta ni una predicción para decidir evacuaciones.** Es un prototipo para medir cuánto de la probabilidad de un día con huaico *catalogado* se conserva cuando, en vez de la lluvia observada, el modelo recibe la lluvia **pronosticada**. Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/13-backtest-con-pronostico.ipynb`](../notebooks/13-backtest-con-pronostico.ipynb). Código: `src/illapa_research/pronostico_probabilidad.py` (7 pruebas sin red en `tests/test_pronostico_probabilidad.py`). Datos del 30 y 31 de octubre de 2026. La revisión de la literatura sobre cómo se hacen estos modelos es el capítulo 16 (otro worker); aquí solo se mide.

## 1. Pregunta

El sistema debe dar la probabilidad de un día con huaico con datos *a futuro*: pronósticos de lluvia y grillas. ¿Se puede, y cuánto se pierde respecto a conocer la lluvia observada? ¿Y por quebrada?

## 2. Pre-registro (escrito en el notebook antes de mirar resultados)

- **Diseño «perfect prognosis».** El modelo de probabilidad del día (regresión logística L2, C = 0,03; antecedentes de ERA5, caudal, mar e ICEN, como en los capítulos 05 y 15) se ajusta solo con el registro observado hasta abril de 2022 (5 868 días de temporada, 105 con huaico, 99 columnas) y se aplica a entradas donde la lluvia del valle es la **pronosticada**.
- **Sin fuga.** Para pronosticar el día `t` con `lead` días de antelación, los antecedentes se desplazan `lead + 1` días (solo información hasta el final del día anterior a la emisión) y la lluvia de `t`, `t-1` y `t-2` es la pronosticada con ese `lead`. La función `probabilidad_desde_pronostico` descarta todo lo posterior a la emisión y una prueba lo verifica cambiando el futuro.
- **Hipótesis.** H-A: con lead 0 el modelo conserva al menos el 70 % del AP del techo. H-B: el AP cae al subir el lead. H-C: el modelo supera a ordenar por mm crudos del pronóstico. H-D: con unos 14 huaicos solo se detectan diferencias grandes.
- **Qué no se ajusta.** Ni umbrales, ni coeficientes, ni C con el período de prueba.

## 3. Datos

| Dato | Fuente | Nota |
|---|---|---|
| Pronósticos pasados | [Open-Meteo *previous runs*](https://open-meteo.com/en/docs/previous-runs-api): lluvia horaria en las 6 celdas de 0,1° de PISCOp sobre el valle del Rímac (lon −76,75 a −76,55; lat −11,95 y −11,85), sumada al día de lluvia de 7 a. m. a 7 a. m. | CC BY 4.0 (la API gratuita es solo no comercial); UKMO CC BY-SA 4.0. 16 peticiones con pausa de 3 s (4 modelos × 4 temporadas), una sola vez; `descargar-datos --solo pronosticos-previous-runs` (opt-in) |
| Lluvia observada | PISCOp v3.0 diario (SENAMHI), hasta el 31 de diciembre de 2025 | «Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad» |
| Antecedentes | ERA5 (6 puntos), caudal GloFAS, mar OISST, ICEN | capítulos 04 y 05 |
| Huaicos | `catalogo/eventos*.csv` (día exacto, confianza no baja) | 14 días en las temporadas de prueba (12 en 2022-23 a 2024-25, más 2026-02-24 y 02-25) |

**Qué es «lead».** `lead 0` es la última salida del modelo para esa hora (`precipitation`); `lead 1 a 3` es el pronóstico emitido 1, 2 o 3 días antes (`precipitation_previous_dayN`). Cada archivo empieza en una fecha distinta, y eso limita el backtest:

| Archivo | lead 0 | lead 1 a 3 |
|---|---|---|
| UK Met Office 10 km | 4 temporadas (dic. 2022 en adelante) | solo desde 2025 (3 a 2 huaicos) |
| JMA GSM (~55 km) | 4 temporadas | **4 temporadas** (14 huaicos) |
| GFS | desde dic. 2022 | desde 2024 (4 huaicos) |
| ECMWF IFS 0,25° | desde feb. 2024 (4 huaicos) | desde feb. 2024 (3 a 4 huaicos) |

El pronóstico se corrige por cuantiles contra PISCOp (cada temporada con un ajuste hecho sin ella; la de 2025-26, con el de las tres anteriores: fuera de tiempo). Ordenar por mm corregidos da el mismo AP que por mm crudos, porque la corrección es monótona.

## 4. Resultados

### 4.1 Lead 0, cuatro temporadas, 14 huaicos

| Pronóstico | Días | AP del modelo | AUC | Brier (clima: 0,0227) | Huaicos en el 5 % de días con más probabilidad | AP de los mm de 3 días | AP del clima | Mundos nulos con tanto AP |
|---|---|---|---|---|---|---|---|---|
| UKMO 10 km | 597 | **0,621** | 0,961 | 0,0138 | **11 de 14** | 0,541 | 0,041 | 0 de 2 000 |
| JMA GSM | 597 | 0,380 | 0,898 | 0,0188 | 7 de 14 | 0,162 | 0,041 | 0 de 2 000 |
| GFS | 584 | 0,396 | 0,943 | 0,0179 | 8 de 14 | 0,368 | 0,041 | 0 de 2 000 |

La base es 0,024 (fracción de días con huaico). El modelo con UKMO **iguala al techo**: con la lluvia observada de PISCOp, en los mismos 12 días hasta 2025, el AP es 0,637 y con el pronóstico 0,637 (fracción 1,00). Con JMA es 0,74 del techo (0,469 contra 0,637) y con GFS 0,69.

### 4.2 Qué pasa al subir el lead (JMA, 4 temporadas, 14 huaicos)

| Lead | AP | AUC | Huaicos en el 5 % | Mundos nulos con tanto AP | Fracción del techo |
|---|---|---|---|---|---|
| 0 | 0,380 | 0,898 | 7 | 0,001 | 0,74 |
| 1 | 0,089 | 0,822 | 4 | 0,011 | 0,25 |
| 2 | 0,048 | 0,741 | 0 | 0,082 | 0,12 |
| 3 | 0,055 | 0,759 | 0 | 0,052 | 0,12 |

Con lead 2 y 3 el modelo ya no se distingue de los mundos nulos al 95 %. Con GFS (4 huaicos) y IFS (3 a 4 huaicos) los leads 1 a 3 dan AP entre 0,07 y 0,15, también sobre pocos eventos; con UKMO (2 a 3 huaicos) no hay resultado utilizable.

### 4.3 Calibración (lead 0)

| Probabilidad | UKMO: días | UKMO: con huaico | UKMO: observado | UKMO: predicho medio |
|---|---|---|---|---|
| 0 a 2 % | 475 | 1 | 0,2 % | 0,5 % |
| 2 a 10 % | 86 | 2 | 2,3 % | 4,4 % |
| 10 a 25 % | 23 | 3 | 13 % | 15 % |
| 25 % o más | 13 | 8 | 62 % (IC 80 %: 44 a 77) | 59 % |

Razón observado / predicho: 0,82 (UKMO), 0,83 (JMA), 1,02 (GFS). Un «MOS ligero» (recalibrar con Platt, temporada por temporada) **empeora** el Brier y el AP en los tres (UKMO: Brier 0,0138 → 0,0158, AP 0,621 → 0,489): con 3 a 4 temporadas y 12 a 14 huaicos no hay base para una segunda capa.

### 4.4 Potencia: qué se detecta con ~14 huaicos

- Contra el azar sí: con lead 0 los tres modelos superan a los mundos nulos (p ≤ 0,001).
- Contra «ordenar por los mm de 3 días del pronóstico» casi nada es detectable. Intervalo del 80 % (bloques de 14 días) de la diferencia de AP: UKMO −0,12 a +0,14; GFS −0,02 a +0,09; solo **JMA lead 0 (+0,025 a +0,27) es claramente mejor que sus propios mm**. H-C se sostiene solo ahí.
- El intervalo del AP en sí es ancho: UKMO lead 0, 0,30 a 0,77.
- Para ver una diferencia de AP de 0,1 entre dos modelos harían falta bastantes más huaicos que los 14 disponibles.

### 4.5 Robustez

- **Sin la temporada 2022-23** (10 de los 14 huaicos; quedan 4): el AP baja a 0,29 (UKMO), 0,08 (JMA) y 0,33 (GFS). Con 4 huaicos esas cifras son orientativas.
- **Modelo compacto** (9 entradas fijadas antes): AP 0,525 (UKMO), 0,264 (JMA), 0,306 (GFS), algo peor que el completo; con tan pocos eventos tampoco se distingue.
- **Un día de ejemplo.** Con el pronóstico de UKMO, el 12 y el 14 de marzo de 2023 (días de huaico) el modelo da 0,84 y 0,85; el 20 de marzo de 2023, 0,11; el 15 de enero de 2024, 0,005.

### 4.6 Por quebrada: P(día) × participación

La participación `π_i` se aprende con los datos hasta abril de 2022. En las temporadas de prueba hay 9 días con huaico con al menos una quebrada ubicada (16 activaciones por quebrada, 20 quebradas con nombre).

| Pronóstico | AP del producto | AP de solo el día | AP de solo la quebrada | AUC del producto | Activaciones en el top 5 de `π` |
|---|---|---|---|---|---|
| UKMO lead 0 | 0,041 | 0,038 | 0,002 | 0,953 | 5 de 16 |
| JMA lead 0 | 0,053 | 0,054 | 0,002 | 0,918 | 5 de 16 |
| GFS lead 0 | 0,044 | 0,033 | 0,002 | 0,949 | 5 de 16 |
| JMA lead 1 | 0,007 | 0,006 | 0,002 | 0,850 | 5 de 16 |

La base por par es 0,001. El producto no aporta nada medible sobre «solo el día», y el top 5 de participación (Corrales, La Ronda, Los Laureles, Pedregal, Quirio) captura 5 de 16 activaciones, contra 4 esperadas al azar. **La parte «qué quebrada» no se confirma en este período**: sigue siendo un reparto por exposición.

## 5. Lectura

- **Con lead 0 la probabilidad con pronóstico funciona** y es consistente con el techo: el pronóstico más fino (UKMO 10 km) no pierde nada medible; los más gruesos (GFS, JMA) pierden entre el 26 y el 31 %. H-A se cumple con UKMO (1,00) y JMA (0,74) y roza el límite con GFS (0,69).
- **Se pierde rápido con el lead.** JMA cae de 0,38 a 0,05 de AP en tres días. Con la precisión de lluvia de un modelo global, el día del huaico solo se anuncia con el pronóstico del propio día; un día antes ya queda a un cuarto del techo y desde dos días no se distingue del azar. H-B se cumple.
- **El modelo no hace más que ordenar bien los días** en casi todos los casos: contra los mm crudos de 3 días solo gana de forma clara en JMA lead 0. La ventaja del modelo está en dar una probabilidad calibrada, no en acertar más días.
- **La calibración sirve en lead 0** (la banda del 25 % o más: observado 62 % con 59 % predicho) y empeora con cualquier capa extra.
- **Lo que esto no demuestra**: que sirva para pronosticar a futuro con lead 1 a 3 (hay 2 a 4 huaicos con la mayoría de archivos), ni por quebrada.

## 6. Límites

- 12 a 14 días con huaico y 3 a 4 temporadas: las cifras son orientativas y los intervalos amplios (ver §4.4). Sin la temporada 2022-23 todo lo medido se apoya en 4 huaicos.
- El catálogo solo trae huaicos reportados: lo que no se reportó cuenta como «no hubo». Los falsos positivos son un máximo.
- `lead 0` no es un pronóstico emitido el día anterior: es la salida más reciente del modelo para esa hora, y puede incorporar parte del día.
- La lluvia pronosticada es el promedio de 6 celdas del valle, no de una quebrada. Un pronóstico de 10 a 55 km no resuelve una quebrada de 1 a 10 km².
- PISCOp termina en diciembre de 2025: el techo no existe para 2026. La temporada 2025-26 se mide solo con el pronóstico y con el ajuste de cuantiles hecho antes (fuera de tiempo).
- Las probabilidades heredan el sesgo de reporte del catálogo (capítulo 15).

## 7. Reproducir

```bash
uv run descargar-datos --solo pronosticos-previous-runs   # una vez; 16 peticiones con pausa
uv run --extra notebooks jupyter lab notebooks/13-backtest-con-pronostico.ipynb
```

Con PyTorch (`--extra gpu`) los mundos nulos y los bootstraps corren en GPU; sin ella corren en CPU.
