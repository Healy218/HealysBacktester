# Handoff — 2026-09-25 — V7-3 resumed with proven kernel compatibility

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-25-before-crash-recovery.md`.
Main is operational. Extensive unrelated dirty/untracked work predates this
session; preserve it and stage only owned changes.

## Current work and preserved freeze

V7-1 and V7-2 are complete; V7-3 is active. The existing 591-security,
1,773-store 5/15/30 catalog remains unchanged. All feature/proposal summary
receipt pairs match the original deep audit. The original completion gates,
historical-loader proofs and daily context remain intact. No proposal refreeze.
All 546 pre-shutdown demand checkpoints are retained. Their declarations bind
21,001,900 inputs across 1,873,058 distinct files; the recovery audit found no
input/source drift. Only the kernel platform string changed on reboot.

The prior launch/handoff edits were staged but uncommitted when the API crashed;
those were recovered in commit `d76c2e1`.

## Active service and progress

**Service:** `healys-v7-entry-demand-recovery-20260925.service`.
**Invocation:** `9a07064bbccd4f91aedd75e46580fd3a`.
**Output:** `nn_meta/validation/v7-3-scheduler-20260925`.
**Current meter:** `kernel-recovery/progress.json` under that output.
**Controller log:** `kernel-recovery/controller.log`.

Verified active/running with four autosized workers, one inner thread, 400% CPU,
14 GiB memory high / 16 GiB maximum, zero swap, nice 10, IO weight 25 and
AF_UNIX-only sockets. It first revalidates/reuses the 546 saved checkpoints,
then builds the remaining 45. Its fresh meter starts at zero and measures
this invocation; it does not mean old checkpoints were lost. The original root
`progress.json` records a failed strict-runtime restart and is no longer the
active meter. Inspect the recovery meter for current progress/failures.

## Exact compatibility and storage evidence

The reboot changed Linux 7.2.6-1-cachyos to 7.2.7-1-cachyos. The unchanged
scheduler correctly refused to reuse old-runtime demand. The user explicitly
approved validating kernel compatibility while preserving every original.
The separate recovery consumer admits only that exact pair with identical
Python, executable, glibc, packages, input/source hashes and all other runtime
fields. Original scheduler/strict readers and producer code were not changed.

Four real replays passed: 97,935 proposals, 7,674 requests, byte-identical
SQLite demand, equal reports and byte-identical exported request batches.
New artifacts record the actual runtime and bind the recovery source/proof;
legacy receipts are never relabeled. This exception is only for frozen-catalog
consumption and entry demand, not regeneration, training or provider capture.
Do not edit either scheduler, recovery source or bound inputs during the run.

The old 200 GiB cap failed the current disk preflight. A new sealed allocation
uses completed actual bytes plus the original per-security forecast for the
45 remaining securities, including partial evidence and 8 GiB working margin.
Total stress forecast: 128.81 GB. Revised cap: **140 GiB** (150.32 GB).
The 100 GiB free reserve, 640 GB project budget and 250 GB acquisition ceiling
remain. No files were deleted. Captures still need a separate storage forecast.

Evidence under `nn_meta/validation/`:
- `v7-3-demand-recovery-plan-20260925`
- `v7-3-recovery-audit-20260925`
- `v7-3-kernel-equivalence-20260925` (replay outputs in sibling `-replays`)
- `v7-3-recovery-launch-20260925`

Full review and exact restart command:
`docs/reviews/2026-09-25-v7-3-crash-recovery.md`.
Use `scripts/start_v7_entry_demand_recovery.sh` after investigating any failure;
the original launcher still rejects old-runtime checkpoints on the new kernel.
The transient service survives terminal closure, not a user-manager shutdown
or reboot. The same exact approved runtime is required for this recovery proof.

Validation: **2,411 tests, 18 subtests, 20 warnings**, 120.33 seconds;
eight focused recovery/scheduler tests, all four real replays and launcher
syntax/read-only preflight passed. Actual service limits were verified.

## Next work

Monitor recovery. After all 591 complete, independently reconcile the full
request union and missing/no-contract outcomes. Then resolve dated option hours
and standard references, and cover entry fills, minute marks, exits, rolls and
applicable stock delivery. Demand completion alone does not close V7-3.
V7-4 through V7-7 and training readiness remain open.

V6 Alpaca fresh scanning/submission remain disabled; prospective scanner/bridge
and multi-roll verification remain open. Preserve separate simulator/broker P/L.
V5/V6 incubator and the October 2 Massive decision remain carried-forward work.
No V6 or incubator runtime was changed during recovery.
