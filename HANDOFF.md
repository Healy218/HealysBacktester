# Handoff — 2026-09-23 — V6 outcomes, V7 audit prep, V5 capture

## Restart first

Read `TODO.md`, then this file. The previous handoff is archived at
`handoff-history/HANDOFF-2026-09-23-before-outcome-catalog-v5.md`. The active
V7-2 compact 5/15/30 catalog is still building at
`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`. Do not stop,
restart, relabel or delete it; do not start 7-3 until full 7-2 verification.

## What landed locally

1. `scripts/export_v6_incubator_outcomes.py` opens the local V6 paper SQLite
   ledger read-only, hashes source/WAL across the read, accepts only fully
   closed midpoint-policy positions with exact V6 identity and close clocks,
   and seals net-return parquet, per-position evidence and manifest. An
   optional exact-identity join is supported. The 2026-09-23 export found 14
   closed positions; only DUOL/macd/30 DTE matched the 304-row 2026-09-22
   candidate matrix (`net_return=-0.12458142055209864`). The other 303 are
   pending, so there is no V6 performance verdict.
2. `scripts/audit_v7_catalog.py` now supports a small read-only live preflight
   and a post-seal `--full` audit of all 1,773 compact stores. The sampled
   preflight passed at 848 present stores/925 missing. Full mode is not yet
   run. `scripts/sample_v7_catalog_resources.py` records cgroup, CPU temp,
   disk, progress and age outside the active catalog. A later sample found 291
   complete securities, 881 proposal stores, 82.25°C CPU, ~12.36 GB current /
   ~19.96 GB peak memory, ~400.52 GB free disk, and zero cgroup CPU
   throttling. See `docs/reviews/2026-09-23-v7-catalog-audit-prep.md`.
3. V5 candidate feature capture is opt-in at the scanner via
   `--incubator-capture-root`; it seals the scored full candidate batch per
   signal bar with `generation=v5`, identity, model-config hash and parquet
   hash. The daily runner can assemble staged passes by date. The V5 replay
   entrypoint now imputes NaNs with each member's saved scaler mean. The active
   ignored registry has `v5-keras-ev-replay-v3.tar.gz` and the current V6 GBT
   bundle; V5 v2 was moved to
   `incubator/artifacts/v5-live-20260923/bundles/v5-keras-ev-replay-v2-retired.tar.gz`.
   No real V5 candidate pass has been captured or validated yet.

## Operational gates

The V5 server remains on a divergent branch with unrelated dirty model-file
deletions, so do not `git pull main`, switch branches or overwrite it blindly.
The scanner capture flag was not deployed or added to server cron; its current
paper ledger alone cannot reconstruct full candidate features. Reconcile that
checkout and use git-pull deployment before adding the opt-in V5 flag; then
stage sealed pass directories locally under `incubator/artifacts/v5-passes`
and verify a genuinely captured day. No V5 performance claim is supported.
The incubator timer remains disabled, the service has no `--allow-execution`,
and production isolation/paper-data approval plus TODO 7-2–7-7 still gate
activation. No V7-3 capture work began.

## Verification and worktree

Focused tests: 23 passed. Full suite: 2,376 passed, 20 warnings, 18 subtests
passed. The updated incubator user-systemd unit verifies outside the sandbox.
The V6 exporter read the actual ledger without modifying it. Live V7 preflight
and resource samples were read-only and wrote only under `logs/v7-progress/`.

Many unrelated V6/V7 changes are present in the worktree. Narrow-stage only
this slice; `nn_meta/live/v4_scan.py` specifically overlaps other uncommitted
V6 shadow work, so stage only the V5 capture lines. Generated incubator
bundles, outcomes and run receipts are ignored and must not be force-added.
