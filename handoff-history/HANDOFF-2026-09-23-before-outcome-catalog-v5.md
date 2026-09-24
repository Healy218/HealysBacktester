# Handoff — 2026-09-23 — daily V5/V6 incubator wiring

## Restart first

Read `TODO.md`, then this file. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-23-before-daily-incubator.md`. Preserve the
active V7-2 compact 5/15/30 catalog; do not stop, restart, relabel, or delete
it, and do not start V7-3 until it is sealed and verified. See the archived
handoff and `logs/v7-progress/v7-2-full-catalog-20260922-rebuild-5-15-30/`
for its last known progress. This session did not operate on that build.

## Incubator result

The scheduled CLI now reads a dated V6 candidate pass, publishes and verifies
a sealed 164-feature matrix under `incubator/artifacts/daily/v6-YYYYMMDD/`,
routes V5 and V6 bundles to separate requests, and writes date-scoped
checkpoints, per-artifact attempt directories/receipts, an after-close summary,
and `performance-log.json`. It refuses changed candidate source hashes on
rerun, and any V5 input without an explicit matching generation/date seal. The
service points to `incubator/artifacts/active/`, includes bounded memory/CPU
configuration, but remains disabled and has no `--allow-execution` flag.

Active bundles are ignored by git under `incubator/artifacts/active/`:

- `v6-gbt-causal-replay-v2.tar.gz`: live 40-member GBT, EV-mode, 164 features.
  Its `prediction` is now the EV decision, not P(win); `p_win` is separate.
- `v5-keras-ev-replay-v2.tar.gz`: server-matching config SHA-256
  `b4631653459490045a92e6305922b40440780f3fd6a8b93edcee462601044182`.
  Uses the magnitude heads and saved `std` scalers. Its 304-row replay smoke
  used V6-origin rows **only for compatibility**, not V5 paper evidence.

The 2026-09-22 active campaign smoke at
`incubator/runs/after-close/close-20260922-active-ev-smoke/` executed the V6
bundle successfully: 304 pending-outcome predictions, 40 members, no execution
failures. It exited nonzero solely because the V5 input was blocked, and the
unified performance log records both states. A prior one-row DUOL outcome join
is partial; 303/304 V6 rows remain pending, so no performance or readiness
result exists. Older V6 replay output labeled P(win) as `prediction`; it must
not be used to score EV. Historical bundles are preserved outside the curated
active registry.

## Remaining gates

1. Capture actual V5 candidate feature batches at the server's V5 scanner
   boundary and publish them separately with `generation=v5`; its current
   `.v5_paper_ledger.json` is only a trade ledger. The after-close CLI has a
   `--v5-feature-dir` slot and fails closed until this exists. Do not substitute
   the V6 compatibility matrix.
2. Add durable exact-identity matured-outcome export/joins for both generations
   and validate multi-day paper scoring. The joined matrix contract now carries
   generation and is accepted via explicit `--v6-feature-dir` or
   `--v5-feature-dir`.
3. Before production activation, validate OS-level network isolation and
   cgroups in the target user-systemd environment, retention/backup operation,
   and the TODO.md 7-2 through 7-7 plus explicit paper-data boundary gate.
   Do not enable the timer or add `--allow-execution` to its service yet.

## Verification and git boundary

Targeted incubator suite: 29 passed after final input-contract edits. Full
suite: 2,368 passed, 20 warnings, 18 subtests passed. `git diff --check`
passes. `systemd-analyze --user verify` passes outside the sandbox. The V5
and V6 active bundles both loaded and produced 304 pending predictions in
isolated smoke runs; neither proves performance.

The workspace contains many unrelated dirty V7/V6 files. Do not broad-stage,
reset, clean, or modify the active V7 catalog. This session still sees `.git`
as a read-only mount (`findmnt -T .../.git` reports `ro`), so it could not
stage, commit or push. After a fresh writable mount, review and narrowly stage
only incubator code/tests/service and documentation for this slice. Generated
artifacts/runs are ignored and should not be force-added without an explicit
artifact-publication decision.
