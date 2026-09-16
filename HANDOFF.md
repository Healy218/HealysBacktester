# V7 preparation checkpoint — not ready for freeze/build/training

Updated September 15, 2026 after the requested roadmap/TODO/feature audit.
Read TODO.md first, then this file. The user plans to clear the session before
continuing. **Finish the pre-freeze gates below before launching a campaign.**
All agreed feature groups are represented; several essential integrations are
unfinished. Passing tests and completed base downloads do not close them.

Current detailed checklist: [feature and freeze audit](docs/reviews/2026-09-15-v7-feature-and-freeze-audit.md).
Previous handoff archived at
[before March 15 migration](handoff-history/HANDOFF-2026-09-15-before-march15-start.md).
Earlier numerical pilots and source investigations remain historical evidence.

## Fixed decisions

- Research **2022-03-15–2026-09-14** inclusive. User chose the birthday start;
  March 8–14 are removed from active working inputs. Keep the real exchange
  calendar. Earlier captures can support separately verified PIT history;
  price-feature state restarts March 15 with explicit missing warmup.
- **Alpaca Algo Trader Plus underlying stocks, Massive options.** The March 8
  repair/stock-upgrade investigation is retired; no subscription purchased or
  support message sent. Do not reopen it as a prerequisite.
- All 20 strategy families, 2,817 variants/timeframe, **11,268/ticker**, on
  1/5/15/30-minute signals. All 13 TradingView scopes and 10 tick features:
  **222 model columns**. No global winner-only selection or 2,000-event cap.
- Every-minute observed option execution/marks, actual 1–9 calendar DTE for
  purchases; planning targets 1/2/4/5/7. Five shared slots, 10% equity, one symbol
  across timeframes, explicit costs/latency/cash reservations.
- Latest expiry policy: **funded physical exercise and stock delivery with
  observed stock liquidation**. This supersedes unresolved-only but is still
  declared, not implemented. Missing funding/evidence remains unresolved.
  Spec: [physical expiry](docs/specs/V7_PHYSICAL_EXPIRY_20260915.md).
- Four bounded workers, **250 GB decimal shared acquisition cap**. Protect V6.
  No subagents authorized, no unsolicited/test notifications, no full launch.
- External Pine comparison remains explicitly deferred. Other experts, learned
  exits/contract selection, new regime features and live-feed promotion are
  separate work, not additions to this run without a new decision.

## Completed and verified this checkpoint

The [March 15 migration review](docs/reviews/2026-09-15-v7-march15-start.md)
records commands, scope and evidence. The new `scripts/rescope_v7_inputs.py`
creates derived receipt-bound inputs while preserving original provider captures.

- Working root: `nn_meta/data_v7/start-20220315`.
- 7,430 stock shards; **711,178,638 retained raw/adjusted rows**;
  **2,226,484 raw/adjusted rows excluded**. Other years hardlinked.
- Independent verification of all **1,238 year-2022 shards**, 117,150,912 rows:
  zero March 8–14 timestamps in New York time; zero excluded option days.
  Receipt: `nn_meta/validation/v7-start-20220315-verification.json`.
- 1,425 option daily captures retained. Original base acquisition had completed
  all 8,284 tasks, including both September 14 files.
- New chain: `nn_meta/validation/v7-chain-start-20220315`, **22,130,242 contracts**,
  8,703 roots, 1,425 days; 99.38 seconds.
- New-date coverage diagnostic:
  `nn_meta/validation/v7-membership-session-coverage-start-20220315`.
  340,208 eligible sessions, 189 original zeros, 67 resolved aliases,
  **122 remaining zeros**. Uses old PIT membership diagnostically; it does
  **not** admit a new universe or resolve remaining lifecycle cases.
- Entry-point date/input guards now select the new scope; pilot dates are
  March 15–18. Old SPY tick store is historical, not active quote coverage.
- Causal-price prototype and its four tests preserved in
  `nn_meta/v7/causal_prices.py`; integration and action-evidence gates stay open.
- Full suite: **1,722 tests +18 subtests passed**, 82.54s, 18 warnings,
  `/tmp/v7-march15-final-tests.log`. This was a working-tree suite, including
  unrelated pending V6 work; do not call it a clean-checkout reproduction.
- Session migration/catalog/coverage/verification jobs finished. Quota last
  read: **62,530,084,555 bytes**, no active reservations. Do not reset quota
  while any future acquisition is active.

## Active manifests and ticker inventories

