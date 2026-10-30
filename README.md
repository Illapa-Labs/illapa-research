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
| `src/illapa_research/grafo.py` | La red de ríos y quebradas como grafo dirigido, y la propagación del riesgo aguas abajo |
| `notebooks/` | `01-red-de-quebradas`: de Chaclacayo a Chosica |
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

## Datos

La licencia AGPL cubre el **código**, no los datos. Cada fuente tiene su propia licencia; mira [DATOS.md](DATOS.md). Por ahora no se incluyen datos del SENAMHI ni del INEI: falta su autorización por escrito.

## Colaborar

Lee [CONTRIBUTING.md](CONTRIBUTING.md) y el [Código de Conducta](CODE_OF_CONDUCT.md).

## Licencia

Código bajo [AGPL-3.0-or-later](LICENSE). Los datos conservan la licencia de su fuente.
