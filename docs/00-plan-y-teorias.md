# 00 · Plan y teorías

## Pregunta

¿Qué quebradas de Lurigancho-Chosica, Chaclacayo y el valle de Santa Eulalia son más propensas a activarse como huaico en un evento El Niño, y qué señales dicen **cuándo** hay condiciones favorables? No se busca una probabilidad anual absoluta ni una alerta: el nivel de cualquier tasa se confunde con cuánto se reporta cada quebrada (ver capítulo 03).

## Qué se aprendió de la literatura

El informe de métodos (`research-workspace/reports/Métodos de probabilidad de huaico.md`, otra sesión del proyecto) concluye: la lluvia sola da muchas falsas alarmas; no hay un odds ratio publicado entre El Niño y huaicos de Lima; con decenas de eventos conviene un modelo jerárquico de conteos con rangos posteriores, validado por episodio y por bloques de quebradas; el sesgo de reporte es la mayor amenaza. Este repositorio sigue ese diseño y lo extiende con señales diarias.

## Teorías en competencia (pre-registradas)

Se escriben antes de mirar los resultados. Cada notebook las prueba con validación fuera de muestra y con una nula que desplaza las fechas.

| # | Teoría | Dónde se prueba |
|---|---|---|
| T0 | La susceptibilidad física (Melton, pendientes) ordena las quebradas que se activan | cap. 03 |
| T1 | El Niño multiplica la frecuencia de activación, igual para todas las quebradas | cap. 03 |
| T2 | El registro sigue a la gente (edificios), no al terreno | cap. 03 |
| T3 | La temperatura del mar sube días antes del huaico (disparador) | cap. 04 |
| T4 | El mar actúa como régimen lento (interanual), no como disparador diario | cap. 04 y 05 |
| T5 | El calor aguas arriba (anomalía de temperatura, isoterma de 0 °C, nieve) precede al evento o al caudal | cap. 04 |
| T6 | La humedad de la selva y el gradiente de presión selva-costa preceden | cap. 04 |
| T7 | Los antecedentes (suelo, lluvia previa, caudal) definen un régimen favorable; la lluvia del día es el disparador | cap. 05 |
| T8 | Hay interacciones no lineales que un modelo lineal no ve | cap. 05 |

## Criterios de validación (fijos)

- Siempre fuera de muestra: dejar fuera una temporada, un episodio Niño completo, o una quebrada; nunca 70/30 aleatorio.
- Siempre contra una referencia: la climatología (solo la fecha) y el modelo sin la señal nueva.
- Siempre con una nula: etiquetas desplazadas dentro de la temporada, que conservan cuántos eventos hay y cómo se agrupan.
- Se reporta lo que falla. Un resultado que cambia al ubicar dos o tres fechas más se llama frágil.
- Ninguna variable ni umbral se ajusta hasta acertar el pasado.

## Cómo se documenta

Toda fuente nueva entra en `fuentes.py` (con licencia y atribución) y en `DATOS.md`. Todo resultado nuevo entra en su capítulo con la fecha de los datos usados y la versión de la definición (por ejemplo, qué definición de Niño). Los datos que faltan se dicen, no se rellenan.
