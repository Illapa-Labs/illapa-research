# 27 · Avisos oficiales del SENAMHI frente a los días con huaico

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide cuánta cobertura de los días con huaico tienen los avisos meteorológicos que ya publica el SENAMHI, y la compara con nuestro modelo diario. Ante una emergencia llama al 115 (INDECI).

Código: [`src/illapa_research/senamhi_api.py`](../src/illapa_research/senamhi_api.py) y [`avisos_senamhi.py`](../src/illapa_research/avisos_senamhi.py), con pruebas en `tests/test_senamhi_api.py` y `tests/test_avisos_senamhi.py`. Resultados: `catalogo/senamhi_avisos_cobertura.csv` y `catalogo/senamhi_avisos_vs_modelo.csv`. Acceso a la API: [docs/notas/senamhi_api.md](notas/senamhi_api.md).

## 1. Datos

- **Avisos meteorológicos** (`/weather-warnings`): se emiten por provincia, con un nivel y una ventana de vigencia. Hay historia desde 2021 (Lima: 32 avisos en 2021, 161 en 2026; Huarochirí: 93 y 185). Antes de 2021 la API devuelve cero.
- **Avisos de lluvia a corto plazo** (`/short-term-warnings`): por distrito, solo 2025 y 2026 (42 para Lurigancho). Demasiado cortos para evaluar.
- **Días con huaico:** los del catálogo con día exacto dentro de la zona de estudio (`solo_zona`), de diciembre a abril, desde diciembre de 2021: **13 días** en 756 días de temporada.
- Todo es información del SENAMHI y lleva su leyenda: «Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad».

## 2. Resultados

Los avisos meteorológicos incluyen viento, temperatura, heladas y nevadas, no solo lluvia: de 1 314 avisos únicos desde 2021, los de lluvia son los que la API marca con el fenómeno 01 (Precipitaciones) o 08 (Lluvia) en el campo `events`; no se cuenta la llovizna (07), el viento, la temperatura ni la nevada. Se calcula con todos los avisos y solo con los de lluvia.

| Señal | Días de temporada en alarma | Huaicos cubiertos (de 13) |
|---|---|---|
| Aviso SENAMHI, Lima, **solo lluvia** | **18,5 %** | 8 (62 %) |
| Modelo diario (con la lluvia del día), mismo 18,5 % de días | 18,5 % | 12 |
| Aviso SENAMHI, Huarochirí, **solo lluvia** | 69,4 % | 11 (85 %) |
| Modelo diario (con la lluvia del día), mismo 69,4 % de días | 69,4 % | 13 |
| Aviso SENAMHI, Lima, todos los tipos | 49,7 % | 11 (85 %) |
| Aviso SENAMHI, Huarochirí, todos los tipos | 82,4 % | 11 (85 %) |
| Modelo diario con la lluvia del día al 5 % de días | 5 % | 9 (69 %) |
| Modelo diario con la lluvia del día al 10 % de días | 10 % | 12 (92 %) |
| Modelo diario solo con antecedentes al 10 % de días | 10 % | 8 (62 %) |
| Modelo diario solo con antecedentes al 20 % de días | 20 % | 12 (92 %) |

Los avisos de lluvia de Lima con nivel 3 o más siguen cubriendo 8 de 13 con 143 días de aviso; no cambian con el nivel (`catalogo/senamhi_avisos_cobertura.csv`).

## 3. Lectura

- **Los avisos de lluvia de Lima son más selectivos de lo que parecía** (activos en el 18 % de los días de lluvia), pero cubren menos: 8 de 13 huaicos (62 %). Los de Huarochirí, la provincia de Santa Eulalia y Ricardo Palma, cubren 11 de 13 pero estuvieron activos en siete de cada diez días.
- **Con todos los avisos (también viento y temperatura)** la cobertura sube a 11 de 13 con la mitad de los días en alarma: ese número cuenta como aviso cosas que no son lluvia y no debe leerse como una cobertura de huaicos.
- **A igual fracción de días en alarma, nuestro modelo cubre más:** 12 de 13 con el 18,5 % de días (contra 8 de los avisos de lluvia de Lima) y 13 de 13 con el 69,4 %. La comparación no es operativa: los avisos se emiten con antelación y cubren una provincia entera, y el modelo usa la lluvia del propio día y se entrenó con las demás temporadas, incluidas las posteriores. Con el modelo «solo antecedentes» (información del día anterior) la ventaja también existe a partir del 20 % de los días.
- **Lo que no dice esta comparación:** que el modelo mejore al SENAMHI. Los avisos son una guía amplia para toda una provincia y no una predicción del día y de la quebrada. Muestran cuánta cobertura da una señal pública y que un modelo local puede ser más selectivo.

## 4. Límites

- Solo 13 días con huaico desde diciembre de 2021: 8 de 13 es 62 % y un día más o menos cambia la cifra ocho puntos.
- El filtro es por el código de fenómeno que trae cada aviso. Un aviso con varios fenómenos (por ejemplo lluvia y viento) cuenta como de lluvia.
- Los avisos de lluvia a corto plazo (distrito) tienen solo dos años y no se evaluaron.
- No se probó un umbral operativo, ni el momento de emisión del aviso (un aviso publicado el mismo día de un huaico cuenta como cobertura).
- Los datos crudos de la API quedan fuera de git y del espejo público: no se conocen las condiciones de redistribución de esta cuenta.
