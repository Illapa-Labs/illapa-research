[Español](README.md) | **English**

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/chakana-mark-for-dark-backgrounds.svg">
    <img alt="Illapa Labs" src="branding/chakana-mark-for-light-backgrounds.svg" width="96">
  </picture>
</p>

# Illapa Research

[![License: AGPL v3](https://img.shields.io/badge/license-AGPL%20v3-blue.svg)](LICENSE)

The research kit of [Illapa Labs](https://github.com/Illapa-Labs): a script that downloads and organises open data, notebooks to explore it and, later on, models to understand rain and natural hazards in Peru and the Andes.

> **This is not an official warning system.** It is ongoing research. In an emergency in Peru, call 115 (INDECI) or 116 (Fire Department).

## What is here

| Folder | Contents |
|---|---|
| `src/illapa_research/fuentes.py` | The data sources, each with its licence and attribution |
| `src/illapa_research/descargar.py` | The `descargar-datos` script |
| `src/illapa_research/grafo.py` | The river and ravine network as a directed graph, and downstream risk propagation |
| `notebooks/` | `01-red-de-quebradas`: from Chaclacayo to Chosica |
| `tests/` | Code tests |

## Getting started

You need [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra notebooks
uv run descargar-datos --listar
uv run descargar-datos
uv run jupyter lab notebooks/
```

`descargar-datos` writes everything to `datos/` (not committed) along with a `MANIFIESTO.json` recording each source's licence, attribution and download date. Use `--solo osm-aguas` to fetch a single source.

## Data

The AGPL covers the **code**, not the data. Each source has its own licence; see [DATOS.en.md](DATOS.en.md). SENAMHI and INEI data are not included for now: written authorisation is still pending.

## Contributing

Read [CONTRIBUTING.en.md](CONTRIBUTING.en.md) and the [Code of Conduct](CODE_OF_CONDUCT.en.md).

## Licence

Code under [AGPL-3.0-or-later](LICENSE). Data keeps the licence of its source.
