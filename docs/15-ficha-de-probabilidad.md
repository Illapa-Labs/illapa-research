# 15 · Ficha de probabilidad

> **No es una alerta ni una predicción para decidir evacuaciones.** Es la frecuencia histórica de días con huaico *catalogado* bajo condiciones parecidas. Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/12-ficha-de-probabilidad.ipynb`](../notebooks/12-ficha-de-probabilidad.ipynb). Código: `src/illapa_research/probabilidad.py` (pruebas en `tests/test_probabilidad.py`). Tablas: `catalogo/probabilidad_*.csv`.

## 1. Pregunta y evento

Dadas las condiciones de un día (lluvia, suelo, caudal, mar, calor en altura, humedad, régimen El Niño), ¿con qué probabilidad es un **día con huaico catalogado** en Chosica, Chaclacayo, Santa Eulalia o Ricardo Palma? ¿Cuánta confianza merece esa cifra, qué condiciones empujan hacia arriba y qué quebradas suelen aparecer?

El evento es exactamente ese: un día de temporada de lluvias (diciembre a abril, 1984-2026) que figura en el catálogo con día exacto y confianza no baja. **No** es peligro absoluto, ni probabilidad anual, ni la de una quebrada en particular. Lo no registrado (1999-2008, quebradas sin gente, eventos sin daños) cuenta como «no huaico». Eso va, en estas palabras, en la salida de la ficha.

## 2. Datos

ERA5 en 6 puntos (3 por la API de Open-Meteo y 3 de sus archivos en AWS, capítulo 13), temperatura del mar NOAA OISST, caudal GloFAS, ICEN oficial (IGP/ENFEN) y el catálogo de 150 fechas. Muestra: 6 473 días de temporada, **121 con huaico**, 43 temporadas, 118 columnas (las del capítulo 05, «+Niño»). Corrida del 30 de octubre de 2026.

## 3. Pre-registro y resultado de cada hipótesis

Las decisiones y las hipótesis se escribieron en el notebook antes de mirar ningún puntaje. Todo es fuera de muestra: se deja fuera una temporada entera (43 pliegues); la penalización C se elige dentro de cada entrenamiento con 4 pliegues internos; la recalibración (Platt) usa solo los logits fuera de muestra de las otras temporadas.

| | Hipótesis | Resultado |
|---|---|---|
| P1 | Un modelo reducido (2 columnas por familia, elegidas dentro de cada entrenamiento) no es peor que el completo | **No.** Log-loss 0,0728 contra 0,0652; Brier 0,0167 contra 0,0155; precisión media 0,18 contra 0,29. Modelo principal: el **completo** (ridge, C = 0,03 en 38 de 43 pliegues y 0,01 en 5; usa 117 de 118 columnas) |
| P2 | La recalibración mejora la fiabilidad | **No.** El ridge ya sale calibrado: Platt es casi la identidad y el log-loss pasa de 0,0644 a 0,0652. Se conserva por el pre-registro, sin efecto práctico |
| P3 | Un ajuste de régimen (ICEN causal ≥ 0,4) corrige el desbalance Niño / no Niño | **No.** Empeora el log-loss 0,29 % y no mueve las razones (1,21 y 0,67 pasan a 1,21 y 0,68). No se adopta |
| P4 | Sigue calibrada por era y sin los grandes racimos | **Solo en conjunto.** Razón observado/predicho 1,009 en total, pero 0,85 (1984-1998), 0,70 (1999-2008) y 1,27 (2009-2026). Reentrenando sin 1983, 1998 y 2017: precisión media 0,159 (12 veces la base), AUC 0,873, razón 1,00 |
| P5 | Las familias que más empujan son estables | **Sí.** En el 92 % a 100 % de los 500 modelos remuestreados |
| P6 | `P(día) × π_quebrada` ordena mejor los pares que solo el día | **Sí, poco.** Precisión media 0,031 contra 0,017 (+79 %), AUC 0,931 contra 0,919; solo la quebrada: 0,0012 |

## 4. Calibración y poder de resolución

Globalmente (probabilidades fuera de muestra): Brier 0,0155 (habilidad 0,15 frente a la climatología por mes), log-loss 0,0652, precisión media 0,285 (base 0,019), AUC 0,899.

**Por banda fija**, con intervalo del 80 % que remuestrea temporadas enteras:

| Banda | Días | Con huaico | Fracción observada | IC 80 % | Probabilidad media |
|---|---|---|---|---|---|
| 0 a 0,5 % | 3 669 | 5 | 0,1 % | 0,0 a 0,3 % | 0,2 % |
| 0,5 a 1 % | 945 | 10 | 1,1 % | 0,5 a 1,6 % | 0,7 % |
| 1 a 2 % | 711 | 9 | 1,3 % | 0,8 a 1,8 % | 1,4 % |
| 2 a 5 % | 617 | 20 | 3,2 % | 2,4 a 4,2 % | 3,2 % |
| 5 a 10 % | 279 | 23 | 8,2 % | 5,7 a 10,6 % | 7,0 % |
| 10 a 25 % | 180 | 29 | 16,1 % | 10,5 a 21,4 % | 15,0 % |
| 25 % o más | 72 | 25 | 34,7 % | 23,4 a 45,3 % | 42,1 % |

La probabilidad separa bien: el 1 % de los días (la banda más alta) contiene el 21 % de los días con huaico; la banda más baja (57 % de los días) contiene el 4 %. La banda más alta sobreestima algo (42 % predicho, 35 % observado, con intervalo amplio).

**Lo que no está calibrado.**
- **Por régimen.** En temporadas Niño el modelo subestima (observado/predicho 1,21) y en no Niño sobreestima (0,67).
- **Por era.** La causa parece ser la cobertura del catálogo, no el Niño: antes de 2009 hay menos fechas por día de lluvia extrema (capítulo 07). Un calibrador *exploratorio* ajustado solo con 2009 en adelante lleva la razón de 1,27 a 1,03 en esos años, pero no mejora Brier ni log-loss (0,0187 contra 0,0189; 0,0744 contra 0,0748). En días de hoy, las probabilidades de este capítulo probablemente son bajas, del orden de un 25 % a 30 %.
- **Racimos.** En 2017 hubo 23 días con huaico y el modelo esperaba 12,9.

## 5. Qué empuja hacia arriba

Aporte medio por familia en escala logit, respecto a un día promedio de temporada (diferencia entre días con huaico y los demás) y estabilidad entre los 500 modelos remuestreados:

| Familia | Diferencia | Estabilidad |
|---|---|---|
| Lluvia del día | +1,76 | 100 % |
| Temperatura del mar | +0,58 | 100 % |
| Lluvia de los días previos | +0,44 | 100 % |
| Humedad y nubes | +0,36 | 99,8 % |
| Caudal de los ríos | +0,31 | 97,8 % |
| Temperatura en altura | +0,27 | 99,6 % |
| Humedad del suelo | +0,21 | 99,0 % |
| Régimen El Niño (ICEN) | +0,13 | 91,8 % |

La lluvia del día manda (y es la condición de la que menos aviso previo hay). Las demás son un fondo favorable: mar cálido, suelo húmedo, lluvia reciente, caudal alto. «Temperatura en altura» no es calor previo: en los días con huaico aparece *fría y nublada* (capítulo 04).

En cada ficha se listan las 5 condiciones que más empujan, en lenguaje claro y con su percentil: por ejemplo «pico horario de lluvia en Chosica: percentil 100 de los días de temporada» o «temperatura en Santa Eulalia alta (valor de ayer): percentil 3». Son asociaciones con el catálogo, no causas, y sin semáforo ni colores oficiales.

## 6. Intervalos

Cada remuestreo de temporadas reajusta el modelo; el intervalo del 80 % de un día pasado usa solo los remuestreos que no vieron su temporada. El intervalo es del orden de la propia probabilidad: el 9 de febrero de 2019 la probabilidad fuera de muestra es 0,58 con intervalo de 0,19 a 0,76, y el 17 de marzo de 2017, 0,91 con 0,74 a 0,98. **Una probabilidad de 0,58 debe leerse como «entre 0,19 y 0,76»**, no como un número exacto.

## 7. Por quebrada

`P(quebrada i el día t) = P(día t) × π_i`, con `π_i` la participación histórica de la quebrada en los días con huaico ubicados (Beta, 10-90 %), en temporadas Niño o en las demás. Participación (todas las temporadas): Pedregal 0,31, Quirio 0,29, Los Laureles 0,27, Chacrasana 0,18, Corrales 0,16, La Ronda, Carossio y Huáscarán 0,14. `π_i` sigue la exposición y el reporte (capítulo 03), no solo el terreno. Con menos de 3 días de historial ubicado la ficha marca `evidencia: solo reparto genérico`; las cuencas sin historial no se estiman. Validación dejando una temporada fuera: ver P6.

## 8. Retrospectiva

Probabilidades fuera de muestra, con el intervalo fuera de bolsa.
- **Días con huaico más probables:** 2017-03-16 (0,98), 2017-03-17 (0,91), 2017-03-15 (0,81), 1985-02-25 (0,78).
- **Días con huaico menos probables:** 2000-01-02 (0,0008), 2012-01-05 (0,0013), 1993-01-25 (0,0033): eventos con poca lluvia en los datos de reanálisis o catalogados con fecha dudosa.
- **Días sin huaico con probabilidad alta:** 1998-02-10 (0,61), 1989-02-11 (0,61), 2008-04-03 (0,59), 2025-02-13 (0,59), 2019-02-09 (0,58): casi los mismos falsos positivos del capítulo 07, que no se pudieron verificar en prensa.
- **Temporadas tipo.** 2017 (Niño costero): 151 días, 23 con huaico, 12,9 esperados, probabilidad máxima 0,98, mediana 0,022. 2016 (Niño casi sin huaicos): 2 con huaico, 2,7 esperados, máxima 0,18. 2018 (sin Niño): 0 con huaico, 1,1 esperados, máxima 0,17.

## 9. La ficha (API)

```python
from illapa_research import probabilidad as pr
R = pr.correr(".")                      # ajusta todo (≈ 15 s en GPU; unos minutos en CPU)
ficha = pr.ficha(R["modelo"], R["X"].loc["2017-03-16"])
```
Devuelve: `probabilidad`, `intervalo_80`, `banda_de_fiabilidad` (cuántos días históricos cayeron en esa banda y cuántos tuvieron huaico), `factores_favorables`, `quebradas` (con `evidencia`), `regimen_nino`, el `evento` definido y el texto de `limites`. Para una fecha pasada la ficha del modelo final es «dentro de muestra» (sale más alta que fuera de muestra: 0,996 contra 0,981 el 16 de marzo de 2017); para ver lo honesto de una fecha pasada usa `pr.retrospectiva`.

## 10. Qué NO garantiza

- Es la frecuencia de días **en el catálogo**; no mide huaicos no registrados.
- Con 121 positivos y 43 temporadas los intervalos son anchos y las bandas altas tienen pocos días; sin 1983, 1998 y 2017 la habilidad baja (AP 0,159).
- El modelo usa 117 de 118 columnas con 121 positivos: sobreajuste posible; la validación (temporada fuera, C elegida dentro) es la única medida honesta, y el reducido, que se pre-registró para limitarlo, rindió peor.
- Calibración desigual por era y por régimen (§4).
- Las probabilidades por quebrada heredan el sesgo de reporte y solo existen para las cuencas con historial ubicado (24).
- Depende de ERA5 en 6 puntos y del ICEN: un cambio de fuente cambia los números.

## 11. Reproducir

```bash
uv run --extra notebooks --extra gpu jupyter lab notebooks/12-ficha-de-probabilidad.ipynb
```
Con GPU CUDA tarda segundos (los ajustes son lotes de regresiones logísticas); sin GPU, PyTorch en CPU (unos minutos).
