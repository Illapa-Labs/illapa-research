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

La cronología del IGP (abajo) aporta el día de 1987 (9 de marzo) y corrige 2015: el evento de febrero fue el 10, no el 15. Siguen sin cubrir 2019, 2020, 2025 y 2026.

## `eventos_igp.csv`

22 fechas de huaico con día exacto entre 1983 y 2017 en Chosica, Chaclacayo, Santa Eulalia y Ricardo Palma, sacadas de la cronología del IGP (2023), que a su vez cita a El Comercio, La República y PREDES. La columna `fuente` trae la sección del informe y el diario. Incluye, por primera vez con día, **1998** (29-ene Chosica, 15-feb Chaclacayo en la quebrada Los Cóndores, 23 y 24-feb) y 1983, 1987, 2009, 2012, 2015 y 2017. `cargar_todos()` junta este archivo con `eventos.csv`.

Faltan los años sin cobertura (1999 a 2008, 2010 a 2011, 2013 a 2014, 2016 y 2018 en adelante). Las fechas vienen de un solo informe: conviene contrastarlas con los diarios originales. La fecha de 2015-03-23 y la de 1998-02-15 tienen versiones distintas (prensa del 24 y Defensa Civil del 16).

## `cuencas.geojson`

Polígonos de Quirio, Pedregal y Los Laureles (8,9 a 9,6 km²), delimitados con el modelo de elevación Copernicus GLO-30 a 30 m, con altitud mínima, máxima y mediana y el punto de salida. Faltan las demás quebradas.

## Licencia y atribución

Los eventos son hechos citados de INDECI, CENEPRED, PREDES y prensa; cada fila conserva su `fuente`. Las cuencas son un derivado de Copernicus DEM: © Unión Europea / ESA, con atribución. Ver [DATOS.md](../DATOS.md).
