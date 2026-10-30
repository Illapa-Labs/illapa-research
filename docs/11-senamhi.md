# 11 · Datos del SENAMHI: ¿sirven los pluviómetros reales?

> **No es un sistema de alerta ni una predicción para decidir evacuaciones.** Mide cuánto de las fechas de huaico del catálogo se explica con la lluvia observada. Ante una emergencia llama al 115 (INDECI).

**Fuente:** Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú (SENAMHI), [Observatorio Nacional del Tiempo, Agua y Clima del Perú](https://observatorio.senamhi.gob.pe).
Notebook: [`notebooks/11-senamhi.ipynb`](../notebooks/11-senamhi.ipynb). Código: [`src/illapa_research/senamhi.py`](../src/illapa_research/senamhi.py) y [`fuentes_restringidas.py`](../src/illapa_research/fuentes_restringidas.py); pruebas en `tests/test_senamhi.py` (sin red). Datos usados: 30 de octubre de 2026.

## 1. Pregunta

El modelo diario del capítulo 05 usa lluvia de ERA5, un reanálisis de ~25 km sin ningún pluviómetro dentro del punto. ¿Mejora si se le da la lluvia medida por las estaciones del SENAMHI? Teorías escritas antes de mirar:

| | Teoría |
|---|---|
| T30 | Los pluviómetros de la cuenca media-alta detectan los días con huaico mejor que ERA5 |
| T31 | El pluviómetro del propio Chosica casi no mide la lluvia que activa las quebradas |
| T32 | El nivel del río en Chosica concuerda solo en parte con el caudal de GloFAS |

## 2. Qué hay y cómo se accede

**Portal** (`/investigadores`): 976 estaciones según su página (657 convencionales, 319 automáticas); series en Excel o CSV, WMS/WFS del GeoServer de IDESEP «sin registrarte», y una **API REST que pide una cuenta gratuita que el SENAMHI revisa y aprueba**. El portal no declara licencia.

**Qué se usó y qué no.** No se creó ninguna cuenta ni se usó ninguna clave: la API documentada se dejó sin tocar. Sí se leyeron los endpoints anónimos que la propia página «Datos hidrometeorológicos» llama para cualquier visitante (`servicios.senamhi.gob.pe/api/station/stations` y `.../periods`, `.../readings?period=`, y `researchers/historical-download/stations/{código}/series`). Es una lectura de cada estación y cada mes, con 2 s de pausa entre llamadas, caché local y parada inmediata si algún endpoint responde 401 o 403. `robots.txt` del observatorio dice `Allow: /`. Aun así, que la página lo sirva a cualquier visitante no es una licencia: ver §3.

**Lo que tiene cerca de Chosica** (`catalogo/senamhi_estaciones_cercanas.csv`, 117 estaciones a ≤45 km; solo metadatos):

| Estación | Tipo | km a Chosica | Qué publica | Años |
|---|---|---|---|---|
| Chosica | pluviométrica (PLU) | 1,1 | lluvia diaria, temperaturas | 2018-2026 (convencional 1989-2014 en la descarga histórica) |
| Chosica | hidrometeorológica automática (EHMA) | 1,1 | **lluvia y nivel del río por hora** | 2001-2026 (65 a 100 % de los días por año) |
| Chosica | hidrológica (HLG) | 1,1 | nivel del río (4 lecturas al día) | 2017-2026 |
| Santa Eulalia | PLU, EHMA, HLM | 3,8 | lluvia / nivel | EHMA 2015-2026; PLU y HLM 2018-2026 |
| Ñaña | EMA, CO | 16,7 | meteorología horaria / diaria | 2017-2026 |
| San Mateo de Otao, Santiago de Tuna | EMA, PLU | 17-20 | meteorología horaria (3500 y 2900 m) | 2013-2026 |
| Autisha, Matucana, Carampoma, Canchacalla, Sheque, Huaros, Lachaqui | convencionales | 23-60 | lluvia diaria | hasta enero de 2014 en la descarga histórica (Autisha y Matucana siguen vigentes en la lectura mensual) |

Huecos importantes: **entre 2014 y 2017 la red de montaña no tiene lluvia publicada** salvo las automáticas; la serie histórica diaria termina en enero de 2014 (Matucana en octubre de 2015); varias estaciones cercanas (Yanacoto, Chacrasana, La Cantuta, Canchacalla, Chaute) están cerradas o paralizadas. El caudal observado **no existe**: el servicio publica el **nivel** del río, no el caudal.

**Avisos e historial.** El WMS de avisos (`g_aviso`) solo muestra el aviso vigente (no tiene dimensión de tiempo) y los endpoints de eventos extremos y de El Niño devuelven mapas de anomalía de lluvia por evento, no un registro de avisos pasados. **No se encontró un histórico descargable de avisos de lluvia o huaico**; si existe, hay que pedirlo (trámite TUSNE del SENAMHI).

## 3. Términos y licencia

Leídos el 30 de octubre de 2026 en [Términos y Condiciones de Uso y Privacidad](https://www.senamhi.gob.pe/?p=terminos-condiciones):

- La información es **«de uso público»** (Ley 24031, art. 4 inciso e, y R.M. 034-2014-MINAM).
- Pero «los derechos de uso y explotación» de los contenidos, «incluyendo su divulgación, publicación, reproducción, distribución y transformación, son propiedad exclusiva del SENAMHI», y el uso del sitio **no es una licencia** para fines distintos de los contemplados.
- Prohíbe presentar la información modificada como oficial del SENAMHI, y hay que citar la fuente.
- La página «Datos hidrometeorológicos» añade: «datos sin control de calidad; su uso es de entera responsabilidad de quien los descarga».
- El conjunto «Datos hidrometeorológicos de libre acceso» de [datosabiertos.gob.pe](https://www.datosabiertos.gob.pe/dataset/datos-hidrometeorol%C3%B3gicos-de-libre-acceso) figura con licencia «no especificada».

**Reglas que se aplican en este repositorio:**

1. Las series se guardan solo en `datos/senamhi/` (ignorado por git).
2. La fuente es **opt-in**: `descargar-datos` sin argumentos no la baja; hay que pedirla con `--solo senamhi`. Una prueba lo verifica.
3. No está en `espejo_hf.ARCHIVOS` ni en el espejo de Hugging Face. Otra prueba lo verifica.
4. Se publican solo resultados agregados (AP, AUC, tablas) y metadatos de estaciones.
5. Toda cifra lleva la cita «Información recopilada y trabajada por el SENAMHI».

## 4. Resultados

**ERA5 frente al pluviómetro** (correlación de rangos, p95 en días lluviosos, mediana en días con huaico):

| Par | Spearman | p95 pluviómetro / ERA5 (mm) | Mediana en días con huaico (mm) |
|---|---|---|---|
| Matucana convencional vs ERA5, 1989-2013 | 0,49 | 7,4 / 18,0 | 5,7 / 14,1 |
| Matucana automática vs ERA5, 2013-2026 | 0,62 | 7,6 / 15,9 | 5,1 / 12,1 |
| Chosica automática vs ERA5, 2001-2026 | 0,37 | 2,0 / 10,7 | 0,9 / 5,1 |

ERA5 da más lluvia en los extremos, a veces el doble, y se parece poco en el día a día. El pluviómetro de Chosica mide poco los días con huaico (T31), pero aun así los separa: AUC 0,80 la automática y 0,67 la convencional. Se alinearon por fecha de calendario (el desfase de 07:00 de los convencionales mejoró con 0 días, no con ±1).

**Qué estación separa los días con huaico** (AUC de la lluvia del día, temporada de lluvias):

- Convencionales 1990-2013: Autisha **0,89**, Matucana 0,82, Santiago de Tuna 0,81, Lachaqui 0,80, Canchacalla 0,80, Carampoma 0,78, Huaros 0,76, Sheque 0,76, Santa Eulalia 0,72, Chosica 0,67, Ñaña 0,53.
- Automáticas 2014-2026: Santiago de Tuna **0,91**, San Mateo de Otao 0,90, Chosica 0,80, Matucana 0,80, Santa Eulalia 0,79, Ñaña 0,68.

Las estaciones de la cuenca media-alta (2900 a 3500 m) separan mejor que las del valle; Ñaña, en el valle bajo, casi no (T30).

**Modelo diario con pluviómetros** (regresión logística con regularización anidada, dejando una temporada fuera, como el capítulo 05):

| Ventana | Modelo | AP (base) | AUC | Aciertos con 5 % de días en alarma |
|---|---|---|---|---|
| 1990-2013 (25 temporadas, 53 días con huaico, 11 pluviómetros) | ERA5, lluvia del día | 0,070 (0,015) | 0,81 | 0,25 |
| | **Pluviómetros, lluvia del día** | **0,233** | 0,90 | 0,47 |
| | ERA5 + pluviómetros | 0,222 | 0,87 | 0,51 |
| | ERA5 día + antecedentes | 0,048 | 0,68 | 0,26 |
| | ERA5 día + antecedentes + pluviómetros | 0,212 | 0,78 | 0,49 |
| 2014-2026 (13 temporadas, 51 días con huaico, 5 automáticas) | ERA5, lluvia del día | 0,196 (0,026) | 0,87 | 0,37 |
| | Pluviómetros, lluvia del día | 0,308 | 0,75 | 0,45 |
| | ERA5 + pluviómetros | 0,311 | 0,86 | 0,45 |
| | ERA5 día + antecedentes | 0,353 | 0,93 | 0,59 |
| | ERA5 día + antecedentes + pluviómetros | 0,387 | 0,93 | 0,55 |

Diferencias de AP con bootstrap de temporadas (mediana e intervalo 90 %): en 1990-2013, pluviómetros menos ERA5 **+0,166 (0,112 a 0,254)**; en 2014-2026, pluviómetros menos ERA5 +0,111 (−0,069 a 0,359), ERA5 + pluviómetros menos ERA5 +0,115 (0,037 a 0,220), y con antecedentes +0,049 (−0,038 a 0,250). Con el modelo ya completo en 2014-2026, los pluviómetros **no se distinguen** de cero. Contra la prueba nula (etiquetas desplazadas dentro de cada temporada, 40 repeticiones; modelo logístico simple de los pluviómetros de montaña de 1990-2013), el AP real es 0,19 y el nulo 0,011 en promedio con máximo 0,028.

**Nivel del río contra GloFAS.** El nivel diario medio de Chosica (EHMA) y el log del caudal de GloFAS tienen Spearman 0,53 en 2001-2026 (0,58 en 2001-2010; 0,50 desde 2011). Como señal de día con huaico, el nivel diario máximo da AUC 0,62, el log del caudal de GloFAS 0,65: ninguno es una señal fuerte (T32).

## 5. Qué dice esto

- La lluvia observada en las estaciones de montaña **sí es mucho mejor** que la de ERA5 para marcar el día de un huaico cuando solo se tiene la lluvia del día. En los 25 años de red convencional la ventaja es clara (AP 0,23 frente a 0,07).
- Cuando se añaden los antecedentes y el resto de predictores, la ventaja baja y deja de ser distinguible en la ventana corta (13 temporadas): la lluvia de ERA5 y sus antecedentes ya capturan buena parte.
- Es un *nowcast*: la lluvia del día se conoce al final del día (o a la mañana siguiente para los convencionales), no antes.

## 6. Límites

- Pocas estaciones, series con huecos y sin control de calidad; la ventana 2014-2026 usa solo 5 automáticas (3 de ellas desde 2013-2017) y 13 temporadas.
- Entre 2014 y 2017 no hay red convencional publicada; la red de 1990-2013 y la de 2014-2026 son distintas, así que los dos bloques no se pueden comparar entre sí.
- Las estaciones automáticas de montaña tienen más ruido (pérdidas de datos, años con 16 a 30 % de días).
- Todo depende del catálogo de fechas (capítulos 03 y 07).
- No se pudo comparar con avisos oficiales pasados, porque no hay histórico accesible.

## 7. Qué falta y cómo se obtiene

1. **Autorización por escrito** para publicar resultados que dependan de las series y, si se desea, para compartir las series derivadas. Borrador abajo.
2. Lluvia horaria de montaña desde 2014 hasta hoy es lo que más aportaría; hay que ver con el SENAMHI si las automáticas tienen más histórico.
3. Histórico de avisos meteorológicos e hidrológicos (por solicitud).
4. Caudal observado en Chosica (aforos): el portal solo publica el nivel.

## 8. Borrador de solicitud (no enviado)

> **Para:** atencionalciudadano@senamhi.gob.pe
> **Asunto:** Solicitud de autorización de uso de datos del Observatorio del SENAMHI para investigación sin fines de lucro sobre huaicos en Lurigancho-Chosica
>
> Estimados señores del SENAMHI:
>
> Somos Illapa Labs, un proyecto comunitario y sin fines de lucro (código abierto, licencia AGPL, https://github.com/Illapa-Labs/illapa-research) que estudia cuándo y dónde se activan huaicos en Lurigancho-Chosica, Chaclacayo y el valle de Santa Eulalia. **No emitimos alertas ni pronósticos oficiales**; todo material lleva la advertencia de que ante una emergencia se debe llamar al 115 (INDECI).
>
> Con fines de investigación hemos leído, con pausas y sin credenciales, las series públicas del Observatorio (https://observatorio.senamhi.gob.pe/investigadores/datos) de estaciones cercanas a Chosica: lluvia diaria histórica y lluvia horaria de las estaciones automáticas de Chosica, Matucana, Ñaña, San Mateo de Otao, Santiago de Tuna y Santa Eulalia. Las guardamos solo en nuestras computadoras y no las redistribuimos. Los términos del sitio reservan la publicación y distribución de la información al SENAMHI, por lo que solicitamos su **autorización por escrito** para:
>
> 1. Publicar en el repositorio resultados agregados que dependen de estas series (métricas de desempeño de modelos, comparaciones con reanálisis), citando siempre «Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú (SENAMHI)».
> 2. Si es posible, publicar los valores diarios de lluvia de las estaciones listadas, con la misma cita y sin presentarlos como información oficial.
> 3. Conocer si existe un histórico descargable de los avisos meteorológicos e hidrológicos de la zona (2010 a la fecha) y cómo solicitarlo, y si hay lluvia horaria de montaña posterior a enero de 2014.
>
> Los datos están sin control de calidad y asumimos esa limitación. Quedamos atentos a sus indicaciones y a cualquier condición adicional.
>
> Atentamente,
> [nombre y datos de contacto de quien firme]

## 9. Reproducir

```bash
uv run descargar-datos --solo senamhi   # opt-in; ~40 min, 2 s entre llamadas, deja todo en datos/senamhi/
uv run jupyter lab notebooks/11-senamhi.ipynb
```
