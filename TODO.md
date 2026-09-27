# TODO — unfinished work only

Updated September 27, 2026. **V7-3 downloads are running. V7 model training has
not started.** Completed work is in [ROADMAP](ROADMAP.md#completed-work).
Start with [HANDOFF](HANDOFF.md) and [current inputs/downloads](docs/V7_CURRENT_STATE.md).
Do not turn historical open items back into tasks after a later completion.

## Active: finish V7-3 option data

[Receipt-level verification](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md)
confirms completed preparation must be reused. Existing dated-reference stores
cover 720 of 2,223,844 planned pairs; r12 has three specific held-quote gaps.
Exit/roll/stock acquisition is conditional on actual replay requests, not a
fresh blanket download or component-reimplementation task.

- [ ] Finish the full-universe entry quote/trade download already running as
  `healys-v7-capture-v4-20260927.service`. Monitor
  `nn_meta/validation/v7-entry-campaign-v4-20260927/progress.json` and reuse every
  completed pack. No new catalog, daily build, demand census or packing trial.
- [ ] Acquire remaining dated contract references from the **already completed**
  `v7-dated-reference-demand-20260927` plan (2,223,844 entry contract/dates).
  Reuse the captured sample and apply the existing five exact blackouts.
  Held paths may add dates; new missing references need explicit treatment.
- [ ] Complete actual held-mark, exit, roll and applicable stock-delivery capture
  using the **existing** replay frontier/quote/physical machinery. Reuse the r12
  execution state and new entry packs. Preserve partial ledgers and count actual
  held blackout crossings. Potential first-leg envelopes are not download orders.
- [ ] Reconcile the complete request/capture/reference census and measured storage
  for execution, assembly, training and recovery. Use the user-authorized live
  disk allocation with a 10 GB reserve and automatic MRHA overflow; earlier
  fixed caps are superseded. Capacity is not a final dataset-size estimate.
- [ ] Publish full V7-3 completion only when actual required paths and provider
  failures are accounted for. A finished entry download alone does not close 7-3.

## In parallel: execution integration, then training launch

- [ ] **7-4 — complete integrated execution coverage:** the versioned runner is
  connected and has a reconciled real partial ledger; continue from
  `v7-integrated-execution-20260927-r2`, quote index `-r2` and source discovery
  `v7-execution-discovery-20260927-r13`. Extend actual paths/full-scope inputs and
  reconcile real expiry, settlement and stock liquidation. No real physical
  event occurred in the retained five-path run. Reuse the completed integration
  and its 58 focused checks; [review](docs/reviews/2026-09-27-v7-integrated-execution.md).
- [ ] **7-5 — assembly and folds:** connect existing packed/hour/blackout inputs
  to the existing assembly and fold/trial components. Produce/reconcile the
  full 221-column dataset, label horizons and purged predeclared fold selections.
  Existing component code is not a missing implementation to rewrite wholesale.
- [ ] **7-6 — launch resources/recovery:** measure the actual integrated build and
  training footprint, bounded memory, restart and coexistence with live V6.
  Reuse applicable completed resource/restart evidence; check only changed paths.
- [ ] **7-7 — current readiness and launch:** make the readiness entrypoint consume
  current completion receipts and the 221-column/5-15-30 amendments. Do not
  rebuild passed stages to satisfy stale checker fields. Launch the predeclared
  training campaign once its real data/execution/resource requirements pass.

## Separate time-sensitive work

- [ ] **By October 2:** give a source-backed Massive Options Advanced keep/cancel
  recommendation based on captured pre-February-2024 V7 ticks, representative
  SPX/NDX Alpaca OPRA history, and V6 adapter/decision parity. The user decides
  cancellation. If required evidence is incomplete, recommend retaining one more
  month. [Decision gate](docs/reviews/2026-09-24-v6-alpaca-paper-start.md).
- [ ] Finish prospective V6 Alpaca bridge/scanner lifecycle integration, including
  rolls, before enabling submissions. Fresh scanning/order submission remain
  disabled; do not import old simulator positions. Preserve account monitoring.
- [ ] Confirm scheduled V5/V6 nightly incubator health, finish exact V5 outcome
  joins and paper scoring. The replay implementation, actual nightly activation,
  V5 capture and V6 exporter already exist. Admit V7 only after its separate gate.

## Scope and working rules

March 15, 2022–September 14, 2026; 591 securities; 20 strategy families;
8,451 variant/timeframe combinations over 5/15/30-minute signals; 221 columns.
One-minute option execution; actual 1–9-DTE purchases, midpoint pricing/costs,
12.5% option-premium stop, strategy exits, 15-minute pre-close ITM expiry exit,
and the agreed funded physical fallback. Preserve PIT inputs, frozen artifacts,
all existing exclusions, portfolio limits and chronological folds.

Use completed [ROADMAP](ROADMAP.md) evidence. Do not rerun completed campaigns
or broad tests without a changed behavior/failure that needs verification.
Record real new decisions and remaining gaps, not repeated component pilots.
Work on main; protect the existing V6 runtime. Deferred FA/panel/Pine/SPX0/stacking
research stays outside this launch queue. Full contracts remain in
[the V7 specification](docs/specs/MULTITIMEFRAME_RESEARCH.md).
