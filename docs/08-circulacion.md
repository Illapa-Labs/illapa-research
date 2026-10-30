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
| T20 | Una vaguada o baja segregada en 500 hPa frente a Chile-Perú precede a los días con huaico (en abril de 2012 la baja estuvo a ~3 días de la lluvia de Chosica; capítulo 09, sección 3.3). | `z500_chile_peru`: NCEP/NCAR R1, altura geopotencial a 500 hPa, **30°S-15°S, 85°W-72°W**, en anomalía; y el indicador `z500_vaguada` = anomalía por debajo del percentil 10 de la climatología 1991-2020 de la temporada de lluvias (dic-abr). | 0 a 4 d (solo ≥ 1 en el modelo) |

Las anomalías se calculan contra una climatología suavizada por día del año de 1991-2020 (`predictores.anomalia`). Una variable en un rezago es **señal** si pasa Benjamini-Hochberg (q = 0,10) frente a la nula que desplaza las etiquetas dentro de cada temporada (`senales.rezagos_nula`), con rezago ≥ 1 día; es **robusta** si además mantiene el signo con p < 0,10 en 2009+ y sin 1983, 1998 y 2017 (`senales.robustez`).

**Criterio de éxito para entrar en un modelo** (fijo): al añadir las variables a `lluvia+antecedentes` (`modelo_diario`), la precisión media (AP) fuera de muestra, dejando temporadas fuera, debe subir más que el percentil 95 de la ganancia que dan las mismas columnas con las fechas de huaico desplazadas dentro de cada temporada, y la ganancia debe mantenerse dejando episodios Niño fuera. Si no, se reporta como nulo.

## 2. Datos y licencias

| Dato | Fuente | Licencia / uso | Cómo se obtiene |
|---|---|---|---|
| u y v a 850 hPa, humedad específica a 850 hPa, viento zonal a 200 hPa y altura geopotencial a 500 hPa, promedio diario ponderado por cos(lat) en las cajas de la sección 1 | NCEP/NCAR Reanalysis 1 (Kalnay et al. 1996) vía el servicio de subconjuntos (NCSS) del THREDDS de NOAA PSL | Dominio público (gobierno de EE. UU.) | `descargar-datos --solo noaa-circulacion` |
| OLR diario en 15°S-5°S, 70°W-55°W | NOAA Interpolated OLR (PSL) | Dominio público | ídem |
| Índice MJO OMI (PC1, PC2, amplitud) | NOAA PSL | Dominio público | ídem |
| SOI mensual (Tahiti - Darwin, estandarizado) | NOAA CPC | Dominio público | ídem |
| Índice MJO RMM (RMM1, RMM2, fase, amplitud) | Oficina de Meteorología de Australia (BoM), Wheeler y Hendon (2004) | Datos públicos del BoM; se cita. No se incluye en el espejo público de Hugging Face (sin licencia de redistribución explícita) | `descargar-datos --solo bom-rmm` (el servidor pide un `User-Agent` de navegador) |
| Fechas de huaico, lluvia, suelo, caudal, mar | Los de los capítulos 04 y 05 | Los de allí | los de allí |

Los reanálisis de la época (R1, 2,5°) no ven una quebrada: describen el patrón regional. Todas las variables se convierten en anomalías contra la climatología suavizada por día del año de 1991-2020 (`predictores.anomalia`), con medias de 3 y 7 días (y de 15 para el OLR). `z500_vaguada` es 1 cuando la anomalía de `z500_chile_peru` queda bajo el percentil 10 de dic-abr de 1991-2020. La humedad×viento es `q850 × u850` (flujo zonal de humedad). El SOI entra con el valor del mes anterior.

### Con qué datos se corrió (corrida final del 30 de octubre de 2026)

