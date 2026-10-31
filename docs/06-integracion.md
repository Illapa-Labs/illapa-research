# 06 · Juntar el día y la quebrada

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/06-dia-y-quebrada.ipynb`](../notebooks/06-dia-y-quebrada.ipynb). Código: `src/illapa_research/integracion.py` (con pruebas en `tests/test_integracion.py`), `modelo_diario.py` y `filtro.py`.

## 1. Pregunta

El capítulo 05 estima si un día tiene condiciones para un huaico en la zona; el capítulo 03 dice qué quebradas aparecen cuando lo hay. ¿Juntarlos mejora la respuesta a «qué quebrada se activa qué día»?

Teorías (escritas antes de mirar):
- **T9** el producto `P(día) × π_i` predice mejor los pares (quebrada, día) que cada parte sola.
- **T10** la participación `π_i` cambia en temporadas Niño: hay más quebradas activas por día con huaico.
- **T11** el resultado no depende de los tres grandes racimos (1983, 1998, 2017).

## 2. Método

- `P(día)`: probabilidad fuera de muestra del modelo `lluvia+antecedentes` (capítulo 05), dejando fuera una temporada cada vez.
- `π_i`: fracción de los días con huaico ubicados en que aparece la quebrada i, con prior Beta(½, ½), aprendida **sin la temporada retenida**. Se calcula para todas las temporadas y separando Niño de las demás.
- Se comparan, sobre todos los pares (24 quebradas con historial ubicado × días de temporada de lluvias 1984+): `dia_y_quebrada = P(día)·π_i`, `solo_dia = P(día)·mean(π)`, `solo_quebrada = tasa base·π_i`. Métricas: precisión media (AP) contra la base, AUC y log-loss.

## 3. Resultados (corrida del 30 de octubre de 2026 sobre el commit `ddc70f0`; ERA5 en los 6 puntos: 3 por la API de Open-Meteo y 3 de sus archivos en AWS, capítulo 13)

- **T9, parcial.** AP del producto 0,029, de solo el día 0,017 y de solo la quebrada 0,0012, contra una base de 0,0006 (el producto es 46 veces la base). AUC 0,934, 0,923 y 0,702. La parte «quebrada» agrega poco (+76 % de AP, AUC casi igual); la parte «día» hace casi todo el trabajo. Sin la parte «día», la quebrada sola apenas supera al azar.
- **T10, sí.** En los 38 días con huaico ubicados en temporadas Niño aparecen en promedio 2,5 quebradas (mediana 2, máximo 7); en los 8 días de temporadas sin Niño, 1,5 (máximo 3). Pocos días sin Niño: no se pueden hacer comparaciones finas.
- **T11, se mantiene.** Sin 1983, 1998 y 2017: AP 0,0228 (producto), 0,0146 (solo día) y 0,0008 (solo quebrada); la ventaja del producto se reduce a +56 %.
- **Participación por quebrada** (todas las temporadas): Pedregal 0,31, Quirio 0,29, Los Laureles 0,27, Chacrasana 0,18, Corrales 0,16, Carossio, Huáscarán y La Ronda 0,14. Las de menos de 0,05 (Vallecito, Huampaní, Barba Blanca, y Carapongo, Cobián, La Laguna, Santa Inés y Señor de los Milagros sin ningún día) casi no aparecen: puede ser que casi no se activen o que casi nadie lo reporte.

## 4. Lectura y límites

- Qué día hay huaico lo explica el tiempo; qué quebrada lo explica sobre todo la presencia de gente que reporta (capítulo 03). El producto no es una probabilidad por quebrada: es un reparto.
- Con 24 quebradas con historial y 46 días con huaico ubicados, los intervalos de `π_i` son anchos (Beta 10-90 %, en el CSV del notebook).
- Modelo diario de base con ERA5 completo: AP 0,289 y 53 % de los días con huaico dentro del 5 % de días en alarma (capítulo 05).

## 5. Reproducir

```bash
uv run --extra notebooks jupyter lab notebooks/06-dia-y-quebrada.ipynb
```
