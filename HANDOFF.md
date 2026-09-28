# Handoff — September 27, 2026 — V7 download prioritized; incubator deferred

## Focus and stopping point

The user clarified the incubator's goal: continually build research data, train
updated models and freeze new artifacts regardless of actual trades. Implemented
for **V6 only** tonight. V5 paper-outcome scoring is superseded. V7 remains at
**Phase 7, gate 7-3**; its existing capture continues without changes.

V6 catch-up started at 19:59 Central and was subsequently stopped at user request
to prioritize the V7 entry download. The 20:18 hold receipt verified 273 completed
feature batches and 1,628 outcome records intact. The V6 timer is completion-gated;
morning retries run every 15 minutes, 04:00–07:45 Central, and resume only after
V7 reports successful entry completion. The goal is a V6 update before the next
trading day if time permits; no full updated ensemble or readiness claim exists.
[Implementation/evidence](docs/reviews/2026-09-27-v6-continual-incubator.md).

## Completed and preserved

- Incremental immutable candidate features and matured simulated labels, pending
  and unfilled coverage, hash-bound resume and unchanged historical base/release.
- Fixed 40-member LightGBM retraining, chronological purging/embargo, incumbent
  and constant-baseline diagnostics, versioned candidate and accepted pointers.
  Research acceptance does not promote or deploy a model.
- New `healys-v6-continual.timer` enabled with the V7 completion condition; old
  replay-only incubator timer disabled. Seven completion-gate tests passed.
  Bounded memory/CPU and morning deadline; completed checkpoints survive retries.
- 39 targeted tests and unit validation passed. Corrected SPY pilot: 160 candidates,
  98 matured / 54 pending / 8 unfilled. Full-size single-member benchmark: 191.32s,
  7.1 GiB cgroup peak. Full pipeline latency and 40-member freeze are still open.
- Rewrote the incubator contract and aligned owning notes. Historical replay
  specification/evidence retained. Preserve unrelated dirty/untracked work.

## Next actions

1. Read TODO then this handoff. Inspect `incubator/continual-v6/r1/latest-run.json`,
   per-symbol progress and service journal; use [CURRENT_STATE](docs/CURRENT_STATE.md)
   for exact configuration, selected inputs, schedules and recovery pointers.
2. Keep V6 deferred until successful V7 entry completion; do not bypass the gate.
   Then complete OPS-INCUBATOR.DATA/OPS/PROOF: full-universe catch-up, full model
   freeze and one steady daily update. Preserve checkpoints; do not claim the
   initial backlog fits tonight or that the nightly SLA is measured.
3. Data labels follow frozen historical V6 aggregate execution, independent of
   broker trades. Partial exit paths remain pending. Latest 40 observed dates are
   validation-only until outside the rolling tail; no untouched-performance claim.
4. Existing V7 entry capture remains running. At 20:11 Central it was 31.06%
   complete, with the 10–30-minute samples forecasting 04:00–06:16 Monday Central.
   The slowest two-minute sample overlapped V6 but also had denser responses;
   causality is unproven. Read the live meter before quoting present progress.
5. Continue selected 7-3 tasks without redoing completed preparation; observe the
   first prospective Alpaca fills, and retain the October 2 provider decision.

## Constraints

Source/config changes require a new research lineage; never relabel old freezes.
The continual contract includes pre-existing local V6 source work. A clean checkout
of the new commit alone does not package all existing V6 runtime inputs. The
operational frozen checkout and paper account were not modified by this work.
Initial incumbent comparison overlaps its original training dates and is only a
research diagnostic. Neither successful retraining nor a pointer advances an
expert admission gate. Full validation/deployment/measurement remain distinct.
