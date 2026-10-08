# Handoff — October 8, 2026 — V8 complete; V9 options experts planned (OEE first)

## Where things stand

- **V9 is the selected work** ([plan](docs/specs/V9_OPTIONS_EXPERTS_PLAN_20261008.md),
  [TODO](TODO.md), [ROADMAP](ROADMAP.md#v9--options-experts-oee-and-ove)). User goal:
  options-native, short-term, high-risk/high-reward, fractional Kelly with 10–20%
  downside caps. Two experts: **OEE** (Options Earnings Expert, first) and **OVE**
  (Options Volume Expert).
- **V8 is complete** ([EXPERIMENTS](docs/EXPERIMENTS.md), October 8 entries). Only H1
  earnings drift (first-reported EPS SUE top tercile, long, 20-day hold) survived: it
  passed the 2026 holdout in stock form (+22.2%, Sharpe 1.31 vs QQQ 1.12). Its call form
  was inconclusive at a pessimistic 6% spread; short stock, long-short and puts failed.
  Stage 1 (price patterns) and stage 2 (vol timing) failed.
- **User decisions to respect:** delisted names stay in histories; no paid data unless
  evidence justifies it; pre-register before looking; worker pools + vectorized code by
  default; Kelly only from out-of-sample stats; V6 stays retired (needed the cancelled
  paid feed).

## Running now

- **V8 H1 paper test** in the "stonks bot 2" paper account (PA3U9D8Q8GQX, $100k, options
  level 3; keys `ALPACA_V8_PAPER_*`): stock + ~45 DTE / 0.60-delta call per signal;
  timers `healys-v8-h1-{signals,trade,reconcile}` at 09:45 / 10:31 / 16:20 ET from
  2026-10-09. First signals expected with mid/late-October earnings. Check:
  `./venv/bin/python scripts/run_v8_h1_paper.py status`, `journalctl --user -u healys-v8-h1-trade`.
- V6 paper account PA3WD22T4IM7 is untouched (TMUS calls open), timers disabled; history
  archived in `nn_meta/validation/v6-paper-archive-20261008/`.

## Next action

**OEE-0:** build the earnings event table (every 8-K Item 2.02, 2022-03 → 2026-09):
entry at the last close before the release, exit at the reaction-day close;
front-expiry ATM straddle and ~0.5-delta call/put prices before and after; implied
move; ATM IV for the 5 prior days (the user's IV run-up idea); skew; realized move;
coverage report. **Coverage only** — then draft OEE-1 for the user's sign-off. Early
and cheap: OVE-0 open-interest recorder (forward-only data).

Inputs (paths in [CURRENT_STATE](docs/CURRENT_STATE.md)): option chains
`nn_meta/validation/v8-stage2-20261008-r0/chains/`, events backfill
`nn_meta/validation/v8-events-20261008-r0/` (8-K acceptance times, XBRL facts),
bars/admission (V8 contract), option spread table, `nn_meta/v8_vol.py`,
`nn_meta/v8_h1_calls.py`, `nn_meta/v8_engine.py`.

Constraints: memory caps on big jobs; stage only your own hunks (other dirty V6/V7
work in the tree is not yours); the 2026 holdout was used once (H1 stock).

[Previous handoff](handoff-history/HANDOFF-2026-10-08-before-v9.md).
