# Handoff — 2026-09-27 — real V7-3 entry capture running

Read TODO first. The user is frustrated by repeated checks and shifting claims.
They directed doing the remaining work needed to start training, using already
completed work. Do not restart catalog/daily/demand/hours/packing/storage cleanup.
All earlier freezes and unrelated dirty/untracked work remain intact. Work on main.

## Current running work

`healys-v7-capture-20260927.service` is capturing real full-universe entry quote/
trade demand with four autosized workers. First 128 capture ranges completed,
then the service reused them and continued. Check the live progress file:
`nn_meta/validation/v7-entry-campaign-20260927/progress.json`.
It is an entry-data job, NOT model training and not yet full V7-3 completion.

Review: `docs/reviews/2026-09-27-v7-entry-campaign-started.md`.
Launcher: `bash scripts/start_v7_capture_campaign.sh`.
Controller: `scripts/run_v7_capture_campaign.py` (now source-bound; don't edit
while running or mutate existing declarations/receipts).
Output: `nn_meta/data_v7/entry-campaign-20260927`.
Frozen inputs: full `v7-3-entry-union-20260926` audit, 591 original demand stores,
and `v7-execution-sample-index-20260927-r12` for already captured coverage.

Each batch is the exact joined demand minus retained coverage. Completed v2
packs are immutable/reusable. The first sandbox attempt failed transport and
retained/charged 65,536 bytes; authorized network retry succeeded. Two focused
controller tests passed; original v2 pack roundtrip checks remain active. No
repeat full regression suite was run for this launcher-only addition.

Resource guards: 100 GB initial new acquisition allocation, conservative
490 GB project baseline, unchanged total 640 GB project / 250 GB acquisition
caps, 20 GiB free reserve, one-GiB quota reservation per worker. Service limits:
MemoryHigh 10 GiB, MemoryMax 14 GiB, MemorySwapMax 0, CPUQuota 400%, Nice 10.
100 GB is an initial cap, not a completed estimate for all training requirements.
Monitor measured growth and finish the complete budget before the guard pauses.
On provider/capacity failure the controller drains current tasks and pauses;
it does not infer completion. No automatic model-training launch is wired yet.

## Completed work to reuse

V7-1 and V7-2 complete: 591 securities / 1,773 frozen 5/15/30 proposal stores,
221 columns, full causal daily context. Full entry-demand union already done.
Cleanup and lossless packed capture/reader already done. Dated hours resolve
301,213 entry root/dates; five exact reference blackouts already implemented.
Full first-leg envelopes and r0–r12 execution pilot remain preserved. DIS/ABBV
pilot labels completed; NVDA/VKTX/FUTU have exact pending held-mark reads.
The ~1 TB number was an overbroad all-possible-first-leg sensitivity, not an
actual storage requirement. Do not present it as required capacity.

Detailed prior evidence and exact blackout/storage/pilot context are preserved
in `handoff-history/HANDOFF-2026-09-27-before-entry-campaign-start.md` and
`docs/reviews/2026-09-27-v7-dated-hours-and-execution-paths.md`.
The prior full suite passed 2,457 tests plus 18 subtests.

## Continue toward actual training

While the real download runs, connect the existing packed/hours/blackout inputs
to existing assembly/folds/trials; finish required held/exit/roll/reference and
physical/shared-capital integrations by reusing existing implementations. The
old readiness script has stale 222-column and pre-amendment requirements: do
not revoke completed gates or rebuild to appease stale flags. Trace current
receipts and replacements. Existing assembly.py/dataset_inputs.py are untracked
prior work; preserve them. Use a complete launch view rather than repeatedly
announcing old components as missing. Be explicit: V7-3 = data preparation;
model training starts only when its actual data/execution inputs are ready.
