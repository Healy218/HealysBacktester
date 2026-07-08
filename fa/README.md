# fa — ticker discovery pipeline (scaffold)

Spec: `../FA_SPEC.md`. Stubs map 1:1 to the spec's build order.
`collectors/` (Stage 0) is the part that deploys EARLY on the live-alert
server — archive-first, because social history can't be bought later.

| Stage | Module | Spec section |
|---|---|---|
| 0 | `collectors/` (reddit, stocktwits, news, edgar) | Raw archive collectors |
| 1 | `entities.py` | Cashtag/name → ticker resolution |
| 2 | `scores.py` | Per-source attention/sentiment velocity z-scores |
| 3 | `overlay.py` | Filings NLP, insider buys, unusual options activity |
| 4 | `ranker.py` | Composite → frozen monthly Top-10 artifact |
| 5 | `tracker.py` | Forward returns + graduation rule |

Shared constants in `config.py`. Every collector writes append-only
timestamped parquet to `archive/<source>/<yyyy-mm>.parquet` and never mutates.
