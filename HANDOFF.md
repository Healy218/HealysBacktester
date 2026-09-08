# Production top-five alert routing — ready for deployment

**2026-09-08 (later): server operations fixes 1–8 on this branch** — see
docs/reviews/2026-09-08-server-ops-fixes.md for the findings, changes and the
deploy sequence (`scripts/configure_cron.py --run`, `scripts/run_refresh.sh v5`).
Option-stream cron lines stay disabled until `option_watch.json` fills.

September 8, 2026. User requested a global five highest-probability entry alert
limit per set of bars, plus overflow count and optional summary when replying yes.
Implementation on ops/server-alert-readiness-20260906, isolated from the running
home v6 freeze. See docs/reviews/2026-09-08-top-five-alerts.md for behavior and
validation. 550 tests +18 subtests passed. New minute cron handles dispatch and
button/yes replies. Apply scripts/configure_top_alerts.py --run after deployment;
it saves the previous cron for rollback. Existing EOD notices stay separate.
