# 21 · ¿Conocer la quebrada agrega algo a conocer el día?

> **No es una alerta ni una predicción para decidir evacuaciones.** Mide cuánto del catálogo se explica con el historial de cada quebrada además del tiempo del día. Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/17-quebradas-y-dia.ipynb`](../notebooks/17-quebradas-y-dia.ipynb). Código: `src/illapa_research/quebradas_dia.py` (pruebas en `tests/test_quebradas_dia.py`). Tablas: `catalogo/quebradas_dia_*.csv`. Es el paso 4 del plan: repite con el catálogo mejorado (150 fechas, 24 quebradas con historial ubicado) lo que los capítulos 06, 17 y 19 midieron con menos datos.

## 1. Pregunta y método

¿Predecir *qué quebrada se activa qué día* mejora si se multiplica la probabilidad del día por la participación histórica de cada quebrada (`π_i`, capítulo 06)?

- **Pares.** (quebrada, día de temporada de lluvias); positivo si la quebrada aparece en el catálogo ese día. Con la lluvia observada: 155 352 pares y 99 positivos (1984-2026). Con GEFS: 70 848 pares y 60 positivos (2000-2019).
- **Modelos.** `solo_dia` = P(día) × participación media de todas las quebradas; `solo_quebrada` = tasa base × π_i; `producto` = P(día) × π_i; `producto_regimen` = P(día) × π_i de las temporadas Niño o no Niño que correspondan.
- **Sin fuga.** La π_i de cada temporada se aprende en las otras temporadas. P(día) es siempre fuera de muestra: el modelo del capítulo 15 con lluvia observada, o las probabilidades GEFS del capítulo 19 a 24, 48 y 72 h.
- **Intervalos.** Diferencia de precisión media con remuestreo de temporadas (90 %).

Teorías (escritas antes de mirar las tablas): Q1 el producto mejora a `solo_dia` con lluvia observada; Q2 también con GEFS; Q3 la participación por régimen mejora al producto; Q4 las 5 quebradas con más historial cubren más que el azar; Q5 nada depende de 2017.

## 2. Resultados (datos del 30 de octubre de 2026)

**Con lluvia observada (ERA5), 1984-2026** (base de pares positivos 0,0006)

| Modelo | Precisión media | AUC |
|---|---|---|
| solo_quebrada | 0,0012 | 0,70 |
| solo_dia | 0,0167 | 0,923 |
| producto_regimen | 0,0261 | 0,931 |
| **producto** | **0,0294** | **0,934** |

- **Q1 se cumple.** `producto` − `solo_dia` = +0,0127, intervalo 90 % de +0,0022 a +0,0251: excluye 0. Sin 2017 sigue siendo positivo (0,0204 contra 0,0128; diferencia +0,0077, de +0,0009 a +0,0228). Desde 2009 la precisión media es 0,0481 contra 0,0273.
- **Q3 no se cumple.** La participación por régimen no mejora (−0,0034, intervalo de −0,0082 a +0,0003): con pocos días por régimen añade ruido.
- **Q4 se cumple.** Las 5 quebradas con más historial (aprendido en las otras temporadas) cubren 44 de 99 activaciones (44,4 %) contra 20,8 % esperado por azar; sin 2017, 35 de 81 (43,2 %). Con empates en la participación (varias quebradas con el mismo historial en el borde del top 5) la cifra se mueve entre 40 y 44 según el desempate; aquí se usa el orden alfabético, igual en toda plataforma.

**Con el pronóstico GEFS, 2000-2019** (60 positivos)

| Plazo | `producto` − `solo_dia` | Intervalo 90 % | Sin 2017 |
|---|---|---|---|
| 24 h | +0,0158 | −0,0001 a +0,0404 | +0,0091 (−0,0006 a +0,0495) |
| 48 h | +0,0101 | −0,0017 a +0,0294 | +0,0014 (−0,0057 a +0,0039) |
| 72 h | +0,0045 | −0,0003 a +0,0114 | +0,0010 (−0,0014 a +0,0026) |

- **Q2 no se cumple.** El producto es mejor en cifras, pero ningún intervalo excluye 0: con este número de eventos no se puede distinguir de «no agrega nada».
- **Q5 se cumple con lluvia observada y no con GEFS.** Con lluvia observada la ventaja sobrevive sin 2017 y sin los tres grandes años (0,0228 contra 0,0146); con GEFS se reduce casi a cero sin 2017.

## 3. Lectura

- **El día sigue mandando.** `solo_dia` ya tiene AUC 0,92; el historial por quebrada lo sube a 0,93 y casi triplica la precisión media de los pares contra no usar el día.
- **El historial de quebradas sí aporta, con lluvia observada.** Saber cuáles se activan más duplica la cobertura del azar y mejora la precisión media entre un 50 % y un 76 % según la ventana. Es una mejora real pero modesta en términos absolutos.
- **Con pronósticos no se puede afirmar.** El orden es el mismo, pero las diferencias no se distinguen del azar.
- **Qué mide y qué no.** `π_i` sigue a la exposición y al reporte (capítulo 03): lo que mejora es predecir **qué quebrada aparece en el catálogo**, no cuál tiene mayor peligro por su terreno.

## 4. Límites

- 24 quebradas con historial ubicado y 99 pares positivos con lluvia observada (60 con GEFS): los intervalos son anchos.
- Las quebradas sin historial ubicado quedan fuera de los pares; no se puede decir nada de ellas.
- El catálogo registra lo reportado, con cobertura muy desigual entre épocas.
- La participación por régimen no se probó con más de 22 temporadas Niño.

## 5. Reproducir

Las cifras de este capítulo salen de una corrida en la PC remota con GPU/CPU (170 pruebas en verde allí), que coincide con una corrida en una Mac salvo por el desempate corregido de la cobertura.

```bash
uv run python -m illapa_research.quebradas_dia   # unos minutos; reentrena el modelo diario
ILLAPA_RECALCULAR=1 uv run jupyter lab notebooks/17-quebradas-y-dia.ipynb
```
