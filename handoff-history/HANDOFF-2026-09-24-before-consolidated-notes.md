# Handoff — 2026-09-24 — V5 capture deployed on server branch

## Restart first

Read `TODO.md`, then this file. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-v5-server-backport.md`. The V7-2
5/15/30 compact catalog remains active on the home box; do not stop, restart,
relabel or delete it. V7-3 still waits for full 7-2 post-seal verification.

## V5 deployment result

The Hetzner server's checkout was on the compatibility branch
`ops/server-alert-readiness-20260906`, with three unpushed commits and
unrelated dirty deletions of retired V3/V4 model files. It was not switched
to `main` or reset. We fetched its exact `c79e877` commit into a temporary
worktree, added a narrow V5 capture backport, and pushed the existing branch
to `059ff1d`, preserving those three commits. The server deployed with
`git pull --ff-only origin ops/server-alert-readiness-20260906` and is now at
`059ff1d`; the touched scanner/cron/incubator paths are clean. The unrelated
model deletions remain untouched.

The V5 scanner now accepts `--incubator-capture-root`, seals full scored
candidate batches under `incubator/artifacts/v5-passes/`, and continues paper
alerts even if capture fails. `scripts/configure_cron.py
--enable-v5-incubator-capture --run` added the flag to the active V5 line
only. The previous crontab is recoverable at
`/home/mrhea/HealysBacktester/logs/ops/ops-fixes-20260924T111725Z/crontab-before.txt`.
The deployed 40-member V5 model self-test passed. Home and server model-config
SHA-256 match (`b4631653459490045a92e6305922b40440780f3fd6a8b93edcee462601044182`).
See `docs/reviews/2026-09-24-v5-capture-deployment.md`.

The server-branch full test suite has the same 59 pre-existing alert/accounting
failures before and after the backport: baseline 682 passed, backport 685
passed. The focused scanner/capture/cron suite passed 19 tests. This is not a
new observed test regression, but the branch-wide suite is not green.

## Next gates

No genuine post-deployment V5 pass had yet appeared at handoff: deployment
occurred before market hours. Inspect the first market-hours V5 cron log and
`incubator/artifacts/v5-passes/YYYY-MM-DD/` on the server. Verify the feature
manifest, parquet hash, config hash and candidate identities; investigate any
`[v5-incubator] candidate capture failed` log. Only then consider staging the
paper data on the home box under the explicit paper-data boundary; the home
after-close runner still treats V5 as input-blocked until a genuine sealed pass
is staged. Do not substitute V6-origin compatibility rows. The incubator timer
remains disabled and the service has no `--allow-execution`.

The active V7 catalog remains untouched by this V5 deployment. The home
worktree still has many unrelated V6/V7 dirty files; narrow-stage only this
handoff/documentation update. Temporary backport and baseline worktrees are
under `/tmp/healys-v5-server-backport-20260923` and
`/tmp/healys-v5-server-baseline-20260923` respectively; the backport commit
has been pushed. Do not broad-clean the repository or server checkout.
