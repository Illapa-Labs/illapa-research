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

## Otras fuentes de fechas

Cada archivo `eventos_*.csv` trae una fuente distinta y `cargar_todos()` los junta todos. La confianza `baja` se puede excluir con `sin_baja_confianza=True`.

| Archivo | Fuente | Fechas |
|---|---|---|
| `eventos_valverde_mdlch.csv` | Cronología de Valverde Torres (CIP, 2012) y registro de la Municipalidad de Lurigancho-Chosica, ambos citados en la tesis de Sánchez Meza (UNFV, 2018) | 1981 a 2012, y 21 días de activación en 2017 |
| `eventos_coen.csv` | Informes del COEN-INDECI leídos completos | 2016, 2017, 2020 y 2024 |
| `eventos_nuevos_1981_1998.csv` | INDECI (emergencias de 1998), INGEMMET y la tesis de la UNFV | 1981 a 1998 |
| `eventos_nuevos_2013_2020.csv` | Prensa (El Comercio, América TV, Panamericana), INDECI | 2014 a 2020 |
| `eventos_observatorio_enso.csv` | Catálogo «Memoria de desastres» de [PillB/observatorio-enso-peru](https://github.com/PillB/observatorio-enso-peru) (DesInventar, SINPAD, prensa): solo las fechas de tipo Huayco/Alud en Lurigancho-Chosica, Chaclacayo, Santa Eulalia y Ricardo Palma que no estaban en las otras fuentes | 1981 a 2026; 66 fechas, 20 con quebrada identificada |
| `eventos_nuevos_2021_2026.csv` | Prensa (Andina, La República, Infobae, Trome, El Peruano) | 2023 a 2026 |

Solo se registró una fecha cuando alguien leyó una fuente que da el día. Lo que no se pudo confirmar quedó fuera: los detalles están en las notas de investigación, que no forman parte de este repositorio. Los años 1990 a 1997, 1999 a 2008, 2010 a 2011 y 2021 a 2022 siguen sin eventos documentados, lo que no prueba que no los hubo.

Las filas del observatorio son **registros por distrito**: la mayoría no dice qué quebrada se activó (`(sin quebrada)`) y el tipo «Huayco/Alud» puede incluir deslizamientos o inundaciones mal clasificados. Se dejaron en confianza media y con la licencia de su origen en `fuente` (DesInventar: uso libre con atribución; SINPAD: información pública).

Dudas conocidas: el evento de Chosica de febrero de 2015 fue el lunes 9 según la prensa (el IGP dice el 10); el de 1998 aparece el 24 (IGP) y el 25 y 26 (Valverde); algunas filas de 2019 son crecidas de agua que Defensa Civil no consideró huaico; las filas de 2017 de la Municipalidad no dicen qué quebrada se activó cada día.

## `cuencas.geojson`

Polígonos de Quirio, Pedregal y Los Laureles (8,9 a 9,6 km²), delimitados con el modelo de elevación Copernicus GLO-30 a 30 m, con altitud mínima, máxima y mediana y el punto de salida. Faltan las demás quebradas.

## Licencia y atribución

Los eventos son hechos citados de INDECI, CENEPRED, PREDES y prensa; cada fila conserva su `fuente`. Las cuencas son un derivado de Copernicus DEM: © Unión Europea / ESA, con atribución. Ver [DATOS.md](../DATOS.md).
