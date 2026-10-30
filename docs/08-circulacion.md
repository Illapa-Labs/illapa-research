# 08 · Circulación de gran escala: ¿viento en altura, convección amazónica y MJO?

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Es un análisis de si la circulación atmosférica de gran escala ayuda a explicar qué días tienen huaico catalogado. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

Notebook: [`notebooks/08-circulacion-de-gran-escala.ipynb`](../notebooks/08-circulacion-de-gran-escala.ipynb). Código: [`src/illapa_research/circulacion.py`](../src/illapa_research/circulacion.py).

## 1. Pregunta e hipótesis (pre-registradas)

Esta sección se escribió y se subió al repositorio **antes de descargar o mirar ninguna de estas variables**. Las cajas, los rezagos y el criterio de éxito no se tocan después.

La literatura de la sierra sur y central del Perú liga las lluvias de verano con el viento del este en 200 hPa (la Alta de Bolivia), con la convección amazónica y con la oscilación de Madden-Julian. Si eso es cierto para los huaicos de Chosica, debería verse en los días previos y debería añadir información sobre lo que ya saben la lluvia local, el suelo, el caudal y el mar.

| | Hipótesis | Variable (promedio de la caja) | Rezagos |
|---|---|---|---|
| T16 | Viento zonal en 200 hPa más del este (u200 más negativo) sobre el Altiplano y los Andes centrales distingue los días con huaico. | `u200_altiplano`: NCEP/NCAR R1, u a 200 hPa, **20°S-12°S, 75°W-65°W**. | 1 a 5 d |
| T17 | La convección amazónica (OLR bajo) y la fase de la MJO modulan la probabilidad. | `olr_amazonia`: NOAA OLR interpolado, **15°S-5°S, 70°W-55°W**; índice **RMM** (BoM: RMM1, RMM2, amplitud, fase) y **OMI** (NOAA PSL: PC1, PC2, amplitud). | 5 a 15 d |
| T18 | El SOI añade algo más allá del mar local. | SOI mensual (CPC/NOAA) del mes anterior, como régimen lento; no es un disparador diario. | mes anterior |
| T19 | El flujo de humedad del este sobre la selva central precede. | `u850_selva`, `v850_selva`, `q850_selva`: NCEP/NCAR R1, u, v y humedad específica a 850 hPa, **14°S-8°S, 72°W-66°W**. | 1 a 5 d |

Las anomalías se calculan contra una climatología suavizada por día del año de 1991-2020 (`predictores.anomalia`). Una variable en un rezago es **señal** si pasa Benjamini-Hochberg (q = 0,10) frente a la nula que desplaza las etiquetas dentro de cada temporada (`senales.rezagos_nula`), con rezago ≥ 1 día; es **robusta** si además mantiene el signo con p < 0,10 en 2009+ y sin 1983, 1998 y 2017 (`senales.robustez`).

**Criterio de éxito para entrar en un modelo** (fijo): al añadir las variables a `lluvia+antecedentes` (`modelo_diario`), la precisión media (AP) fuera de muestra, dejando temporadas fuera, debe subir más que el percentil 95 de la ganancia que dan las mismas columnas con las fechas de huaico desplazadas dentro de cada temporada, y la ganancia debe mantenerse dejando episodios Niño fuera. Si no, se reporta como nulo.

## 2. Datos, licencias y resultados

(Se completan en los siguientes commits, a medida que se descargan y analizan.)
