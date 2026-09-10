# FA monthly and operational health automation coded

September 10, 2026. User explicitly authorized continuing coding while the
next-sale broker check remains pending, superseding the earlier sequencing
pause. New work is on ops/fa-automation-20260910 in /tmp/healys-fa-automation,
based on corrected main 22ea559. FA is fingerprinted by the active campaign;
neither primary main nor the isolated live-production branch was modified.

Implemented prospective monthly snapshots and safe retries, publication-based
forward measurement with frozen baseline/local price inputs, monthly/daily
systemd templates, per-source collector receipts, scheduled-job lock/timeout
receipts, freshness checks and bounded backup sample restoration tooling.
See docs/reviews/2026-09-10-fa-automation.md for exact contracts and commands.

Full suite passed 1,469 tests and 18 subtests. Final focused run passed
17 tests after a Markdown publication-label fix and child-process timeout
regression test. systemd-analyze verify and git diff --check passed. Preview correctly reports
September 10 outside the August freeze window. No real cohort was created,
collectors run, provider calls made, schedules installed, cloud files changed,
or live backup restored. Health preview on this clean checkout correctly
reports missing receipts/captures; that is not an audit of the installed host.

Next: review/activate the automation after choosing a compatible deployment
location and configuring archive ownership + daily prices. Normal next freeze
is October 1 (September captures). Existing live accounting remains separately
deployed on the ops branch; reconcile the user's next sale when supplied.
