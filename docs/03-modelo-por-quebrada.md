# 03 · Ranking de quebradas y modelo jerárquico

## Pregunta

Entre las quebradas con nombre ubicado, ¿cuáles se activan más en temporadas El Niño, y se puede ordenar a las demás por su terreno?

## Datos y definiciones

- Catálogo de huaicos: 150 fechas con día exacto y confianza no baja (`catalogo/eventos*.csv`); 48 se ubican en una cuenca, 18 nombran una quebrada sin cuenca y 84 no dicen cuál. Las fechas por quebrada se asignan con `catalogo/quebradas_referencias.csv` (capítulo 01).
- Temporada = diciembre a abril, con el año de enero. **Niño** = Niño global (ONI de NOAA ≥ +0,5 °C en DJF-JFM-FMA) o Niño costero oficial (ICEN del IGP/ENFEN: evento de la lista que cubre al menos dos de febrero-abril, o ICEN medio de enero a abril ≥ +0,4 °C después de la lista). 22 temporadas de 45. Los umbrales se fijaron antes de mirar los huaicos; el proxy anterior (Niño 1+2 ≥ +1,0 °C, 15 temporadas) queda como sensibilidad.
- Atributos físicos y de exposición: capítulo 01.

## Método

1. **Puntaje físico** (sin pesos): promedio de los percentiles de Melton, pendiente del cauce (10-85 %) y pendiente media entre cuencas de 2 a 50 km².
2. **Niveles** (regla fija): 1 = activada en 2 o más temporadas Niño; 2 = en una; 3-5 = sin historial, por tercio del puntaje físico; 6 = menos de 2 km².
3. **Modelo Gamma-Poisson por temporadas**: `P(activa) = 1 - exp(-λ·ρ^Niño)`, `log λ = μ0 + γ·física + δ·exposición`; `ρ` común a todas las quebradas; Metropolis sobre `(μ0, ρ, γ, δ)` con priors anchos. Se usa la versión por temporadas con al menos un día (y no por días) porque los días se agrupan (23 en 2017).
4. **Validación**: dejando una quebrada fuera (predecir una quebrada nueva), dejando un episodio Niño fuera (predecir temporadas retenidas) y un contraste por temporada que cuenta cuántas quebradas ubicadas se activan (evita que quebradas que se activan juntas inflen la evidencia).

## Resultados (corrida del 30 de octubre de 2026 con 150 fechas de huaico)

- **El Niño sí cambia la frecuencia.** Con cualquier quebrada, 17 de 22 temporadas Niño tienen huaico catalogado contra 10 de 23 (Fisher p = 0,033). Contando quebradas ubicadas activas por temporada: 3,1 contra 0,5 (1983 a 2026, Mann-Whitney p = 0,004) y 4,4 contra 0,7 desde 2009 (p = 0,015). Razón de tasas ρ ≈ 4,7 (IC 80 % 3,0 a 7,8) desde 2009 y 5,9 (4,1 a 8,7) desde 1983. Mucho viene de 2015, 2017, 2019 y 2023, años de mucha cobertura de prensa.
- **La física no ayuda.** γ ≈ 0,0 a +0,1, con intervalo que incluye 0. Dejando un Niño fuera, el percentil físico de las quebradas evaluadas (0 = más susceptible; 50 = azar) va de 13 (Barba Blanca) a 74 (Vallecito), con Pedregal 50 y Quirio 56.
- **El registro sigue a la gente.** Entre las 19 quebradas con alguna activación, los días de activación se correlacionan con los edificios cerca de la salida (Spearman +0,70, p < 0,01) y no con Melton (-0,11) ni con la pendiente del cauce (-0,14). δ ≈ +0,25 a +0,35 (positivo con probabilidad 0,83 a 0,91).
- **Validación.** Dejando una quebrada fuera, el Niño mejora el log score en 14 de 24 quebradas (+12,8 en total contra un modelo sin Niño); la exposición suma +0,3 y la física nada. Dejando un episodio fuera (desde 2009), log score medio -0,350 con Niño contra -0,379 sin Niño, y Brier 0,104 contra 0,110; añadir física o exposición no mejora.
- **Ranking posterior** (rango en una temporada Niño, mediana): Los Laureles 2, Pedregal 3, Quirio 3, Chacrasana 5, Mariscal Castilla 7, California 8, Corrales, La Ronda, Huáscarán y Carossio 9. Las cuencas sin historial ubicado conservan solo el prior: no se pueden ordenar con estos datos.

## Límites

- 24 quebradas con historial, casi todas muy conocidas: la validación mide consistencia, no acierto en quebradas que nadie ha registrado.
- Un «nivel bajo» no es «no se activa»; es que el nombre no se pudo ubicar.
- El catálogo registra lo que se vio y se reportó. 1999-2008 está casi vacío; 2015 en adelante tiene mucha más cobertura.
- El efecto de ρ cambia con la definición de Niño; con el proxy Niño 1+2 (15 temporadas) es mucho más débil. Es un indicio fuerte pero no una cifra para citar sola.

## Reproducir

```bash
uv run descargar-datos --solo igp-icen noaa-enso
uv run filtro-quebradas
uv run modelo-quebradas
```
Notebook: `notebooks/03-filtro-quebradas-nino.ipynb`. Resultados: `catalogo/ranking_*.csv`, `parametros_modelo_quebradas.csv`, `contraste_temporadas_nino.csv`, `validacion_*.csv`.
