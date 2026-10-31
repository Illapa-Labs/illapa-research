# 20 · Ficha de probabilidad desde pronóstico

> **No es una alerta ni una predicción para decidir evacuaciones.** Es la frecuencia histórica de días con huaico *catalogado* bajo pronósticos parecidos. Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/16-ficha-desde-pronostico.ipynb`](../notebooks/16-ficha-desde-pronostico.ipynb). Código: `src/illapa_research/ficha_pronostico.py` (pruebas en `tests/test_ficha_pronostico.py`). Tablas: `catalogo/ficha_pronostico_calibracion.csv` y `ficha_pronostico_bandas.csv`. Se apoya en el capítulo 15 (ficha desde observaciones) y en el 19 (backtest con el reforecast GEFSv12).

## 1. Pregunta

Cuando solo hay un pronóstico de lluvia a 24, 48 o 72 horas, ¿qué probabilidad de un día con huaico catalogado se puede dar, con qué intervalo y qué tan fiable es?

## 2. Datos y método

- **Datos.** Las probabilidades fuera de muestra del capítulo 19 (`catalogo/gefs_probabilidades_fuera_de_muestra.csv.gz`): 2 952 días de temporada de lluvias por plazo (2000-2019), 55 con huaico (32 sin 2017). `pp_qm` es el modelo del capítulo 15, entrenado con ERA5 y alimentado con la lluvia GEFS corregida por cuantiles contra PISCOp.
- **Recalibración.** Platt (`sigmoid(a + b·logit(p))`) por plazo, ajustado dejando una temporada fuera; su intervalo sale de 500 remuestreos de temporadas.
- **Bandas de fiabilidad.** Días y huaicos por banda de probabilidad calibrada (0-2 %, 2-10 %, 10-25 %, 25 % o más), con intervalo de Wilson del 80 %.
- **Qué informa la ficha.** La frecuencia observada de la banda con su intervalo, no la curva de Platt (ver §3). Además: la curva calibrada, la probabilidad sin 2017, cuántas veces la frecuencia base, advertencias, las condiciones y quebradas que se pasen, y el texto fijo de límites.

Hipótesis (escritas antes de leer las tablas de este capítulo): H1 Platt acerca observado/predicho a 1; H2 mejora Brier y log-loss en los tres plazos con y sin 2017; H3 las bandas altas son fiables; H4 no depende de 2017. La regla de reporte (frecuencia observada de la banda) se decidió al ver que la curva se sale en la cola.

## 3. Resultados (datos del 30 de octubre de 2026)

**Calibración (dejando una temporada fuera; base 0,019)**

| Plazo | Versión | Brier skill (todo) | Observado / predicho (todo) | Brier skill (sin 2017) |
|---|---|---|---|---|
| 24 h | cruda | +0,083 | 0,78 | −0,125 |
| 24 h | calibrada | +0,040 | 1,05 | −0,103 |
| 48 h | cruda | −0,068 | 0,66 | −0,255 |
| 48 h | calibrada | +0,009 | 1,02 | −0,023 |
| 72 h | cruda | −0,126 | 0,66 | −0,317 |
| 72 h | calibrada | −0,005 | 1,02 | −0,006 |

- **H1 se cumple.** La razón observado/predicho pasa de 0,66-0,78 a 1,02-1,05 con todos los años y a 0,88-0,94 sin 2017.
- **H2 se cumple a 48 y 72 h y falla a 24 h.** A 24 h la calibración empeora un poco el Brier (de +0,083 a +0,040): la cruda ordena mejor y exagera; la calibrada acierta el nivel. A 48 y 72 h la calibración lleva el Brier skill de negativo a casi cero: **la cifra no es mejor que la climatología**. Lo que queda es el orden de los días (precisión media 0,25, 0,17 y 0,13, capítulo 19).
- **H3 se cumple solo a 24 h.** Banda de 25 % o más: 11 de 27 días con huaico a 24 h (41 %, intervalo 30 a 53 %); a 48 h, 3 de 20 (15 %); a 72 h, 2 de 25 (8 %), contra 45 % y 37 % predichos. **A 48 y 72 h esa banda no es fiable.**
- **H4 no se cumple.** Sin 2017 la banda de 25 % o más a 24 h baja de 41 % a 20 % (4 de 20), y las demás bandas se reducen a la mitad o menos.
- **La curva de Platt se sale en la cola.** Para una probabilidad cruda de 0,99 a 24 h da 90 %, pero de los 27 días históricos de esa banda solo 41 % tuvo huaico. Por eso la ficha informa la frecuencia observada y lo avisa cuando la curva se separa más del doble.

**Ejemplos** (días reales del backtest, notebook 16): el día de mayor probabilidad cruda a 24 h (9 de febrero de 2019, 0,99) da 41 % observado (intervalo 30-53 %; 20 % sin 2017) y no tuvo huaico; un día de 0,18 cruda da 13 %; un día de 0,84 a 48 h da 15 %, con la advertencia de banda no fiable.

## 4. Cómo se lee una ficha

1. La **cifra** es la frecuencia de días con huaico catalogado entre los días históricos con una probabilidad calibrada parecida, a ese plazo.
2. El **intervalo** es el de Wilson de esa frecuencia; es ancho porque las bandas altas tienen entre 20 y 54 días.
3. **«Sin 2017»** dice cuánto depende del año con 23 de los 55 huaicos.
4. Las **advertencias** son parte de la ficha: a 48 y 72 h, bandas con pocos días, y dependencia de 2017.

## 5. Límites

- **Una sola ventana.** 2000-2019 con GEFS (5 miembros, resolución gruesa); no se probó con pronósticos operativos actuales de mejor resolución. El prototipo del capítulo 17 (UK Met Office, 14 huaicos) sugiere que a plazo 0 un modelo de 10 km se acerca al techo.
- **Poca potencia por banda** y dependencia de 2017.
- **El catálogo** mezcla años con registro muy desigual (1999-2008 casi vacío, mucha cobertura desde 2015) y registra lo reportado.
- **Plazos mayores.** A 48 y 72 h la ficha ordena pero no calibra mejor que la climatología.
- **Quebradas.** Se pueden pasar las probabilidades por quebrada del capítulo 15, pero el producto con la participación no gana de forma robusta sin 2017 (capítulos 17 y 19): se muestran como reparto, no como estimación propia.
- **Calibración por era o por régimen.** No se hizo aquí; el capítulo 15 muestra que el nivel cambia con la cobertura del catálogo.

## 6. Reproducir

```bash
uv run python -m illapa_research.ficha_pronostico --n-boot 500
```
```python
from illapa_research import ficha_pronostico as F
modelo = F.correr(".")["modelo"]
modelo.ficha(p_crudo=0.30, plazo=1)   # plazo 1, 2 o 3 días
```
