# Training dashboard — September 12, 2026

The Training library is implemented on the isolated Firebase dashboard line.
The private app is https://stonks-22367.web.app (project stonks-22367, Spark).
The user requested all historical training summaries plus the completed v6
summary on the dashboard only, without Telegram delivery.

Training has Compare and individual V2, V3, V3.1, V4, V5 and V6 views. Original
source text, hashes, explanatory notes, fold tables, diagnostics and Markdown
downloads are private home-payload data; no reports enter the public bundle.
V2–V5 are explicitly pre-audit history. V4's missing original reports are
represented by preserved documentation with missing dates/metrics left unknown.

The home environment now pins TRAINING_ROOT to the primary research checkout
and TRAINING_CAMPAIGN to v6-train-20260912r2. PROGRESS_RECEIPT points to that
campaign too. The existing publisher timer refreshes Training and Research
from the same live observation and automatically appends the final validation
table and gate log when completion receipts and hashes agree. No new schedule
or notification service is required. No model deployment is performed.

Validation: 16 Python publisher tests; 7 frontend unit tests; 8 desktop/phone
browser checks; 2 Firebase-emulator authentication checks covering training
access and revocation; production build and private-evidence bundle scan.
Review: docs/reviews/2026-09-12-training-dashboard.md.

The primary v6 campaign remains source-pinned and separate. Its watcher was
fixed on main to recognize the training supervisor/seed jobs and installed
with the explicit current campaign, without --telegram. The old build's
failed assembly remains preserved. Main's full suite passed 1,472 tests and
18 subtests. Current training/service evidence is in the primary HANDOFF.

Prior dashboard setup, Firebase login, owner verification and deployment notes
are preserved in handoff-history/HANDOFF-2026-09-12-before-training-dashboard.md
and dashboard/README.md. Do not print publisher credentials or embed captures
in the frontend. The standalone iOS branch still needs Mac/device acceptance.
