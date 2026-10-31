# 14 · Corregir el sesgo del pronóstico del UK Met Office contra PISCOp

> Capítulo técnico. **Resultado corto:** la corrección arregla la calibración (el modelo marca 2,6 veces más lluvia de la que cae) pero **no mejora la detección de huaicos**. Sirve para que un umbral en mm signifique lo que dice, no para acertar más.

## 1. Pregunta

La API de Illapa sirve el pronóstico del modelo global de 10 km del UK Met Office (illapa-engine#6). Sobre las quebradas de Chosica y Chaclacayo marca bastante más lluvia que la observada por el SENAMHI (PISCOp v3.0). ¿Corregir ese sesgo lo hace más útil en los días de huaico?

## 2. Datos

| Dato | Fuente | Detalle |
|---|---|---|
| Lluvia observada | PISCOp v3.0 diario (SENAMHI, GPL-3.0, [Figshare](https://figshare.com/articles/dataset/High-resolution_grids_of_rainfall_for_Peru_-_PISCOp_v3_0_dataset/32411886)) | Promedio de las 6 celdas de 0,1° sobre el valle del Rímac: lon −76,75, −76,65 y −76,55; lat −11,85 y −11,95. Día de 7 a. m. a 7 a. m. (hora de Lima) |
| Pronóstico | Archivo de pronósticos de Open-Meteo (`ukmo_global_deterministic_10km`, CC BY-SA 4.0) | Lluvia por hora en esas mismas 6 celdas, sumada al mismo día. Alineación medida: 0 días de desfase |
| Huaicos | `catalogo/eventos*.csv` (confianza no baja, solo día exacto) | 12 días: 2023-02-17, 02-19, 03-12, 03-14 a 03-18, 04-06, 04-07; 2024-02-08; 2025-02-12 |

Temporadas lluviosas (diciembre a abril) 2022-23, 2023-24 y 2024-25: 454 días. El archivo del modelo empieza a fines de 2022, así que no hay más.

## 3. Método

Código: `src/illapa_research/correccion_sesgo.py` (`uv run python -m illapa_research.correccion_sesgo <PISCOp_d.nc>`).

- **Dos correcciones:** un factor de escala (lluvia observada total sobre lluvia modelada total) y un mapeo empírico de cuantiles (el valor del modelo en cada cuantil pasa a ser el observado; por encima del máximo se suma la diferencia de la cola).
- **Sin ver el dato que se corrige:** cada temporada se corrige con un ajuste hecho solo con las otras dos.
- **Umbrales en mm sacados de PISCOp:** percentiles 90, 95 y 99 de la lluvia observada (4,24, 5,91 y 10,45 mm).
- **Huaico capturado:** el pronóstico del día del huaico, o del día anterior, llega al umbral (la fecha de la prensa puede ser la del día siguiente a la lluvia).
- **Alarmas en los otros días:** el catálogo solo trae huaicos reportados, así que esta tasa es un **máximo** de falsas alarmas, no una medida.

Una corrección monótona **no cambia el orden de los días**. No puede mejorar nada que se mida por percentil; solo cambia cuántos días pasan un umbral dado en mm. Por eso hay dos pruebas.

## 4. Resultados

### 4.1 Con umbrales en mm (calibración)

| Corrección | Umbral (percentil de lo observado) | Sesgo (modelo / observado) | Aciertos | Falsas alarmas | Perdidos | CSI | Huaicos capturados | Alarmas en los otros días |
|---|---|---|---|---|---|---|---|---|
| Sin corregir | 4,24 mm (p90) | 2,57 | 30 | 98 | 16 | 0,21 | 12 de 12 | 25 % |
| Sin corregir | 5,91 mm (p95) | 2,57 | 16 | 69 | 7 | 0,17 | 12 de 12 | 16 % |
| Sin corregir | 10,45 mm (p99) | 2,57 | 5 | 29 | 0 | 0,15 | 8 de 12 | 5 % |
| Escala | 4,24 mm | 0,99 | 14 | 19 | 32 | 0,22 | 8 de 12 | 5 % |
| Escala | 5,91 mm | 0,99 | 7 | 3 | 16 | 0,27 | 5 de 12 | 1 % |
| Escala | 10,45 mm | 0,99 | 0 | 0 | 5 | 0,00 | 0 de 12 | 0 % |
| **Cuantiles** | 4,24 mm | **1,01** | 18 | 29 | 28 | **0,24** | 8 de 12 | 8 % |
| **Cuantiles** | 5,91 mm | **1,01** | 11 | 16 | 12 | **0,28** | 8 de 12 | 4 % |
| **Cuantiles** | 10,45 mm | **1,01** | 3 | 1 | 2 | **0,50** | 4 de 12 | 0 % |

- El sesgo pasa de 2,57 a 1,0 con cuantiles y el error medio de 2,64 a 1,23 mm por día.
- Con los mismos umbrales en mm, el modelo sin corregir **alarma de más** (25 % de los otros días con 4,24 mm) y captura todos los huaicos; el corregido alarma poco y deja pasar más huaicos. El CSI sube (0,21 → 0,24; 0,17 → 0,28; 0,15 → 0,50) porque desaparecen las falsas alarmas.
- La **escala** es peor que los cuantiles: aplasta los días fuertes (con el umbral de p99 no detecta ninguno), porque el sesgo no es uniforme: el modelo exagera más la lluvia débil que la fuerte.
- La correlación baja un poco (0,60 → 0,58 con cuantiles): es el costo de ajustar cada temporada con las otras dos.

### 4.2 A igual proporción de alarmas (habilidad)

Cada variante puede alarmar la misma parte de los otros días. Aquí desaparece la diferencia de calibración.

| Alarmas en los otros días | Sin corregir | Escala | Cuantiles |
|---|---|---|---|
| 5 % | 8 de 12 (umbral 10,45 mm) | 8 de 12 (4,15 mm) | 8 de 12 (5,19 mm) |
| 10 % | 10 de 12 (7,85 mm) | 10 de 12 (2,99 mm) | 10 de 12 (3,77 mm) |
| 25 % | 12 de 12 (4,14 mm) | 12 de 12 (1,60 mm) | 12 de 12 (1,51 mm) |

**Capturan exactamente los mismos huaicos.** Corregir el sesgo no hace que el modelo detecte más huaicos con las mismas falsas alarmas: solo cambia el número de mm que corresponde a cada nivel de alarma. Sin corregir, para alarmar el 10 % de los días hace falta un umbral de 7,85 mm; corregido, 3,77 mm, cerca de lo que mide PISCOp.

## 5. Qué significa

- **Para decidir qué pronóstico es mejor, el sesgo no importa**: se compara por orden de los días o a igual proporción de alarmas, y ahí la corrección no cambia nada.
- **Para comparar con umbrales en mm (los de SENAMHI, los de la literatura, 13,4 mm en 8 horas de Cusipata) sí hace falta corregirlo**; con el modelo crudo un umbral de 10 mm salta 2,6 veces más de lo debido.
- Mejor usar cuantiles que escala.
- Mejorar la **detección** pide otra cosa: más información (humedad del suelo, intensidad horaria, lluvia previa; capítulos 04 y 05), no un ajuste de la salida del modelo.

## 6. Límites

- **12 días de huaico** de 3 temporadas y en realidad pocos episodios (2023-02, 2023-03, 2023-04, 2024-02, 2025-02): una diferencia de uno o dos huaicos no es evidencia.
- Las fechas del catálogo son de prensa y de varias fuentes; puede haber un día de error (por eso la ventana de un día antes).
- PISCOp sobre la sierra se interpola con pocas estaciones: puede **subestimar** la lluvia, y entonces el sesgo del modelo sería menor que 2,6. La corrección lleva al modelo hacia PISCOp, no hacia la verdad.
- Se usó el promedio de 6 celdas de 0,1°; los pluviómetros reales (`catalogo/senamhi_estaciones_cercanas.csv`) quedarían como segundo contraste.
- El archivo del modelo (Open-Meteo) trae solo las primeras horas de cada corrida; para pronósticos a 24 o más horas el sesgo puede ser distinto.
- No es un sistema de alerta ni una predicción para decidir evacuaciones.

## 7. Qué falta

- Repetir con la temporada 2025-26 (y las siguientes), con más huaicos.
- Los pluviómetros automáticos del SENAMHI (hora por hora) como referencia, en vez de PISCOp.
- Aplicar el mapeo de cuantiles en la API solo si el umbral que se muestre al usuario está en mm; si no, no cambia nada.
