# Handoff — October 5, 2026 — Shared scheduler and stress matrix

## Focus and completed result

User asked to keep going. Completed **ETFE-3.integration-components** in bounded
synthetic scope. Real input admission, scientific labels, full execution and
freeze/train remain open. [Review](docs/reviews/2026-10-05-etfe-integration-components.md),
[machine receipt](docs/reviews/2026-10-05-etfe-integration-components.json).

- One shared ledger now handles ordinary entries, expiry/roll/delivery and
  settlement. Scheduler generates entry retries, regular/availability/expiry
  clocks, stock latency and settlement; no caller-supplied observation gaps.
- Cash/slot reservations constrain new entries. Consecutive roll windows
  preserve the old deadline before the next regular observation starts one.
- Terminal diagnostic horizons include final cash settlement; short fixture
  ends stay open, while a completed fixed-end tape can right-censor liabilities.
- Six tapes × 27 profiles = 162 complete combinations / 189 proposal outcomes:
  95 settled, 24 observed-unfilled, 20 open, 3 input-unresolved, 23 funding-
  unresolved and 24 right-censored. Synthetic arithmetic only; targets all null.
- Three stress paths need a later roll quote or an official exercise reference
  absent from their tape. Retained explicitly as acquisition-demand evidence.
- All 289 focused ETFE tests pass, including 24 integration checks. Independent
  Decimal cash/share/contract/cost/census audit and every final state replay pass.
- Actual new-process restart preserved event-20 checkpoint and completed all
  combinations. Missing receipt recovery and corrupted inputs are also tested.

## Evidence boundary and stopping point

Synthetic miniature sessions only, not full-history/real execution validation.
Model admission remains false. Isolated scientific proposal labels, temporal
fold purging, real inputs and resource-scale integration remain open. Cash-only
single-underlying policy does not establish a funded-put inventory path.
No market capture, training, orders, deployment or ongoing process this session.
Previous bound option/expiry/feature/action sources and evidence are unchanged.

## Next selected work

1. **ETFE-1.demand:** finish full phase-B/C acquisition census and measured
   request/storage budgets. Include holding, roll, physical-stock and stress-
   contingent quote/exercise paths; this is next before broader capture.
2. **ETFE.provider-action-timing / provider-contract / history-boundary:**
   resolve required dated action revisions, terms/sector/session/source facts
   and usable coverage. Do not repeat empty action controls without a budgeted
   new question. All 221-field real diagnostics remain unadmitted.
3. **ETFE-4.pilot:** integrate fresh capture/features/execution/isolated labels/
   dataset/training smoke and recovery, with measured resources. Full build and
   independently verified dataset/experiment freeze precede training.

## Artifacts and constraints

Selected: `nn_meta/validation/etfe-integration-components-20261005-r0/`.
PLAN binds thirteen files; 162 hashed results, event-20 checkpoint, COMPLETE,
RESUME-1 and INDEPENDENT_AUDIT. Full small ZIP linked in the review.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#bounded-shared-scheduler-and-stress-matrix),
[contract](docs/specs/ETFE_INTEGRATION_COMPONENTS_20261005.md).

Fresh Alpaca only; actual 0–5 DTE purchases/rolls. Bound sources stay immutable;
use successors. Preserve unrelated dirty work, including DECISIONS/EXPERIMENTS.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-integration-components.md).
