# 15 · Ficha de probabilidad

> **No es una alerta ni una predicción para decidir evacuaciones.** Es la frecuencia histórica de días con huaico *catalogado* bajo condiciones parecidas. Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/12-ficha-de-probabilidad.ipynb`](../notebooks/12-ficha-de-probabilidad.ipynb). Código: `src/illapa_research/probabilidad.py` (pruebas en `tests/test_probabilidad.py`). Tablas: `catalogo/probabilidad_*.csv`.

## 1. Pregunta y evento

Dadas las condiciones de un día (lluvia, suelo, caudal, mar, calor en altura, humedad, régimen El Niño), ¿con qué probabilidad es un **día con huaico catalogado** en Chosica, Chaclacayo, Santa Eulalia o Ricardo Palma? ¿Cuánta confianza merece esa cifra, qué condiciones empujan hacia arriba y qué quebradas suelen aparecer?

El evento es exactamente ese: un día de temporada de lluvias (diciembre a abril, 1984-2026) que figura en el catálogo con día exacto y confianza no baja. **No** es peligro absoluto, ni probabilidad anual, ni la de una quebrada en particular. Lo no registrado (1999-2008, quebradas sin gente, eventos sin daños) cuenta como «no huaico». Eso va, en estas palabras, en la salida de la ficha.

## 2. Datos

ERA5 en 6 puntos (3 por la API de Open-Meteo y 3 de sus archivos en AWS, capítulo 13), temperatura del mar NOAA OISST, caudal GloFAS, ICEN oficial (IGP/ENFEN) y el catálogo de 148 fechas. Muestra: 6 473 días de temporada, **119 con huaico**, 43 temporadas, 118 columnas (las del capítulo 05, «+Niño»). Corrida del 30 de octubre de 2026.

## 3. Pre-registro y resultado de cada hipótesis

Las decisiones y las hipótesis se escribieron en el notebook antes de mirar ningún puntaje. Todo es fuera de muestra: se deja fuera una temporada entera (43 pliegues); la penalización C se elige dentro de cada entrenamiento con 4 pliegues internos; la recalibración (Platt) usa solo los logits fuera de muestra de las otras temporadas.

| | Hipótesis | Resultado |
|---|---|---|
| P1 | Un modelo reducido (2 columnas por familia, elegidas dentro de cada entrenamiento) no es peor que el completo | **No.** Log-loss 0,0725 contra 0,0646; Brier 0,0166 contra 0,0154; precisión media 0,17 contra 0,28. Modelo principal: el **completo** (ridge, C = 0,03 en 40 de 43 pliegues; usa 117 de 118 columnas) |
| P2 | La recalibración mejora la fiabilidad | **No.** El ridge ya sale calibrado: Platt da a = 0,023 y b = 0,978 (casi la identidad) y el log-loss pasa de 0,0637 a 0,0646. Se conserva por el pre-registro, sin efecto práctico |
| P3 | Un ajuste de régimen (ICEN causal ≥ 0,4) corrige el desbalance Niño / no Niño | **No.** Empeora el log-loss 0,27 % y no mueve las razones (1,22 y 0,67 pasan a 1,21 y 0,68). No se adopta |
| P4 | Sigue calibrada por era y sin los grandes racimos | **Solo en conjunto.** Razón observado/predicho 1,009 en total, pero 0,85 (1984-1998), 0,69 (1999-2008) y 1,28 (2009-2026). Reentrenando sin 1983, 1998 y 2017: precisión media 0,155 (12 veces la base), AUC 0,873, razón 1,00 |
| P5 | Las familias que más empujan son estables | **Sí.** En el 93 % a 100 % de los 500 modelos remuestreados |
| P6 | `P(día) × π_quebrada` ordena mejor los pares que solo el día | **Sí, poco.** Precisión media 0,029 contra 0,020 (+51 %), AUC 0,923 contra 0,920; solo la quebrada: 0,0012 |

## 4. Calibración y poder de resolución

Globalmente (probabilidades fuera de muestra): Brier 0,0154 (habilidad 0,14 frente a la climatología por mes), log-loss 0,0646, precisión media 0,278 (base 0,018), AUC 0,900.

**Por banda fija**, con intervalo del 80 % que remuestrea temporadas enteras:

| Banda | Días | Con huaico | Fracción observada | IC 80 % | Probabilidad media |
|---|---|---|---|---|---|
| 0 a 0,5 % | 3 679 | 7 | 0,2 % | 0,1 a 0,3 % | 0,2 % |
| 0,5 a 1 % | 937 | 8 | 0,9 % | 0,4 a 1,3 % | 0,7 % |
| 1 a 2 % | 716 | 10 | 1,4 % | 0,8 a 2,1 % | 1,4 % |
| 2 a 5 % | 616 | 17 | 2,8 % | 2,0 a 3,6 % | 3,2 % |
| 5 a 10 % | 280 | 24 | 8,6 % | 5,8 a 11,1 % | 7,0 % |
| 10 a 25 % | 175 | 28 | 16,0 % | 9,9 a 21,4 % | 14,9 % |
| 25 % o más | 70 | 25 | 35,7 % | 23,7 a 46,9 % | 42,1 % |

La probabilidad separa bien: el 3 % de los días (la banda más alta) contiene el 21 % de los días con huaico; la banda más baja (57 % de los días) contiene el 6 %. La banda más alta sobreestima algo (42 % predicho, 36 % observado, con intervalo amplio).

**Lo que no está calibrado.**
- **Por régimen.** En temporadas Niño el modelo subestima (observado/predicho 1,22) y en no Niño sobreestima (0,67).
- **Por era.** La causa parece ser la cobertura del catálogo, no el Niño: antes de 2009 hay menos fechas por día de lluvia extrema (capítulo 07). Un calibrador *exploratorio* ajustado solo con 2009 en adelante lleva la razón de 1,28 a 1,03 en esos años, pero no mejora Brier ni log-loss (0,0187 contra 0,0184; 0,0734 contra 0,0728). En días de hoy, las probabilidades de este capítulo probablemente son bajas, del orden de un 25 % a 30 %.
- **Racimos.** En 2017 hubo 23 días con huaico y el modelo esperaba 12,3.

## 5. Qué empuja hacia arriba

Aporte medio por familia en escala logit, respecto a un día promedio de temporada (diferencia entre días con huaico y los demás) y estabilidad entre los 500 modelos remuestreados:

| Familia | Diferencia | Estabilidad |
|---|---|---|
| Lluvia del día | +1,79 | 100 % |
| Temperatura del mar | +0,57 | 100 % |
| Lluvia de los días previos | +0,42 | 99,6 % |
| Humedad y nubes | +0,36 | 99,8 % |
| Caudal de los ríos | +0,30 | 97,8 % |
| Temperatura en altura | +0,24 | 99,4 % |
| Humedad del suelo | +0,22 | 99,6 % |
| Régimen El Niño (ICEN) | +0,14 | 93,2 % |

La lluvia del día manda (y es la condición de la que menos aviso previo hay). Las demás son un fondo favorable: mar cálido, suelo húmedo, lluvia reciente, caudal alto. «Temperatura en altura» no es calor previo: en los días con huaico aparece *fría y nublada* (capítulo 04).

En cada ficha se listan las 5 condiciones que más empujan, en lenguaje claro y con su percentil: por ejemplo «pico horario de lluvia en Chosica: percentil 100 de los días de temporada» o «temperatura en Santa Eulalia alta (valor de ayer): percentil 3». Son asociaciones con el catálogo, no causas, y sin semáforo ni colores oficiales.

## 6. Intervalos

Cada remuestreo de temporadas reajusta el modelo; el intervalo del 80 % de un día pasado usa solo los remuestreos que no vieron su temporada. En días con huaico la probabilidad mediana es 0,089 (10 a 90 %: 0,009 a 0,50) y el ancho mediano del intervalo, 0,116; en los demás días, 0,0035 y 0,0047. Es decir, el intervalo es del orden de la propia probabilidad (ancho relativo mediano 1,2 a 1,4): **una probabilidad de 9 % debe leerse como «entre 4 % y 17 %»**, no como 9 %.

## 7. Por quebrada

`P(quebrada i el día t) = P(día t) × π_i`, con `π_i` la participación histórica de la quebrada en los días con huaico ubicados (Beta, 10-90 %), en temporadas Niño o en las demás. Participación (todas las temporadas): Pedregal 0,31, Quirio 0,29, Los Laureles 0,27, Chacrasana 0,18, Corrales 0,16, La Ronda, Carossio y Huáscarán 0,14. `π_i` sigue la exposición y el reporte (capítulo 03), no solo el terreno. Con menos de 3 días de historial ubicado la ficha marca `evidencia: solo reparto genérico`; las cuencas sin historial no se estiman. Validación dejando una temporada fuera: ver P6.

## 8. Retrospectiva

Probabilidades fuera de muestra, con el intervalo fuera de bolsa.
- **Días con huaico más probables:** 2017-03-16 (0,98), 2017-03-17 (0,90), 1985-02-25 (0,79), 2015-03-21 (0,78).
- **Días con huaico menos probables:** 2000-01-02 (0,0009), 2012-01-05 (0,0015), 1993-01-25 (0,003): eventos con poca lluvia en los datos de reanálisis o catalogados con fecha dudosa.
- **Días sin huaico con probabilidad alta:** 2019-02-09 (0,62), 1998-02-10 (0,60), 1989-02-11 (0,59), 2008-04-03 (0,59): los falsos positivos del capítulo 07, que no se pudieron verificar en prensa.
- **Temporadas tipo.** 2017 (Niño costero): 151 días, 23 con huaico, 12,3 esperados, probabilidad máxima 0,98, mediana 0,022. 2016 (Niño casi sin huaicos): 2 con huaico, 2,6 esperados, máxima 0,17. 2018 (sin Niño): 0 con huaico, 1,1 esperados, máxima 0,16.

## 9. La ficha (API)

```python
from illapa_research import probabilidad as pr
R = pr.correr(".")                      # ajusta todo (≈ 15 s en GPU; unos minutos en CPU)
ficha = pr.ficha(R["modelo"], R["X"].loc["2017-03-16"])
```
Devuelve: `probabilidad`, `intervalo_80`, `banda_de_fiabilidad` (cuántos días históricos cayeron en esa banda y cuántos tuvieron huaico), `factores_favorables`, `quebradas` (con `evidencia`), `regimen_nino`, el `evento` definido y el texto de `limites`. Para una fecha pasada la ficha del modelo final es «dentro de muestra» (sale más alta que fuera de muestra: 0,997 contra 0,982 el 16 de marzo de 2017); para ver lo honesto de una fecha pasada usa `pr.retrospectiva`.

## 10. Qué NO garantiza

- Es la frecuencia de días **en el catálogo**; no mide huaicos no registrados.
- Con 119 positivos y 43 temporadas los intervalos son anchos y las bandas altas tienen pocos días; sin 1983, 1998 y 2017 la habilidad baja (AP 0,155).
- El modelo usa 117 de 118 columnas con 119 positivos: sobreajuste posible; la validación (temporada fuera, C elegida dentro) es la única medida honesta, y el reducido, que se pre-registró para limitarlo, rindió peor.
- Calibración desigual por era y por régimen (§4).
- Las probabilidades por quebrada heredan el sesgo de reporte y solo existen para las 20 con historial ubicado.
- Depende de ERA5 en 6 puntos y del ICEN: un cambio de fuente cambia los números.

## 11. Reproducir

```bash
uv run --extra notebooks --extra gpu jupyter lab notebooks/12-ficha-de-probabilidad.ipynb
```
Con GPU CUDA tarda segundos (los ajustes son lotes de regresiones logísticas); sin GPU, PyTorch en CPU (unos minutos).
