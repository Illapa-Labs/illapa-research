# 20 · Análogos: los días más parecidos

> **No es una alerta ni una predicción para decidir evacuaciones.** Es una prueba de si buscar en el historial los días más parecidos mejora al modelo logístico. Ante una emergencia llama al 115 (INDECI).

Código: `src/illapa_research/analogos.py` (pruebas en `tests/test_analogos.py`). Corrido en la GPU del Mac (MPS), no en la PC remota.

## 1. Pregunta

Lguensat et al. (2017, *Monthly Weather Review*, «The Analog Data Assimilation») pronostican con los K vecinos más cercanos de un catálogo, ponderados por un kernel gaussiano, en tres variantes: localmente constante (Nadaraya–Watson), incremental y localmente lineal (regresión ponderada sobre los vecinos). Advierten dos cosas que respetamos: los análogos solo sirven en espacios de baja dimensión (dimensión intrínseca menor que unos 10; con 118 columnas no hay vecinos cercanos) y los extremos caen fuera de la envolvente de sus vecinos, donde conviene la variante lineal.

**Pregunta:** con pocas variables, ¿los K días más parecidos estiman mejor «hoy habrá huaico» que la regresión logística L2 (capítulo 05), validando dejando una temporada fuera?

## 2. Método

- **Variables.** Tres conjuntos de la selección parsimoniosa del capítulo 05: 11 variables (`SELECCION_PARSIMONIOSA`), 6 y 3 (lluvia de 1 y 3 días, suelo, lluvia previa de 7 días, caudal, ICEN).
- **Distancia.** Puntajes normales de cada columna (ranking dentro de las temporadas de entrenamiento; la lluvia es muy asimétrica) y distancia euclidiana. Los faltantes valen 0. El ancho del kernel sigue la densidad local: `exp(-d² / (h · media de d² de los K vecinos))`.
- **Estimadores.** Constante (fracción ponderada de huaicos entre los vecinos, encogida hacia la tasa base con fuerza 1) y lineal (mínimos cuadrados ponderados con penalización ridge en las pendientes; el intercepto es la estimación; se recorta a [0, 1]).
- **Sin fuga.** Dejando una temporada fuera; K, ancho y ridge se eligen **dentro** de cada conjunto de entrenamiento con otra validación por temporada. Rejillas: constante K ∈ {60, 240, 480, 960} × ancho {1, 2, 4, 8}; lineal K ∈ {240, 480, 960} × ancho {2, 4, 8} × ridge {0,05; 0,3}. La primera corrida usó rejillas más chicas y la configuración elegida caía en el borde; se ampliaron y se repitió (ambas se informan abajo en lo que cambió).
- **Mundos nulos.** 2 000 mundos con las etiquetas desplazadas dentro de cada temporada, igual que en el capítulo 12, con la configuración más elegida para las etiquetas reales. Los vecinos y coeficientes no dependen de las etiquetas, así que cada mundo es un `gather` (ambas variantes son suavizadores lineales de las etiquetas de entrenamiento). Una prueba lo comprueba contra el camino directo.
- **Comparación.** Regresión logística L2 con C = 0,03 fijo, mismas variables, mismos pliegues y mismos mundos (`gpu.ap_real_y_nulas`). Ojo: esta línea base no elige C dentro del entrenamiento, así que su ventaja no viene de un ajuste más fino.

## 3. Resultados (6 473 días de temporada, 121 días con huaico, 43 temporadas, base 0,019)

| Variables | Modelo | AP | AUC | Huaicos en el 5 % de días con más probabilidad | AP de la nula (p95) |
|---|---|---|---|---|---|
| 11 | Logística L2 | **0,240** | **0,893** | 50 % | 0,061 |
| 11 | Análogos, lineal | 0,201 | 0,879 | 46 % | 0,047 |
| 11 | Análogos, constante | 0,191 | 0,849 | 41 % | 0,030 |
| 6 | Logística L2 | **0,130** | 0,861 | 40 % | 0,056 |
| 6 | Análogos, lineal | 0,100 | 0,864 | 33 % | 0,042 |
| 6 | Análogos, constante | 0,096 | 0,851 | 35 % | 0,033 |
| 3 | Logística L2 | 0,105 | 0,810 | 31 % | 0,022 |
| 3 | Análogos, lineal | **0,109** | 0,804 | 33 % | 0,032 |
| 3 | Análogos, constante | 0,088 | 0,785 | 32 % | 0,026 |

