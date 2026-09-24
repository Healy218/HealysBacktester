# Handoff — 2026-09-24 — V5 live capture and incubator/V7 checkpoint

## Start here

Read `TODO.md`, then this file. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-consolidated-notes.md`. The active
V7-2 compact 5/15/30 catalog is still building; do not stop, restart,
relabel, delete or deep-audit it during the build. Do not start 7-3 until its
full 1,773-store post-seal and resource/recovery verification passes.

## State and evidence

- V7-2: `nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`
  remained active. At 2026-09-24 15:50 UTC, a read-only sample found 423/591
  complete securities, 1,277 proposal stores, ~376.6 GB disk free, 20.05 GB
  current / 22.42 GB peak cgroup memory, 73.625°C CPU and no cgroup CPU
  throttling. This is a point-in-time resource sample, not a 7-2 verdict.
  `scripts/audit_v7_catalog.py --full` is reserved for after seal; see
  `docs/reviews/2026-09-23-v7-catalog-audit-prep.md`.
- V6 incubator: the read-only closed-position exporter sealed 14 midpoint-policy
  outcomes. Only DUOL/macd/30 DTE exactly matched the 304-row 2026-09-22
  candidate matrix (`net_return=-0.12458142055209864`); 303 remain pending.
  The 40-member live GBT replay produces prediction receipts, not a supported
  performance verdict. See `docs/specs/AI_INCUBATOR.md`.
- V5 incubator: the server-compatible branch is deployed at `059ff1d` with
  `--incubator-capture-root` on only the active V5 cron line. Nine real
  market-hours passes under `incubator/artifacts/v5-passes/2026-09-24/` had
  sealed by 15:47 UTC, with 3,555 distinct exact candidate identities and 48
  model features. A read-only check verified generation, config binding,
  Parquet hashes, row counts and single signal bars. Recent V5 scan summaries
  reported zero errors. The day's full pass census is not final; no V5 paper
  outcomes or performance result exist, and the passes have not been staged
  on the home box. The model manifest uses a canonical JSON digest
  `b6a71bbfb74c3de71384e4612106d6bc72e8a0caf8c02726dcba82258c7d213c`;
  the raw config file SHA-256 is
  `b4631653459490045a92e6305922b40440780f3fd6a8b93edcee462601044182`.
  See `docs/reviews/2026-09-24-v5-capture-deployment.md`.

## Deployment and next gates

The server stayed on `ops/server-alert-readiness-20260906`. The narrow V5
backport preserved three server-local commits and its unrelated dirty retired
V3/V4 model deletions; it was pushed and deployed by fast-forward Git pull,
not by switching to `main` or scp. The previous crontab is recoverable at
`/home/mrhea/HealysBacktester/logs/ops/ops-fixes-20260924T111725Z/crontab-before.txt`.
The deployed 40-member V5 model self-test passed. The server branch has the
same 59 pre-existing alert/accounting test failures before and after the
backport; targeted scanner/capture/cron tests passed 19/19.

After today's last V5 market-hours scan, verify the final dated pass census,
manifest hashes and scanner error log. Paper-data staging to the home box
requires the explicit boundary decision; the home after-close runner remains
V5 input-blocked until a genuine sealed day is staged. Exact-identity V5
outcome export and multi-day scoring remain open. Never substitute V6-origin
compatibility rows. The incubator timer remains disabled and its service has
no `--allow-execution`; V7/FA admission still awaits 7-2 through 7-7 and
separate production isolation approval.

## Git boundary

Main already contains the V5/V6 incubator and V7 audit code (`4783385`,
`2f39e72`) plus the first deployment record (`d2ba550`). The V5 server
backport is `059ff1d` on its separate production branch. The home worktree
still has many unrelated V6/V7 source and documentation changes. Do not
broad-stage, clean or reset it; stage only this notes update. Generated
incubator artifacts and the active V7 catalog are ignored and must not be
force-added. Temporary backport/baseline worktrees remain under
`/tmp/healys-v5-server-backport-20260923` and
`/tmp/healys-v5-server-baseline-20260923` for audit.
