# 27 · Avisos oficiales del SENAMHI frente a los días con huaico

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide cuánta cobertura de los días con huaico tienen los avisos meteorológicos que ya publica el SENAMHI, y la compara con nuestro modelo diario. Ante una emergencia llama al 115 (INDECI).

Código: [`src/illapa_research/senamhi_api.py`](../src/illapa_research/senamhi_api.py) y [`avisos_senamhi.py`](../src/illapa_research/avisos_senamhi.py), con pruebas en `tests/test_senamhi_api.py` y `tests/test_avisos_senamhi.py`. Resultados: `catalogo/senamhi_avisos_cobertura.csv` y `catalogo/senamhi_avisos_vs_modelo.csv`. Acceso a la API: [docs/notas/senamhi_api.md](notas/senamhi_api.md).

## 1. Datos

- **Avisos meteorológicos** (`/weather-warnings`): se emiten por provincia, con un nivel y una ventana de vigencia. Hay historia desde 2021 (Lima: 32 avisos en 2021, 161 en 2026; Huarochirí: 93 y 185). Antes de 2021 la API devuelve cero.
- **Avisos de lluvia a corto plazo** (`/short-term-warnings`): por distrito, solo 2025 y 2026 (42 para Lurigancho). Demasiado cortos para evaluar.
- **Días con huaico:** los del catálogo con día exacto dentro de la zona de estudio (`solo_zona`), de diciembre a abril, desde diciembre de 2021: **13 días** en 756 días de temporada.
- Todo es información del SENAMHI y lleva su leyenda: «Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad».

## 2. Resultados

| Señal | Días en alarma | Días con huaico cubiertos |
|---|---|---|
| Aviso SENAMHI, provincia de Lima (cualquier nivel) | **50 %** | 11 de 13 (85 %) |
| Aviso SENAMHI, provincia de Huarochirí | **82 %** | 11 de 13 (85 %) |
| Modelo diario con la lluvia del día, mismo 50 % de días | 50 % | 13 de 13 |
| Modelo diario solo con antecedentes, mismo 50 % de días | 50 % | 13 de 13 |
| Modelo diario con la lluvia del día al 5 % de días | 5 % | 9 de 13 (69 %) |
| Modelo diario con la lluvia del día al 10 % de días | 10 % | 12 de 13 (92 %) |
| Modelo diario solo con antecedentes al 10 % de días | 10 % | 8 de 13 (62 %) |
| Modelo diario solo con antecedentes al 20 % de días | 20 % | 12 de 13 (92 %) |

Con el nivel mínimo 2 o 3 la cobertura de Lima no cambia (11 de 13) y la fracción de días con aviso baja del 50 % a unos 42 %.

## 3. Lectura

- **Los avisos están activos en la mitad de los días de lluvia de Lima y en cuatro quintos de los de Huarochirí.** Cubren 11 de los 13 huaicos, pero con una alarma casi permanente: de los 413 días de temporada con aviso en Lima, solo 11 tuvieron huaico (97 % de «falsas alarmas» por día).
- **A igual fracción de días en alarma, nuestro modelo cubre más** (todos los huaicos con el 50 % de días, 92 % con el 10 %). No es una comparación operativa justa: los avisos se emiten con antelación y cubren una provincia entera, y el modelo usa la lluvia del propio día y se entrenó con las demás temporadas, incluidas las posteriores. Compararlo con el modelo «solo antecedentes» (información del día anterior) es más honesto, y aun así supera a los avisos con el 20 % de días.
- **No sustituye ni mejora lo que hace el SENAMHI:** sus avisos son una guía amplia para toda una provincia, no una predicción del día y la quebrada. Lo que muestra esta comparación es cuánta cobertura da una señal pública y que un modelo local puede ser mucho más selectivo.

## 4. Límites

- Solo 13 días con huaico desde diciembre de 2021: el 85 % es 11 de 13 y un día más o menos cambia la cifra 7 puntos.
- Los avisos de lluvia a corto plazo (distrito) tienen solo dos años y no se evaluaron.
- No se probó un umbral operativo, ni el momento de emisión del aviso (un aviso publicado el mismo día de un huaico cuenta como cobertura).
- Los datos crudos de la API quedan fuera de git y del espejo público: no se conocen las condiciones de redistribución de esta cuenta.
