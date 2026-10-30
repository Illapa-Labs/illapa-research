[Español](CONTRIBUTING.md) | **English**

# How to contribute

Thank you for wanting to help. Illapa Research is the research kit of a community open source project: it has no ads, it is not monetized, and it aims to be useful to people who live in or travel through areas of heavy rain in Peru.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.en.md).

## What helps most

- Reviewing and documenting the licenses of the data sources.
- Improving the ravine network: names, missing stretches, direction of flow.
- New, reproducible notebooks, citing the source of every dataset.
- Tests, and comparing results with past events (for example the Chosica huaicos).

## Branches and workflow

We use [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow): a single main branch and short branches for each change.

- `main` is the production branch: it must always build and be deployable. It is protected and nobody writes to it directly.
- Each change goes on a branch created from `main`, named `type/short-description`: `feat/river-graph`, `fix/stream-direction`.
- If you are not part of the team, work from your fork and send the pull request to `main`.
- To merge, a pull request needs at least one approval and passing checks. It is merged with a squash merge, so the title must follow Conventional Commits in English: it becomes the commit message on `main`.

## Before sending

```bash
uv run ruff check .
uv run pytest
```

Notebooks are committed with their outputs cleared and must run top to bottom on a freshly downloaded `datos/`.

## Style

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org) in English, for example `feat(grafo): add downstream risk propagation`.
- Identifiers and technical comments are in English. Domain names (`quebrada`, `aguas_abajo`, `riesgo`) are in Spanish, as in the rest of Illapa Labs.
- Units go in the field name when there are units (`pp_mm`, `area_km2`).
- Do not make up data: if a source is missing, the result says so; it is never filled with zero. Do not commit data without a clear licence.
- No secrets in the repository.

## License of your contributions

The project is distributed under the [AGPL-3.0-or-later](LICENSE). By sending a contribution you agree that it is published under that same license; you remain the author of what you write. Do not include code you cannot publish under the AGPL; data keeps the license of its source.

## Security

If you find a security problem, do not publish it in an issue: write to contacto@illapalabs.org.
