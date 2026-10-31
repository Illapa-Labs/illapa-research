# Catálogo de eventos y cuencas (piloto Chosica y Chaclacayo)

Punto de partida para cruzar lluvia y huaicos y, más abajo, el ranking de quebradas para El Niño. Viene de un proyecto previo (`huaico`, octubre de 2026) y se importó tal cual, sin agregar datos nuevos. **No está verificado fuente por fuente.**

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
| `eventos_hemeroteca_2026.csv` | INDECI-COEN, Informe de Emergencia N° 599 (19 de marzo de 2023), leído completo: el 12 de marzo de 2023 a las 17:44 se activaron Huaycoloro 1 y 2 y Río Seco 2, con afectación en Chaclacayo y Lurigancho-Chosica | 12 de marzo de 2023 (1 fecha verificada al revisar los mayores falsos positivos del modelo diario; ver `docs/07`) |
| `eventos_nuevos_2021_2026.csv` | Prensa (Andina, La República, Infobae, Trome, El Peruano) | 2023 a 2026 |

Solo se registró una fecha cuando alguien leyó una fuente que da el día. Lo que no se pudo confirmar quedó fuera: los detalles están en las notas de investigación, que no forman parte de este repositorio. Los años 1990 a 1997, 1999 a 2008, 2010 a 2011 y 2021 a 2022 siguen sin eventos documentados, lo que no prueba que no los hubo.

Las filas del observatorio son **registros por distrito**: la mayoría no dice qué quebrada se activó (`(sin quebrada)`) y el tipo «Huayco/Alud» puede incluir deslizamientos o inundaciones mal clasificados. Se dejaron en confianza media y con la licencia de su origen en `fuente` (DesInventar: uso libre con atribución; SINPAD: información pública).

Dudas conocidas: el evento de Chosica de febrero de 2015 fue el lunes 9 según la prensa (el IGP dice el 10); el de 1998 aparece el 24 (IGP) y el 25 y 26 (Valverde); algunas filas de 2019 son crecidas de agua que Defensa Civil no consideró huaico; las filas de 2017 de la Municipalidad no dicen qué quebrada se activó cada día.

## `cuencas.geojson`

124 cuencas de 0,4 km² o más que drenan al Rímac y a Santa Eulalia entre Huachipa y Ricardo Palma (lon -76,90 a -76,52, lat -12,02 a -11,80). Se generan con `uv run delimitar-quebradas` desde Copernicus GLO-30 (30 m, reproyectado a UTM 18S) con pysheds: el cauce del Rímac y de Santa Eulalia (OSM) se hunde 30 m para que el flujo siga el río real, se rellenan depresiones, y cada afluente que llega al río es una cuenca, hasta la confluencia. Campos: `slug`, `nombre` (vacío si no se pudo ubicar), `ubicacion` (`referencia` o `sin_nombre`), `area_km2`, `z_min_m`, `z_max_m`, `z_media_m`, `relieve_m`, `pendiente_media_pct`, `longitud_cauce_km` (cauce más largo), `pendiente_cauce_pct`, `pendiente_cauce_1085_pct` (Taylor-Schwarz), `melton` (relieve / raíz del área), `indice_forma` (A/L²), `compacidad` (Gravelius), `edificios_1km` (edificaciones OSM a ≤1 km de la desembocadura y fuera de toda cuenca: proxy de exposición en el cono, no un censo; OSM no cubre todo por igual) y el punto de salida.

**Validación contra valores publicados** (la cuenca llega al río, unos 0,5 km² más que hasta el ápice del cono): Quirio 10,0 km² (9 a 10 de referencia), Pedregal 9,8 (9,6 a 10), Los Laureles 9,05 (9), Chacrasana 4,99 (IGP 2020: 4,7; +6 %), La Ronda 8,83 (8,9) y Barba Blanca 3,2 (3,5; -9 %). Río Seco: la cuenca que lleva ese nombre en OSM (Ñaña) da 194 km², pero el «Río Seco» del IGP 2020 (167 km²) está en Carabayllo, otra cuenca: **no se pueden comparar** y el nombre queda por confirmar. Las cuencas de menos de 2 km² están en el límite de lo que resuelve el DEM.

