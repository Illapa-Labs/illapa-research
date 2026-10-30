# Notas de investigación

Cada archivo es un capítulo, escrito como se escribiría una tesis: pregunta, datos con su fuente, método, resultados con cifras, límites y qué falta. Los notebooks (`notebooks/`) reproducen los resultados; los datos descargados no se suben (`datos/`), pero `descargar-datos` los vuelve a bajar y deja la licencia en `datos/MANIFIESTO.json`.

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Es investigación en curso. Ante una emergencia llama al 115 (INDECI).

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
