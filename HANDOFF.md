# Handoff — October 8, 2026 — H1 paper test live; next phase: options-native, high-risk, Kelly-sized

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

No jobs running. V6 paper retired Oct 8: account archived (`nn_meta/validation/v6-paper-archive-20261008/`), V6 retired for good by the user (needed the cancelled paid feed), timers disabled; the H1 paper test runs in "stonks bot 2" (PA3U9D8Q8GQX); its timers are enabled from 2026-10-09. The 2026 holdout has not
been read by any stage-1 code.

## Next action

The H1 paper test is live in "stonks bot 2" (first runs 2026-10-09; first signals with
mid/late-October earnings). Review it after the first earnings wave.

**User direction for the next phase (Oct 8):** options-native, short-term,
high-risk/high-reward, fractional-Kelly sizing with 10–20% downside caps
([DECISIONS](docs/DECISIONS.md)). Agree the research plan with the user before building:
candidates include options-flow signals from the OPRA day aggregates we already hold
(2021–2026), H1 expressed through calls with Kelly sizing once paper fills exist, and a
Kelly/risk module fed only by out-of-sample trade statistics.

Tools ready for reuse: `nn_meta/v8_engine.py` (numba slot simulator, ~5 ms per hourly
variant), `nn_meta/v8_fills.py`, `nn_meta/v8_contract.verify()`,
`nn_meta/v8_parallel.py`.

Constraints: run under `systemd-run --user --scope -p MemoryMax=…`; local footprint a
few GB; stage only your own hunks (other dirty V6/V7 work is not yours).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-before-v8-stage1-verdict.md).
