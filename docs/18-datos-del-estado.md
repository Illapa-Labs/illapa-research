# 18 · Datos del Estado: INGEMMET, INDECI, CENEPRED, ANA y ANIN

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Ante una emergencia llama al 115 (INDECI).

Notebook: [`notebooks/14-datos-del-estado.ipynb`](../notebooks/14-datos-del-estado.ipynb). Código: `src/illapa_research/fuentes_estado.py` (pruebas en `tests/test_fuentes_estado.py`). Descarga opt-in: `uv run descargar-datos --solo datos-del-estado`.

## 1. Pregunta

El usuario preguntó por qué no teníamos datos de la ANA, la ANIN o el CENEPRED, y si los tienen. Se buscó qué publican esas entidades (y el INGEMMET y el INDECI, que las complementan) para las dos mayores limitaciones del proyecto: el catálogo de huaicos (82 de 148 fechas sin quebrada, 1999-2008 casi vacío) y las quebradas con nombre (faltaban Huampaní, Santa María, Cashahuacra...).

## 2. Método y reglas

Navegador integrado y peticiones HTTP anónimas, una cada 1,5 s, un solo hilo, con caché en `datos/<fuente>/` (ignorado por git). **Sin cuentas, sin credenciales y sin tokens:** cuando un servicio ArcGIS responde «Token Required» el cliente se detiene (`PermissionError`) y se documenta. El servidor del INGEMMET envía una cadena de certificados incompleta; se usa el almacén de certificados del sistema (`truststore`) y nunca `verify=False`. Todo es información pública del Estado (Ley 27806); se registran además las condiciones de uso de cada una.

## 3. Inventario por entidad

