# 01 · Cuencas y ubicación de quebradas

## Pregunta

¿Qué cuencas drenan al Rímac y al Santa Eulalia entre Huachipa y Ricardo Palma, cuáles son sus atributos físicos y a cuál corresponde cada nombre de quebrada que aparece en el catálogo de huaicos?

## Datos

- Copernicus DEM GLO-30 (30 m), teselas S12 y S13 W077, del bucket público de AWS (`descargar-datos --solo copernicus-dem`). © Unión Europea / ESA.
- Cauce del Rímac y del Santa Eulalia de OpenStreetMap (ODbL), para hundirlo en el DEM.
- Edificaciones de OpenStreetMap (centros), para un indicador de exposición (cobertura desigual).
- Ubicación de nombres: informe del IGP 2020 (CENEPRED/SIGRID 13867), Ordenanza N° 2542 de la Municipalidad de Lima (SIGRID 16316), resoluciones de faja marginal de la ANA en SIGRID (varias de 2015-2016 son imágenes y se leyeron con OCR), Acuerdo de Concejo 010-2016/CDL (El Peruano), INGEMMET A7458, y los puntos del proyecto previo `huaico` (INGEMMET).

## Método

1. Mosaico de las dos teselas, recorte lon -77,0 a -76,0 y lat -12,15 a -11,0, reproyección a UTM 18S a 30 m.
2. Se hunde 30 m el cauce del Rímac y del Santa Eulalia (buffer de 30 m) para que el flujo siga el río real: sin eso, los afluentes se juntaban al río casi 1 km aguas abajo de su confluencia verdadera.
3. `pysheds`: relleno de depresiones, resolución de planos, dirección D8 y acumulación. `pysheds` 0.5 usa `numpy.in1d`, que NumPy 2.5 quitó: `quebradas.py` lo reemplaza por `isin`.
4. Red del Rímac: celdas con más de 200 km² que desembocan en la misma boca. Cada celda de afluente de 0,4 km² o más cuyo vecino aguas abajo es del río (dentro de lon -76,90 a -76,52 y lat -12,02 a -11,80) es la salida de una cuenca. El etiquetado es por doblado de punteros, sin una pasada por cuenca.
5. Atributos por cuenca: área, relieve, pendiente media, cauce más largo, pendiente del cauce (extremos y 10-85 %), Melton, índice de forma, compacidad y edificios a ≤1 km de la salida y fuera de toda cuenca.

El umbral de 0,4 km² se bajó desde 1 km² cuando las coordenadas de Carossio, La Libertad, Mariscal Castilla y La Cantuta mostraron que eran cuencas de 0,55 a 0,90 km². Las cuencas de menos de 2 km² se listan pero no reciben puntaje físico (un DEM de 30 m no las resuelve).

## Validación contra valores publicados

Las áreas llegan al río, unos 0,5 km² más que hasta el ápice del cono. Quirio 10,0 km² (9 a 10 de referencia), Pedregal 9,8 (9,6 a 10), Los Laureles 9,05 (9), Chacrasana 4,99 (IGP 2020: 4,7), La Ronda 8,83 (8,9) y Barba Blanca 3,2 (3,5). El «Río Seco» del IGP (167 km²) está en Carabayllo; el de OSM (Ñaña, 194 km²) es otra cuenca y no se puede comparar.

## Ubicación de nombres

Una cuenca toma un nombre solo con evidencia: un punto de referencia dentro de ella o los vértices de una faja marginal que caen enteros dentro. La Ordenanza 2542 confirmó de forma independiente a Quirio, Pedregal, Chacrasana, La Ronda y Los Cóndores. Los Cóndores y Los Laureles son **la misma cuenca** (321 de 321 vértices y 280 de 280 hitos de la ANA, RD 0656-2022). «Corrales» y «Rayos del Sol» también: la ANA los delimita como una sola quebrada.

