# Handoff — 2026-09-26 — full entry demand/union complete; first actual ticks captured

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-26-before-full-union-completion.md`.
Main is operational. Preserve extensive unrelated dirty/untracked work.

## Current stage and user authorization

V7-1 and V7-2 are complete; V7-3 remains active. The user requested starting
option captures and training, a separate terminal progress bar and stopping
hourly finished-build alerts. Actual captures have started with a bounded first
consumer window. Full acquisition and training have NOT launched. Continue
through the capture-volume/storage, full execution, assembly and readiness gates.
No broad policy or scope reduction was authorized.

All 1,773 frozen stores and original receipts/gates remain preserved. The exact
user-approved kernel 7.2.6 → 7.2.7 compatibility proof remains valid for demand
consumption only. Original producer/reader/scheduler source was left intact.

## Demand and full entry-union completion

Recovery completed **591/591**, no failures, at 06:03:03 UTC September 26.
It reused all 546 preserved checkpoints and generated the remaining 45.
Output: `nn_meta/validation/v7-3-scheduler-20260925` (106.546 GB logical).
Final meter: `kernel-recovery/progress.json`. The root progress file still
records the historical failed strict-runtime restart, not the completion.
Service: `healys-v7-entry-demand-recovery-20260925.service`;
invocation `9a07064bbccd4f91aedd75e46580fd3a`. Do not restart completed demand.

The queued full union audit finished at 06:27:56 UTC. Its immutable output is
`nn_meta/validation/v7-3-entry-union-20260926`:
- All 591 securities and 793,394,264 proposals reconcile.
- 76,910,536 unique quote/trade entry-feature requests.
- 42,030,534 union captures: 21,015,267 each quotes/trades.
- 1,057,177 contracts and 2,223,844 contract-days.
- 14,404,985,220 requested union seconds per quote/trade kind.
- 2,605,230 no-contract and 770,705 no-fresh-spot outcomes retained.
- 2,027,648 distinct demand input bindings checked.
This is full entry-feature demand only, not entry fills/marks/exits/rolls/delivery.
Union service `healys-v7-entry-union-20260926.service`, invocation
`ceded52087f74d238c957df81eb1305b`, completed its work; do not duplicate it.

## First actual capture

The first chronological actual SPY quote request plus its matching trade request
was chosen before inspecting provider ticks: `SPY220316P00420000`, March 15, 2022,
SIP interval [1647351270000000000, 1647351600000000000).
Plan: `nn_meta/validation/v7-first-actual-capture-plan-20260926`.
Raw capture: `nn_meta/data_v7/entry-first-actual-20260926`.
Verification: `nn_meta/validation/v7-first-actual-capture-verified-20260926`.
Both windows passed immutable receipt, count, scope, pagination and record-hash
checks: **3,239 quotes, 1,208 trades, 73,313 total bytes**. This demonstrates
pre-February-2024 provider access for this exact case, not full older coverage.
Dated standard-contract references/hours and feature-row integration remain open.

The bounded plan reserved a conservative 3 GiB capacity ceiling including two
per-window reservations and metadata, within all existing budgets. Actual shared
acquisition quota is 68,973,094,838 / 250,000,000,000 bytes, no reservations.
At the follow-up about 158.07 GB was free, leaving only ~50.69 GB for additions
above the 100 GiB reserve. The 640 GB total-project budget remains. Do not launch
42 million provider windows without a measured full-scope volume/storage plan;
this single capture and old SPY-only pilot cannot establish that forecast.

## Monitoring and alerts

Konsole was opened with `./venv/bin/python scripts/watch_v7_demand.py --follow`.
It is read-only and stops refreshing on full demand completion; --hold keeps the
finished terminal visible. It separately showed saved versus revalidated counts.
No `v7_training_progress.py` exists here; the old catalog --follow viewer was for
7-2. A training progress monitor belongs to the eventual gated training launch.

The repeated completed-build alerts were HOME timers, not Hetzner.
`healys-v6-progress.timer` and `healys-v7-catalog-progress.timer` are disabled
and inactive. Do not re-enable them for completed campaigns. Live scanner/feed/
health/publisher/V6 paper/incubator jobs were not changed.

## Next work and evidence

Build a measured capture-volume/storage plan for the actual full entry union;
reuse captures and retain provider failures. Resolve dated option hours and
standard references, then cover entry fills, minute marks, exits, rolls and
stock delivery. Complete integrated execution, full assembly/folds/trials and
resource/readiness gates before training. Entry-demand completion does not close
V7-3 or imply a trained model.

Reviews: `docs/reviews/2026-09-26-v7-capture-preparation.md` and
`docs/reviews/2026-09-26-v7-entry-union-and-first-capture.md`.
Full suite: **2,415 tests + 18 subtests**, 20 warnings, 123.33 seconds.
No production code changed after that run; actual capture was independently
verified with the existing receipt/provider validators. The frozen catalog and
kernel proof remain unchanged.

October 2 Massive keep/cancel recommendation, V6 Alpaca bridge lifecycle and
incubator outcome/daily-health work remain separate carried-forward items.
