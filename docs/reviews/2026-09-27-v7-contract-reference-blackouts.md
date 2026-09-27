# V7 finite contract-reference blackouts — 2026-09-27

The user authorized treating the five previously identified missing dated
references as unavailable research days: “can we just treat those days as a
weekend for those 5 instances?” This is implemented as exact contract/date
research-path exclusion. Actual exchange calendars and original observations
remain unchanged. It is retrospective data-quality admission, not eligibility
known to a historical trader.

| Contract | Reference date | Entry proposal/target outcomes |
|---|---|---:|
| CMA230630C00041000 | 2023-06-22 | 122 |
| FANG220520P00130000 | 2022-05-18 | 8,520 |
| MSTR230630P00320000 | 2023-06-27 | 310 |
| RH230630P00290000 | 2023-06-22 | 246 |
| VFC230630C00019000 | 2023-06-28 | 3,772 |

Total: 12,970 entry proposal/target outcomes, 294 selected decision/target
outcomes, 192 original quote/trade requests. All remain in their frozen demand
stores. The complete 720-reference sample partitions into 715 verified standard
references and five explicit blackouts. No new downloads were needed.

## Implementation and evidence

- Declaration: `docs/specs/V7_CONTRACT_REFERENCE_BLACKOUTS_20260927.json`.
- Sealed evidence: `nn_meta/validation/v7-contract-blackouts-20260927`.
- Frozen entry impact: `nn_meta/validation/v7-contract-blackout-impact-20260927`.
- Producer: `scripts/compile_v7_contract_blackouts.py`; verifies each exact 404
  and both complete same-date alternative-list probes before sealing.
- Consumer: `nn_meta/v7/contract_blackouts.py`; adapter wraps the actual
  feature/replay reference consumers without editing frozen producers.
- Additive dataset launcher: `scripts/build_v7_blackout_dataset.py`, with
  mandatory `--blackouts` binding. Full dataset assembly has not launched.

Affected outcomes are retained with `excluded_contract_reference_blackout`,
treatment IDs and source hashes, but no numerical feature row or training label.
An entry blackout never selects another contract. A held path reaching a
blackout retains legitimate prior fills/cash/open positions and stays incomplete:
no invented settlement, skipped held session or return. A path already closed
before a later blackout is identical to its original result. Rolls retain any
legitimate prior sale without inventing a replacement purchase. Unknown future
missing references still fail closed and do not join this finite declaration.

## Limits and remaining work

The impact count covers frozen entries, not all positions crossing the dates.
Full execution/physical/shared-capital integration and held-path census remain
open. Retrospective exclusions must not silently rerank a historical portfolio
or claim complete shared-capital performance. This does not establish training
readiness or full execution coverage.

The user also authorized using MRHA disk if necessary. Storage forecasts still
need held paths, assembly, training and recovery allowances; that permission
alone does not increase the numerical 250 GB acquisition or 640 GB project caps.
Historical hours, full-path budgeting and resumable packed scheduling remain
V7-3 work. Original proposal/demand/packed freezes are preserved.

## Validation

Seven focused tests pass: exact scope, declaration/evidence drift, alternative
match rejection, actual assembly census, held positions, earlier closes and roll
handling. The new launcher help/argument path also passes. Full-suite result is
recorded in HANDOFF.md after completion.

Full suite: 2,448 passed, 18 subtests passed, one skipped, 20 warnings, 115.95s.
