# Notas de investigación

Cada archivo es un capítulo, escrito como se escribiría una tesis: pregunta, datos con su fuente, método, resultados con cifras, límites y qué falta. Los notebooks (`notebooks/`) reproducen los resultados; los datos descargados no se suben (`datos/`), pero `descargar-datos` los vuelve a bajar y deja la licencia en `datos/MANIFIESTO.json`.

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Es investigación en curso. Ante una emergencia llama al 115 (INDECI).

**Versión de los datos de las cifras.** Las cifras de los capítulos 03 a 22 salen de una corrida completa sobre el catálogo de **150 fechas con día exacto (121 días con huaico en las temporadas de lluvia 1984-2026)**, en el commit `ddc70f0`. Después se añadieron 2 fechas y 7 fechas con quebrada ubicada: hoy el catálogo tiene 152 fechas y 123 días con huaico. Eso mueve las cifras en la tercera cifra y no cambia ninguna conclusión (por ejemplo, la logística de ancho fijo da AP 0,303 con 121 días y 0,299 con 123, capítulo 24), así que no se rehicieron todas las corridas por dos fechas. Se rehacen cuando el catálogo cambie de forma material. Los capítulos 23 y 24 usan el catálogo actual.

| Capítulo | Contenido | Notebook |
|---|---|---|
| [00 · Plan y teorías](00-plan-y-teorias.md) | Preguntas, teorías en competencia, criterios de validación | — |
| [01 · Cuencas y ubicación de quebradas](01-cuencas-y-ubicacion.md) | Cómo se delimitaron 124 cuencas y cómo se ubicó cada nombre | `03` |
| [03 · Ranking de quebradas y modelo jerárquico](03-modelo-por-quebrada.md) | Susceptibilidad física, historial, Niño, exposición | `03` |
| [04 · Señales y rezagos](04-senales-y-rezagos.md) | ¿Qué cambia días antes? (mar, calor aguas arriba, humedad de la selva, caudal) | `04` |
| [05 · Modelo diario](05-modelo-diario.md) | Probabilidad de un día con huaico, validada por temporada y episodio Niño | `05` |
| [07 · Calidad de las etiquetas](07-calidad-de-etiquetas.md) | Etiquetas alternativas, sesgo por era, falsos positivos | `07` |
| [08 · Circulación de gran escala](08-circulacion.md) | Viento en altura, convección, MJO | `08` |
| [09 · Literatura de mecanismos](09-literatura-mecanismos.md) | Qué ocurre antes de las lluvias que activan huaicos y qué falta probar | — |
| [12 · Cómputo: CPU y GPU](12-computo-gpu.md) | Cómo se ejecutan los miles de modelos de las pruebas nulas y cuánto se gana | — |
| [13 · ERA5 sin la API](13-era5-alterno.md) | Cómo se leen los archivos de Open-Meteo en AWS cuando la API agota su cuota, y equivalencia medida | — |
| [11 · Datos del SENAMHI](11-senamhi.md) | Pluviómetros reales, umbrales oficiales, avisos de 2020 y anomalías de los Niños; términos de uso y leyenda | `11` |
| [14 · Corregir el sesgo del pronóstico](14-correccion-sesgo.md) | El modelo del UK Met Office marca 2,6 veces más lluvia que PISCOp; corregirlo arregla la calibración pero no la detección de huaicos | — |
| [15 · Ficha de probabilidad](15-ficha-de-probabilidad.md) | Probabilidad de un día con huaico catalogado, con intervalo, fiabilidad por banda y condiciones que empujan | `12` |
| [16 · De pronóstico de lluvia a probabilidad](16-pronostico-a-probabilidad.md) | Cómo se hace en otros sistemas, cómo se hace el backtest y qué archivos de pronósticos históricos hay | — |
| [17 · Backtest con pronósticos de lluvia](17-backtest-con-pronostico.md) | Del pronóstico de lluvia a la probabilidad del día: qué se conserva a cada lead, calibración y potencia | `13` |
| [18 · Datos del Estado](18-datos-del-estado.md) | Qué publican INGEMMET, INDECI, CENEPRED, ANA y ANIN, qué se obtuvo y cómo cae su lista de quebradas priorizadas frente a nuestro ranking | `14` |
| [19 · Backtest con el reforecast GEFS](19-backtest-gefs-reforecast.md) | Probabilidad de un día con huaico con lluvia pronosticada a 24, 48 y 72 h, 2000-2019, con y sin 2017 | `15` |
| [20 · Ficha de probabilidad desde pronóstico](20-ficha-desde-pronostico.md) | Probabilidad con intervalo y fiabilidad por plazo (24, 48, 72 h) a partir del reforecast GEFS | `16` |
| [21 · Quebrada y día](21-quebradas-y-dia.md) | Si conocer la quebrada agrega algo a conocer el día, con lluvia observada y con pronóstico GEFS | `17` |
| [22 · Análogos: los días más parecidos](22-analogos.md) | Búsqueda de los K días más parecidos (Lguensat et al. 2017) contra la regresión logística: señal real, no la supera | — |
| [23 · Geoquebradas del MINAM](23-geoquebradas.md) | Avisos oficiales diarios de activación de quebradas (desde febrero de 2026) frente a los huaicos de 2026 y nuestra ficha | — |
| [24 · Banco de modelos](24-banco-de-modelos.md) | Logística, boosting monótono, GRU y conjunto con la misma validación: la logística sigue siendo la mejor | `05` |
