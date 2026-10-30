# Cómo colaborar

Gracias por querer ayudar. Illapa Research es el kit de investigación de un proyecto comunitario de código abierto: no tiene anuncios, no se monetiza y busca ser útil para quien vive o viaja por zonas de lluvias fuertes en el Perú.

Al participar aceptas el [Código de Conducta](CODE_OF_CONDUCT.md).

## Qué ayuda más

- Revisar y documentar las licencias de las fuentes de datos.
- Mejorar la red de quebradas: nombres, tramos que faltan, sentido del flujo.
- Notebooks nuevos y reproducibles, con la fuente de cada dato citada.
- Pruebas y comparación de resultados con eventos pasados (por ejemplo, los huaicos de Chosica).

## Ramas y flujo de trabajo

Usamos [GitHub Flow](https://docs.github.com/es/get-started/using-github/github-flow): una sola rama principal y ramas cortas por cambio.

- `main` es la rama de producción: siempre debe compilar y poder desplegarse. Está protegida y no se escribe en ella directamente.
- Cada cambio va en una rama creada desde `main`, con un nombre del tipo `tipo/descripcion-corta`: `feat/grafo-rios`, `fix/sentido-quebrada`.
- Si no formas parte del equipo, trabaja desde tu *fork* y envía el *pull request* a `main`.
- Para fusionar, un *pull request* necesita al menos una aprobación y que pasen las revisiones. Se fusiona con *squash merge*, así que el título debe seguir Conventional Commits en inglés: será el mensaje del commit en `main`.

## Antes de enviar

```bash
uv run ruff check .
uv run pytest
```

Los notebooks se suben con las salidas borradas y deben correr de arriba abajo con `datos/` recién descargado.

## Estilo

- Los mensajes de commit siguen [Conventional Commits](https://www.conventionalcommits.org) en inglés, por ejemplo `feat(grafo): add downstream risk propagation`.
- Los nombres en el código y los comentarios técnicos van en inglés. Los nombres de dominio (`quebrada`, `aguas_abajo`, `riesgo`) van en español, como en el resto de Illapa Labs.
- Las unidades van en el nombre del campo cuando hay unidades (`pp_mm`, `area_km2`).
- No inventes datos: si falta una fuente, el resultado lo dice; nunca se rellena con cero. No subas datos sin licencia clara.
- Nada de secretos en el repositorio.

## Licencia de tus aportes

El proyecto se distribuye bajo la [AGPL-3.0-or-later](LICENSE). Al enviar un aporte aceptas que se publique bajo esa misma licencia; sigues siendo la persona autora de lo que escribes. No incluyas código que no puedas publicar bajo la AGPL; los datos van con la licencia de su fuente.

## Seguridad

Si encuentras un problema de seguridad, no lo publiques en un *issue*: escribe a contacto@illapalabs.org.
