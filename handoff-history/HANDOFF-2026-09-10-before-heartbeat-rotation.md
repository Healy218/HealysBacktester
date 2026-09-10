# Accounting and recovery deployed; verify next sale

September 10, 2026. User approved task 2 before deploying actual accounting,
then selected verification of their NEXT sale before FA/backup tasks 3–4.
All changes remain on ops/server-alert-readiness-20260906. The home v6
campaign source, inputs and jobs are unchanged.

Deployed fef6542 on Hetzner. Final verification 16:08:47 UTC: all 104 server
acceptance tests passed, SQLite integrity is ok, accounting schema is present,
and monitor/dispatcher cron entries remain scheduled. Existing position fields
were compared exactly across the initial migration and remained unchanged.
No real fills were inserted and no extra Telegram messages were sent.

Server receipts and private SQLite backup:
logs/ops/accounting-deploy-20260910T155016Z/{verified.json,deployment.json,
queue-before.sqlite3,acceptance-r2/}. The first acceptance result is retained:
103/104 because an old fallback test read the production calendar. Fixed test
isolation; production calendar logic unchanged. Final accepted code is fef6542.

Local full suite: 694 passed +18 subtests. Focused acceptance: 104 passed,
including full synthetic 390-minute replay, real strategy exits, stream/REST
fallback, quiet minutes, restart/backfill, partial/final sale accounting,
failed delivery retries and reconciliation with fictional broker records.
Evidence /tmp/healys-session-recovery-20260910-r2/.

Repairs found: same-bar successful recovery now clears the prior monitor error;
quote lookup outages no longer suppress independently verified exit warnings.
Commands/accounting scope: docs/reviews/2026-09-10-trade-accounting.md.
Harness/evidence limits: docs/reviews/2026-09-10-session-recovery.md.

NEXT: use the user's next actual sale, with entry/sale quantities, premiums,
actual fees and broker fill reference, to reconcile against their confirmation.
Keep private details in server SQLite/records. Actual broker and captured live
full-session verification remain pending; synthetic tests do not establish them.
Do not start FA/backup work before the agreed broker verification checkpoint.
