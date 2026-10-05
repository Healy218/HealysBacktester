# Handoff — October 4, 2026 — Causal components and phase-B pilot

## Focus and completed result

Fresh Alpaca-only ETFE, SPY/QQQ/VOO × 1/5/15m, all twenty families.
Purchases/rolls remain **0–5 calendar DTE**, including qualifying 0DTE.
[Review](docs/reviews/2026-10-04-etfe-causal-pilot.md),
[machine receipt](docs/reviews/2026-10-04-etfe-causal-pilot.json).

- Completed ETFE-2.causal-components / ETFE-1.demand-pilot: new session grid,
  fifteen raw technical diagnostics/masks and all-family catalog adapters.
- Full captured stock calendar yields 1,019,958 bins. Twelve VOO source minute
  gaps remain null at each timeframe; no missing clock compression or fill.
- January 18–19 signal census uses January 2 engineering padding: every one
  of 25,353 ticker/variant combinations, including zero-event variants.
- All four signal channels matched shorter-prefix recomputation for every
  variant, also changing consumer batch width. Actual scope stop/resume preserved
  four completed files and computed eight remaining scopes. 109 tests passed.
- Retained 458,133 logical signal/target links. 195,435 acquisition candidates;
  262,698 lack prior-date observed candidates. No selected/eligible entries.
- Independent audit checked 13,746 distinct candidate rankings and every
  logical-to-physical link: 68 contracts, 179 bar and 225 trade intervals.
- All bar intervals already captured. Trade intervals remain uncaptured:
  4,626 contract-minutes. This study made zero network requests.
- Compute: 110.37 seconds, 1.20 GiB peak RSS, 121.16 MiB local footprint.
  Fifteen raw diagnostics are not the final adjusted 221-field model schema.

## Stopping point and next work

No ETFE job remains running. Full ETFE-1/2 and integrated ETFE-4.pilot remain open.

1. Use GLOBAL_DEMAND to prepare bounded capture of the 225 missing trade
   intervals, normalize and reconcile them before option trade/bar features.
   Preserve logical membership and account for windows outside stock RTH;
   dated option hours remain unresolved rather than assumed from stock hours.
2. Complete remaining option/context/TV features and full-window phase-B demand;
   phase-C holding/roll/physical-stock paths remain. Do not count the component
   study as the integrated execution/dataset/training resource pilot.
3. Resolve dated actions, terms/multipliers/expiry close, historical discovery
   and publication provenance before model-input/selection admission. Usable
   history start remains null; prior January boundary evidence is unchanged.
4. Follow ROADMAP's integrated pilot → acquisition/freeze → complete features /
   execution/build/recovery → dataset freeze/training/evaluation sequence.

## Selected artifacts and constraints

Study: `nn_meta/validation/etfe-causal-20261004-r0/` with PLAN/COMPLETE,
per-scope receipts, GLOBAL_DEMAND, INDEPENDENT_AUDIT, RESUME_AUDIT and PAYLOAD_INDEX.
Plan SHA256: `79b7f75d7d66a00adfe81cc31720659a944da2d3e744490f459fba3dd5fb86c2`.
GLOBAL_DEMAND SHA256: `44fd73587ed8e2d503a5d7b7354d8cc8770034a96785aa8d2ab23104eccfc689`.
The evidence ZIP contains source/metadata and hashes for eighteen local Parquets.
Current v4 setup and selected fresh normalized input roots are unchanged.
[Exact inputs](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#causal-component-pilot),
[study contract](docs/specs/ETFE_CAUSAL_PILOT_20261004.md).

Source-bound snapshots are immutable; changed code requires a successor study.
Only pure mathematical kernels are reused; no old data/metadata/configuration/
feature/model artifact enters ETFE. No training, deployment or economic verdict.
Preserve unrelated dirty work, including the pre-existing DECISIONS additions.
[Previous handoff](handoff-history/HANDOFF-2026-10-04-before-causal-pilot.md).