## `quebradas_referencias.csv`

Nombre, alias y, cuando se conoce, un punto dentro de la cuenca. Una cuenca solo toma nombre si el punto cae dentro (o a menos de 150 m); si hay varias candidatas, gana la que cae estrictamente dentro y, si la fila trae `area_ref_km2`, la de área más cercana. Hoy hay 22 cuencas con nombre, por cuatro vías:

- **Puntos del proyecto previo (INGEMMET)**: Quirio, Pedregal, Los Laureles.
- **Informe del IGP 2020** (CENEPRED/SIGRID 13867, §6, coordenadas UTM 18S): Chacrasana, La Ronda y Barba Blanca, cada una con un área parecida a la publicada.
- **Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2** ([SIGRID 16316](https://sigrid.cenepred.gob.pe/sigridv3/documento/16316)): vértices UTM 18S de la faja marginal de cada quebrada, que cae entera dentro de una cuenca: California (71 de 71 vértices), Corrales (25 de 25), Huáscarán (172 de 172), Santa Inés (106 de 106), Cobián (108 de 108), Yanacoto (35 de 35), Vallecito (78 de 78) y Cusipata (196 de 218). Esta fuente también **confirma de forma independiente** a Quirio, Pedregal, Chacrasana y La Ronda, y a Los Cóndores: sus 321 vértices (y los 280 hitos de la ANA, RD 0656-2022-ANA-AAA.CF) caen dentro de la cuenca de Los Laureles, que es la misma.
- **Resoluciones de faja marginal de la ANA** (SIGRID; las de 2015-2016 son imágenes y se leyeron con OCR): Santo Domingo (RD 1156-2025; puntos de campo a 0-53 m de una cuenca de 3,7 km²), La Cantuta (RD 075-2016, RD 0609-2025; la faja en el abanico queda a unos 165 m de la cuenca de 14 km², confianza media), Cupiche (RD 079-2016; 30 de 30 puntos en una cuenca de 9,2 km²) y Corrales-Rayos del Sol (RD 2071-2015: la ANA la delimita como una sola quebrada; sus puntos caen en la cuenca de 1,25 km²).
- **Río Seco** (desembocadura de OSM) es dudosa: ver arriba.

Carossio (0,55 km²), La Libertad (0,60), Mariscal Castilla (0,88) y La Cantuta (0,90) solo aparecen con el umbral de 0,4 km²: sus vértices (Ordenanza 2542, ANA RD 075-2016 y RD 077-2016 leídas con OCR, y el Acuerdo de Concejo 010-2016/CDL para Carossio) caen enteros dentro de ellas. Siguen sin asignar Cashahuacra (solo un punto aproximado de OSM), Huampaní y las demás. El informe INGEMMET A6680 se pasó por OCR y solo trae mapas, sin coordenadas. **Para mejorar el filtro, lo más útil es completar las filas `sin_ubicar`**: el ranking se recalcula solo.

## Ranking de quebradas para El Niño

`uv run filtro-quebradas` escribe tres archivos:

- `ranking_quebradas_nino.csv`: las 121 cuencas de hasta 50 km². Columnas físicas, `fisica` (0 a 100), activaciones por temporada Niño y no Niño, tasa de temporadas Niño con activación con intervalo de 80 % (Jeffreys) y `nivel`.
- `analogos_resultados.csv`: capítulo 20. Logística L2 contra análogos (constante y lineal) con 11, 6 y 3 variables: AP y AUC dejando una temporada fuera, p95 de 2 000 mundos nulos, valor de p y configuración elegida. Lo escribe `analogos-informe`.
- `temporadas_nino.csv`: las 45 temporadas 1982 a 2026 con ONI, ICEN, Niño 1+2 y las marcas. Temporada = diciembre a abril con el año de enero (noviembre y diciembre cuentan para la siguiente). **Niño global**: ONI medio de DJF, JFM y FMA ≥ +0,5 °C (NOAA). **Niño costero**: el ICEN oficial del ENFEN/IGP, es decir, un evento de la lista del IGP que cubre al menos dos de febrero, marzo y abril, o, para los años posteriores a la lista, ICEN medio de enero a abril ≥ +0,4 °C (umbral del ENFEN para condición cálida débil). Una temporada es Niño si cumple cualquiera de las dos. Son 22 temporadas: 1983, 1987, 1992, 1993, 1995, 1997, 1998, 2002, 2003, 2005, 2008, 2010, 2012, 2015, 2016, 2017, 2019, 2020, 2023, 2024, 2025 y 2026; incluye eventos débiles. Los umbrales se fijaron antes de mirar los huaicos. La primera versión usaba un proxy (anomalía Niño 1+2 ≥ +1,0 °C, 15 temporadas); sigue en la columna `nino_costero_n12` como sensibilidad. La de 2009 **no** cuenta: fue La Niña hasta que el Niño se formó a mitad de año (el evento costero de 2009 va de mayo a septiembre).
- `validacion_dejar_un_nino_fuera.csv`: ver abajo.

**Niveles** (regla fija, sin ajustar con los eventos): 1 activada en 2 o más temporadas Niño; 2 en una; 3, 4 y 5 sin historial ubicado según el tercio (alto, medio, bajo) de la susceptibilidad física; 6 menos de 2 km², no evaluable. La susceptibilidad física es el promedio de los percentiles de Melton, pendiente del cauce (10 a 85 %) y pendiente media entre las cuencas de 2 a 50 km², sin pesos. Dentro de un nivel se ordena por la tasa y luego por la física. Hoy 19 cuencas están en los niveles 1 y 2.

**Historial.** De 150 fechas de huaico con día exacto y confianza no baja, 48 se ubican en una cuenca, 18 nombran una quebrada que no se pudo ubicar y 84 no dicen cuál. «Sin historial ubicado» no es «nunca se activó».

**Qué dicen los datos.**
- Con cualquier quebrada, 17 de 22 temporadas Niño tienen alguna fecha catalogada contra 10 de 23 sin Niño; la mediana de días por temporada es 2,5 contra 0 (Fisher p = 0,033; Mann-Whitney p = 0,009). Con el proxy anterior (15 temporadas) el contraste era mucho más débil (p = 0,33 y 0,08): la definición oficial del ICEN separa mejor, pero esa definición se eligió porque es la oficial, no por el resultado.
- Contando las quebradas ubicadas **activas por temporada** (un número por temporada, para que quebradas que se activan juntas no inflen la evidencia), las temporadas Niño tienen en promedio 3,1 contra 0,5 las demás (1983 a 2026; Mann-Whitney p = 0,004) y 4,4 contra 0,7 desde 2009 (p = 0,015). Pero casi todo viene de 2015, 2017, 2019 y 2023, años de mucha cobertura de prensa; antes de 2009 solo 1983, 1987 y 1998 tienen registros.
- Temporadas Niño con activación (de 22) y sin Niño (de 23): Pedregal 6 y 3, Quirio 6 y 2, Chacrasana 5 y 0, Los Laureles 5 y 1, Huáscarán 5 y 0, California 5 y 0, Carossio 5 y 0, Corrales 5 y 1, Santo Domingo 4 y 0, La Ronda 4 y 1, Mariscal Castilla 4 y 1, La Libertad 3 y 0, Yanacoto 3 y 0, Cupiche 2 y 0, Cusipata 2 y 0, La Cantuta 2 y 1, Barba Blanca 1 y 0, Vallecito 1 y 0 y Huampaní 1 y 0.
- **La susceptibilidad física no discrimina.** Dejando un Niño fuera, su percentil medio en las 13 quebradas evaluadas (0 = la más susceptible, 50 = azar) es: Barba Blanca 13, Cupiche 30, Santo Domingo 30, La Ronda 35, Yanacoto 37, Chacrasana 41, Pedregal 50, Quirio 56, Los Laureles 63, Huáscarán 65, California 67, Cusipata 69, Vallecito 74. Solo Barba Blanca está bien arriba. Además, entre las 19 quebradas con alguna activación, los días de activación se correlacionan con las edificaciones cerca de la desembocadura (Spearman +0,70, p < 0,01) y no con Melton (-0,11) ni con la pendiente del cauce (-0,14): el catálogo sigue a la gente, no al terreno. No se reajustaron pesos.

## Modelo jerárquico por quebrada (`modelo_quebradas.py`)

Siguiendo el informe de métodos (inferencia sin publicación para Lima): las temporadas con al menos un día de huaico de cada quebrada siguen `P(activa) = 1 - exp(-λ_i · ρ^Niño)`, con `λ_i ~ Gamma` y `log λ_i = μ0 + γ·física + δ·exposición`. `ρ` es **una razón de tasas común** a todas las quebradas (prior ancho, 0,14 a 7,4 al 95 %); la base sin Niño se mantiene. La exposición es el logaritmo de las edificaciones de OSM cerca de la desembocadura: no mide peligro sino cuánto se reporta. Se usa la versión por temporadas (binomial) y no por días, porque los días se agrupan (23 en 2017) y inflarían la certeza. `uv run modelo-quebradas` escribe `parametros_modelo_quebradas.csv`, `contraste_temporadas_nino.csv`, `ranking_bayes_quebradas_nino.csv` (rango posterior, P(top-5)), `ranking_bayes_quebradas_nino_sin_exposicion.csv` (lo mismo con el efecto de reporte neutralizado) y dos validaciones.

- **ρ ≈ 4,7** (IC 80 % 3,0 a 7,8) con las temporadas desde 2009 (11 Niño, 7 sin Niño) y ≈ 5,9 (4,1 a 8,7) desde 1983. Es la razón de tasas con todas las quebradas juntas; como las quebradas se activan juntas, el contraste por temporada de arriba es la evidencia más honesta (p = 0,004 a 0,015). No existe un odds ratio publicado para Lima con el que compararlo, y Chosica también se activó sin Niño fuerte (1987 en parte, 2009, 2012).
- **γ (física) ≈ 0,0 a +0,1 (IC 80 % incluye 0)**: sin efecto. **δ (exposición) ≈ +0,25 a +0,35** (positivo con probabilidad 0,83 a 0,91): más edificios, más reportes.
- **Dejando una quebrada fuera** (predecir los conteos de una quebrada nueva, 24 veces): el Niño mejora el log score en 14 de 24 quebradas contra el modelo sin Niño (+12,8 en total); la exposición suma poco (+0,3, 17 de 24) y la física nada (0,0). El «bloque de quebradas» del informe sí es evaluable ahora, pero solo mide qué tan bien se predicen quebradas ya conocidas.
- **Dejando un episodio Niño fuera** (predecir qué quebradas se activan en temporadas retenidas, desde 2009): log score medio -0,350 con Niño, -0,379 sin Niño; Brier 0,104 contra 0,110. Con física o exposición nada mejora (-0,350 a -0,351). Falla en las temporadas sin Niño con activaciones y en Niños sin activaciones.
- **Ranking.** Con las 24 quebradas con historial el rango mediano en una temporada Niño es: Los Laureles 2, Pedregal 3, Quirio 3, Chacrasana 5, Mariscal Castilla 7, California 8, Corrales 9, La Ronda 9, Huáscarán 9, Carossio 9, Yanacoto 11, La Libertad 13, Santo Domingo 19 (rangos 10-90 % anchos, p. ej. 1 a 7 para Pedregal). Las cuencas sin historial ubicado conservan solo el prior: **no se pueden ordenar con estos datos** (P(top-5) < 0,01 no quiere decir que sean seguras).

Ventana principal: temporadas desde 2009, por cobertura más consistente (INDECI/SINPAD y prensa); 1983 queda como sensibilidad. La elección se fijó por la cobertura documental, no por el resultado. No se usó código de terceros (el repositorio de Arango et al. es GPL-3.0+ y su compatibilidad con la AGPL no está verificada).

## Licencia y atribución

Los eventos son hechos citados de INDECI, CENEPRED, PREDES y prensa; cada fila conserva su `fuente`. Las cuencas son un derivado de Copernicus DEM: © Unión Europea / ESA, con atribución. Ver [DATOS.md](../DATOS.md).
