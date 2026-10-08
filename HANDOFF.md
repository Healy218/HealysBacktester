# Handoff — October 8, 2026 — H1 earnings drift confirmed on 2026 holdout; paper forward test next

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

**H1 earnings drift is the first V8 strategy confirmed on unseen data** (stock form,
2026 holdout: +22.2%, Sharpe 1.31 vs QQQ 1.12, alpha +13.8%/yr; [evidence](docs/EXPERIMENTS.md)).
The calls form failed its pessimistic-cost dev test (t = 1.84): option costs are
unknown, not disproven. The user approved an Alpaca paper forward test and prefers
options over stocks. Next: agree the paper design with the user (calls vs stock or
both side by side; live SUE pipeline from SEC submissions/companyfacts polling;
entries at 10:30 ET), then build it. The 2026 holdout has been used once; do not
re-tune H1 on it.

Tools ready for reuse: `nn_meta/v8_engine.py` (numba slot simulator, ~5 ms per hourly
variant), `nn_meta/v8_fills.py`, `nn_meta/v8_contract.verify()`,
`nn_meta/v8_parallel.py`.

Constraints: run under `systemd-run --user --scope -p MemoryMax=…`; local footprint a
few GB; stage only your own hunks (other dirty V6/V7 work is not yours).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-before-v8-stage1-verdict.md).
