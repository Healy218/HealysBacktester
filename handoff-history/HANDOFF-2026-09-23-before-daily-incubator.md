# Handoff — 2026-09-23 — V7-2 active, V6 incubator contract aligned

## Restart first

Read `TODO.md`, then this file. Preserve the active V7 build and do not start
V7-3 until V7-2 is sealed and verified. The previous handoff is archived at
`handoff-history/HANDOFF-2026-09-23-before-session-restart.md`.

## Current V7 run

V7 item 7-2 remains the active work item. The current run is the systemd-managed
compact 5/15/30 catalog rebuild:

`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`

Run configuration:

- 591 securities and 1,773 target stores
- all 20 strategy families at 5/15/30 minutes
- four outer security workers, one inner thread
- compact-final enabled, checkpoint/restart capable
- validation-only; it is not research-ready or training authorization

Latest available progress receipt, observed 2026-09-23 11:00 UTC:

- 88/591 complete securities
- 566 feature receipts
- 276 sealed feature stores
- 275 proposal stores
- 20.96 GB output, approximately 19.5 GiB
- 452.5 GB free disk
- observer estimate: approximately 55.8 hours remaining, around 2026-09-25 13:46 CDT
- active worker logs include `BBG000BQ8KV2`, `BBG000BQLTW7`, `BBG000BR2TH3`,
  `BBG000BRD0D8`, `BBG000BRK7L6`, `BBG000BRNLL2`, and `BBG000BS1YV5`

Evidence is in:

- `logs/v7-progress/v7-2-full-catalog-20260922-rebuild-5-15-30/latest.json`
- `logs/v7-progress/v7-2-full-catalog-20260922-rebuild-5-15-30/progress.txt`
- `logs/v7-progress/v7-2-full-catalog-20260922-rebuild-5-15-30/history.jsonl`

Do not stop, restart, relabel, or delete this run. The user-systemd status
could not be queried from this Codex session because the user bus is outside
the session namespace; use the progress receipts and the host terminal when
service state must be checked.

## V6 incubator checkpoint

V6 daily updating is now the priority over V5 because V7 is expected in roughly
one to two weeks. The V6 incubator uses the actual live V6 GBT release, not the
older archived Keras contract:

- release source: `deploy/v6/releases/v6-cash-repair-20260913/model/`
- family: GBT; 40 ensemble members; 164 feature columns
- current matrix: `incubator/artifacts/v6-live-20260922/`
- current pass: `/home/healy/Coding/HealysV6/nn_meta/live/v6_server/passes/20260922T193000Z/candidates.parquet`
- matrix: 304 rows, zero duplicate `symbol/strategy/dte/entry_ts` keys,
  complete identity fields, model-native NaN policy
- replay bundle used: `/tmp/incubator-registry-smoke/v6/incubator-v6-gbt-20260922.tar.gz`
- execution receipt: 304 read-only predictions, `model_loaded=true`,
  `status=executed_pending_outcome`

The 2026-09-23 exact-identity join matured one candidate: DUOL/macd/30 DTE at
2026-09-22T19:15Z, with explicit `net_return=-0.12458142055209864` derived from
the closed paper position's recorded return factor. The remaining 303 of 304
candidate rows are still pending. The curated registry contains only the live
GBT artifact (`v6-gbt-causal-20260922`); the duplicate old Keras replay bundles
are excluded. The bounded campaign passed with one artifact, 40 members loaded,
and zero failures. This is an execution/data-integrity pass, not a performance
or readiness result. The older Keras V6 bundle is
retired from the daily V6 path because its `prem_spot` feature contract does
not match the current causal live pass. V5 remains supported for its transition
period.

Relevant implementation and notes:

- `incubator/gbt_replay_entrypoint.py`
- `incubator/live_features.py`
- `incubator/sandbox.py`
- `scripts/publish_v6_incubator_features.py`
- `scripts/ai_incubator.py`
- `docs/specs/AI_INCUBATOR.md`
- `TODO.md` item 8

The after-close incubator service/timer is committed in the worktree but remains
disabled. Keep production activation, V7 onboarding, and FA admission gated
until the V7 readiness gates and explicit paper-data boundary are complete.

## Validation

- Focused incubator suite: `26 passed`.
- Full suite: `2365 passed, 20 warnings, 18 subtests passed`.
- V6 live matrix quality checks: 304 rows, 168 total columns, 164 model
  features, zero duplicate identity keys, zero missing identity fields.

## Git/session blocker

The repository working tree is writable, but this Codex session sees `.git` as
a separate read-only mount. `findmnt` reports `.git` with `ro`, so staging,
committing, and pushing cannot occur here. The user attempted host remounts,
but this existing session still sees the old mount namespace. After restarting
Codex/the workspace, verify:

```bash
findmnt -T /home/healy/Coding/HealysBacktester/.git -o TARGET,OPTIONS
```

It must show `rw`. Then stage only the incubator and note files, review the
diff, commit, and push `main`; preserve unrelated V7 and historical changes.

## Working-tree caution

The worktree contains many unrelated user changes from the V7 build and prior
V6/FA work. Do not reset, clean, or broadly stage them. Generated daily
incubator artifacts are ignored under `/incubator/artifacts/`.