- **ERA5 completo, 6 puntos** de Open-Meteo (Chosica, costa de Lima, Matucana, Santa Eulalia alta, selva de Tarma y Ticlio), con el modelo base `lluvia+antecedentes` de 97 columnas. Una primera versión de este capítulo usó 3 puntos de ERA5 y 3 de MERRA-2 (NASA POWER); **sus conclusiones sobre T19 cambiaron** al completar ERA5 (sección 4.2).
- **Huecos de las fuentes de circulación:** el OLR de NOAA termina el **31 de diciembre de 2022** (producto discontinuado): no hay OLR para 2023-2026. Los archivos diarios de NCEP/NCAR R1 que sirve PSL llegan solo hasta el **17 de marzo de 2026**. El OMI llega al 24 de junio de 2026. Por eso hay una versión «hasta 2022» que no imputa nada.
- Temporadas 1984 a 2026, 6 473 días de diciembre a abril, 118 con huaico catalogado (64 episodios). Con la etiqueta del día anterior hay 202 días positivos.
- Los cálculos pesados se hicieron en la PC remota con GPU (RTX 4080 SUPER) con `gpu.py`; los resultados están en `docs/08-resultados/`.

## 3. Método

1. **Rezagos 1 a 15 días** con `senales.rezagos_nula`: AUC de la variable `k` días antes frente a una nula de etiquetas desplazadas 7 a 25 días dentro de la temporada; Benjamini-Hochberg con q = 0,10; con y sin restar la media de cada temporada. Robustez con `senales.robustez` (2009+, sin 1983-1998-2017; Niño y no Niño se reportan, no se exigen).
2. **¿Mejora el modelo diario?** `circulacion.ganancia_bloque` agrega un bloque de columnas, desplazadas un día (`con_circulacion` lo exige), a las 97 columnas de `lluvia+antecedentes` del capítulo 05 y mide la ganancia de AP fuera de muestra. Los dos modelos (base y base + bloque) son la misma regresión logística con L2 fija (C = 0,03, la que el ajuste anidado del capítulo 05 eligió en 42 de 43 pliegues), con los mismos pliegues (una temporada fuera, o un episodio Niño fuera), ajustados por lotes en la GPU. **Nula:** las filas del bloque se mueven cíclicamente dentro de cada temporada (conservan su persistencia y su ciclo estacional, pero pierden el vínculo día a día con las etiquetas) y se vuelven a ajustar todos los pliegues; **2 000 mundos nulos** en la prueba principal y 1 000 en las de robustez. `p` es la fracción de mundos nulos cuya ganancia alcanza la real. Criterio de la sección 1: ganancia > percentil 95 de la nula y se mantiene dejando episodios fuera.
3. **Robustez del modelo:** etiqueta del día anterior (`dias_antes=1`), sin 1983, 1998 y 2017, desde 2009, y hasta 2022 (sin imputar medianas en el OLR), y una ablación de T19 variable por variable.

## 4. Resultados

### 4.1 Rezagos: hay estructura, pero es lenta y se solapa con la lluvia

Con 435 pruebas (29 variables × 15 rezagos, 2 000 permutaciones cada una) pasan Benjamini-Hochberg **134** (restando la media de la temporada; 115 sin restarla), 146 tienen p < 0,05 contra 22 esperadas por azar, y **86 son robustas**. Con la etiqueta del día anterior pasan 140. Es estructura real, pero son rezagos consecutivos de series que cambian despacio: una señal que dura 10 días cuenta 10 veces. Tablas completas en `docs/08-resultados/rezagos_*.csv`.

| Hipótesis | Qué se ve (AUC; < 0,5 = valor bajo precede al huaico) | Signo frente a lo pre-registrado |
|---|---|---|
| T16 `u200_altiplano` | 0,40 a 0,41 (viento más del este), rezagos 1 a 12; robusta en 1 a 6 | **Coincide**: más viento del este en 200 hPa |
| T17 OLR | 0,58 a 0,64 (OLR más **alto**), rezagos 1 a 12; robusta | **Contrario a la expectativa ingenua**: menos convección amazónica 1 a 2 semanas antes |
| T17 MJO | `rmm_amp` 0,61 a 0,65 en rezagos 5 a 15 (robusta 5 a 14); `omi_amp` 0,63 a 0,64 en 8 a 13; `rmm1` 0,39 en 1 a 4 | La amplitud alta de la MJO precede; la fase concreta no se pre-registró |
| T19 850 hPa | `u850` AUC 0,58 en el rezago 1 y 0,42 en 10-11; `v850` 0,42 en el 1; flujo q·u 0,58 en el 1 (idéntico a `u850`: la humedad casi no cambia); `q850` sola no pasa | Débil y **contrario**: el día anterior el viento del este está más débil, no más fuerte |
| T20 `z500_chile_peru` | 0,59 a 0,64 (altura **mayor**), rezagos 1 a 10; robusta | **Contrario**: una cresta (anomalía positiva), no una vaguada. El indicador de vaguada (p10) no separa |
| T18 SOI | no se examina por rezago (es mensual) | — |

