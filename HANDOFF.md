# Handoff — 2026-09-26 — capture volume measured; storage placement unresolved

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-26-before-capture-volume-sample.md`.
Work on main; preserve extensive unrelated dirty/untracked work.

## Current stage

V7-1 and V7-2 complete. V7-3 remains current. User said "lets keep going" after
the first real capture. We completed full-population sample planning, 1,440 actual
captures, storage estimates, a lossless encoding benchmark and exact contiguous
range census. Full acquisition and training have NOT launched.

All original 1,773 stores, catalog/daily gates, 591 demand outputs, kernel parity
proof and first SPY captures remain preserved. Do not rebuild or relabel them.
The user-approved kernel 7.2.6 → 7.2.7 exception is scoped to demand consumption.

## Completed upstream evidence

- Full demand: `nn_meta/validation/v7-3-scheduler-20260925`, 591/591 complete,
  793,394,264 proposals. `kernel-recovery/progress.json` is the final meter;
  the root progress file is the historical failed strict-runtime restart.
- Full entry union: `nn_meta/validation/v7-3-entry-union-20260926`,
  76,910,536 unique requests, 42,030,534 fixed-cell quote/trade captures,
  1,057,177 contracts, 2,223,844 contract-days; no-fresh/no-contract outcomes
  explicit. This is entry-feature demand, not complete execution demand.
- First actual SPY capture: `nn_meta/data_v7/entry-first-actual-20260926`,
  March 15, 2022, 3,239 quotes and 1,208 trades; verified separately.

## Actual volume sample and storage constraint

Plan: `nn_meta/validation/v7-entry-volume-sample-20260926`.
Its scanner reconciled every security/request/contract-day/union second with
full demand. Sixty strata span year, security request-count quartile and window
length. Twelve paired windows per stratum were selected by seeded SHA256 before
provider inspection: 720 pairs / 1,440 captures, 362 securities, all five years.
Preserved scan checkpoints are in the sibling `.checkpoints` directory.

Raw: `nn_meta/data_v7/entry-volume-sample-20260926`.
Evidence: `nn_meta/validation/v7-entry-volume-forecast-20260926` and its sibling
`.attempts` directory. All 1,440 passed with zero failures: 231,858 quote records,
5,559 trades, 52 empty quote and 437 empty trade windows. The 620 pre-February-2024
captures contain 100,426 records. Empty/failure states are never invented fills.
The actual sample used 7,030,384 bytes and 186.55 seconds with four autosized
workers and one inner thread, within the 8 GiB bounded acquisition plan.

Estimated full entry captures in current layout: **218.04 GB**, standard error
15.91 GB; mean plus three SE 265.77 GB. These exclude request mappings, dated
references and full execution paths. Three SE is not a guaranteed upper bound.
Current quota: 68,980,125,222 / 250,000,000,000 bytes, no reservations.
Local free space around 158.04 GB; only ~50.67 GB remains above 100 GiB reserve.
Existing total-project ceiling is still 640 GB. Full current-layout capture
cannot be launched against these budgets.
Fresh `du -sb .` returned 489,135,748,190 apparent project bytes (non-atomic).
Adding full gross estimates yields 707.18 GB current layout / 653.22 GB candidate,
both above 640 GB before other missing stages. Saved capacity snapshot:
`nn_meta/validation/v7-entry-capacity-verdict-20260926`.

## Lossless and request-count experiments

`nn_meta/validation/v7-entry-encoding-benchmark-20260926`:
all 1,440 raw streams and exact manifest/receipt texts round-trip through the
candidate JSON-column/zstd encoding. Estimated 164.08 GB, standard error 12.40 GB,
mean plus three SE 201.28 GB, with a modeled 128-byte index allowance per capture.
This is an encoding experiment, NOT an implemented archive/consumer or migration.
All original files remain intact. Do not present it as admitted production input.

`nn_meta/validation/v7-contiguous-entry-union-20260926`:
full read-only scan merges only touching/overlapping intervals within contract/day.
10,941,828 contiguous ranges (5,470,914 per kind) preserve all 14,404,985,220 seconds
per kind and all 2,223,844 contract-days. Zero added seconds; ~74% fewer ranges.
Dense ranges may need pagination splitting. Long-range throughput, memory,
retention and consumer receipt compatibility are not yet measured/implemented.
The old fixed-cell audit has not changed.

## Pending user input and next actions

Asked via async input which additional disk/storage location is available.
Read-only `lsblk` sees `/dev/sda2`, label MRHA, 1.8 TiB exFAT, unmounted. No mount,
format, write or archive placement was performed. Its free capacity is unknown.
Await the user's identification before selecting a new storage destination.
More disk does not authorize increasing the 250 GB acquisition/640 GB project
caps. Do not delete originals or narrow scope to make the forecast fit.

Next: resolve placement, measure/validate exact contiguous capture and archive
costs (including bounded paging and preserving failure receipts), then make an
updated full-project acquisition plan. Dated standard-contract references and
class hours remain missing. Full fill/mark/exit/roll/delivery demand, execution,
assembly/folds/trials and readiness gates still precede training.

## Monitoring, validation, durable notes

The separate Konsole tab now shows completed sample progress:
`./venv/bin/python scripts/watch_v7_capture_sample.py --status nn_meta/validation/v7-entry-volume-forecast-20260926.status.json --follow`
This is a read-only capture monitor, not a training progress bar.
Old `healys-v6-progress.timer` and `healys-v7-catalog-progress.timer` remain
inactive/disabled. V6 live paper/scanners/feeds/health jobs were not changed.

Final full suite: **2,424 tests + 18 subtests**, 20 warnings, 128.23 seconds.
All nine focused sampling/encoding/range tests pass. No producer or frozen
scheduler source was edited; new scripts are separate consumers/experiments.
Review: `docs/reviews/2026-09-26-v7-capture-storage-forecast.md`.

October 2 Massive decision, V6 Alpaca bridge lifecycle and incubator outcome/
daily-health remain separate carried-forward work.
