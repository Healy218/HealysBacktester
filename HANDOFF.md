# Handoff — 2026-09-24 — V7-2 reviewed coverage restart

Read `TODO.md` first. The prior handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-reviewed-coverage-restart.md`.
V7-1 is complete under its agreed exclusion policy; V7-2 is the active
proposal catalog build; V7-3 follows a fully verified V7-2. Do not claim the
591-security/1,773-store gate has passed while the 45 noncash cases below are
unbuilt. Main is the operating branch. The worktree has extensive unrelated
dirty files; do not clean, reset, broad-stage, or modify V7 producer sources
while the build is running.

## V7 live state

`healys-v7-catalog-build.service` was restarted at 2026-09-24 16:36:37 CDT.
At 16:44:13 CDT it was active as PID 3093731, with zero restarts, four real
proposal workers and 1,259/1,773 sealed proposal stores. The first corrected
GOLD/B worker was generating real signals. The independent service has
`Restart=no`; its journal is the controller progress bar. The CLI is
`./venv/bin/python -m scripts.watch_v7_catalog --follow --interval 5` from
repo root. It follows the same output path and reports host-side service state.
The one-shot observer may show `unknown` when run in a restricted sandbox;
the host-side CLI reported `active` and zero restarts.

The first 7-2 restart stopped at 419 complete securities after the GOLD/B
worker found no admitted history. Root cause: the repaired September 21
coverage had zero reviewed rename events and omitted the sealed unrelated-
instrument treatments because the original auditor rejected a historical
`ordinary_actions.py` hash conflict between sealed parents. The original
auditor was restored byte-for-byte (its hash matches the September 21
coverage). A separate `scripts/audit_v7_action_coverage_compatible.py` retains
the historical review source hash in its report while binding computation to
the current source. It sealed
`nn_meta/validation/v7-action-coverage-20260924-reviewed-v2`. This has 4,354
admitted events and four unresolved rows. It changes admission on exactly
eight securities and leaves the other 583 with identical admitted dates and
action events. The service uses this supplemental coverage only for those
eight, the original coverage for others. Its exact preflight verified 415
reuse-manifest securities, four newly sealed securities, action-event parity,
127 schedulable builds, and 45 zero-admission securities. Full suite: 2,381
passed and 18 subtests. Recovery code/unit commit `de7aada` is pushed to main.

The 45 still unbuildable securities have no admitted observed day under the
September 18 explicit noncash boundary exclusions: 36 involve at least one
undated name-change record and nine have only dated noncash events before any
observed usable history. Do not turn these into empty stores or silently lower
the 591 target. Their records require exact primary-source review to admit
history. All 45 are visibly deferred by the runner; it will return failure
rather than claim catalog completion when the schedulable work finishes.
Several undated cases have promising local listed-identity evidence (ELV,
OSTK/BYON, MPW/MPT), but no new admission has been sealed. Web primary
issuer notices were identified for those three. The full target remains
incomplete and V7-3 must not start.

The build output remains
`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`. Original
415 sealed stores have an explicit compatibility manifest at
`nn_meta/validation/v7-2-catalog-reuse-20260924.json`; four additional stores
were audited on resume. Do not relabel any old receipt. The old eight changed
and four partial directories remain preserved under the sibling
`-superseded-20260924` archive. A superseded staged draft describing the old
53-security finding was removed; the current zero-admission count is 45.

## V6 state inherited from prior handoff

The V6 quote-evidence repair is deployed from the separate V6 checkout branch
`ops/v6-quote-evidence-20260924` at `e6991f2`; 19:45 UTC paper pass recorded,
but 20:00 UTC final-bar pass still failed closed due missing fresh option quote
observations. Dashboard broker projection was refreshed. See
`docs/reviews/2026-09-24-v6-quote-evidence.md` and the archived handoff for
full context. Current user focus is V7.
