# 23 · Geoquebradas del MINAM: avisos oficiales de activación de quebradas

> **No es una alerta ni una predicción para decidir evacuaciones.** Es una comparación, con 3 días con huaico, entre los avisos oficiales de activación de quebradas y nuestra ficha de probabilidad. Ante una emergencia llama al 115 (INDECI).

Código: `fuentes_estado.geoquebradas_historico` y `geoquebradas_resumen` (prueba en `tests/test_fuentes_estado.py`). Tabla derivada: [`catalogo/geoquebradas_lima_2026.csv`](../catalogo/geoquebradas_lima_2026.csv).

## 1. Qué es y cómo se obtiene

Geoquebradas (<https://geoservidorperu.minam.gob.pe/geoquebradasestadistica/>) es la plataforma del MINAM que publica, a diario, qué quebradas podrían activarse con la lluvia pronosticada y a quién afectarían. Combina SENAMHI (zonas con posible activación), ANA, INEI, Minsa, Minedu, MTC, OEFA y SERNANP. El visor está detrás de una protección anti-bots (Incapsula) que **no se evade**. Lo que sí es público es el servidor ArcGIS REST del propio MINAM, de donde sale todo lo de este capítulo con consultas de solo lectura, con pausa de 1,5 s, sin credenciales y con caché local (`datos/geoquebradas/`, no se sube):

`https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicios_Geoquebradas/geoquebradas/MapServer`

| Capa | Contenido | Registros (30-10-2026) |
|---|---|---|
| 0 `Geoquebradas` | Estado actual | 2 353 |
| 1 `Geoquebradas historico` | Avisos diarios desde el 1-02-2026: polígono de la quebrada, fecha, nivel (1 amarillo, 2 naranja, 3 rojo), distrito, población y vivienda expuestas, prioridad, persistencia y recurrencia a 7 días, `quebrada_uid` | 99 172 |

En el mismo servidor, `ServicioActivacionQuebrada` (peligros geológicos, 24 681 puntos de 2013; peligros por inundación, 3 814 puntos; y cinco capas de «Posible activación de quebrada – SENAMHI» del 3 al 7 de marzo de 2024) se solapa con lo que ya se usó de INGEMMET y SINPAD (capítulo 18) y no se descargó.

## 2. Qué dicen los datos (departamento de Lima)

5 779 avisos en 24 días distintos entre el 1-02-2026 y el 26-10-2026; 2 164 en Yauyos, 1 430 en Huarochirí, 514 en Huaral. Casi nada en el valle bajo: Lurigancho 6, Chaclacayo 1, Ate 1. La mayoría de los avisos del Rímac son aguas arriba (San Mateo 128, Carampoma 86, Chicla 73, Santa Eulalia 31). Hay días con cientos de avisos de nivel 3 en octubre (23 a 26) que no corresponden a la temporada de lluvias del valle.

**Faltan días.** En febrero a abril de 2026 (89 días) el departamento tiene avisos en solo 20. No sabemos si los días sin fila son días sin aviso o días que el servicio no conserva (el 19 de febrero, día con huaico, no tiene ninguno).

## 3. Comparación con los huaicos de 2026

Temporada 2026 (1-02 a 30-04), 89 días, **3 días con huaico catalogado**: 19, 24 y 25 de febrero. Se compara con nuestro modelo de la ficha (regresión L2 con todas las variables, dejando fuera esa temporada, mismo método del capítulo 05).

| Señal | Días con señal | AP (empates al azar) | Valor el 19-02 | el 24-02 | el 25-02 |
|---|---|---|---|---|---|
| Avisos en el departamento de Lima | 20 | 0,20 | 0 | 264 | 462 |
| Avisos en Huarochirí | 19 | **0,43** | 0 | 88 | 134 |
| Avisos en el valle bajo (Lurigancho, Chaclacayo, Ate, Santa Eulalia, Ricardo Palma) | 12 | 0,19 | 0 | 2 | 5 |
| Nuestro modelo (probabilidad) | 89 | 0,30 | 0,012 | 0,135 | 0,126 |

La base es 0,034. Rango de nuestro modelo en esos días: 39 (19-02), 3 (24-02) y 4 (25-02) de 89.

## 4. Qué se aprende y qué no

- **Con 3 positivos no se puede decir quién es mejor.** Los dos aciertan el 24 y el 25 de febrero y fallan el 19; las diferencias de AP (0,43 contra 0,30) caben en un solo día de diferencia en el ranking.
- **Cubren lo mismo.** Marcando los 19 días con aviso en Huarochirí o los 19 días con más probabilidad del modelo se capturan 2 de 3 en ambos casos. El 19 de febrero se escapa a los dos, lo que sugiere un huaico con poca señal meteorológica (o una fecha imprecisa en el catálogo).
- **Los avisos son útiles como control externo y como contexto de la sierra**, pero el servicio no cubre las quebradas de Chosica (casi sin polígonos en Lurigancho y Chaclacayo) y no tiene historia antes de 2026, así que no sirve para entrenar ni para validar por temporada.
- **No es independiente de nuestras fuentes** (comparte SENAMHI, INEI y compañía), y el criterio de los niveles lo define el MINAM (campo `observacion_metodologica`, que no se analizó).

## 5. Límites

- 89 días y 3 huaicos: es un control de coherencia, no una prueba estadística.
- No se comparó por quebrada (hay `quebrada_uid` y polígonos; se descartaron los polígonos por tamaño y por no tener correspondencia con nuestras 124 cuencas).
- Licencia: el servidor no declara una. Se trata como información pública del Estado y **no se espeja el crudo**: en `catalogo/` solo va el resumen por día y provincia (157 filas), con la fuente.
- Las fechas del servicio son de la fecha del aviso, no del evento.

## 6. Reproducir

```python
from pathlib import Path
from illapa_research import fuentes_estado as FE
c = FE.ClienteEstado(Path("datos/geoquebradas"))
filas = FE.geoquebradas_historico(c, "nombdep='LIMA'")      # 5 779 filas, unos 8 s
FE.geoquebradas_resumen(filas).to_csv("catalogo/geoquebradas_lima_2026.csv", index=False)
```

Fuentes: MINAM, Geoquebradas (consultado el 30-31 de octubre de 2026); la ayuda del visor y el listado de servicios del Geoservidor (<https://geoservidor.minam.gob.pe/recursos/servicios-de-wmswfs/>).
