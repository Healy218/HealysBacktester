# Handoff — 2026-09-24 — V7 catalog recovery and V6 paper quote evidence

## Start here

Read `TODO.md`, then this file. The previous handoff is archived at
`handoff-history/HANDOFF-2026-09-24-before-v7-catalog-recovery.md`.
The active phase is still V7-2; do not begin 7-3 until the full 1,773-store
audit and resource/recovery checks pass. Main is the operating branch. The
worktree has extensive unrelated dirty V6/V7 sources: never broad-stage,
clean, reset or relabel them. The active V7 build must not be casually stopped
or restarted. The user expressly authorized the September 24 recovery below.

## V7 live state and exact recovery

**New gate conflict found at 20:47 UTC:** the recovered build reached 416
complete securities and 1,252 proposal stores, then worker
`BBG000BB07P9` failed because all 1,129 selected sessions are unadmitted.
The controller stops scheduling on the first failure and will exit after its
three in-flight workers finish; `Restart=no` prevents a loop. A full read-only
census found 53 of 591 securities with zero admitted observed sessions: 45
dominated by approved noncash boundary exclusions and eight by unresolved
action records. `TODO.md` still requires 591/1,773 stores, which cannot be
produced under this admission. Do not restart or silently shrink the target.
Reconcile the gate first. See
`docs/reviews/2026-09-24-v7-admission-target-conflict.md`.

At 2026-09-24 20:31 UTC, `healys-v7-catalog-build.service` was **active** with
one controller (PID 3072297), four outer security builders, zero restarts, 415
complete securities and 1,245/1,773 sealed proposal stores. About 350 GiB of
disk remained. The four new workers were calculating signals; no new proposal
store had sealed yet. The service has `Restart=no` and now stops scheduling
new securities on its first worker failure. If it stops, inspect the failed
worker and the exact receipt before resuming; do not revert the input guard.

Root cause: the September 18 action and coverage files matched at 4,305
admitted events when originally checked. A September 21 repaired coverage
artifact was later paired in the installed service with the old action file.
That installed pair differed for 96 securities. The corrected sealed action
artifact `v7-dividends-complete-20260918` matches the repaired coverage for all
591 securities and all 4,314 admitted events. The old runner continued beyond
failed securities and systemd auto-retried, so the large receipt count hid
the configuration regression. The user's prior checks were real and passed
for the earlier pair; do not describe this as an omitted initial check.

Of 423 completed securities before recovery, 415 have exactly the same typed
actions with the corrected artifact. Their recorded source hashes still match
current files; the only added source-inventory files are the read-only audit
modules. The repaired coverage receipt was already bound in these stores.
`nn_meta/validation/v7-2-catalog-reuse-20260924.json` binds all 415 original
feature/proposal summary receipts and is verified before every runner start.
The eight changed completed securities and four partial checkpoint directories
were moved without deletion to sibling directory
`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30-superseded-20260924`.
The active output is unchanged at
`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`; 176 securities
remain to build. Never relabel the original sealed stores as new-action stores.
See `docs/reviews/2026-09-24-v7-catalog-recovery.md` for the complete proof.

The corrected runner/unit were committed and pushed in `12847c1` and `81d9e04`.
The first service invocation caught a launcher import error before any worker;
`81d9e04` fixed it. The exact service command with `--preflight-only` then
passed (591 securities, 4,314 events, 415 reused, 176 remaining). The full
suite passed 2,378 tests and 18 subtests before the restart. Observer repair
`0c11606` removes its recursive artifact-size scan, reports live service state
and resets ETA to the recovery run. One local observer snapshot completed in
under a second, reported `active`, zero restarts and 350 GiB free. A new V7
source file or code change inside the producer's broad source inventory will
invalidate future working-store identities; freeze computational sources while
this build runs. The observer script is outside that inventory.

## V6 paper state

The V6 broker-ledger projection timer from `19b9ad6` is active; the app's
broker projection was refreshed from the real paper SQLite. The separate
V6 quote-evidence repair is on pushed V6 branch
`ops/v6-quote-evidence-20260924` at `e6991f2`, deployed via Git with verified
activation and an unchanged SQLite hash. The user authorized exact-leg,
post-close, 30-second-valid observations from the minute-risk worker within
the five-minute entry window; missing evidence still blocks entries. The
isolated V6 suite passed 1,612 tests and 18 subtests.

The first live postdeployment forward pass at 19:45 UTC recorded successfully
(20 closed and four open positions, two new paper openings). The final-bar
20:00 UTC pass failed closed: AAOI, CELH, CLF and TTWO had no fresh
post-decision quote; minute-risk also lacked a qualifying observation.
`SessionCalendar.scan_open` intentionally permits the final closed-bar scan
through :03, so do not simply skip the final pass to hide this. The dashboard
can still show a latest-pass warning after the market close; investigate a
truthful last-success/failure presentation and any source-backed quote remedy.
See `docs/reviews/2026-09-24-v6-quote-evidence.md`. Main commit `de280dd`
records the timer and this limited live verdict. Do not claim full V6 quote
recovery yet.

## Other queued work

The V5 server capture backport remains on
`ops/server-alert-readiness-20260906` at `059ff1d`; finish its day's pass
census and hashes. Paper staging to home still needs an explicit boundary
decision. The incubator after-close timer remains disabled without
`--allow-execution`. V7/FA admission still awaits gates 7-2 through 7-7 and
separate isolation approval. The V7 progress timer is enabled; watch for its
hourly state report or use the lightweight `scripts/watch_v7_catalog.py`.
