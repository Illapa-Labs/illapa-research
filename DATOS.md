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
| Pronósticos de lluvia pasados (lead 0 a 3 días) de UKMO 10 km, JMA GSM, GFS y ECMWF IFS 0,25° sobre el valle del Rímac | [Open-Meteo previous runs](https://open-meteo.com/en/docs/previous-runs-api) (`descargar-datos --solo pronosticos-previous-runs`, opt-in) | CC BY 4.0; la API gratuita es solo no comercial; el modelo del UK Met Office va bajo CC BY-SA 4.0 | "Weather data by Open-Meteo.com" y el modelo de origen |
| Series de estaciones, avisos, umbrales y anomalías de lluvia del SENAMHI | [Observatorio Nacional del Tiempo, Agua y Clima](https://observatorio.senamhi.gob.pe/investigadores/), series públicas y capas WFS/WMS de IDESEP | Información pública y gratuita; uso con o sin fines de lucro con la leyenda del SENAMHI, sin presentarla como oficial y sin comercializarla ([términos](https://www.senamhi.gob.pe/?p=terminos-condiciones)); sin control de calidad | «Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad». Descarga con `descargar-datos --solo senamhi` (opt-in por tamaño y cortesía) |
| Pronósticos de lluvia, CAPE y agua precipitable de GEFSv12 (reforecast 2000-2019) en cajas del valle del Rímac | [NOAA GEFSv12 reforecast](https://registry.opendata.aws/noaa-gefs-reforecast/), AWS Open Data (`descargar-datos --solo gefs-reforecast`, opt-in: unos 100 GB leídos por rangos de bytes; solo se guardan CSV pequeños) | Datos abiertos de NOAA (atribuir; no insinuar respaldo) | NOAA/NCEP GEFS v12 reforecast (Hamill et al. 2022) |
| Polígonos de cuenca (`catalogo/cuencas.geojson`) | Derivados de [Copernicus DEM GLO-30](https://registry.opendata.aws/copernicus-dem/), teselas S12 y S13 W077, bajadas del bucket público de AWS (`descargar-datos --solo copernicus-dem`) | Uso libre con atribución | © Unión Europea / ESA |
| Edificaciones (centros) para el proxy de exposición | [OpenStreetMap](https://www.openstreetmap.org/copyright), vía Overpass (`--solo osm-edificios`). La cobertura es desigual | ODbL 1.0 | "© colaboradores de OpenStreetMap". Una base derivada que se publique debe seguir bajo ODbL |
| ICEN oficial y lista de eventos El Niño costero | [IGP](http://met.igp.gob.pe/elnino/indices.html) / ENFEN (`--solo igp-icen`) | Datos públicos del IGP, sin licencia explícita: se citan | Instituto Geofísico del Perú y ENFEN |
| Índices E y C mensuales (Takahashi et al. 2011) | [IGP](http://met.igp.gob.pe/variabclim/indices.html) (`--solo igp-ec`) | Datos públicos del IGP, sin licencia explícita: se citan; no van al espejo público | Instituto Geofísico del Perú; Takahashi et al. (2011) |
| Lluvia diaria de pluviómetros interpolados (CPC, 0,5°) en los 5 puntos de predictores, desde 1983 | [NOAA PSL](https://psl.noaa.gov/data/gridded/data.cpc.globalprecip.html) (`--solo cpc-lluvia`) | Dominio público | NOAA PSL, CPC Global Unified Gauge-Based Analysis of Daily Precipitation |
| Lluvia diaria satelital PERSIANN-CDR (0,25°), noviembre a abril desde 1983-84, en los 5 puntos | [NOAA NCEI](https://doi.org/10.7289/V51V5BWQ) (`--solo persiann-cdr`; ~6 500 archivos, no se baja por defecto) | Dominio público (NOAA NCEI CDR) | Ashouri et al. (2015), BAMS, doi:10.1175/BAMS-D-13-00068.1 |
| Lluvia diaria CHIRPS v3 (tiempo de IMERG), medias de 5 cajas de 0,2°, noviembre a abril desde 1998 | [Climate Hazards Center](https://www.chc.ucsb.edu/data/chirps3) (`--solo chirps-v3`) | Dominio público y CC BY 4.0 | Funk et al. (2026), Scientific Data 13, 718 |
| Temperatura diaria del mar (Niño 1+2, costa de Perú y Lima) | [NOAA OISST v2.1](https://www.ncei.noaa.gov/products/optimum-interpolation-sst) vía ERDDAP de CoastWatch (`--solo noaa-oisst`) | Dominio público | NOAA OISST v2.1 |
| Variables diarias de ERA5 en 6 puntos (temperatura, humedad, presión, nubes, nieve, viento, suelo) | [Open-Meteo](https://open-meteo.com) (`--solo open-meteo-predictores`) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com" |
| Caudal diario del Rímac y Santa Eulalia (modelo) | [Open-Meteo / GloFAS](https://open-meteo.com/en/docs/flood-api) (`--solo open-meteo-caudal`) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com"; GloFAS (Copernicus Emergency Management Service) |
| ERA5 y ERA5-Land leídos de los archivos de Open-Meteo en AWS (puntos que la API no entregó) | [Open-Meteo en AWS Open Data](https://registry.opendata.aws/open-meteo/) (`--solo era5-aws`, opt-in) | CC BY 4.0 (Open-Meteo); datos de Copernicus Climate Change Service, uso libre con atribución | «Weather data by Open-Meteo.com»; «contains modified Copernicus Climate Change Service information» |
| Resumen diario de MERRA-2 (malla de 0,5° × 0,625°) en los 6 puntos de predictores | [NASA POWER](https://power.larc.nasa.gov/) (`--solo nasa-power`) | Datos abiertos de la NASA; cítese POWER | NASA POWER Project, MERRA-2 |
| Viento (u200, u850, v850) y humedad específica (850 hPa) de NCEP/NCAR Reanalysis 1 y OLR interpolado, promedios diarios sobre cajas fijas; índice OMI y SOI mensual | [NOAA PSL](https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.html) y [CPC](https://www.cpc.ncep.noaa.gov/data/indices/soi) (`--solo noaa-circulacion`) | Dominio público (gobierno de EE. UU.) | NOAA PSL / CPC |
| Índice MJO RMM diario | [Oficina de Meteorología de Australia](http://www.bom.gov.au/climate/mjo/) (`--solo bom-rmm`) | Datos públicos del BoM; se cita Wheeler & Hendon (2004) | Australian Bureau of Meteorology |
| Índices de El Niño: ONI (Niño 3.4) y anomalía Niño 1+2, mensuales | [NOAA Climate Prediction Center](https://www.cpc.ncep.noaa.gov/data/indices/) (`--solo noaa-enso`) | Dominio público (gobierno de EE. UU.) | NOAA Climate Prediction Center |
| Nombres y puntos de referencia de quebradas (`catalogo/quebradas_referencias.csv`) | Proyecto previo `huaico` (puntos de INGEMMET), informe del IGP 2020 (CENEPRED/SIGRID), Ordenanza N° 2542 de la Municipalidad de Lima (vértices de fajas marginales), resoluciones de la ANA y OpenStreetMap | Hechos citados con su fuente | Cada fila trae `fuente_referencia` |
| Estaciones del SENAMHI cercanas a Chosica (solo metadatos, `catalogo/senamhi_estaciones_cercanas.csv`) | [Observatorio del SENAMHI](https://observatorio.senamhi.gob.pe/investigadores/) | Metadatos de estaciones; citar «Información recopilada y trabajada por el SENAMHI» | SENAMHI |

## Fuera por ahora

- **INEI** (Censo 2017): condiciones por verificar.
- **Modelos de elevación para hidrología**: solo se usa Copernicus GLO-30; revisar la licencia de cualquier otro antes de usarlo.
- **Coordenadas de las quebradas que faltan** (Carossio, La Cantuta, Santo Domingo, Cashahuacra...): salen de las resoluciones de faja marginal de la ANA en SIGRID y de informes del INGEMMET; se agregan a mano en `quebradas_referencias.csv`.

## Espejo en Hugging Face

Las APIs gratuitas (sobre todo Open-Meteo) limitan las llamadas por hora y por día: reconstruir `datos/` desde las fuentes originales puede tardar horas. Para no repetirlo hay una copia pública en [renzoedu25/illapa-research-datos](https://huggingface.co/datasets/renzoedu25/illapa-research-datos). `uv run --extra hf descargar-datos --desde-hf renzoedu25/illapa-research-datos` la baja; `--subir-hf USUARIO/REPO [--publico]` sube la propia (privada por defecto). Hace falta `hf auth login` una vez; el código nunca lee ni guarda el token.

**Qué contiene el espejo:** todo lo que usan los 16 cuadernos de `notebooks/`, salvo los índices del IGP (ICEN, E y C) y el RMM de la BoM, que no traen licencia explícita y se bajan con `descargar-datos --solo igp-icen igp-ec bom-rmm`. Incluye la serie PISCOp del valle (`pisco/rimac_diario.csv`), las respuestas crudas públicas del SENAMHI (`senamhi/cache`, `senamhi/ogc`, `senamhi/datosabiertos`, con su leyenda), y del reforecast GEFS solo la serie reducida a cuatro cajas (`gefs_reforecast/gefs_corridas.csv.gz`, 5 MB): los archivos originales de NOAA (unos 100 GB) no se usan ni se guardan. Las fuentes opcionales (INGEMMET, CENEPRED, INDECI, pronósticos de Open-Meteo) se piden con `descargar-datos --solo <id>`.

Revisión de licencias del 30 de octubre de 2026, fuente por fuente:

| Fuente | ¿Se puede redistribuir? | Condición que va en la tarjeta |
|---|---|---|
| Copernicus DEM GLO-30 | Sí, uso libre | Texto de atribución de Copernicus (DLR / Airbus / UE / ESA) |
| NOAA (ONI, Niño 1+2, OISST) | Sí, dominio público | Citar a NOAA |
| NASA POWER | Sí, datos abiertos | Citar POWER / MERRA-2 |
| Open-Meteo (ERA5, ERA5-Land, GloFAS) | Sí: sus datos son CC BY 4.0 y permiten copiar y redistribuir con atribución | «Weather data by Open-Meteo.com»; Copernicus C3S y GloFAS. La API gratuita es solo no comercial: quien vuelva a pedirla debe respetarlo |
| OpenStreetMap (ríos, edificios) | Sí, bajo ODbL | © colaboradores de OpenStreetMap; una base derivada debe seguir bajo ODbL |
| NOAA GEFSv12 reforecast (series reducidas a cajas) | Sí, datos abiertos de NOAA | Citar a NOAA (Hamill et al. 2022) |
| Pronósticos de Open-Meteo (previous runs y archivo del UK Met Office) | Sí: CC BY 4.0; el archivo del UKMO es CC BY-SA 4.0 (compartir igual en derivados) | «Weather data by Open-Meteo.com» y UK Met Office |
| PISCOp v3.0 (serie diaria sobre el valle del Rímac) y tablas del SENAMHI | Sí, con la leyenda del SENAMHI, sin comercializar ni presentar como oficial | Leyenda del SENAMHI |
| IGP (ICEN y lista de eventos costeros) | **No se incluye**: no traen licencia explícita | Se bajan del IGP con `descargar-datos --solo igp-icen` |
| INGEMMET (GEOCATMIN: peligros geológicos, zonas críticas) | **No se espeja el crudo**: licencia para uso no comercial con obras derivadas permitidas | Citar a INGEMMET como fuente original; solo tablas derivadas pequeñas en `catalogo/`. `descargar-datos --solo datos-del-estado` |
| INDECI (SINPAD, emergencias desde 2019) | Solo tablas derivadas en `catalogo/`; información pública (Ley 27806), sin licencia explícita | Citar al INDECI; no es un registro completo de huaicos |
| CENEPRED (SIGRID: FEN 2027), ANA y ANIN | Solo listas de quebradas priorizadas (prensa) y tablas pequeñas; no se espeja | Citar a cada entidad; los servicios con token no se usan |

La licencia AGPL cubre el código; cada archivo conserva la licencia de su fuente.

## Publicar datos derivados

Antes de subir un conjunto a Hugging Face u otro sitio, confirma que cada fuente que lo compone permite redistribuirlo, y publícalo con su licencia y atribución.
