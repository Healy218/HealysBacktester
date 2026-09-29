# V6 continual update — duplicate identities and transient tick failures

September 28, 2026. User selected resolving V6 errors before further V7-3 work.
This repair affects the research update only; the frozen base, accepted model and
Alpaca paper runtime remain unchanged.

## Causes and correction

The r2 run recorded 17 failures: eleven Massive tick HTTP 502 responses and six
`invalid candidate features` errors (AFRM, AI, AMDL, ANF, ARM, BBAI). Offline
reproduction showed that all six were duplicate identities for multiple frozen
vectorBT trade records sharing a strategy and entry timestamp. All numerical
features were finite or valid missing values. Dropping rows or filling values
would not fix the identity and label association problem.

The new `incubator/recovery_v6` consumer assigns a stable occurrence ordinal
within each strategy/entry group and retains each original trade's exit horizon.
Ordinal zero keeps the existing candidate hash; later occurrences get distinct
hashes. Duplicate groups are built per proposal so downstream as-of merges cannot
silently swap their identities. Label lookup and training assembly consume that
same identity. No trade records, feature values or candidate outcomes are dropped.

Tick requests now retry only transient transport errors and HTTP 429/500/502/503/504,
up to five attempts with bounded backoff and the overall build deadline. Authentication,
permanent missing-data and invalid-capture failures remain errors. Pagination,
raw tick multiplicity, scope and completeness validation are unchanged. Successful
new captures retain retry history in their manifests; existing captures remain intact.

## Explicit checkpoint inheritance

New root: `incubator/continual-v6/r3/`; selected config:
`deploy/incubator-continual-v6-r3.json`. Original r2 source/artifacts are preserved.
`inherited-r2.json` binds 4,623 feature seals, 23,569 label seals and 38 completed
symbol inventories. Each reused artifact retains its original declaration/hash;
new inventories explicitly identify inherited parents instead of relabeling them.
The frozen September 28 snapshot and original base dataset are unchanged.
Partial completed entry/label checkpoints are reused as well as whole symbols.

The deployed `healys-v6-continual.service` now selects
`scripts/v6_continual_resume_v3.py` and `scripts/run_v6_continual_v3.py`.
Original installed unit and exit receipt are retained at
`incubator/continual-v6/r3/runtime-revision/`. Existing overnight timer, market-hours
condition, unfinished-date/snapshot pinning, two autosized workers, CPU 200%,
11/12-GiB memory limits, no swap and pre-market cutoff remain. Failed symbols are
prioritized ahead of untouched symbols. This continues the full 449-symbol update;
it does not deploy a candidate model.

## Validation

- Eighteen focused tests passed across continual pipeline/recovery tests, including
  real LightGBM train/resume, colliding closed/open horizons, independent training
  outcomes, parent reuse with exact scope checks, transient retry
  pagination, permanent-error rejection and deadline handling. Existing library
  deprecation/feature-name warnings remain.
- All six actual formerly failing feature batches now pass: **80 rows**, unique
  identities and exact equality of every preexisting feature value. Evidence:
  `nn_meta/validation/v6-candidate-repair-parity-20260928/`.
- Exact original tick-failure prefixes are verified by
  `scripts/verify_v6_failure_frontiers.py` under
  `nn_meta/validation/v6-tick-error-recovery-20260928/`. Its cache writes are
  isolated from the concurrently running full update. See the final observation
  below for the completed census.
- Installed unit validation and unchanged r3 runtime-source bindings passed.

## Remaining boundary

Resolving the recorded failure cases is separate from finishing the full 449-symbol
catch-up, retraining all 40 members, evaluating/freezing a candidate and proving
next-day latency. Pending labels stay pending. A failed/rejected/deadline-limited
update cannot replace the accepted model. Further failures, if any, must be diagnosed
from the selected r3 receipts rather than rerunning the original r2 implementation.

## Final observation

All **17 original failure cases** passed targeted checks: six duplicate-feature
prefixes (80 rows, exact feature parity) and eleven complete tick-failure prefixes.
At 23:44 Central, r3 had 45/449 symbols complete and no recorded errors; 7
of the formerly failed symbols had completed their full catch-up. Training had
not started. [Observation](2026-09-28-v6-continual-error-repair-observation.json).
The full update continues under its existing deadline and immutable freeze gates.
