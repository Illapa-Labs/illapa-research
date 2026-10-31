# 24 · Banco de modelos: ¿un modelo más flexible mejora la probabilidad del día?

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Compara familias de modelos para la probabilidad de un día con huaico catalogado en la zona. Ante una emergencia llama al 115 (INDECI).

Código: [`src/illapa_research/banco_modelos.py`](../src/illapa_research/banco_modelos.py), con pruebas en `tests/test_banco_modelos.py`. Se ejecuta con `uv run python -m illapa_research.banco_modelos` (unos 2 minutos en la PC remota con GPU). Resultados: `catalogo/banco_modelos.csv` y `catalogo/banco_modelos_diferencias.csv`.

## 1. Pregunta

El capítulo 05 usa una regresión logística con penalización L2. Con unos 120 días positivos en 43 temporadas, ¿un modelo más flexible (árboles con restricciones, red recurrente, conjunto) predice mejor, dejando una temporada fuera?

## 2. Modelos (misma validación, mismas variables, mismas etiquetas)

| Modelo | Qué es |
|---|---|
| `logistica` | Regresión logística ridge con C = 0,03 fijo, ajustada en la GPU (`gpu.ajustar_logit_lote`). |
| `boosting_monotono` | Gradient boosting con árboles de hasta 6 hojas, L2 = 10, 120 iteraciones, y restricción monótona: más lluvia, humedad del suelo o caudal nunca bajan la probabilidad. |
| `gru` | Red recurrente pequeña (GRU de 32 unidades, dropout 0,3, AdamW, 25 épocas) sobre los últimos 14 días de las mismas variables. La lluvia del día entra con rezago 0 y las demás con un día de retraso, igual que en el capítulo 05. Promedio de 3 semillas. |
| `conjunto` | Promedio de las tres probabilidades. |

La diferencia de AP contra la logística se calcula pareada, con remuestreo de temporadas completas (90 %).

## 3. Resultados (123 días con huaico, 6 473 días de temporada)

| Modelo | AP | AUC | Brier skill | Aciertos con 5 % de días | con 10 % |
|---|---|---|---|---|---|
| Logística | 0,299 | 0,903 | 0,155 | 0,54 | 0,69 |
| Boosting monótono | 0,260 | 0,850 | 0,110 | 0,46 | 0,57 |
| GRU | 0,219 | 0,868 | 0,090 | 0,47 | 0,64 |
| Conjunto | 0,305 | 0,898 | 0,149 | 0,52 | 0,68 |

Diferencia de AP contra la logística:

| Modelo | Diferencia (90 %) | ¿Excluye el cero? |
|---|---|---|
| Boosting monótono | −0,039 (−0,111 a +0,055) | No |
| GRU | **−0,080 (−0,124 a −0,021)** | **Sí, peor** |
| Conjunto | +0,006 (−0,020 a +0,034) | No |

## 4. Lectura

- **La regresión logística regularizada sigue siendo el modelo a batir.** Ni los árboles con restricciones ni la red recurrente la mejoran; la GRU es peor de forma demostrable.
- **El conjunto no ayuda de forma medible** (+0,006, dentro del ruido): los modelos más débiles no aportan información complementaria.
- Es el resultado esperable con 123 positivos concentrados en pocas temporadas: más parámetros significan más ajuste a los racimos de 1983, 1998, 2017 y 2023.

## 5. Límites

- La GRU y el boosting se probaron con una sola configuración fijada de antemano; no se afinaron los hiperparámetros, porque hacerlo con tan pocos eventos sería ajustar a la validación. Una búsqueda más amplia podría acercarlos, pero hay poco espacio por encima de la logística.
- Un modelo profundo tendría sentido con más datos: la ruta es entrenar de forma conjunta con otras zonas del país (huaicos y deslizamientos del SINPAD por distrito), no una arquitectura más grande con las mismas fechas.
- No se calcularon mundos nulos para la GRU y el boosting; la pregunta aquí es cuál ordena mejor, no si supera el azar (la logística ya lo hace con p = 0,0005, capítulo 05).
- Las cifras dependen del catálogo de esta corrida (152 fechas); cambian en la tercera cifra cuando se añaden fechas.