Los 2 000 mundos nulos no alcanzan al valor real en ninguna fila (p = 0,0005, el mínimo posible). Medias de AP de las nulas: 0,02 a 0,03.

Con la rejilla chica, el modelo lineal de 11 variables daba 0,168 y el constante 0,188; ampliarla subió el lineal a 0,201.

## 4. Qué se aprende

1. **Los análogos tienen señal real pero no superan a la logística.** Con 11 y 6 variables la logística gana (0,240 contra 0,201 y 0,130 contra 0,100); con 3 variables empatan (0,105 contra 0,109, dentro del ruido de 121 positivos).
2. **Piden vecindarios enormes.** La configuración elegida tiende al borde: K = 960 (de 6 300 días de entrenamiento) y ancho 8 en el lineal. Es decir, el método converge hacia una regresión casi global: el historial local no aporta estructura más allá de la tendencia suave que ya capta la logística. Eso es coherente con lo que el paper advierte sobre la dimensión y con tener 121 positivos.
3. **La variante lineal gana a la constante**, como dice el paper para los extremos: los días con huaico son justo los que caen en el borde de la nube de vecinos.
4. **Promediar rangos de la logística y del análogo no mejora** (AP 0,226 con 11 variables, entre ambos). No hay información complementaria que explotar con esta combinación sencilla (sin ajustar).
5. **Utilidad práctica que sí queda:** para la ficha del capítulo 15, listar los huaicos pasados más parecidos a un día dado (los vecinos) es una explicación entendible, aunque la probabilidad siga viniendo de la logística.

## 5. Límites

- 121 positivos en 43 temporadas: diferencias de 0,01 a 0,04 de AP están dentro del ruido (no se calcularon intervalos por temporada para este capítulo).
- Los mundos nulos usan la configuración más elegida para las etiquetas reales, sin volver a elegirla en cada mundo (la logística también usa un C fijo). Con p en el mínimo posible en todas las filas esto no cambia la conclusión de que hay señal.
- Se probó solo el espacio de las columnas de la selección parsimoniosa; no se buscó otra métrica de distancia (Mahalanobis, pesos por variable) ni la variante incremental, que no tiene sentido para un objetivo binario sin estado siguiente.
- No se corrió en la PC con la RTX 4080 ni se ajustó el mismo código a `float64`; en MPS el cálculo es en `float32`.

## 6. Reproducir

```bash
uv run --extra gpu analogos-informe          # escribe catalogo/analogos_resultados.csv
```

Necesita `datos/` (ver `descargar-datos`). Con `--nulas 200` sirve para probar rápido. El CSV trae AP, AUC, el p95 de las nulas, el valor de p y la configuración elegida; la columna `top5` (huaicos en el 5 % de días con más probabilidad) solo se calcula para los análogos, y los valores de la logística (50 %, 40 % y 31 %) salen de una corrida aparte con `gpu.ajustar_logit_lote`, mismas variables y pliegues. Sin la CLI:

```python
from pathlib import Path
from illapa_research import analogos, modelo_diario as M
D = M.cargar_datos(Path("."))
X, y, ts, _ = M.matrices(D)
cols = [c for c in M.SELECCION_PARSIMONIOSA if c in X["+nino"].columns]
r = analogos.evaluar(X["+nino"][cols].to_numpy(float), y.to_numpy(float), ts, "lineal", n_nulas=2000)
```

Tiempos en la GPU del Mac: unos 35 s la variante constante y 1 a 2 min la lineal, con 2 000 nulas (la logística con sus nulas, unos 10 s). Comparación de dispositivos en el [capítulo 12](12-computo-gpu.md).

## 7. Fuentes

- Lguensat, R., Tandeo, P., Ailliot, P., Pulido, M. y Fablet, R. (2017). *The Analog Data Assimilation*. Monthly Weather Review 145(10), 4093-4107. DOI 10.1175/MWR-D-16-0441.1. Código de los autores: <https://github.com/ptandeo/AnDA>. Se leyó el texto completo del PDF del repositorio de los autores (secciones 3 y 6).
- Van den Dool, H. M. (1994), citado por el paper: sin ~10³⁰ años de datos no hay buen análogo sinóptico del hemisferio norte; de ahí la regla de pocas dimensiones.
- Cleveland, W. S. (1979), citado por el paper: regresión local ponderada, que da la variante lineal.
- El paper trabaja con dinámica caótica (Lorenz-63 y Lorenz-96) y asimilación de datos; **no** trata clasificación ni eventos raros. Llevarlo a «día con huaico sí o no» es una adaptación de este proyecto, no una receta suya.
