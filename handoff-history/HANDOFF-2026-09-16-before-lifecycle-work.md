# V7 preparation — tested progress; full training remains gated

Updated September 15, 2026. Read TODO.md first. User asked to get V7 ready to
train; this session rebuilt membership, fixed row semantics and implemented
physical-ledger/shared-replay mechanics. **No full campaign or training launched.**
Full-universe data/execution/training integration remains unfinished.

Review: [training preparation](docs/reviews/2026-09-15-v7-training-preparation.md).
Previous handoff: [before this work](handoff-history/HANDOFF-2026-09-15-before-training-preparation.md).
The earlier [full feature audit](docs/reviews/2026-09-15-v7-feature-and-freeze-audit.md)
remains the scope reference; its row-placeholder and missing-ledger statements
are superseded by the component implementation described here, not by admission.

## Fixed scope

- March 15, 2022–September 14, 2026 inclusive. March 8–14 absent from active
  price/options inputs; full exchange calendar retained. Earlier captures can
  support PIT membership; price-feature state restarts March 15 with missing warmup.
- Alpaca underlying stocks, Massive options. Full 20 families, 2,817 variants
  per 1/5/15/30-minute timeframe, 11,268/ticker, 222 columns; all 13 TV scopes
  and 10 tick features. External Pine comparison remains deferred.
- Actual 1–9 calendar DTE purchases, targets 1/2/4/5/7, minute execution/marks,
  five shared slots, 10% equity premium allocation, one symbol across timeframes.
- Funded physical exercise/stock delivery and observed stock liquidation.
  Insufficient funding/shares/evidence stays unresolved; never inject capital,
  create stock shorts or turn absent bids into intrinsic-value sales.
- Four bounded workers, shared 250 GB decimal acquisition cap, protect V6.
  No subagents, no unsolicited/test notifications, no full launch before gates.

## Landed and verified

1. `universe.membership` supports explicit excluded sessions. Deleted dates
   consume the 63-session lookback, but contribute neither zeros nor activity;
   no older-session backfill. The 50-active-session minimum remains. Builder
   requires current filtered inputs/full calendar and persists provenance.
2. New immutable universe `nn_meta/validation/v7-identity-universe-start-20220315`:
   **597 tickers, 595 securities, 16,580 research membership rows**; reviewed
   transitions pass. Old 598-name list is historical, not active admission.
3. New `nn_meta/validation/v7-membership-session-coverage-rebuilt-20220315`:
   **340,272 eligible sessions, 189 original zeros, 67 aliases resolved, 122
   unresolved**. No lifecycle/complete-feed admission. Manifest points here.
4. `v7-selected-contract-rows-v2`: actual DTE / 9; log(strike/raw spot), with
   completed raw spot available by decision and <=60s old. Target DTE remains
   metadata. Initial unavailable daily context yields explicit NaNs/status,
   preserving March 15. Factorized format advances to v2 and rejects v1.
5. New `nn_meta/v7/physical.py`: shared funded cash/share commitments, official
   reference/standard-contract checks, explicit nonexercise, delivery/settlement,
   sized observed stock fills, stock marks and full cash reconciliation. Optional
   funded stock inventory enables put delivery without creating free shares.
   Pro-rata fractional paper convention; zero exercise fee and .001/.0005 stock
   fee/slippage are declared research inputs. Settlement availability is
   conservative: next trading open after the captured settlement date.
6. `portfolio_replay(..., physical=context)` integrates the ledger, preserves
   slots through stock sale/cash settlement and records extended completion times.
   Ten physical tests are **synthetic**, not real captured exercise admission.
   Standalone replay is still unresolved at unsold expiry; no artificial funding.
7. `scripts/v7_readiness.py` aggregates immutable full-universe stage evidence.
   Current command exits **1**, correctly refusing training. Active inputs,
   rebuilt membership and coverage inventory pass; eight substantive stages
   still lack evidence. The aggregator is not the missing full campaign builder.

