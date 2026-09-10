# Session/recovery harness and deployment preparation

September 10, 2026. User approved session/recovery tests followed by accounting
deployment and broker verification, before FA/backup work. All code remains on
ops/server-alert-readiness-20260906; the home v6 campaign is untouched.

Added synthetic full-session acceptance and a receipt-producing runner. Found
and fixed same-bar error recovery and quote-outage suppression of verified exit
warnings. Details: docs/reviews/2026-09-10-session-recovery.md.
Focused acceptance: 104 passed, /tmp/healys-session-recovery-20260910/.
Full suite: 694 passed and 18 subtests; only existing dependency warnings. Deployment: pending. Server inspected at d2708d6 with no
tracked changes; private runtime artifacts preserved. Actual broker records
have not been supplied, so real reconciliation remains pending.

First server rollout at 15:50 UTC pulled 47bb457; SQLite backup and integrity
passed and every pre-existing position field was preserved. Acceptance was
103/104: an old fallback-calendar test accidentally read the host calendar.
Test isolation repaired without production calendar changes; rerun pending.
Backup/evidence: logs/ops/accounting-deploy-20260910T155016Z/ on server.
User selected verification of their NEXT sale; no historical broker import
requested. Hold FA/backup work until that verification.