| Quebrada | Cuenca | km² | Salida (lon, lat) | Vía | Evidencia |
|---|---|---|---|---|---|
| Río Seco | `rio-seco` | 194.55 | -76.8835, -11.9529 | desembocadura_osm | OpenStreetMap: la quebrada Río Seco termina aquí en el Rímac |
| Cobián | `cobian` | 1.79 | -76.8245, -11.9878 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 108 de 108 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 1,79 km2 |
| Vallecito | `vallecito` | 15.75 | -76.8052, -11.9825 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 78 de 78 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 15,75 km2 |
| Huascarán | `huascaran` | 9.75 | -76.7966, -11.9803 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 172 de 172 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 9,75 km2 |
| Cusipata | `cusipata` | 8.39 | -76.7779, -11.9753 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 196 de 218 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 8,39 km2 |
| Santa Inés | `santa-ines` | 2.60 | -76.7679, -11.9735 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 106 de 106 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 2,6 km2 |
| Los Laureles | `los-laureles` | 9.05 | -76.7577, -11.9711 | punto_en_cauce | Proyecto previo huaico (INGEMMET): punto de referencia. Los Cóndores es la misma cuenca: los 280 hitos de la faja marginal de la ANA (RD 0656-2022-ANA-AAA.CF, UTM 18S) caen dentro de ella |
| Chacrasana | `chacrasana` | 4.99 | -76.7401, -11.9644 | punto_utm_igp | IGP 2020 (CENEPRED/SIGRID 13867), §6: UTM 18S 310218 E 8677071 N; área 4,7 km2 |
| Yanacoto | `yanacoto` | 4.85 | -76.7309, -11.9561 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 35 de 35 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 4,85 km2 |
| California | `california` | 8.34 | -76.7301, -11.9558 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 71 de 71 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 8,34 km2 |
| Quirio | `quirio` | 10.02 | -76.7083, -11.9446 | punto_en_cauce | Proyecto previo huaico (INGEMMET): punto de referencia del huayco de Quirio |
| La Cantuta | `la-cantuta` | 0.90 | -76.7033, -11.9451 | faja_ana | ANA RD 075-2016 (SIGRID 6074, OCR; 25 de 25 puntos UTM 18S), RD 0609-2025 (SIGRID 19341) y Ordenanza N° 2542 (27 de 27 vértices) caen dentro de esta cuenca de 0,90 km2 (con el umbral de 1 km2 no aparecía) |
| Santo Domingo | `santo-domingo` | 3.71 | -76.7014, -11.9441 | faja_ana | ANA RD 1156-2025-ANA-AAA.CF (SIGRID 19947): puntos de campo UTM 18S 314701 E 8679015 N, 314867 E 8678996 N y 315340 E 8678884 N, a 0-53 m de la cuenca de 3,71 km2 (la siguiente queda a 236 m) |
| Pedregal | `pedregal` | 9.82 | -76.7005, -11.9424 | punto_en_cauce | Proyecto previo huaico (INGEMMET): punto de referencia de la quebrada Pedregal |
| La Libertad | `la-libertad` | 0.60 | -76.6925, -11.9343 | faja_ana | Ordenanza N° 2542, anexo 2 (SIGRID 16316): 25 de 25 vértices UTM 18S dentro de esta cuenca de 0,60 km2 |
| Mariscal Castilla | `mariscal-castilla` | 0.88 | -76.6900, -11.9319 | faja_ana | Ordenanza N° 2542 (33 de 39 vértices) y ANA RD 077-2016 (SIGRID 6065, OCR; 33 de 37 puntos) dentro de esta cuenca de 0,88 km2 |
| La Ronda | `la-ronda` | 8.83 | -76.6861, -11.9273 | punto_utm_igp | IGP 2020 (CENEPRED/SIGRID 13867), §6: UTM 18S 317344 E 8680380 N (distrito de Ricardo Palma); área 8,9 km2 |
| Carossio | `carossio` | 0.55 | -76.6856, -11.9262 | faja_ana | Acuerdo de Concejo N° 010-2016/CDL (El Peruano), referencia UTM 18S 316230 E 8681389 N, y Ordenanza N° 2542 (15 de 15 vértices): dentro de esta cuenca de 0,55 km2 |
| Corrales | `corrales` | 1.25 | -76.6798, -11.9241 | vertice_ordenanza_2542 | Ordenanza N° 2542 de la Municipalidad de Lima, anexo 2 (SIGRID 16316): 25 de 25 vértices UTM 18S de la faja marginal caen dentro de una cuenca de 1,25 km2. ANA RD 2071-2015 (SIGRID 6062, OCR) delimita «Corrales-Rayos del Sol» como una sola quebrada: 10 de 10 puntos dentro de esta cuenca |
| Barba Blanca | `barba-blanca` | 3.20 | -76.6236, -11.8363 | punto_utm_igp | IGP 2020 (CENEPRED/SIGRID 13867), §6: UTM 18S 323250 E 8690608 N (distrito de Callahuanca); área 3,5 km2 |
| Cupiche | `cupiche` | 9.21 | -76.6114, -11.9142 | faja_ana | ANA RD 079-2016-ANA-AAA.CAÑETE-FORTALEZA (SIGRID 6061, OCR): 30 de 30 puntos UTM 18S dentro de la cuenca de 9,21 km2 (margen del Santa Eulalia) |

Siguen sin cuenca: Cashahuacra, Huampaní, Huascata, Huaycoloro, La Floresta. Cashahuacra tiene solo un punto aproximado de OSM (a 246 m de una cuenca de 15 km²). El informe INGEMMET A6680 (Rayos de Sol, Quirio, Cashahuacra) se pasó por OCR y solo trae mapas.

## Límites

- Una cuenca de 30 m puede unir o partir quebradas reales; los nombres con pocos vértices (Mariscal Castilla: 33 de 39) tienen la confianza más baja.
- «Sin cuenca» no es «no existe»: es que no hay coordenadas abiertas.
- Las áreas no son de la fuente oficial; son del DEM.

## Reproducir

```bash
uv run descargar-datos --solo copernicus-dem osm-aguas osm-edificios
uv run delimitar-quebradas
```
