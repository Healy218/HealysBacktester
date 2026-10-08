# Handoff — October 8, 2026 — V8 stages 1 and 2 FAILED; event/FA backfill built, hypotheses next

## Where things stand

- **V8** ([ROADMAP](ROADMAP.md#v8--edge-first-on-liquid-stocks-and-etfs),
  [spec](docs/specs/V8_DESIGN_20261007.md), [TODO](TODO.md)): prove an edge on liquid
  stocks/ETFs under realistic fills before any model or options.
- **Stage 0 complete:** frozen [contract](docs/specs/V8_CONTRACT_20261008.json) (pool
  with delisted names, hourly/daily bars, measured stock/option spreads, user-approved
  [liquidity rule](docs/specs/V8_LIQUIDITY_20261008.json), [cost table](docs/specs/V8_COSTS_20261008.json)).
- **Stage 1 FAILED** (pre-registered, committed `d5cd2ad` before results): 5,680
  long-only variants (1h/1d), 10-slot equal weight, six half-year folds 2023–2025.
  The top in-sample pick beat every benchmark in 0/6 folds; rank persistence ~0;
  deflated Sharpe 0.05; PBO 0.89. [Evidence](docs/EXPERIMENTS.md).
- **User decisions (Oct 8):** keep delisted names in history; long-only first (shorts
  and puts later); broker path Alpaca paper → Alpaca live → Robinhood much later;
  half-Kelly sizing belongs to the paper simulator after an edge passes, not the test;
  worker pools and vectorized code by default.

## Status at session end

No jobs running. V6 paper paused (one TMUS position open). The 2026 holdout has not
been read by any stage-1 code.

## Next action

Stages 1 and 2 failed. The user chose event-driven/FA history next (Oct 8): free PIT
backfill 2021–2025 is built (SEC facts/filings, insider, FINRA short volume, news;
[evidence](docs/EXPERIMENTS.md)). **Next: V8-EV-prereg** — bring 3–4 literature-backed
hypotheses (e.g. post-earnings drift, insider cluster buying, short-volume ratio,
news-driven continuation) to the user for sign-off before examining any
signal-return relationship.

Tools ready for reuse: `nn_meta/v8_engine.py` (numba slot simulator, ~5 ms per hourly
variant), `nn_meta/v8_fills.py`, `nn_meta/v8_contract.verify()`,
`nn_meta/v8_parallel.py`.

Constraints: run under `systemd-run --user --scope -p MemoryMax=…`; local footprint a
few GB; stage only your own hunks (other dirty V6/V7 work is not yours).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-before-v8-stage1-verdict.md).