| Entidad | Qué hay | Acceso sin cuenta (probado el 30-10-2026) | Condiciones |
|---|---|---|---|
| **INGEMMET** (GEOCATMIN) | `SERV_PELIGROS_GEOLOGICOS`: inventario de peligros geológicos (1 433 puntos en la zona), otros peligros (230), zonas críticas (108), cartografía por franjas. `SERV_PERU_ALERTA`: zonas críticas (185), zonas críticas por activación de quebradas (14, con nombre de paraje), activación de quebrada (109 polígonos con nivel y fecha, de aviso vigente). `SERV_SUSCEPTIBLE_MOV_MASA_REGIONAL`. | Sí: `https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/<servicio>/MapServer/<capa>/query`. No pagina: se piden los `objectIds` y luego lotes. Las carpetas `GEOCATMIN_SOCIAL` y otras piden token. | [Licencia para uso no comercial](https://geocatminapp.ingemmet.gob.pe/complementos/Descargas/Licencia.html): se pueden usar los datos y hacer obras derivadas citando a INGEMMET como fuente original. No se espeja el crudo; solo tablas pequeñas con cita. |
| **INDECI** (SINPAD) | Lista pública de emergencias (136 305 registros de todo el país): código, peligro principal, departamento/provincia/distrito, fecha y hora, nivel, estado. Solo SINPAD v2.1: **desde 2019**. | Sí: `https://prod4.indeci.gob.pe/portal-sinpad/api/v1/public/emergencias?pageNumber=&pageSize=&fechaInicio=&fechaFin=&ubigeo=` (fechas `dd/MM/yyyy`). Antes de 2019 no devuelve nada. | Información pública; sin licencia explícita; se cita al INDECI. |
| **CENEPRED** (SIGRID) | Biblioteca de documentos (PDF y el «ámbito» de cada documento como polígono WKT dentro de su página pública). Servicios ArcGIS: `FEN/ER_NINO2027_BD` (susceptibilidad y riesgo por movimientos en masa por distrito) y `sectores/COEN_FEN_2027` (37 capas: puntos críticos 2027, intervenciones 2027, almacenes…). | Solo esos dos servicios. `Cartografia_Peligros`, `Cartografia_Riesgos`, `Informacion_CENEPRED`, `Elementos_Expuestos`, `prevaed` responden «Token Required» y **no se usaron** (el visor entrega a la página un token propio; copiarlo sería usar una credencial). | Información pública; se cita al CENEPRED. |
| **ANA** | Fajas marginales (resoluciones directoras en SIGRID; ya usadas en el capítulo 01), 755 puntos críticos y 12 barreras dinámicas (prensa). La capa de puntos críticos 2027 está en el servicio del COEN en SIGRID. | No se halló una API propia (`snirh` y otros dominios no responden o dan 404). | Información pública. |
| **ANIN** | Cartera de 13 quebradas del Rímac (prensa y Andina). `geo.anin.gob.pe` es una aplicación web sin API pública hallada. | Solo notas de prensa. | Información pública. |

## 4. Resultados

### 4.1 Ubicación de quebradas

- **Validación independiente.** De 80 puntos del INGEMMET que nombran una quebrada con nombre («Qda.», «Quebrada» o «Huayco»), **62 (78%) caen dentro de la cuenca que habíamos asignado**, 12 en otra cuenca (casi siempre el sector urbano de la desembocadura) y 6 fuera de toda cuenca. Los de Río Seco se explican porque hay otro «Río Seco» en Pachacámac; solo el punto «Quebrada Silencio, Quebrada Colca, Quebrada Río Seco» (-76,875; -11,952) cae en la nuestra. Tabla: `catalogo/ingemmet_validacion_nombres.csv`; los puntos: `catalogo/ingemmet_puntos_quebradas.csv`.
- **Cuencas nuevas con nombre** (regla de siempre: punto dentro de la cuenca): **Huampaní** (7 puntos «Huampaní Alto», incluida «Qda. Huampani Alto», dentro de una cuenca de 1,08 km²; otros sectores de Huampaní caen en cuencas vecinas y no se asignaron), **La Laguna** (7,28 km²; «Quebrada La Laguna» y «Huayco de la Laguna»), **Carapongo** (12,02 km²; «Quebrada Carapongo») y **Señor de los Milagros** (0,45 km²; la ANA instala allí una barrera). Alias nuevos: **Rayito de Sol** = Corrales (el punto «Qda. Rayito de Sol» cae a 5 m de esa cuenca) y **Vizcachera** = Vallecito (4 puntos dentro).
- **Siguen sin cuenca:** Santa María (el huayco «Quebrada Santa María» cae en la cuenca de Yanacoto y «AAHH Yanacoto / Quebrada Santa María» en la de 1,15 km² vecina: ambigua), Cashahuacra (ningún punto del INGEMMET; la ANA instala dos barreras, «Cashahuacra 1» y «Cashahuacra 2»), Huascata, La Floresta (el punto del INGEMMET está en Ñaña y el catálogo la pone en Chaclacayo) y Chingolay (194 m fuera de una cuenca de 1,1 km²).
- **Puntos críticos 2027 del COEN** (capa pública de SIGRID): 28 en la zona, la mayoría tramos de río. Los de tipo quebrada: Huayco (Pascana III, Ricardo Palma), Guayabo (Corcona), Chingolay, Huayaringa 2 y Mariano Melgar 1 y 2 (Santa Eulalia), con población y viviendas expuestas. Hay coordenadas para ubicarlas en cuencas, pero no tienen historial en el catálogo, así que no se agregaron.

### 4.2 Catálogo de huaicos

- **SINPAD confirma el catálogo en 2019-2026.** Las 8 emergencias con peligro principal «HUAICO» de Lurigancho-Chosica y Chaclacayo ya estaban en nuestras fechas (2019-02-25 dos distritos, 2020-01-23, 2020-01-29, 2023-03-14, 2023-03-15, 2023-04-07 y 2026-10-02): recuperación 8 de 8. Ninguna fecha nueva en esos distritos.
- **Fechas nuevas verificadas (2):** 2025-02-19 y 2026-02-19, Callahuanca (valle de Santa Eulalia), en `catalogo/eventos_sinpad_2026.csv` con el número de emergencia. Tres huaicos más de Matucana (2024-01-31, 2024-04-01 y 2025-04-03) quedan fuera de la zona de estudio y de ese archivo. También se publican las emergencias de lluvia, inundación y movimientos en masa de 11 distritos (`catalogo/sinpad_emergencias_lluvia_zona.csv`, 182 filas) como contexto; no son todas huaicos.
- **Lo que NO se ganó:** 1999-2008 y 1981-2018 en general. SINPAD público empieza en 2019 y el inventario del INGEMMET trae como `FECHA` la del estudio (2003, 2008, 2021…), no la del evento; la columna `ANIO` de las zonas críticas parece el año de evaluación. Para esos años hay que pedir la base histórica (ver §5).

### 4.3 Listas oficiales de quebradas priorizadas frente a nuestro ranking

Rango mediano posterior en una temporada Niño (1 = la más propensa) del modelo del capítulo 03, para cada nombre oficial que tiene cuenca.

| Entidad | Quebrada oficial | Medida | Nuestra cuenca | Rango | P(top-5) |
|---|---|---|---|---|---|
| ANIN | La Libertad | obras (10 primeras, más de S/150 millones) | la-libertad | 13 | 0.09 |
| ANIN | Carosio | obras (10 primeras, más de S/150 millones) | carossio | 9 | 0.23 |
| ANIN | Mariscal Castilla | obras (10 primeras, más de S/150 millones) | mariscal-castilla | 7 | 0.34 |
| ANIN | Santo Domingo | obras (10 primeras, más de S/150 millones) | santo-domingo | 19 | 0.04 |
| ANIN | Rayito de Sol | obras (10 primeras, más de S/150 millones) | corrales | 9 | 0.22 |
| ANIN | Yanacoto | obras (10 primeras, más de S/150 millones) | yanacoto | 11 | 0.14 |
| ANIN | Chacrasana | obras (10 primeras, más de S/150 millones) | chacrasana | 5 | 0.51 |
| ANIN | La Ronda | obras (10 primeras, más de S/150 millones) | la-ronda | 9 | 0.21 |
| ANIN | Quirio | obras (10 primeras, más de S/150 millones) | quirio | 3 | 0.80 |
| ANIN | Pedregal | obras (10 primeras, más de S/150 millones) | pedregal | 3 | 0.81 |
| ANIN | La Laguna | diseño (se suman en septiembre) | la-laguna | 72 | 0.00 |
| ANIN | San Francisco Ñaña | diseño (se suman en septiembre) | — | — | — |
| ANIN | Vizcachera | diseño (se suman en septiembre) | vallecito | 39 | 0.01 |
| CENEPRED | Pedregal | se activan incluso con lluvias de menor intensidad | pedregal | 3 | 0.81 |
| CENEPRED | Quirio | se activan incluso con lluvias de menor intensidad | quirio | 3 | 0.80 |
| CENEPRED | Carapongo | se activan incluso con lluvias de menor intensidad | carapongo | 63 | 0.00 |
| CENEPRED | Santo Domingo | quebrada seca de Lima Este con exposición alta | santo-domingo | 19 | 0.04 |
| CENEPRED | Cusipata | quebrada seca de Lima Este con exposición alta | cusipata | 19 | 0.03 |
| CENEPRED | Huascarán | quebrada seca de Lima Este con exposición alta | huascaran | 9 | 0.25 |
| ANA | Huayaringa | barrera dinámica | — | — | — |
| ANA | Cupiche | barrera dinámica | cupiche | 69 | 0.00 |
| ANA | La Ronda | barrera dinámica | la-ronda | 9 | 0.21 |
| ANA | Señor de los Milagros | barrera dinámica | senor-de-los-milagros | 66 | 0.00 |
| ANA | Cashahuacra 1 | barrera dinámica | cashahuacra | — | — |
| ANA | Cashahuacra 2 | barrera dinámica | cashahuacra | — | — |
| ANA | Quirio | barrera dinámica | quirio | 3 | 0.80 |
| ANA | Los Cóndores 1 y 2 | priorizadas para barreras dinámicas y diques | los-laureles | 2 | 0.92 |

Coinciden Quirio, Pedregal, La Ronda y Chacrasana (rangos 3 a 10). Santo Domingo, Cusipata y las quebradas con historial nulo (La Laguna, Carapongo, Señor de los Milagros, Cupiche) quedan abajo en nuestro ranking por tener pocas activaciones reportadas, aunque las entidades las priorizan: el ranking mide historial documentado y no peligro absoluto.

## 5. Qué NO hay público y qué se podría pedir

| Qué | A quién (Ley 27806) | Para qué |
|---|---|---|
| Base histórica de emergencias del SINPAD anterior a 2019 (por distrito, peligro y fecha) | INDECI | Cubrir 1981-2018 y 1999-2008 del catálogo |
| Inventario de peligros del INGEMMET con fecha del evento y campos `F_EVENTO` completos | INGEMMET | Fechas por quebrada |
| Capas de peligro y riesgo de SIGRID (token) y la lista nominal de 755 puntos críticos | CENEPRED y ANA | Polígonos oficiales de quebradas y exposición |
| Expedientes y mapas de las 13 quebradas de la cartera | ANIN | Polígonos y proyectos |

## 6. Límites

- El inventario del INGEMMET es de estudios de campo, no un catálogo completo de eventos.
- Las listas de ANA, ANIN y CENEPRED vienen de notas de prensa; pueden estar incompletas (CENEPRED habla de unas 15 quebradas y nombra solo seis).
- SINPAD registra emergencias, no todos los huaicos; un huaico sin daños puede no estar.

## 7. Reproducir

```bash
uv run descargar-datos --solo datos-del-estado   # INGEMMET, CENEPRED FEN 2027 y SINPAD (moderado)
uv run python -m illapa_research.fuentes_estado   # lo mismo
```
