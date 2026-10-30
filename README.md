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
| `notebooks/` | `01-red-de-quebradas`, `02-estudio-de-eventos`, `03-filtro-quebradas-nino`, `04-senales-y-rezagos`, `05-modelo-diario` y `06-dia-y-quebrada` |
| `docs/` | Capítulos de investigación (plan, cuencas, modelo por quebrada, señales, modelo diario) con sus datos, métodos, cifras y límites |
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

El ranking mezcla dos cosas que se mantienen separadas: la susceptibilidad física de la cuenca (sin pesos ajustados) y las activaciones documentadas en temporadas Niño. Hoy 22 cuencas tienen nombre ubicado (Quirio, Pedregal, Los Laureles, Chacrasana, La Ronda, Barba Blanca, California, Corrales, Huáscarán, Santa Inés, Cobián, Yanacoto, Vallecito, Cusipata, Santo Domingo, La Cantuta, Cupiche, Carossio, La Libertad, Mariscal Castilla y, dudosa, Río Seco) porque el catálogo no trae coordenadas de las demás quebradas; las reglas, la validación dejando un Niño fuera y sus límites están en [catalogo/README.md](catalogo/README.md). Es investigación, no una alerta. Los capítulos en [docs/](docs/README.md) explican cada paso y qué falló.

## Qué se ha aprendido hasta ahora (30 de octubre de 2026)

Resumen honesto; el detalle, las cifras con intervalos y los límites están en los capítulos de [docs/](docs/README.md).

- **El Niño sí importa, y es costero.** Con el ICEN oficial, 17 de 22 temporadas Niño tienen huaico catalogado contra 10 de 23 (Fisher p = 0,033); la razón de tasas por quebrada ronda 4,9 (IC 80 % 3,0 a 8,1). E y C (índices del Niño costero y central): gana el ICEN. El efecto cambia con la definición de Niño y viene en buena parte de 2015, 2017, 2019 y 2023, años de mucha cobertura de prensa.
- **El terreno no ordena las quebradas que se activan.** Melton y las pendientes no discriminan (γ ≈ -0,2, intervalo con 0). El historial sigue a los edificios cerca de la salida (Spearman +0,61 en 20 quebradas): el catálogo registra donde vive la gente. Hay 22 cuencas con nombre ubicado, de 124 delimitadas.
- **Qué día hay condiciones sí tiene señal.** Dejando una temporada fuera, lluvia más antecedentes (suelo, lluvia previa, caudal, mar) da precisión media 0,28 contra una base de 0,018, y el 5 % de días en alarma contiene el 53 % de los días con huaico. 2 000 mundos nulos en la GPU no se le acercan (p = 0,0005). Pero cuatro de cada cinco alarmas fallan, sin 1983, 1998 y 2017 baja a 0,19, y con 118 columnas para 119 positivos hay sobreajuste (0,45 dentro de muestra). **No es una alerta.**
- **Qué cambia días antes, y qué no.** El mar cálido es un régimen lento entre temporadas más que un disparador (alza de 14 días del mar: AUC 0,64-0,66, débil). No hay calor previo aguas arriba: lo que se ve es el frío de la tormenta. La humedad de la selva no precede. Viento y humedad a 850 hPa (T19) pareció una señal y se cayó con ERA5 completo y 2 000 nulos. Viento en 200 hPa, OLR, Madden-Julian, SOI y altura a 500 hPa no mejoran el modelo. La hora de la lluvia no distingue; la duración sí un poco.
- **Datos observados valen más que reanálisis.** Los pluviómetros del SENAMHI (con su leyenda; ver [DATOS.md](DATOS.md)) mejoran mucho al modelo de solo lluvia en 1990-2013 (precisión media 0,23 contra 0,07 con ERA5) y no se distinguen de cero en 2014-2026 con antecedentes. Las lluvias satelitales PERSIANN-CDR y CPC no mejoran ni sustituyen a ERA5.
- **Día × quebrada.** El producto de la probabilidad del día por la participación de cada quebrada predice un poco mejor qué quebrada se activa qué día (precisión media 0,027 contra 0,018 de solo el día); la parte «día» hace casi todo.
- **Ficha de probabilidad.** Para un día dado: probabilidad de un día con huaico catalogado, con intervalo, fiabilidad histórica por banda, condiciones que empujan hacia arriba y reparto por quebrada; calibrada en conjunto pero no por era ni por régimen (ver [docs/14](docs/14-ficha-de-probabilidad.md)). No es una alerta.
- **Qué falta.** Coordenadas de Cashahuacra, Huampaní, Huascata y otras; lluvia de montaña horaria entre 2014 y 2017; fechas verificadas de 1999-2008; CAPE y agua precipitable (piden cuenta de Copernicus).

## Datos

La licencia AGPL cubre el **código**, no los datos. Cada fuente tiene su propia licencia; mira [DATOS.md](DATOS.md). Los datos del SENAMHI se usan y se redistribuyen con la leyenda que piden sus términos de uso (ver [DATOS.md](DATOS.md)); los del INEI (Censo 2017) siguen sin incluirse.

## Datos en Hugging Face

Las APIs gratuitas limitan las llamadas, así que hay una copia pública de `datos/` en [renzoedu25/illapa-research-datos](https://huggingface.co/datasets/renzoedu25/illapa-research-datos): `uv run --extra hf descargar-datos --desde-hf renzoedu25/illapa-research-datos`. Cada archivo conserva la licencia de su fuente (revisión en [DATOS.md](DATOS.md)); los datos del IGP no se incluyen por no traer licencia explícita.

## Colaborar

Lee [CONTRIBUTING.md](CONTRIBUTING.md) y el [Código de Conducta](CODE_OF_CONDUCT.md).

## Licencia

Código bajo [AGPL-3.0-or-later](LICENSE). Los datos conservan la licencia de su fuente.
