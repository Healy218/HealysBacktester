# v3 historical data and technical indicators

This directory contains implemented historical-data and indicator tools plus a few superseded scaffold entry points. The meta-labeling orchestration lives in `nn_meta/`; the historical design is [V3_SPEC.md](../docs/specs/V3_SPEC.md).

| Modules | Implemented role |
|---|---|
| `flatfiles.py`, `derive_contracts.py` | Ingest minute option aggregates and derive contract/daily archives |
| `underlying.py`, `build_underlying.py` | Crawl underlying bars and build resampled views |
| `indicators.py`, `tv_rating.py` | Technical indicators and composite ratings |
| `audit_data.py`, `pilot_tv.py`, `gbt_baseline.py` | Historical coverage/pilot/baseline tools |
| `select_120.py` | Historical liquidity-based bootstrap selection |

`universe.select_universe` remains a scaffold; the implemented monthly PIT workflow is `nn_meta/universe_pit.py`. Check individual modules rather than assuming every old spec-stage entry point is operational. Historical bootstrap universes and pilot reports do not establish current point-in-time performance.

See [current repair status](../docs/reviews/2026-09-05-remediation.md) before reusing derived artifacts. Preserve existing raw archives and rebuild derived outputs with the current causal/provenance contract.
