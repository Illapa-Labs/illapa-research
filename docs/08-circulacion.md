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

### Con qué datos se corrió (30 de octubre de 2026)

- **Huecos de las fuentes que hay que tener presentes:** el OLR de NOAA termina el **31 de diciembre de 2022** (el producto se discontinuó): las variables de OLR no existen para 2023-2026, que incluyen el Niño costero de 2023 y el de 2024; en el modelo esas filas se rellenan con la mediana de entrenamiento. Los archivos diarios de NCEP/NCAR R1 que sirve PSL llegan solo hasta el **17 de marzo de 2026**. El OMI llega al 24 de junio de 2026.
- ERA5 de Open-Meteo: **solo Matucana, Santa Eulalia alta y Ticlio**. Chosica, la costa de Lima y la selva de Tarma salen de NASA POWER (MERRA-2, malla gruesa; ver `predictores.cargar_con_respaldo`), por una cuota diaria agotada. El modelo base (`lluvia+antecedentes`, AP 0,282) es el de esa mezcla; **debe re-ejecutarse cuando llegue ERA5 completo** (`datos/open_meteo_predictores_diarios.json`).
- Temporadas 1984 a 2026, 6 473 días de diciembre a abril, 118 con huaico catalogado (64 episodios).

## 3. Método

1. **Rezagos 1 a 15 días** con `senales.rezagos_nula`: AUC de la variable `k` días antes frente a una nula de etiquetas desplazadas 7 a 25 días dentro de la temporada; Benjamini-Hochberg con q = 0,10; con y sin restar la media de cada temporada. Robustez con `senales.robustez` (2009+, sin 1983-1998-2017; Niño y no Niño se reportan, no se exigen).
2. **¿Mejora el modelo diario?** `circulacion.ganancia_ap` agrega las columnas, desplazadas un día (`con_circulacion` lo exige), a `lluvia+antecedentes` del capítulo 05 y mide el AP fuera de muestra con regularización elegida dentro del entrenamiento, dejando fuera cada temporada y cada episodio Niño. `circulacion.ganancia_nula` repite el cálculo con las fechas de huaico desplazadas dentro de la temporada (12 réplicas) para saber cuánto AP «gana» una columna por azar. Criterio de la sección 1: ganancia > percentil 95 de la nula y se mantiene dejando episodios fuera.

## 4. Resultados

### 4.1 Rezagos: hay estructura, pero es lenta y se solapa con la lluvia

Con 435 pruebas (29 variables × 15 rezagos) pasan Benjamini-Hochberg **126** (restando la media de la temporada; 113 sin restarla), 141 tienen p < 0,05 contra 22 esperadas por azar, y **84 son robustas**. Es estructura real, pero son rezagos consecutivos de series que cambian despacio: una señal que dura 10 días cuenta 10 veces.

| Hipótesis | Qué se ve (AUC, rezagos que pasan; < 0,5 = valor bajo precede al huaico) | Signo frente a lo pre-registrado |
|---|---|---|
| T16 `u200_altiplano` | 0,40 a 0,41 (viento más del este), rezagos 1 a 12; robusta en 1 a 7 | **Coincide**: más viento del este en 200 hPa |
| T17 OLR | 0,58 a 0,64 (OLR más **alto**), rezagos 1 a 12; robusta | **Contrario a la expectativa ingenua**: menos convección amazónica 1 a 2 semanas antes |
| T17 MJO | `rmm_amp` 0,61 a 0,65 en rezagos 5 a 15 (robusta 5 a 14); `omi_amp` 0,63 a 0,64 en 8 a 12; `rmm1` 0,39 en 1 a 4 | La amplitud alta de la MJO precede; la fase concreta no se pre-registró |
| T19 850 hPa | `u850` AUC 0,58 en el rezago 1 y 0,42 en 10-11; `v850` 0,42 en el 1; flujo q·u 0,58 en el 1; la humedad `q850` sola no pasa | Débil y **contrario**: el día anterior el viento del este está más débil, no más fuerte |
| T20 `z500_chile_peru` | 0,61 a 0,64 (altura **mayor**), rezagos 1 a 10; robusta | **Contrario**: una cresta (anomalía positiva), no una vaguada. El indicador de vaguada (p10) da 0,46 a 0,52 |
| T18 SOI | no se examina por rezago (es mensual) | — |