Estas estructuras son en buena parte lo mismo que la lluvia ya mide: una racha húmeda en los Andes centrales viene con viento del este en altura, convección amazónica suprimida días antes y una cresta de gran escala; no es una causa independiente.

### 4.2 Modelo: nada de la circulación añade lo que ya saben la lluvia y los antecedentes

Ganancia de AP fuera de muestra (base: `lluvia+antecedentes` con ERA5 completo, AP 0,290 dejando temporadas fuera y 0,298 dejando episodios fuera; tasa base 0,018). Prueba principal, 2 000 mundos nulos:

| Grupo | Columnas | Ganancia (temporada fuera) | p95 de la nula | p | Ganancia (episodio fuera) | p95 | p | ¿Cumple? |
|---|---|---|---|---|---|---|---|---|
| T16 u200 | 3 | +0,0002 | 0,0057 | 0,18 | -0,0023 | 0,0069 | 0,44 | No |
| T17 OLR y MJO | 10 | -0,0111 | 0,0132 | 0,65 | -0,0048 | 0,0109 | 0,41 | No |
| T18 SOI | 1 | -0,0058 | 0,0003 | 0,78 | -0,0043 | 0,0010 | 0,71 | No |
| T19 850 hPa (completo) | 11 | +0,0078 | 0,0112 | 0,10 | +0,0086 | 0,0139 | 0,14 | **No** |
| T20 z500 | 4 | -0,0047 | 0,0066 | 0,61 | -0,0010 | 0,0084 | 0,44 | No |
| Todas | 29 | -0,0056 | 0,0112 | 0,28 | -0,0055 | 0,0093 | 0,25 | No |

**Ninguno de los cinco bloques cumple el criterio pre-registrado.** El único candidato, T19, mejoraba el AP en +0,0225 en la primera versión del capítulo (con 3 puntos de ERA5 y 3 de MERRA-2 en el modelo base, 12 réplicas de la nula); con ERA5 completo la ganancia baja a +0,008, dentro de lo que da el azar. La señal de 850 hPa estaba compensando la humedad y el viento de baja calidad de la malla gruesa, no una señal propia.

**Ablación de T19** (variable por variable, 2 000 mundos): `u850` +0,0039 (p = 0,08); **`v850` +0,0092 (p = 0,014; episodio +0,0115, p = 0,006)**; `q850` -0,0026; flujo q·u +0,0019 (p = 0,12); `u850 + v850` +0,0073 (p = 0,034); `u850 + v850 + flujo` +0,0064 (p = 0,046). Solo `v850` y la pareja con `u850` superan el percentil 95 en una de las dos validaciones, con p entre 0,006 y 0,05 sobre 14 pruebas de esta ablación y unas 80 en total: con esa multiplicidad es compatible con azar.

**Robustez** (1 000 mundos nulos; cada fila repite el modelo base y el bloque en la ventana indicada):

| Escenario | Filas / positivos | Base AP | T19 completo: ganancia (temporada) / p | T19: ganancia (episodio) / p | ¿Algún otro bloque cumple? |
|---|---|---|---|---|---|
| Etiqueta del día anterior | 6 473 / 202 | 0,307 | +0,0040 / 0,15 | +0,0045 / 0,16 | No |
| Sin 1983, 1998 y 2017 | 6 171 / 80 | 0,192 | +0,0124 / 0,065 | +0,0008 / 0,31 | No |
| Desde 2009 | 2 691 / 64 | 0,375 | **+0,0130 / 0,050** (cumple, justo) | **+0,0404 / 0,004** (cumple) | No |
| Hasta 2022, sin imputar el OLR | 5 868 / 105 | 0,253 | -0,0010 / 0,46 | +0,0032 / 0,43 | No (T17 con OLR real: -0,018 / p = 0,87) |

