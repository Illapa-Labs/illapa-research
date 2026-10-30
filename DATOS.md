# Datos y atribución

La licencia AGPL de este repositorio cubre el **código**, no los datos. `descargar-datos` solo baja fuentes con licencia clara; cada descarga queda registrada en `datos/MANIFIESTO.json`. Revisión del 29 de octubre de 2026. Este proyecto no es el dueño de estos datos ni los garantiza.

| Dato | Fuente | Licencia | Atribución |
|---|---|---|---|
| Ríos y departamentos | [Natural Earth](https://www.naturalearthdata.com) | Dominio público | No se exige |
| Ríos y quebradas (Chaclacayo a Chosica) | [OpenStreetMap](https://www.openstreetmap.org/copyright), vía Overpass | ODbL 1.0 | "© colaboradores de OpenStreetMap". Una base derivada que se publique debe seguir bajo ODbL |
| Lluvia horaria y humedad del suelo desde 1983 (2 puntos) | [Open-Meteo](https://open-meteo.com) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com" |
| Lluvia diaria histórica | [Open-Meteo](https://open-meteo.com) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com" |

| Eventos y cuencas del piloto (`catalogo/`) | Proyecto previo `huaico`; hechos de INDECI, CENEPRED, PREDES y prensa | Hechos citados con su fuente; sin verificar fila por fila | Cada fila conserva su `fuente` |
| Cronología de huaicos 1983–2017 (`catalogo/eventos_igp.csv`) | IGP (2023), *Análisis y evaluación histórica de precipitaciones en Chaclacayo, Chosica y áreas aledañas*, que cita a El Comercio, La República y PREDES | Informe público; se copian solo fechas, lugares y datos básicos con su cita | Citar el informe del IGP y el diario de cada fila |
| Fechas de huaicos (otros `eventos_*.csv`) | Tesis UNFV (2018), informes COEN-INDECI, INDECI 1998, prensa peruana | Hechos citados con su fuente; no se copia texto de los artículos | Cada fila cita su fuente |
| Fechas de huaicos del observatorio ENSO (`catalogo/eventos_observatorio_enso.csv`) | [PillB/observatorio-enso-peru](https://github.com/PillB/observatorio-enso-peru) (código MIT), que recopila DesInventar Sendai (UNDRR / OSSO), INDECI SINPAD y prensa | DesInventar: uso libre con atribución. SINPAD: información pública (Ley 27806). Prensa: solo titular y fecha. Se descartaron las filas del IDMC (CC BY-NC-SA) | Citar al observatorio y la fuente de cada fila |
| Polígonos de cuenca (`catalogo/cuencas.geojson`) | Derivados de [Copernicus DEM GLO-30](https://registry.opendata.aws/copernicus-dem/), teselas S12 y S13 W077, bajadas del bucket público de AWS (`descargar-datos --solo copernicus-dem`) | Uso libre con atribución | © Unión Europea / ESA |
| Edificaciones (centros) para el proxy de exposición | [OpenStreetMap](https://www.openstreetmap.org/copyright), vía Overpass (`--solo osm-edificios`). La cobertura es desigual | ODbL 1.0 | "© colaboradores de OpenStreetMap". Una base derivada que se publique debe seguir bajo ODbL |
| ICEN oficial y lista de eventos El Niño costero | [IGP](http://met.igp.gob.pe/elnino/indices.html) / ENFEN (`--solo igp-icen`) | Datos públicos del IGP, sin licencia explícita: se citan | Instituto Geofísico del Perú y ENFEN |
| Índices E y C mensuales (Takahashi et al. 2011) | [IGP](http://met.igp.gob.pe/variabclim/indices.html) (`--solo igp-ec`) | Datos públicos del IGP, sin licencia explícita: se citan; no van al espejo público | Instituto Geofísico del Perú; Takahashi et al. (2011) |
| Lluvia diaria CHIRPS v3 (tiempo de IMERG), medias de 5 cajas de 0,2°, noviembre a abril desde 1998 | [Climate Hazards Center](https://www.chc.ucsb.edu/data/chirps3) (`--solo chirps-v3`) | Dominio público y CC BY 4.0 | Funk et al. (2026), Scientific Data 13, 718 |
| Temperatura diaria del mar (Niño 1+2, costa de Perú y Lima) | [NOAA OISST v2.1](https://www.ncei.noaa.gov/products/optimum-interpolation-sst) vía ERDDAP de CoastWatch (`--solo noaa-oisst`) | Dominio público | NOAA OISST v2.1 |
| Variables diarias de ERA5 en 6 puntos (temperatura, humedad, presión, nubes, nieve, viento, suelo) | [Open-Meteo](https://open-meteo.com) (`--solo open-meteo-predictores`) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com" |
| Caudal diario del Rímac y Santa Eulalia (modelo) | [Open-Meteo / GloFAS](https://open-meteo.com/en/docs/flood-api) (`--solo open-meteo-caudal`) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com"; GloFAS (Copernicus Emergency Management Service) |
| Resumen diario de MERRA-2 (malla de 0,5° × 0,625°) en los 6 puntos de predictores | [NASA POWER](https://power.larc.nasa.gov/) (`--solo nasa-power`) | Datos abiertos de la NASA; cítese POWER | NASA POWER Project, MERRA-2 |
| Viento (u200, u850, v850) y humedad específica (850 hPa) de NCEP/NCAR Reanalysis 1 y OLR interpolado, promedios diarios sobre cajas fijas; índice OMI y SOI mensual | [NOAA PSL](https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.html) y [CPC](https://www.cpc.ncep.noaa.gov/data/indices/soi) (`--solo noaa-circulacion`) | Dominio público (gobierno de EE. UU.) | NOAA PSL / CPC |
| Índice MJO RMM diario | [Oficina de Meteorología de Australia](http://www.bom.gov.au/climate/mjo/) (`--solo bom-rmm`) | Datos públicos del BoM; se cita Wheeler & Hendon (2004) | Australian Bureau of Meteorology |
| Índices de El Niño: ONI (Niño 3.4) y anomalía Niño 1+2, mensuales | [NOAA Climate Prediction Center](https://www.cpc.ncep.noaa.gov/data/indices/) (`--solo noaa-enso`) | Dominio público (gobierno de EE. UU.) | NOAA Climate Prediction Center |
| Nombres y puntos de referencia de quebradas (`catalogo/quebradas_referencias.csv`) | Proyecto previo `huaico` (puntos de INGEMMET), informe del IGP 2020 (CENEPRED/SIGRID), Ordenanza N° 2542 de la Municipalidad de Lima (vértices de fajas marginales), resoluciones de la ANA y OpenStreetMap | Hechos citados con su fuente | Cada fila trae `fuente_referencia` |

## Fuera por ahora

- **SENAMHI** (avisos, estaciones, límites): no hay licencia de reutilización publicada. Falta pedir autorización por escrito a atencionalciudadano@senamhi.gob.pe.
- **INEI** (Censo 2017): condiciones por verificar.
- **Modelos de elevación para hidrología**: solo se usa Copernicus GLO-30; revisar la licencia de cualquier otro antes de usarlo.
- **Coordenadas de las quebradas que faltan** (Carossio, La Cantuta, Santo Domingo, Cashahuacra...): salen de las resoluciones de faja marginal de la ANA en SIGRID y de informes del INGEMMET; se agregan a mano en `quebradas_referencias.csv`.

## Espejo en Hugging Face

Las APIs gratuitas (sobre todo Open-Meteo) limitan las llamadas por hora y por día: reconstruir `datos/` desde las fuentes originales puede tardar horas. Para no repetirlo hay una copia pública en [renzoedu25/illapa-research-datos](https://huggingface.co/datasets/renzoedu25/illapa-research-datos). `uv run --extra hf descargar-datos --desde-hf renzoedu25/illapa-research-datos` la baja; `--subir-hf USUARIO/REPO [--publico]` sube la propia (privada por defecto). Hace falta `hf auth login` una vez; el código nunca lee ni guarda el token.

Revisión de licencias del 30 de octubre de 2026, fuente por fuente:

| Fuente | ¿Se puede redistribuir? | Condición que va en la tarjeta |
|---|---|---|
| Copernicus DEM GLO-30 | Sí, uso libre | Texto de atribución de Copernicus (DLR / Airbus / UE / ESA) |
| NOAA (ONI, Niño 1+2, OISST) | Sí, dominio público | Citar a NOAA |
| NASA POWER | Sí, datos abiertos | Citar POWER / MERRA-2 |
| Open-Meteo (ERA5, ERA5-Land, GloFAS) | Sí: sus datos son CC BY 4.0 y permiten copiar y redistribuir con atribución | «Weather data by Open-Meteo.com»; Copernicus C3S y GloFAS. La API gratuita es solo no comercial: quien vuelva a pedirla debe respetarlo |
| OpenStreetMap (ríos, edificios) | Sí, bajo ODbL | © colaboradores de OpenStreetMap; una base derivada debe seguir bajo ODbL |
| IGP (ICEN y lista de eventos costeros) | **No se incluye**: no traen licencia explícita | Se bajan del IGP con `descargar-datos --solo igp-icen` |

La licencia AGPL cubre el código; cada archivo conserva la licencia de su fuente.

## Publicar datos derivados

Antes de subir un conjunto a Hugging Face u otro sitio, confirma que cada fuente que lo compone permite redistribuirlo, y publícalo con su licencia y atribución.