Estas estructuras son en buena parte lo mismo que la lluvia ya mide: una racha húmeda en los Andes centrales viene con viento del este en altura, convección amazónica suprimida días antes y una cresta de gran escala; no es una causa independiente.

### 4.2 Modelo: casi nada añade lo que no sepa ya el modelo de lluvia y antecedentes

AP fuera de muestra de `lluvia+antecedentes` = **0,282** (base 0,018). Al agregar cada grupo, desplazado un día:

| Grupo | Columnas | AP con | Ganancia (temporada fuera) | Percentil 95 de la nula | Ganancia (episodio fuera) | ¿Cumple el criterio? |
|---|---|---|---|---|---|---|
| T16 u200 | 3 | 0,280 | -0,0018 | 0,0035 | +0,0123 | No |
| T17 OLR y MJO | 10 | 0,281 | -0,0008 | 0,0031 | +0,0089 | No |
| T18 SOI | 1 | 0,281 | -0,0013 | 0,0009 | +0,0039 | No |
| T19 viento y humedad 850 hPa (con flujo q·u) | 11 | 0,304 | **+0,0225** | 0,0024 | +0,0198 | **Sí** en el período completo |
| ↳ solo flujo q·u | 2 | 0,298 | +0,0159 | 0,0006 | +0,0226 | Sí |
| T20 z500 | 4 | 0,275 | -0,0070 | 0,0012 | +0,0063 | No |
| Todas | 29 | 0,301 | +0,0189 | 0,0035 | +0,0216 | Sí (lo pone T19) |

Con las 12 réplicas, el percentil 95 de la nula es un estimado grueso (máximos de 0,003 a 0,006).

**La única señal que pasa es la del viento y la humedad a 850 hPa sobre la selva central, y es frágil.** Con la misma prueba: sin 1983, 1998 y 2017 la ganancia cae a +0,0016 (el AP base cae a 0,203); y **desde 2009 es de -0,0135**, es decir, el efecto vive en las temporadas de 1984 a 2008 y en los tres grandes racimos. Por eso no se recomienda meter estas variables en un modelo: se anota como **hipótesis para repetir con ERA5 completo**, que no lleva a una mejora comprobada.

## 5. Qué se concluye

- **Nulos reportados:** la Alta de Bolivia (T16), el OLR y la MJO (T17), el SOI (T18) y la baja segregada/vaguada en 500 hPa (T20) **no añaden** a la lluvia y los antecedentes, aunque los rezagos muestren estructura.
- **Direcciones contrarias a lo pre-registrado:** T17 (OLR alto, no bajo), T19 (viento del este más débil el día antes) y T20 (cresta, no vaguada). Se publican tal cual; el caso de abril de 2012 (baja segregada con huaico) es un solo evento y no hace una regla.
- **Un indicio frágil:** el flujo de humedad a 850 hPa, que mejora el AP fuera de muestra sobre una nula pero no resiste quitar los racimos grandes ni mirar solo 2009 en adelante.
- **El patrón de fondo es el del capítulo 04:** lo que precede al huaico a escala sinóptica es persistencia de una racha húmeda; lo que decide el día es la lluvia local y el estado de la cuenca.

## 6. Límites

- Reanálisis de 2,5° (R1) para describir cajas de varios grados: no hay resolución para una quebrada.
- Solo 118 días y 64 episodios con huaico; los racimos de 1983, 1998 y 2017 pesan mucho.
- Hueco del OLR en 2023-2026, archivos de R1 hasta el 17 de marzo de 2026, y ERA5 incompleto en el modelo base (3 puntos de 6 de Open-Meteo, el resto de MERRA-2).
- 12 réplicas de la nula por grupo: el umbral p95 es grueso. Con más réplicas puede subir un poco.
- Una variable «de ayer» puede ya contener el inicio de la tormenta si el huaico se reportó con la fecha del día siguiente (evento nocturno): no se probó la etiqueta con día anterior en este capítulo.
- No es un sistema de alerta.

## 7. Reproducir

```bash
uv run descargar-datos --solo noaa-circulacion bom-rmm
uv run jupyter nbconvert --to notebook --execute notebooks/08-circulacion-de-gran-escala.ipynb
```
El notebook tarda unos 15 minutos (los modelos anidados con 12 réplicas de la nula por grupo). Pendiente: re-ejecutarlo cuando exista `datos/open_meteo_predictores_diarios.json` (ERA5 completo) y repetir con la etiqueta del día anterior.
