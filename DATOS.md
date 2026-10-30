# Datos y atribución

La licencia AGPL de este repositorio cubre el **código**, no los datos. `descargar-datos` solo baja fuentes con licencia clara; cada descarga queda registrada en `datos/MANIFIESTO.json`. Revisión del 29 de octubre de 2026. Este proyecto no es el dueño de estos datos ni los garantiza.

| Dato | Fuente | Licencia | Atribución |
|---|---|---|---|
| Ríos y departamentos | [Natural Earth](https://www.naturalearthdata.com) | Dominio público | No se exige |
| Ríos y quebradas (Chaclacayo a Chosica) | [OpenStreetMap](https://www.openstreetmap.org/copyright), vía Overpass | ODbL 1.0 | "© colaboradores de OpenStreetMap". Una base derivada que se publique debe seguir bajo ODbL |
| Lluvia diaria histórica | [Open-Meteo](https://open-meteo.com) | CC BY 4.0; la API gratuita es solo no comercial | "Weather data by Open-Meteo.com" |

| Eventos y cuencas del piloto (`catalogo/`) | Proyecto previo `huaico`; hechos de INDECI, CENEPRED, PREDES y prensa | Hechos citados con su fuente; sin verificar fila por fila | Cada fila conserva su `fuente` |
| Polígonos de cuenca | Derivados de [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) | Uso libre con atribución | © Unión Europea / ESA |

## Fuera por ahora

- **SENAMHI** (avisos, estaciones, límites): no hay licencia de reutilización publicada. Falta pedir autorización por escrito a atencionalciudadano@senamhi.gob.pe.
- **INEI** (Censo 2017): condiciones por verificar.
- **Modelos de elevación para hidrología**: revisar la licencia de cada uno antes de usarlo.

## Publicar datos derivados

Antes de subir un conjunto a Hugging Face u otro sitio, confirma que cada fuente que lo compone permite redistribuirlo, y publícalo con su licencia y atribución.
