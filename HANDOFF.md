# Handoff — September 28, 2026 — V6 error repair verified, full update running

## Focus and stopping point

User selected V6 error resolution before returning to the rest of 7-3.
All 17 recorded failure cases now pass targeted checks. Corrected r3 is running
its full 449-symbol catch-up; training/freezing remain incomplete. V7 jobs were
left running under their existing bounds; no new V7 work was launched this turn.

## Changes and evidence

- Eleven HTTP 502 failures came from the tick client lacking transient retries.
  The research adapter now retries transport/429/selected-5xx errors up to five
  attempts within the build deadline. Pagination/raw integrity checks are unchanged.
- Six `invalid candidate features` failures were identity collisions, not bad
  numerical values: multiple frozen trade records shared strategy/entry time.
  Stable occurrence ordinals preserve every row and independent exit horizon;
  label lookup and training assembly consume the same keys. No deduplication.
- Actual six-prefix parity: 80 rows, all previous feature values exactly equal,
  unique corrected identities. All eleven original tick-error prefixes completed
  in isolated verification caches. Eighteen focused tests passed, including
  pagination retry, separate collision outcomes and actual LightGBM train/resume.
- Explicit inheritance preserves 38 complete r2 symbols, 4,623 feature seals,
  23,569 label seals and the frozen snapshot/base. Old artifacts keep old hashes.
- [Repair review](docs/reviews/2026-09-28-v6-continual-error-repair.md),
  [dated observation](docs/reviews/2026-09-28-v6-continual-error-repair-observation.json).

## Running V6 and continuation

Selected config: `deploy/incubator-continual-v6-r3.json`; root:
`incubator/continual-v6/r3/`. Service `healys-v6-continual.service` now uses
`scripts/v6_continual_resume_v3.py`, then `run_v6_continual_v3.py` and
`incubator/recovery_v6/`. Started at 23:07:14 Central. Existing timer, two autosized
workers, CPU 200%, 11/12-GiB memory bounds, no swap and pre-market cutoff remain.
At 23:44 Central: 45/449 complete, zero recorded errors; training not started.
7 of the formerly failed symbols had completed full catch-up; all 17 original
failure points were separately verified. Do not confuse that with full-universe completion.

1. Read latest-run, progress, symbol seals and service-exit together. Finish the
   remaining catch-up, all 40 training members and candidate evaluation/freeze.
   Preserve accepted model on failure/rejection/deadline. No automatic deployment.
2. Resume remaining 7-3 work from its existing selected state below. Known exact
   reference exceptions are already approved; actual held/exit/roll/stock/reference
   gaps and final full-scope reconciliation remain. Do not restart entry capture.
3. Keep prospective V6 paper-fill observation and October 2 provider decision.

## V7 pointers and constraints

Queue: `nn_meta/validation/v7-full-execution-plan-20260928/`.
Discovery: `nn_meta/validation/v7-execution-campaign-20260928-r1/` (eight-hour limit).
Quote base: `v7-frontier-quote-index-20260928-r4`; approved finite policy:
`v7-contract-blackouts-20260928-approved` (10,831 pairs including the original five).
The discovery controller does not automatically finish capture/replay epochs.
Audited pilots stay stopped; source-bound implementations stay immutable.
[Exact pointers](docs/CURRENT_STATE.md), [V7 review](docs/reviews/2026-09-28-v7-full-execution-discovery.md).
Preserve unrelated dirty/untracked work and the original V6 paper runtime/model.
