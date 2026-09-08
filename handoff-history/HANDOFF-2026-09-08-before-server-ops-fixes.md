# Handoff — reply fix deployed; post-freeze launchers prepared

September 8, 2026. Production now 05f8a68 on isolated compatibility branch
ops/server-alert-readiness-20260906. Telegram answerCallbackQuery rejection no
longer aborts the requested summary; acknowledgements are best effort and reply
offsets progress after summary delivery. User notification floors strictly
v5 P(win)>55%, v4 P(win)>51%, applied before top-five ranking and to unsent queue
entries. Below-floor candidates excluded from remainder summaries too. Existing
expert scoring/admission and EOD flows unchanged. Full compatibility 552 tests
+18 subtests, seven focused tests on server, dispatcher/poll exited successfully.
If earlier callback is no longer queued, user can click old notice again.

Home v6 header no longer contains the word progress. Halfway launcher checkpoint
is complete. Prepared run_build_v6_local.sh (build+assemble),
run_evaluate_v6_local.sh and run_finalize_v6_local.sh via run_v6_next_stage.py.
All default to preview; build/training remain UNLAUNCHED. Sealed input SHA checked;
saved previews in preparation root post-freeze-launchers.json. Actual execution
requires successful predecessor receipts, merged freeze and dataset artifacts.
Sizing happens after freeze completion, preserving 4 GiB reserve and two physical
cores. Original fingerprint and fold/admission gates remain active. Requests 3
folds; actual eligible post-freeze fold count determined by original evaluator.
Details: docs/reviews/2026-09-08-v6-stage-launchers.md. Main 1452 tests +18 subtests.

The running freeze remains on four slots under controller 2541751. Do not change
its source snapshot or pinned causal packages. Current source changes to model
notification code exist ONLY on the production compatibility branch, not main.
See docs/reviews/2026-09-08-top-five-alerts.md for production deployment details.
