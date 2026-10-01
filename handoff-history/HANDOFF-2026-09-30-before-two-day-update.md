# Handoff — September 30, 2026 — V6 initial candidate frozen; jobs restored

## Completed milestone

The September 28 V6 r3 catch-up finished all 449 symbols, trained all 40 ensemble
members, evaluated and froze a research candidate at **22:40:47 Central**.
All 122 candidate payload files were independently hash-verified at 22:40:57.
Main service exited successfully at 22:40:49. No new run errors.

Training ran 21:59:42–22:35:11 (35m29s). Evaluation/freeze took **5m36s**.
Data: 307,702 candidates, 111,958 matured labels, 92,723 pending and 103,021
unfilled; training arrays: 2,905,632 training / 205,816 validation rows.
OPS-INCUBATOR.DATA is complete for the pinned initial catch-up. A subsequent
full daily update/coexistence proof remains under OPS-INCUBATOR.OPS/PROOF.

## Evaluated verdict

**Diagnostic gate failed; updated V6 freeze retained.** Candidate return MSE
5.325676 exceeds incumbent 5.323277 and zero-return baseline 5.310690.
Classification Brier improved slightly (0.216986 vs 0.216994) but both acceptance
conditions must pass. Research-only; no deployment approved or performed.
This is purged temporal validation reused for daily selection, not an untouched
performance test or proof of trading profitability.

## Exact evidence

Candidate: `incubator/continual-v6/r3/runs/2026-09-28/candidate/`.
`evaluation.json`, `complete.json`, `ensemble_config.json`; seal SHA-256
`4da950595e68f1db0d68431e85a1bbca22f8345c5472fae2dcaabe722e5f16d2`.
Run: `incubator/continual-v6/r3/latest-run.json` (`candidate_frozen`, `done`).
Focus: `nn_meta/validation/v6-focus-20260930/progress.json` (`restored`),
`restored-services.json`, `service-exit.json` (success/0).
Focus JSON retains old merged error/returncode fields from earlier failures;
final candidate receipt, restored phase and fresh exit receipt resolve them.

## Automatic restoration

At 22:40:49 timers were restored and research starts requested. Restoration
readback showed MRHA migration plus required-discovery/frontier services active.
This establishes restoration at that time; inspect their live receipts for
continued health/progress. Original discovery/capture units stay stopped;
successor controllers own further work. V7-3 remains selected/open.

## User clarification and daily goal

Keep V6's historical base plus new daily data in versioned updated freezes.
A worse score is recorded; it does not erase the update or block future days.
Tonight's completed freeze is through September 28, not September 30.
The next cycle must select the latest fully closed session and add remaining
new examples/outcomes. Existing daily timer is 15:45 Central weekdays, with
midnight–07:45 quarter-hour retry opportunities; market-window guard remains.
No model-selection pointer or paper deployment was changed by this clarification.

## Next work and constraints

Follow [TODO](TODO.md) and [ROADMAP](ROADMAP.md); no further initial catch-up
retraining or recapture is needed. Inspect restored V7/migration receipts and
measure a subsequent daily V6 update before closing full-incubator proof.
October 2 provider decision remains separate. Keep MRHA mounted.

The terminal viewer remains `./venv/bin/python scripts/watch_v6_incubator.py
--follow`; a completed run and rejected verdict are consistent. Ctrl-C closes
only the viewer. The old side-retry helper is finished and bound to the previous
invocation; do not restart it as-is. Earlier resume/retry receipts are preserved.
[State](docs/CURRENT_STATE.md) · [Experiment](docs/EXPERIMENTS.md) ·
[Review](docs/reviews/2026-09-30-v6-dedicated-compute.md).
Preserve unrelated dirty/untracked work and existing paper/live isolation.
