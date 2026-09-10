# Heartbeat rotation false alarm repair

September 10, 2026. User pasted the 17:00 UTC heartbeat reporting v3/v4/v31
zero passes. Server logs prove successful completions around 17:18; cron entries
remain installed. All three logs had reached the previous day's 51 passes /14
RTH passes after daily copytruncate, defeating the count-decrease-only detector.

Added independent log-generation detection (device/inode + dateext rotation
suffix), compatible migration from old state and five regressions. No scanner,
model, position, cron or feed changes. Details:
docs/reviews/2026-09-10-heartbeat-rotation.md.
Focused tests 59 passed; full suite 699 passed plus 18 subtests. Deployed
a79cda1 and verified at 17:34:03 UTC: server acceptance passed and read-only
preview reports all four scanners healthy, 2–3 RTH passes each since 17:00,
zero new crashes. Baseline bytes unchanged; no notification sent. Evidence on
server: logs/ops/heartbeat-rotation-20260910T173350Z/. Verification must use build_message only, never send or
persist a replacement heartbeat unless the user explicitly requests that.

Accounting/recovery remains deployed; user chose their next sale for broker
verification. User subsequently authorized independent FA/backup coding despite
that pending sale: implemented separately at cae40a2 on
ops/fa-automation-20260910, /tmp/healys-fa-automation. Not deployed or installed.
Do not merge either runtime branch into the active source-pinned home campaign.