Full suite: **1,746 tests +18 subtests passed**, 18 warnings, 81.97s;
`/tmp/v7-preparation-20260915-final-tests.log`. Includes preserved unrelated V6
working-tree changes, so not a clean-checkout reproduction. No active jobs from
this session remain after final verification.

## Current inputs and reports

- Active selection: `docs/specs/V7_ACTIVE_INPUTS_20220315.json`, still
  `research_ready=false`, `quote_inputs=null`, `readiness_evidence={}`.
- Working root: `nn_meta/data_v7/start-20220315` (7,430 stock shards; 1,425
  option daily captures). Original provider captures remain historical.
- Chain: `nn_meta/validation/v7-chain-start-20220315` (22,130,242 contracts).
- Plan: `nn_meta/research_plans/v7-20220315-20260914/plan.json`; parse selected
  fields, never print the large catalog. Existing plan dates remain unchanged.
- Evaluation: `docs/specs/V7_EVALUATION_20220315_PHYSICAL.json`; original frozen
  declaration remains immutable. New engine defaults need final evidence binding.
- Readiness: `nn_meta/validation/v7-readiness-20260915-preparation-final.json`.
  Reproduce with `./venv/bin/python scripts/v7_readiness.py --output NEW_REPORT.json`.
- Earlier scope verification and chain hashes remain bound by the active manifest.
  No acquisition ran, and the quota was not reset. Last previous recorded quota
  was 62,530,084,555 bytes; reread before any new acquisition.

## Next required work, in dependency order

1. Resolve the 122 zero-session cases in the new coverage CSV: ATVI, BBBY, BIIB,
   CLSK, COUP, DISCA, FRC, NVAX, REV, SGEN, SI, TWTR, VERU, VMW, X. Distinguish
   known nontrading/lifecycle intervals from capture gaps using dated evidence.
   Resolve held options/deliverables, consume exact session aliases, freeze sectors.
2. Integrate causal prices with publication/effective evidence for splits,
   dividends, combined actions and spin-offs; preserve contemporaneous tick units
   and cross-action stops. Vendor all-adjusted history is not vintage proof.
3. Replace SPY-only daily pilot with every eligible identity's causal daily/market
   context and first-eligible/missingness report. No pre-March15 price warmup.
4. Supply real physical context/receipt loaders: official expiry references,
   dated deliverables, settlement business calendar, Alpaca stock quote captures
   and quote adapter. Engine accepts provider interfaces; no captured adapter was
   implemented this session. Audit stock actions during delivery, costs, session
   rules and real funded expiry paths. Current 10% option budgets may be unable
   to fund exercise; preserve unresolved fallback and do not silently resize.
5. Validate historical option hours/weeklies. Build actual proposal/feature/roll/
   exercise interval unions on the new universe; measure feasibility and capture
   required quote/trade observations under the cap. No old SPY capture reuse.
6. Connect full-history factorized rows/labels/marks to runnable V7 training,
   declare model/objective/seeds/weight/calibration/threshold trials, and measure
   binned-dataset memory, recovery and concurrent V6 load. Retain baseline fairness,
   finite NN/GBT checks, PBO/deflated-Sharpe and purging through cash settlement.
7. Produce complete-universe stage evidence and real integrated/resource pilots
   for `readiness.REQUIRED`; pass every stage before freeze/build/training.
   Source/runtime/input mutation guards still apply to bound pilots.

## Repository and operations

Work on main with `./venv/bin/python`. Keep the extensive pre-existing dirty V6
work. Only scoped paths/hunks were selected for this milestone; no V6 deployment,
runtime, timers or alert settings changed and no messages were sent.

No fresh operational V6 inspection was performed. Prior checkpoint had data
through September 14, runtime d6660af and the next session September 16.
Dashboard/evidence collection remain separate. First-week maturity reassessment
is due on/after September 21; no score uplift from component tests.
