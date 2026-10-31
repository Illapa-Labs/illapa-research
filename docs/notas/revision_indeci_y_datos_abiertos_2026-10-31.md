# Revisión del portal del INDECI y de datos abiertos (31 de octubre de 2026)

Se hizo con el Chrome de la persona usuaria (extensión de Claude), sin evadir ningún bloqueo, para buscar fechas y nombres de quebradas que faltan.

## Archivo de emergencias del COEN/INDECI (`portal.indeci.gob.pe/emergencias/`)

- Tiene 3 354 páginas (unos 20 documentos por página) y cubre aproximadamente de 2020 a la fecha: reportes complementarios, de peligro inminente y boletines. El distrito va en el título.
- La búsqueda del sitio (`?s=`) no filtra: devuelve siempre la misma lista. Se recorrieron las páginas con una pausa de 0,5 s y tres consultas en paralelo.
- Se recorrieron solo las temporadas de lluvia (diciembre a abril) de 2022-23 (páginas 1940-2190), 2024-25 (900-1140) y 2025-26 (370-610), unas 730 páginas.
- **Resultado:** ningún reporte de huaico ni de activación de quebrada con Lurigancho-Chosica, Chaclacayo, Santa Eulalia o Ricardo Palma en el título. Solo aparecen derrumbes de cerro en Lurigancho-Chosica (reportes complementarios de enero de 2025), y derrumbes y colapsos en San Juan de Lurigancho y Ate.
- Los reportes que sí se leyeron para 2023 y 2026 (RC 1955, informe 599, RC 3172 y 4047) están como PDF en `wp-content/uploads/`, pero **no aparecen con el distrito en el título del archivo**: el archivo no sirve para encontrar por distrito todos los reportes. La lista debe armarse por fecha, no por título.
- No se recorrieron 2020-2022 (páginas 2190-3354) ni 2023-24 (1420-1670).

## Datos abiertos (`datosabiertos.gob.pe`)

- «Emergencias históricas registradas por el INDECI» (SINPAD 2003-2018, un archivo por año, licencia ODC-By): **los 15 archivos `.xls` devuelven 404 incluso con el navegador, y la tabla de vista previa muestra 0 registros.** El catálogo existe, pero los archivos no están disponibles.
- Otros conjuntos relacionados: «Emergencias y daños a nivel nacional por departamento» (agregado), INGEMMET «Inventario de peligros geológicos» y «Zonas críticas por peligros geológicos» (ya usamos GEOCATMIN), CENEPRED «Movimientos en masa registrados en el departamento de Amazonas» (fuera de zona).

## gob.pe/indeci

El portal institucional redirige a gob.pe, que bloquea el acceso automático fuera del navegador. Con el navegador se abre, pero «Informes y publicaciones» son documentos institucionales (planes, boletines de gestión), no informes de emergencia.