**T19 es inconsistente entre ventanas**: no cumple en el período completo, ni con la etiqueta del día anterior, ni sin los grandes racimos, ni hasta 2022; sí cumple (y con el episodio fuera muy claro, +0,040) desde 2009, que es solo la época con 64 positivos y 18 temporadas. En la primera versión del capítulo era justo al revés (cumplía en el período completo y fallaba desde 2009), lo que confirma que la señal depende de la configuración de datos y no de una relación estable. **El OLR, con solo años donde existe, empeora el modelo** (-0,018): la versión con medianas imputadas no era la que lo perjudicaba.

## 5. Qué se concluye

- **Nulos reportados:** la Alta de Bolivia (T16), el OLR y la MJO (T17), el SOI (T18), el flujo de humedad a 850 hPa (T19) y la baja segregada/vaguada en 500 hPa (T20) **no añaden** a la lluvia y los antecedentes de ERA5 completo, aunque los rezagos muestren estructura. Esto contradice la lectura de la primera versión de este capítulo.
- **Direcciones contrarias a lo pre-registrado:** T17 (OLR alto, no bajo), T19 (viento del este más débil el día antes) y T20 (cresta, no vaguada). Se publican tal cual; el caso de abril de 2012 (baja segregada con huaico) es un solo evento y no hace una regla.
- **Una lección de método:** una ganancia que pasa una nula con 12 réplicas, con un modelo base construido con datos de mala calidad, desaparece con 2 000 réplicas y datos completos. Las ganancias de AP de este tamaño (menos de 0,02) son comparables con el ruido de elegir un escenario de entre varios.
- **El patrón de fondo es el del capítulo 04:** lo que precede al huaico a escala sinóptica es persistencia de una racha húmeda; lo que decide el día es la lluvia local y el estado de la cuenca.

## 6. Límites

- Reanálisis de 2,5° (R1) para describir cajas de varios grados: no hay resolución para una quebrada.
- Solo 118 días y 64 episodios con huaico; los racimos de 1983, 1998 y 2017 pesan mucho, y desde 2009 solo hay 64 positivos y 18 temporadas.
- Hueco del OLR en 2023-2026 y archivos de R1 hasta el 17 de marzo de 2026.
- Base y bloque usan una regresión logística con L2 fija (C = 0,03), no el ajuste anidado del capítulo 05; el AP base (0,290) difiere un poco del anidado (0,282 con la mezcla de datos de la primera versión).
- La nula mueve las filas del bloque, no las etiquetas: es la pregunta «¿cuánto gana este bloque por estar bien o mal alineado con los días con huaico?». No prueba que el bloque no tenga ninguna relación con el tiempo en general.
- Una variable «de ayer» puede ya contener el inicio de la tormenta si el huaico se reportó con la fecha del día siguiente (evento nocturno); la etiqueta del día anterior lo cubre en parte y los resultados no cambian.
- No es un sistema de alerta.

## 7. Reproducir

```bash
uv run descargar-datos --desde-hf renzoedu25/illapa-research-datos   # o --solo noaa-circulacion bom-rmm
uv run python - <<'PY'
from pathlib import Path
from illapa_research import circulacion as c, modelo_diario as md
D = md.cargar_datos(Path("."))
G = c.grupos(list(c.construir(Path("datos"), D.F.index).columns))
c.correr_gpu(Path("."), [{"prueba": k, "columnas": v} for k, v in G.items()], n_nulas=2000)
PY
```
Resultados en `docs/08-resultados/`: `gpu_resultados.csv` (todas las pruebas del modelo, con la nula), `rezagos_*.csv` (435 pruebas × 4 variantes) y `rezagos_robustez.csv`. La corrida pesada (unos 55 minutos con 2 000 mundos nulos en la RTX 4080 SUPER) está en el notebook con `RECALCULAR = True`.
