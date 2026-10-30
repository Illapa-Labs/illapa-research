# Catálogo de eventos y cuencas (piloto Chosica y Chaclacayo)

Punto de partida para cruzar lluvia y huaicos. Viene de un proyecto previo (`huaico`, octubre de 2026) y se importó tal cual, sin agregar datos nuevos. **No está verificado fuente por fuente.**

## `eventos.csv`

13 eventos, de 1983 a 2023.

| Campo | Qué es |
|---|---|
| `fecha` | Fecha del evento. Si solo se conoce el año o el mes, el día es `01` |
| `precision_fecha` | `dia`, `mes`, `anio` o `dia_por_confirmar`. **Hay que mirarla antes de usar la fecha** |
| `hora_local` | Hora aproximada, casi siempre vacía |
| `distrito`, `quebradas` | Dónde. Las quebradas van separadas por `;` |
| `fuente`, `confianza`, `notas` | De dónde sale, `alta`, `media` o `baja`, y lo que falta confirmar |

Solo 4 de los 13 eventos tienen día exacto (2015-03-23 y los tres de 2023-03-14), y ninguno de 1987 ni de 1998. Un backtest solo puede usar los de `dia`.

Pendientes que aparecen al cruzar con la investigación de fuentes (todo por verificar en la fuente primaria): 1987 sería el 9 de marzo; 2015 tuvo eventos el 9 de febrero (no el 15) y el 23 de marzo; 2017 el 15 de marzo; faltan 2012, 2019, 2020, 2025 y 2026.

## `cuencas.geojson`

Polígonos de Quirio, Pedregal y Los Laureles (8,9 a 9,6 km²), delimitados con el modelo de elevación Copernicus GLO-30 a 30 m, con altitud mínima, máxima y mediana y el punto de salida. Faltan las demás quebradas.

## Licencia y atribución

Los eventos son hechos citados de INDECI, CENEPRED, PREDES y prensa; cada fila conserva su `fuente`. Las cuencas son un derivado de Copernicus DEM: © Unión Europea / ESA, con atribución. Ver [DATOS.md](../DATOS.md).
