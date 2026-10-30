# 12 · Cómputo: CPU de todos los núcleos y GPU

> Capítulo técnico: cómo se ejecuta lo pesado y cuánto se gana. No cambia ningún resultado científico.

## Qué es pesado aquí

Un modelo es pequeño (unos 6 500 días × 100 variables). Lo caro son **miles de modelos**: las distribuciones nulas (etiquetas desplazadas dentro de cada temporada y vueltas a ajustar en cada pliegue de «una temporada fuera»), los bootstraps por temporadas y los barridos de regularización. Son problemas pequeños, independientes y casi idénticos: justo lo que una GPU hace en un solo paso.

## Qué se usa

- **CPU, todos los núcleos.** `modelo_diario` usa `joblib` con `n_jobs=-1` (antes 8). En una PC con 24 hilos, la validación anidada de `lluvia+antecedentes` baja de 41,5 s (4 hilos) a 6,3 s, con el mismo resultado (AP 0,282).
- **GPU, PyTorch.** `src/illapa_research/gpu.py` (extra opcional `--extra gpu`):
  - `ajustar_logit_lote`: ajusta cientos de regresiones logísticas L2 a la vez con pasos de Newton, equivalentes a `LogisticRegression(C=...)` de scikit-learn (la prueba `tests/test_gpu.py` lo comprueba contra scikit-learn en CPU a 2e-3);
  - `auc_ap_lote`: AUC y precisión media de muchas filas a la vez (coinciden con scikit-learn a 1e-6);
  - `nulas_desplazadas` y `ap_real_y_nulas`: el mundo real y los nulos con los mismos pliegues y la misma regularización.
  Sin GPU CUDA ni PyTorch, el mismo código corre en CPU (más lento); en Mac usa MPS si existe.
- No se usó la GPU para los modelos pequeños sueltos (regresión logística, árboles de 4 hojas): ahí el tiempo es de arranque, no de cálculo.

## Medidas

PC remota (WSL2 Ubuntu, 24 hilos, RTX 4080 SUPER 16 GB), datos de `lluvia+antecedentes` (6 473 días, 113 columnas, 118 positivos):

| Cálculo | Dispositivo | Tiempo |
|---|---|---|
| 20 mundos nulos (45 pliegues cada uno) | CPU (PyTorch, 24 hilos) | 5,0 s (0,25 s por mundo) |
| 100 mundos nulos | GPU | 1,1 s (0,011 s por mundo) |
| 1 000 mundos nulos | GPU | 6,6 s |
| 2 000 mundos nulos + mundo real, 4 teorías | GPU | 6 a 14 s cada una |

La versión de scikit-learn en serie (`evaluacion_diaria.prueba_nula`, medida en un Mac) tarda unos 1,2 s por mundo; 2 000 mundos serían unos 40 minutos por teoría, contra 6 a 14 s en la GPU (unas 100 a 200 veces menos).

## Resultado científico que esto permitió

Con 2 000 mundos nulos por teoría, ninguno alcanza la precisión media real en ninguna de las cuatro teorías (`p = 0,0005`, el mínimo posible con 2 000 nulos). Archivo: `catalogo/nulas_gpu_modelo_diario.csv`. Misma regularización fija para el real y los nulos (C = 0,03), por eso las AP reales (0,12; 0,25; 0,30; 0,30) difieren un poco de las del capítulo 05, que afina la regularización dentro de cada pliegue.

| Teoría | AP real | AP nula media / p95 / máx | AUC real |
|---|---|---|---|
| lluvia del día | 0,122 | 0,016 / 0,022 / 0,037 | 0,824 |
| antecedentes | 0,247 | 0,024 / 0,041 / 0,081 | 0,888 |
| lluvia + antecedentes | 0,298 | 0,024 / 0,041 / 0,082 | 0,908 |
| + Niño (ICEN causal) | 0,296 | 0,026 / 0,044 / 0,081 | 0,910 |

(Datos del 30 de octubre de 2026: ERA5 en Matucana, Santa Eulalia alta y Ticlio; MERRA-2 de NASA POWER en Chosica, costa de Lima y selva de Tarma.)

## Cómo ejecutar en la PC remota

1. Clonar el repositorio y `uv sync --extra dev --extra notebooks --extra hf --extra gpu`.
2. `uv run --extra hf descargar-datos --desde-hf renzoedu25/illapa-research-datos` baja la copia pública de los datos. Los del IGP no están en la copia: `uv run descargar-datos --solo igp-icen`.
3. Los notebooks se ejecutan con `uv run jupyter nbconvert --to notebook --execute ...` y se guardan **sin** salidas en el repositorio.
4. Los datos del SENAMHI (capítulo 11) no se copian a ningún lado: se quedan en la PC donde se bajaron.

## Límites

- La GPU ajusta con `float32`: el ajuste difiere en el cuarto decimal de la versión de 64 bits; irrelevante para una distribución nula, pero la validación anidada del capítulo 05 sigue en scikit-learn.
- Los nulos usan regularización fija; no repiten la elección anidada de C.
- Hace falta PyTorch con CUDA (el extra `gpu` lo instala; ocupa unos 2 GB).
