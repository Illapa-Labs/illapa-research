# 11 · Datos del SENAMHI: pluviómetros, umbrales, avisos y anomalías de los Niños

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide cuánto de las fechas de huaico del catálogo se explica con la lluvia observada y con los productos públicos del SENAMHI. Ante una emergencia llama al 115 (INDECI).

> **Fuente de los datos de este capítulo:** Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad. Fuente: SENAMHI, [Observatorio Nacional del Tiempo, Agua y Clima del Perú](https://observatorio.senamhi.gob.pe) y su GeoServer IDESEP. Los datos no tienen control de calidad.

Notebook: [`notebooks/11-senamhi.ipynb`](../notebooks/11-senamhi.ipynb). Código: [`src/illapa_research/senamhi.py`](../src/illapa_research/senamhi.py) y [`fuentes_opt_in.py`](../src/illapa_research/fuentes_opt_in.py); pruebas en `tests/test_senamhi.py` (sin red). Datos leídos el 30 de octubre de 2026.

## 1. Preguntas y teorías (escritas antes de mirar)

| | Teoría |
|---|---|
| T30 | Los pluviómetros de la cuenca media-alta detectan los días con huaico mejor que ERA5 |
| T31 | El pluviómetro del propio Chosica casi no mide la lluvia que activa las quebradas, pero que llueva algo en el pueblo ya separa los días |
| T32 | El nivel del río en Chosica concuerda solo en parte con el caudal de GloFAS |
| T33 | Las reglas oficiales de umbral de lluvia (`g_umbrales`) logran un POD parecido al de nuestros modelos al mismo número de días de alarma, con tanta alarma falsa como ellos |
| T34 | Los avisos meteorológicos históricos del GeoServer marcan los huaicos de 2020, pero con casi todos los días de lluvia como aviso |
| T35 | La anomalía de lluvia de los Niños del SENAMHI ordena los trimestres por días de huaico |
| T36 | Las capas de «activación de quebrada» permiten ubicar las quebradas que faltan (Cashahuacra, Huampaní, Santa María…) |

## 2. Qué hay y cómo se accede

**Portal** (`/investigadores`): 976 estaciones según su página, series en Excel/CSV, servicios espaciales WMS/WFS «de acceso libre» del GeoServer de IDESEP y una **API REST que exige una cuenta gratuita que el SENAMHI aprueba, con clave e IP registradas**. Aquí **no se usa la API REST ni se creó ninguna cuenta** (decisión del usuario si la solicita).

**Lo que sí se leyó, siempre sin credenciales, con 2 s de pausa, un hilo y caché local:**

1. Los endpoints anónimos que la propia página «Datos hidrometeorológicos» llama para cualquier visitante: catálogo de estaciones, meses con datos, lectura mensual y la serie diaria histórica del «Portal del investigador».
2. Los servicios WFS 2.0.0 del GeoServer `https://idesep.senamhi.gob.pe/geoserver/{espacio}/ows` (GeoJSON, `bbox`, `CQL_FILTER`, `count`, `propertyName`). El `GetCapabilities` declara `AccessConstraints: NONE` y `Fees: NONE`, y la página de servicios dice que las capas «se usan sin registrarse». Ojo: en WFS 2.0 con EPSG:4326 los puntos de `CQL_FILTER` van en orden *latitud longitud* (`INTERSECTS(geom,POINT(-11.93 -76.70))`); con el orden contrario no devuelve nada.
3. Los conjuntos del SENAMHI en la Plataforma Nacional de Datos Abiertos (§3).

## 3. Términos de uso y base legal

**Términos de uso del sitio** ([Términos y Condiciones de Uso y Privacidad](https://www.senamhi.gob.pe/?p=terminos-condiciones), leídos el 30 de octubre de 2026). La cláusula que rige el uso de los datos dice, textualmente:

> «La Información y Contenidos a los que el usuario puede acceder en la página web son de acceso público y gratuito. El usuario puede utilizar la información para realizar acciones con o sin fines de lucro, siempre aceptando la obligación de reconocer de manera expresa que el SENAMHI es el propietario de la información en todo soporte en que dicha información sea usada. Para ello debe indicarse como fuente en todo tipo de soporte la siguiente leyenda: “Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. El uso que se le da a esta información es de mi (nuestra) entera responsabilidad”.»

Además: la información no puede modificarse para presentarla como oficial del SENAMHI, del MINAM o del Estado; «la página es para el uso personal y del usuario por lo que no podrá comercializar de manera alguna los Servicios, Contenidos e Información»; «la modificación del orden, series y todo método, elemento, coyuntura, diseño en el que se presenta la información es total responsabilidad del usuario»; y la página «Datos hidrometeorológicos» añade «datos sin control de calidad».

**Cómo se aplica en este repositorio:** se usan y se comparten (también en el espejo de Hugging Face) con la leyenda exacta en cada soporte, sin comercializarlos y sin presentarlos como oficiales; las salidas de este capítulo repiten la leyenda y el aviso de calidad. La fuente se baja aparte (`descargar-datos --solo senamhi`) solo por su tamaño y por cortesía con el servicio.

**Comparación de textos, para quien quiera una lectura más fina.** El mismo documento tiene una cláusula de propiedad intelectual: los derechos de «divulgación, publicación, reproducción, distribución y transformación» son del SENAMHI y el uso del sitio «no será considerado como una autorización ni licencia para utilizar» los contenidos «con fines distintos a los que se contemplan en los presentes Términos». Se lee junto con la cláusula de arriba: el uso con o sin fines de lucro con la leyenda es uno de esos fines contemplados. No hay una licencia formal tipo Creative Commons.

**Base legal pública.** La [Ley 27806, Ley de Transparencia y Acceso a la Información Pública](https://www2.congreso.gob.pe/sicr/cendocbib/con5_uibd.nsf/DE0722775AABAAC9052586DB001D51FA/$FILE/TUO-LEY27806.pdf) (TUO aprobado por D.S. 021-2019-JUS) somete las actividades de las entidades al principio de publicidad (art. 3) y da derecho a pedir información que no se publique. Es un derecho de acceso, no una licencia de reutilización; por eso aquí mandan los términos de uso del sitio. El mismo sitio declara la información «de uso público» según la Ley 24031 (art. 4, inciso e) y la R.M. 034-2014-MINAM.

**Plataforma Nacional de Datos Abiertos** ([grupo SENAMHI](https://www.datosabiertos.gob.pe/group/servicio-nacional-de-meteorolog%C3%ADa-e-hidrolog%C3%ADa-del-per%C3%BA-senamhi)): 5 conjuntos.

| Conjunto | Licencia declarada | Útil para Chosica |
|---|---|---|
| [Variables meteorológicas de las estaciones automáticas de intercambio internacional](https://www.datosabiertos.gob.pe/dataset/variables-meteorologicas-de-las-estaciones-autom%C3%A1ticas-de-intercambio-internacional-servicio) | **Open Data Commons Attribution (ODC-By)** | Sí: horario validado de temperatura, humedad y lluvia de **Matucana** (2015 a junio de 2024) y Caranía; 416 mil filas, 5 estaciones en total |
| [Variables ambientales atmosféricas del Observatorio de Marcapomacocha](https://www.datosabiertos.gob.pe/dataset/variables-ambientales-atmosf%C3%A9ricas-del-observatorio-de-vigilancia-atmosf%C3%A9rica-marcapomacocha) | **ODC-By** | Parcial: lluvia diaria a 4443 m en la cabecera, 2015 a 2024 (2807 días con dato) |
| [Datos hidrometeorológicos de libre acceso](https://www.datosabiertos.gob.pe/dataset/datos-hidrometeorol%C3%B3gicos-de-libre-acceso) | «License Not Specified» | Es un enlace al portal; vale lo de arriba |
| Contaminantes del aire de Lima Metropolitana (2 conjuntos) | no mostrada | No (calidad del aire) |

El horario de Matucana de datos abiertos y la estación automática del portal son **la misma serie** (3224 días comunes, Spearman 0,999), así que con ese conjunto el dato de Matucana se puede redistribuir con atribución ODC-By además de las condiciones de arriba. En Chosica y Santa Eulalia no hay equivalente con licencia explícita. Se guardan como metadatos y en `senamhi/tablas/datosabiertos_*_ODC-By.csv*` con su atribución.

## 4. Inventario de capas útiles (GeoServer IDESEP, 1038 capas WFS)

| Capa (`espacio:capa`) | Qué es | Filas / fechas | Se usó |
|---|---|---|---|
| `g_acti_quebrada:view_av_activ_qdra` | Aviso de activación de quebrada, nacional: polígonos por distrito con nivel, fecha, descripción | 2522 el 30-oct-2026; **0 en la zona de estudio** ese día | §6 (no sirve para nombres) |
| `g_acti_quebrada:view_av_activ_qdrahist` | Histórico del anterior | **0 filas** (sin parámetros que lo llenen) | — |
| `g_acti_quebrada:ccpp_filter`, `eess_filter`, `iiee_filter`, `vial_*_filter` | Centros poblados, salud, colegios y vías bajo aviso | solo avisos vigentes | — |
| `g_100_01:aviso001…aviso273` | Avisos meteorológicos numerados de **2020** (nivel, fenómeno, f_emi, fech_ini/fin, hr_ini/fin); 272 y 273 vacíos | 2020 (con algunas fechas de fines de 2019 y enero de 2021) | §7 |
| `g_aviso:view_aviso`, `view_aviso_v2` | Avisos meteorológicos vigentes | solo hoy | — |
| `g_umbrales:umbrales_precipitacion` | Umbral diario y acumulado oficial por estación | 215 estaciones, foto del 30-oct-2026 | §5 |
| `g_02_01…g_02_06` | Anomalía de precipitación de los Niños 1983, 1998, 2017, 2023 y 2024 por trimestre DEF/EFM/FMA (clases `rango`) | 13 capas | §8 |
| `g_04_08:04_08_001…007` | Peligro de movimientos en masa por lluvias intensas, 24 a 168 h | pronóstico vigente | — |
| `g_99_01` | Estaciones meteorológicas, hidrológicas e hidrometeorológicas | catálogo | inventario |
| `silvia:cuencas_nivel_12_*`, `g_carto_fundamento:cuencas` | Cuencas nivel 12 / límites de cuencas del SENAMHI | — | no se usó (ver issue de unidades hidrográficas) |
| `dhi-seh-sonics:*` | Pronóstico de inundación por subcuencas (57 capas) | pronóstico vigente | — |
| `g_dbphisis:aviso_hidro_pub` | Avisos hidrológicos | vigentes | — |

**Lo que sí pide cuenta (API REST):** avisos históricos por año (2021 a hoy), lecturas en lote, y la documentación OpenAPI con consola. No se usó.

## 5. Estaciones cercanas a Chosica

`catalogo/senamhi_estaciones_cercanas.csv` (117 estaciones a ≤45 km; metadatos de estaciones). Las más útiles:

| Estación | Tipo | km | Qué publica | Años |
|---|---|---|---|---|
| Chosica | hidrometeorológica automática (EHMA) | 1,1 | **lluvia y nivel del río por hora** | 2001-2026 (65 a 100 % de los días por año) |
| Chosica | pluviométrica (PLU) / hidrológica (HLG) | 1,1 | lluvia diaria / nivel | PLU 2018-2026 (convencional 1989-2014 en el histórico) / HLG 2017-2026 |
| Santa Eulalia | EHMA, PLU, HLM | 3,8 | lluvia / nivel | EHMA 2015-2026; PLU y HLM 2018-2026 |
| Ñaña | EMA, CO | 16,7 | meteorología horaria / diaria | 2017-2026 |
| San Mateo de Otao, Santiago de Tuna | EMA, PLU | 17-20 | meteorología horaria (3500 y 2900 m) | 2013-2026 |
| Autisha, Matucana, Carampoma, Canchacalla, Sheque, Huaros, Lachaqui | convencionales | 23-60 | lluvia diaria | hasta enero de 2014 (histórico); Autisha y Matucana siguen en la lectura mensual |

Huecos: entre 2014 y 2017 la red de montaña no tiene lluvia publicada salvo las automáticas; el histórico diario termina en enero de 2014 (Matucana en octubre de 2015); Yanacoto, Chacrasana, La Cantuta, Canchacalla y Chaute están cerradas o paralizadas. **No hay caudal observado**, solo nivel del río.

## 6. Resultados

### 6.1 ERA5 frente al pluviómetro

| Par | Spearman | p95 pluviómetro / ERA5 (mm) | Mediana en días con huaico (mm) |
|---|---|---|---|
| Matucana convencional vs ERA5, 1989-2013 | 0,49 | 7,4 / 18,0 | 5,7 / 14,1 |
| Matucana automática vs ERA5, 2013-2026 | 0,62 | 7,6 / 15,9 | 5,1 / 12,1 |
| Chosica automática vs ERA5, 2001-2026 | 0,37 | 2,0 / 10,7 | 0,9 / 5,1 |

ERA5 da más lluvia en los extremos y se parece poco en el día a día. El pluviómetro de Chosica mide poco los días con huaico (mediana 0,9 mm) pero aun así los separa (AUC 0,80 la automática, 0,67 la convencional): T31 se cumple a medias. Se alinearon por fecha de calendario (los convencionales leen a las 07:00; el desfase 0 concordó mejor que ±1).

### 6.2 Qué estación separa los días con huaico (AUC de la lluvia del día, temporada de lluvias)

- Convencionales 1990-2013: Autisha **0,89**, Matucana 0,82, Santiago de Tuna 0,81, Lachaqui 0,80, Canchacalla 0,80, Carampoma 0,78, Huaros 0,76, Sheque 0,76, Santa Eulalia 0,72, Chosica 0,67, Ñaña 0,53.
- Automáticas 2014-2026: Santiago de Tuna **0,91**, San Mateo de Otao 0,90, Chosica 0,80, Matucana 0,80, Santa Eulalia 0,79, Ñaña 0,68.

Las estaciones de la cuenca media-alta (2900 a 3500 m) separan mejor que las del valle (T30).

### 6.3 Modelo diario con pluviómetros (T30; regresión logística con regularización anidada, una temporada fuera, como el capítulo 05)

| Ventana | Modelo | AP (base) | AUC | Aciertos con 5 % de días en alarma |
|---|---|---|---|---|
| 1990-2013 (25 temporadas, 53 días con huaico, 11 pluviómetros) | ERA5, lluvia del día | 0,070 (0,015) | 0,81 | 0,25 |
| | **Pluviómetros, lluvia del día** | **0,233** | 0,90 | 0,47 |
| | ERA5 día + antecedentes | 0,048 | 0,68 | 0,26 |
| | ERA5 día + antecedentes + pluviómetros | 0,212 | 0,78 | 0,49 |
| 2014-2026 (13 temporadas, 51 días con huaico, 5 automáticas) | ERA5, lluvia del día | 0,196 (0,026) | 0,87 | 0,37 |
| | Pluviómetros, lluvia del día | 0,308 | 0,75 | 0,45 |
| | ERA5 día + antecedentes | 0,353 | 0,93 | 0,59 |
| | ERA5 día + antecedentes + pluviómetros | 0,387 | 0,93 | 0,55 |

Diferencias de AP (bootstrap de temporadas, mediana e intervalo 90 %): 1990-2013, pluviómetros menos ERA5 **+0,166 (0,112 a 0,254)**; 2014-2026, +0,111 (−0,069 a 0,359) y con el modelo completo +0,049 (−0,038 a 0,250), **indistinguible de cero**. La prueba nula (etiquetas desplazadas dentro de cada temporada, 40 repeticiones) da AP 0,011 de media y 0,028 de máximo contra 0,19 real. Los pluviómetros dan la lluvia del día: es un *nowcast*.

### 6.4 Nivel del río frente a GloFAS (T32)

Spearman 0,53 entre el nivel diario medio de Chosica (EHMA) y el log del caudal de GloFAS, 2001-2026 (0,58 en 2001-2010; 0,50 desde 2011). Como señal de día con huaico: nivel diario máximo AUC 0,62; log caudal de GloFAS 0,65. Ninguno es fuerte.

### 6.5 Umbrales oficiales de lluvia (T33)

Umbrales vigentes el 30-oct-2026 (`umbral` diario / `umb_acum` acumulado, mm): Chosica y Ñaña 1 / 3; Santa Eulalia 2 / 6; Matucana y San Mateo de Otao 4 / 12; Casapalca 5 / 15. La capa no dice la ventana de la acumulada: se leyó como **3 días** (es el triple del umbral en todos). Regla: alarma el día en que la lluvia del día llega al umbral o la de los últimos 3 días a la acumulada. Con las series del §5 y los días de huaico del catálogo (POD con el mismo día; FAR_días = alarmas sin huaico en ±1 día, que es un máximo porque el catálogo es incompleto):

| Red | Regla | Días de alarma por temporada de 151 días | POD | FAR_días |
|---|---|---|---|---|
| Convencionales 1990-2013 | Chosica | 10,6 | 0,51 | 0,81 |
| | Matucana | 36,7 | 0,76 | 0,90 |
| | Santa Eulalia | 6,5 | 0,43 | 0,70 |
| | **cualquier estación** | 41,0 | 0,81 | 0,90 |
| Automáticas 2014-2026 | Chosica | 12,4 | 0,60 | 0,66 |
| | Matucana | 38,5 | 0,69 | 0,86 |
| | San Mateo de Otao | 37,9 | 0,96 | 0,88 |
| | **cualquier estación** | 54,5 | 0,87 | 0,88 |

Contra nuestros modelos con el mismo porcentaje de días en alarma (27 % en 1990-2013, 36 % en 2014-2026): en 1990-2013 el modelo de pluviómetros del día da POD 0,91 y FAR 0,89 contra 0,81 y 0,90 de la regla oficial; en 2014-2026 el modelo ERA5 día + antecedentes + pluviómetros da POD 0,98 y FAR 0,85 contra 0,87 y 0,88. La ventaja de los modelos aparece con presupuestos más estrictos (con 5 % de días en alarma, POD de 0,26 a 0,61 según el modelo y la ventana). Contra los percentiles del capítulo 02 (ERA5 percentil 90: 74 % de los eventos con 33 días de alarma por año) el orden es el mismo: la lluvia sola alarma entre un cuarto y un tercio de los días de la temporada para capturar la mayoría de los huaicos. Todo con la advertencia de siempre: FAR contado contra un catálogo incompleto.

### 6.6 Avisos meteorológicos de 2020 (T34)

Solo 2020 está en el GeoServer. Se tomaron los avisos que contienen el punto de Chosica o de Matucana, de lluvia o precipitación en sierra o costa (los de «lluvia en selva» sola se descartaron). En la temporada de 2020 (152 días) hubo 3 días de huaico catalogados (21, 23 y 29 de enero).

| Punto | Aviso de nivel ≥ | Días de aviso | % de días | Huaicos con aviso | FAR_días |
|---|---|---|---|---|---|
| Chosica | 1 | 122 | 80 % | 3/3 | 0,94 |
| | 2 | 45 | 30 % | 3/3 | 0,84 |
| | 3 | 12 | 8 % | 1/3 | 0,83 |
| Matucana | 1 | 122 | 80 % | 3/3 | 0,94 |
| | 2 | 79 | 52 % | 3/3 | 0,91 |
| | 3 | 37 | 24 % | 3/3 | 0,81 |

Con tres huaicos no hay potencia para decir nada fino: el aviso de nivel 1 cubrió el 80 % de la temporada (casi siempre hay un aviso de lluvia en sierra), el de nivel 3 en Chosica cubrió solo 1 de 3 y en Matucana 3 de 3 con 24 % de los días. De 2021 en adelante el historial está en la API con cuenta.

### 6.7 Anomalías de lluvia de los Niños (T35)

Clase de anomalía (centro del rango, unidad no declarada en la capa) en el punto y días de huaico del catálogo en la ventana de tres meses:

| Evento | Trimestre | Chosica | Santa Eulalia | Matucana | Ticlio | Días de huaico |
|---|---|---|---|---|---|---|
| 1983 | DEF / EFM / FMA | — / 45 / 45 | −15 / 90 / 45 | −90 / 45 / 90 | — / −15 / — | 2 / 17 / 20 |
| 1998 | DEF / EFM / FMA | — / 45 / 15 | 90 / 45 / 15 | 90 / 90 / 90 | — / −90 / — | 13 / 15 / 10 |
| 2017 | DEF / EFM / FMA | 15 / 90 / 15 | 45 / 90 / 45 | 90 / 255 / 90 | 90 / 165 / 15 | 15 / 23 / 14 |
| 2023 | EFM / FMA | −15 / — | −15 / −15 | −45 / −15 | −90 / −90 | 8 / 10 |
| 2024 | DEF / EFM | 15 / — | 15 / 15 | 45 / 45 | — | 1 / 1 |

Spearman entre la anomalía y los días de huaico: Chosica +0,87 (n = 9), Santa Eulalia +0,76 (n = 13), Matucana +0,69 (n = 13), Ticlio +0,67 (n = 7, p = 0,10). Los trimestres de un mismo evento se solapan, así que no son independientes, y 13 puntos son pocos. **2023 contradice la regla:** anomalías negativas en todos los puntos y aun así 8 y 10 días de huaico catalogados (Yaku, con lluvias costeras que estos mapas no ven y mucha cobertura de prensa).

### 6.8 Capas de «activación de quebrada» (T36): no sirven para ubicar quebradas

`view_av_activ_qdra` y `ccpp_filter` traen polígonos por distrito (`nombdep`, `nombprov`, `nombdist`), centros poblados bajo aviso, nivel, fecha y descripción, **sin el nombre de la quebrada**; el histórico (`view_av_activ_qdrahist`) devuelve 0 filas. El 30 de octubre de 2026 no había ningún aviso dentro de lon −77,0 a −76,4 y lat −12,1 a −11,8 (la prueba de que el filtro espacial funciona: en un cuadro de Amazonas devolvió 37). Por eso no se agregó ninguna quebrada a `catalogo/quebradas_referencias.csv` desde esta fuente. Cashahuacra, Huampaní, Huascata, La Floresta y Santa María siguen sin cuenca.

## 7. Qué dice esto

- La lluvia observada en las estaciones de montaña es mucho mejor que la de ERA5 para marcar el día de un huaico cuando solo se tiene la lluvia del día; con antecedentes y el resto de predictores la ventaja baja y deja de distinguirse en la ventana corta.
- Las reglas oficiales de umbral alarman entre un cuarto y un tercio de los días y aciertan entre 4 de 5 y 9 de 10 huaicos; nuestros modelos hacen lo mismo con ese presupuesto y algo mejor con presupuestos estrictos. Ninguno de los dos evita que 8 de cada 10 alarmas caigan en días sin huaico catalogado.
- Es *nowcast*: la lluvia del día se conoce al final del día.

## 8. Límites

- Pocas estaciones, series con huecos y sin control de calidad; la ventana 2014-2026 usa 5 automáticas y 13 temporadas, y las redes de 1990-2013 y 2014-2026 no son comparables entre sí.
- Entre 2014 y 2017 no hay red convencional publicada.
- Los avisos históricos del GeoServer cubren solo 2020 (3 días de huaico); la ventana de la lluvia acumulada del umbral es una lectura nuestra.
- Todo depende del catálogo de fechas (capítulos 03 y 07), incompleto; el FAR es un máximo.

## 9. Información que no es pública y se puede pedir

Está abierto el [issue 1 del repositorio](https://github.com/Illapa-Labs/illapa-research/issues/1). Según la Ley 27806 o por correo a atencionsistemas@senamhi.gob.pe:

- El **Inventario de Movimientos en Masa Generados por Lluvias (IMMS)**, que el SENAMHI registra desde 2019 (330 eventos de 2018 a 2020 en el estudio de Millán et al. 2022), con coordenadas o lugar.
- La tabla `ID_Hydro` → cuenca usada en ese estudio y en SILVIA.
- La salida del modelo WRF de 1 km para Lima.
- Lo que hoy solo da la API con cuenta: avisos históricos de 2021 a hoy y lluvia horaria de montaña posterior a enero de 2014, si existe.

## 10. Reproducir

```bash
uv run descargar-datos --solo senamhi        # ~40 min, 2 s entre llamadas, deja todo en datos/senamhi/
uv run --extra hf descargar-datos --desde-hf USUARIO/REPO   # o bajarlo del espejo
uv run jupyter lab notebooks/11-senamhi.ipynb
```
