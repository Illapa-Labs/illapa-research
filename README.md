<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/chakana-mark-for-dark-backgrounds.svg">
    <img alt="Illapa Labs" src="branding/chakana-mark-for-light-backgrounds.svg" width="96">
  </picture>
</p>

# Illapa Research

[![Licencia: AGPL v3](https://img.shields.io/badge/licencia-AGPL%20v3-blue.svg)](LICENSE)

El kit de investigación de [Illapa Labs](https://github.com/Illapa-Labs): un script que descarga y ordena datos abiertos, notebooks para explorarlos y, más adelante, modelos para entender la lluvia y los peligros naturales en el Perú y los Andes.

> **No es un sistema oficial de alerta.** Es investigación en curso. Ante una emergencia llama al 115 (INDECI) o al 116 (Bomberos).

## Qué hay

| Carpeta | Qué contiene |
|---|---|
| `src/illapa_research/fuentes.py` | Las fuentes de datos, cada una con su licencia y su atribución |
| `src/illapa_research/descargar.py` | El script `descargar-datos` |
| `src/illapa_research/estudio_eventos.py` | Percentiles de lluvia en los días de huaico y aciertos contra alarmas por año |
| `src/illapa_research/grafo.py` | La red de ríos y quebradas como grafo dirigido, y la propagación del riesgo aguas abajo |
| `src/illapa_research/quebradas.py` | Delimita con el DEM las cuencas que drenan al Rímac y a Santa Eulalia y calcula sus atributos físicos |
| `src/illapa_research/nino.py`, `filtro.py`, `modelo.py` | Temporadas con El Niño (NOAA) y ranking de quebradas por evidencia física e historial |
| `src/illapa_research/predictores.py`, `evaluacion_diaria.py`, `senales.py`, `modelo_diario.py`, `integracion.py` | Señales diarias (mar, calor aguas arriba, humedad de la selva, caudal, suelo), análisis de rezagos, modelo de «día con huaico» validado fuera de muestra, y su unión con las quebradas |
| `src/illapa_research/banco_modelos.py`, `satelite.py`, `satelite_piloto.py` | Banco de modelos (logística, boosting monótono, GRU, conjunto) y piloto de etiquetas con satélite (Sentinel-2) |
| `notebooks/` | 16 cuadernos numerados del 01 al 17 (red de quebradas, estudio de eventos, filtro, señales, modelo diario, calidad de etiquetas, circulación, hipótesis de la literatura, SENAMHI, ficha de probabilidad, backtests con pronóstico y GEFS, ficha desde pronóstico, quebradas y día) |
| `docs/` | 25 capítulos de investigación (plan, cuencas, modelo por quebrada, señales, modelo diario, pronóstico, banco de modelos, satélite) con sus datos, métodos, cifras y límites |
| `catalogo/` | Eventos de huaico y polígonos de cuenca del piloto (Chosica y Chaclacayo) |
| `tests/` | Pruebas del código |

## Empezar

Necesitas [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra notebooks
uv run descargar-datos --listar
uv run descargar-datos
uv run jupyter lab notebooks/
```

`descargar-datos` deja todo en `datos/` (no se sube al repositorio) junto con un `MANIFIESTO.json` que registra la licencia, la atribución y la fecha de cada fuente. Con `--solo osm-aguas` baja una sola fuente.

## Filtro de quebradas para El Niño

```bash
uv run descargar-datos --solo copernicus-dem osm-aguas osm-edificios noaa-enso
uv run delimitar-quebradas   # escribe catalogo/cuencas.geojson (124 cuencas)
uv run filtro-quebradas      # escribe catalogo/ranking_quebradas_nino.csv y la validación
uv run modelo-quebradas      # modelo Gamma-Poisson por quebrada: rangos posteriores y razón de tasas del Niño
```

El ranking mezcla dos cosas que se mantienen separadas: la susceptibilidad física de la cuenca (sin pesos ajustados) y las activaciones documentadas en temporadas Niño. Hoy 25 cuencas tienen nombre ubicado (entre ellas Quirio, Pedregal, Los Laureles, Chacrasana, La Ronda, California, Huáscarán, Carossio, Huampaní y Carapongo; lista completa en `docs/01`) porque el catálogo no trae coordenadas de las demás quebradas; las reglas, la validación dejando un Niño fuera y sus límites están en [catalogo/README.md](catalogo/README.md). Es investigación, no una alerta. Los capítulos en [docs/](docs/README.md) explican cada paso y qué falló.

## Qué se ha aprendido hasta ahora (31 de octubre de 2026)

Resumen honesto; el detalle, las cifras con intervalos y los límites están en los capítulos de [docs/](docs/README.md).

- **El Niño sí importa, y es costero.** Con el ICEN oficial, 17 de 22 temporadas Niño tienen huaico catalogado contra 10 de 23 (Fisher p = 0,033); la razón de tasas por quebrada ronda 4,7 (IC 80 % 3,0 a 7,8). E y C (índices del Niño costero y central): gana el ICEN. El efecto cambia con la definición de Niño y viene en buena parte de 2015, 2017, 2019 y 2023, años de mucha cobertura de prensa.
- **El terreno no ordena las quebradas que se activan.** Melton y las pendientes no discriminan (γ ≈ 0, intervalo con 0). El historial sigue a los edificios cerca de la salida (Spearman +0,70 en las 19 quebradas con alguna activación): el catálogo registra donde vive la gente. Hay 25 cuencas con nombre ubicado, de 124 delimitadas.
- **Qué día hay condiciones sí tiene señal.** Dejando una temporada fuera, lluvia más antecedentes (suelo, lluvia previa, caudal, mar) da precisión media 0,29 contra una base de 0,019, y el 5 % de días en alarma contiene el 53 % de los días con huaico. 2 000 mundos nulos en la GPU no se le acercan (p = 0,0005). Pero cuatro de cada cinco alarmas fallan, sin 1983, 1998 y 2017 baja a 0,19, y con 118 columnas para 121 positivos hay sobreajuste (0,45 dentro de muestra). **No es una alerta.**
- **Qué cambia días antes, y qué no.** El mar cálido es un régimen lento entre temporadas más que un disparador (alza de 14 días del mar: AUC 0,64-0,66, débil). No hay calor previo aguas arriba: lo que se ve es el frío de la tormenta. La humedad de la selva no precede. Viento y humedad a 850 hPa (T19) pareció una señal y se cayó con ERA5 completo y 2 000 nulos. Viento en 200 hPa, OLR, Madden-Julian, SOI y altura a 500 hPa no mejoran el modelo. La hora de la lluvia no distingue; la duración sí un poco.
- **Datos observados valen más que reanálisis.** Los pluviómetros del SENAMHI (con su leyenda; ver [DATOS.md](DATOS.md)) mejoran mucho al modelo de solo lluvia en 1990-2013 (precisión media 0,23 contra 0,09 con ERA5) y no se distinguen de cero en 2014-2026 con antecedentes. Las lluvias satelitales PERSIANN-CDR y CPC no mejoran ni sustituyen a ERA5.
- **Día × quebrada.** El producto de la probabilidad del día por la participación de cada quebrada predice un poco mejor qué quebrada se activa qué día (precisión media 0,029 contra 0,017 de solo el día); la parte «día» hace casi todo.
- **Ficha de probabilidad.** Para un día dado: probabilidad de un día con huaico catalogado, con intervalo, fiabilidad histórica por banda, condiciones que empujan hacia arriba y reparto por quebrada; calibrada en conjunto pero no por era ni por régimen (ver [docs/15](docs/15-ficha-de-probabilidad.md)). No es una alerta.
- **Con pronóstico de lluvia (backtest).** El reforecast GEFSv12 de 2000 a 2019 (55 días con huaico; 32 sin 2017) conserva el 67 % de la ganancia de la lluvia perfecta a 24 h, 45 % a 48 h y 39 % a 72 h (precisión media 0,254, 0,169 y 0,131 contra 0,366, 0,345 y 0,297 con lluvia ERA5; base 0,019). Sin 2017 baja a 0,102 a 24 h y queda empatado con un modelo simple, y el pronóstico sobreestima (de 63 días con probabilidad de 25 % o más, el 28,6 % tuvo huaico). Con el UK Met Office a 10 km y plazo 0 se llega al techo (precisión media 0,62) en 4 temporadas con 14 huaicos; desde plazo 2 no se distingue del azar. Ver [docs/17](docs/17-backtest-con-pronostico.md) y [docs/19](docs/19-backtest-gefs-reforecast.md). Sigue sin ser una alerta.
- **Quebrada y día (catálogo mejorado).** Con lluvia observada, multiplicar la probabilidad del día por la participación histórica de cada quebrada mejora la precisión media de los pares (0,029 contra 0,017; la diferencia excluye 0, también sin 2017) y las 5 quebradas con más historial cubren el 44 % de las activaciones contra 21 % esperado; con el pronóstico GEFS la ventaja no se distingue de cero. Ver [docs/21](docs/21-quebradas-y-dia.md).
- **Ficha desde pronóstico.** Con un pronóstico de lluvia a 24, 48 o 72 h la ficha informa la frecuencia observada de días con huaico en la banda de probabilidad, con intervalo y advertencias: a 24 h la banda de 25 % o más tuvo huaico en 41 % de 27 días (20 % sin 2017); a 48 y 72 h esa banda no es fiable (15 % y 8 %). Ver [docs/20](docs/20-ficha-desde-pronostico.md).
- **Datos del Estado.** INGEMMET, SINPAD y CENEPRED (FEN 2027) aportaron 4 cuencas nuevas (Huampaní, La Laguna, Carapongo, Señor de los Milagros) y 2 fechas verificadas de Callahuanca; el 77,5 % de los puntos nombrados de INGEMMET cae en la cuenca que habíamos asignado. Coinciden con las listas oficiales Quirio, Pedregal, Chacrasana y La Ronda; Santo Domingo, Cusipata y las quebradas sin historial quedan abajo en nuestro ranking (ver [docs/18](docs/18-datos-del-estado.md)).
- **Qué modelo.** Probamos logística regularizada, boosting con relaciones monótonas, una red recurrente (GRU) y un conjunto con la misma validación (una temporada fuera): **la logística sigue siendo la mejor** (AP 0,30; la GRU queda 0,08 por debajo, con intervalo que excluye el cero). Con 123 días con huaico un modelo más grande no ayuda (ver [docs/24](docs/24-banco-de-modelos.md)). El SINPAD público tampoco sirve para entrenar con todo el país: solo registra desde 2019 y recoge una quinta parte de los huaicos de nuestra zona.
- **Los límites son de los datos, no del modelo.** De 152 fechas con día exacto, 55 tienen quebrada ubicada y solo unas 11 quebradas pasan de 4 días de historial; 4 temporadas (1983, 1998, 2017, 2023) pesan casi la mitad. Cuatro agentes de búsqueda y la revisión del archivo del INDECI y de datos abiertos sumaron 7 fechas ubicadas; el conjunto de emergencias históricas del INDECI en datos abiertos tiene los archivos caídos (404). **Etiquetas objetivas con satélite:** dos diseños con Sentinel-2 (disco de la salida y cauce del DEM, 10 a 20 m) no separan las cuencas activadas de las demás (AUC 0,43 a 0,61, ver [docs/25](docs/25-etiquetas-con-satelite.md)). Con celdas de 10 a 25 km, la lluvia de Chosica predice igual de bien los eventos de Santa Eulalia: la lluvia por zona no ayuda.
- **Qué falta.** Una validación prospectiva en la temporada 2026-27 (el ranking y la ficha se fijan antes y se comparan con los avisos oficiales y los reportes del COEN); etiquetas de gravedad y localización (coordenadas o kilómetro de la Carretera Central) en vez de nombres; coordenadas de Cashahuacra, Huaycoloro, Cuculí, Lucumaseca y Palle; fechas verificadas de 1999-2008 y de 1983-1998 (solo salen de hemeroteca de papel); CAPE y agua precipitable (piden cuenta de Copernicus).

## Datos

La licencia AGPL cubre el **código**, no los datos. Cada fuente tiene su propia licencia; mira [DATOS.md](DATOS.md). Los datos del SENAMHI se usan y se redistribuyen con la leyenda que piden sus términos de uso (ver [DATOS.md](DATOS.md)); los del INEI (Censo 2017) siguen sin incluirse.

## Datos en Hugging Face

Las APIs gratuitas limitan las llamadas, así que hay una copia pública de `datos/` en [renzoedu25/illapa-research-datos](https://huggingface.co/datasets/renzoedu25/illapa-research-datos): `uv run --extra hf descargar-datos --desde-hf renzoedu25/illapa-research-datos`. Cada archivo conserva la licencia de su fuente (revisión en [DATOS.md](DATOS.md)); los datos del IGP no se incluyen por no traer licencia explícita.

## Reproducir los cuadernos

Con los datos del espejo cualquiera puede correr los 16 cuadernos de `notebooks/` sin repetir las descargas (los 100 GB de archivos GEFS originales no se usan: del reforecast solo se guarda la serie reducida a cuatro cajas, 5 MB):

```bash
git clone https://github.com/Illapa-Labs/illapa-research.git && cd illapa-research
uv sync --extra notebooks --extra hf --extra gpu        # `gpu` es opcional: sin CUDA todo corre en CPU, más lento
uv run --extra hf descargar-datos --desde-hf renzoedu25/illapa-research-datos
uv run descargar-datos --solo igp-icen igp-ec bom-rmm    # fuentes que el espejo no incluye (sin licencia explícita)
cd notebooks && uv run jupyter nbconvert --to notebook --execute --inplace 05-modelo-diario.ipynb
```

Para una corrida rápida de comprobación: `ILLAPA_N_NULL=200 ILLAPA_B=200 ILLAPA_NULAS=20 ILLAPA_GPU=1` (menos réplicas y mundos nulos; las cifras cambian en la tercera cifra). Las fuentes opcionales (INGEMMET, CENEPRED, INDECI, SENAMHI crudo) no son necesarias para los cuadernos; se piden con `descargar-datos --solo <id>`. Los cuadernos se ejecutaron todos desde un clon limpio con estos pasos (resultado en la sección siguiente de cada capítulo).

## Colaborar

Lee [CONTRIBUTING.md](CONTRIBUTING.md) y el [Código de Conducta](CODE_OF_CONDUCT.md).

## Licencia

Código bajo [AGPL-3.0-or-later](LICENSE). Los datos conservan la licencia de su fuente.
