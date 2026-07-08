# v3 — big-universe TA pipeline (scaffold)

Spec: `../V3_SPEC.md`. Not started; stubs map 1:1 to the spec's build order.

| Stage | Module | Spec section |
|---|---|---|
| 0 | `audit_data.py` | Data audit (gates the window choice) |
| 1 | `universe.py` | Point-in-time universe selection |
| 2 | `underlying.py` | 1m crawl → resample stack → parquet |
| 3 | `indicators.py` | TV-validated indicator library |
| 4–5 | `pilot.py` | SPY pilot, then diverse-basket calibration |
| 6 | `dataset.py` | Parallel full-universe dataset build |
| 7–8 | `models.py` | GBT-vs-NN bake-off, walk-forward + regime report |

Shared constants live in `config.py`. Nothing here runs yet; each stub raises
`NotImplementedError` with its contract in the docstring.