The tracked [active-input manifest](docs/specs/V7_ACTIVE_INPUTS_20220315.json)
binds the working-input report, independent verification, chain and policy.
It explicitly has `research_ready=false`, `quote_inputs=null`.

- Plan: `nn_meta/research_plans/v7-20220315-20260914/plan.json`.
  Plan SHA: `0328ecd49e75f97c8af93f51ebe6709131bd833e9e2a32920c9588c8697c439f`.
  Large file: parse selected fields, never print the whole catalogue.
- Current evaluation: `docs/specs/V7_EVALUATION_20220315_PHYSICAL.json`.
  Nested `evaluation` is what the loader consumes. Train starts March 15;
  expanding validation 2024H2/2025H1/2025H2, final 2026Jan1–Sep14,
  ten-session embargo and completed-label purging. Physical delivery extends
  label horizons. Previously inspected periods remain revalidation.
  Older declarations are immutable history, not active policy.
- Current 449 ticker list: `docs/specs/v7-tickers-20260915.txt`.
- Historical 598-name inventory:
  `nn_meta/validation/v7-identity-universe-20260915r3/symbols.txt`.
  596 identities/16,577 memberships; new-scope membership rebuild pending.
  Old 622 static-alias draft is invalid. Exact dated alias mappings, including
  GAP, are in the prior handoff; never infer identity from ticker/name alone.

## Ordered next work — before freeze

1. Rebuild PIT membership with explicit deleted-session/lookback treatment.
   The current builder requires every calendar session and will reject the
   removed dates. Do not shorten the calendar or reuse affected old rankings.
   Finish lifecycle/halts/session aliases and frozen dated sectors.
2. Integrate causal corporate-action prices: dated publication/effective
   evidence, splits/dividends/spin-offs, combined actions, contemporaneous tick
   units, stops across actions. Vendor all-adjusted data is not vintage proof.
3. Build daily/context features for every eligible security (real builder is
   still SPY-only), with full market/sector histories and visible warmup
   missingness. Record first eligible observations without silently changing
   the requested research start or inventing pre-gap rolling state.
4. Resolve row semantics: current `FeatureRows.row` uses `target_dte / 45` and
   constant-zero `moneyness`. These are legacy baseline conventions, not actual
   selected-contract fields. Freeze intended semantics explicitly before training.
5. Implement exercise/stock ledger: shared cash/share reservations, settlement,
   dated exercise evidence, fractional-paper treatment, Alpaca stock quotes,
   liquidation costs/marks, extended label horizons and real replay tests.
   Current replay still returns `expiry_liquidation_unresolved`.
6. Validate historical class hours/early closes and weekly eligibility. Build
   actual proposal/feature/roll/exercise interval unions, measure retained
   densities and finish quote/trade capture under the cap. Old 76M quote-hour
   broad demand and March 7 SPY capture cannot establish current feasibility.
7. Connect bounded full-history rows/labels/marks to training. Factorized rows
   and fold-indexed LightGBM Sequence were demonstrated on only 72 real rows;
   measure full binned-dataset RAM/disk/recovery and coexistence with V6.
8. Predeclare runnable V7 model/objective/seed/weight/calibration/threshold
   trials. Retain baseline fairness, finite NN/GBT validation, deterministic
   seeds, cost/ex-outlier diagnostics and PBO/deflated-Sharpe trial accounting.
   Explicitly classify existing V6 event-balanced/downside-quantile trials;
   do not assume V6's 164-column adapters work with the V7 schema.
9. Pass new-window integrated/resource pilots with sparse markets, actions,
   early closes, aliases, rolls and funded expiry, then implement/pass one
   executable complete-universe launch gate. `test_v7_readiness.py` is only
   component coverage. Source/runtime/data/policy hashes and mutation guards
   must bind the final run. RunBinding hashes Python, spec JSON and Pine;
   do not edit these while a bound pilot is running.

## Operations and repository continuity

Work on main using `./venv/bin/python`; never expose `.env`. There is extensive
unrelated dirty V6 work in this checkout. Preserve it and stage scoped paths or
hunks only. This checkpoint does not deploy anything; server deployment uses
Git, never scp. See git log for scoped V7 commits after prior `3f12edb`.

Prior saved V6 status inspection at 21:15Z showed data through September 14,
idle/outside-market-hours, next session September 16; no new runtime inspection
or intraday audit was performed by this documentation checkpoint. Runtime
`d6660af` remains the prior recorded deployment. Dashboard hosting and ongoing
V6 evidence collection remain open. First-week maturity reassessment is due
on/after September 21; no GOALS score uplift from component tests alone.
