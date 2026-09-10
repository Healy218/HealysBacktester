# False scanner DOWN warnings after daily log rotation

User reported a 17:00 UTC heartbeat showing zero passes for v3/v4/v31 despite
fresh feeds and nonzero alert deltas. Read-only server inspection found all
scanner cron entries present, recent successful completions around 17:18 UTC,
and no new scanner tracebacks in the reported interval. No scanners restarted.

Each affected log had 51 completed passes, including 14 RTH passes, at the
17:00 heartbeat. Logs rotate via copytruncate daily at 04:07 UTC. At the same
time each day the new logs can reach the previous day's counts exactly. The
old detector recognized rotation only if at least one count decreased; equal
pass counts with equal/increasing alert counts therefore yielded zero deltas
and false DOWN warnings. v5 happened to trigger the count-decrease fallback.

The heartbeat now stores log device/inode and latest dateext rotation date
beside each expert's counters. A new rotation generation resets the interval
counts even when they have equalled or exceeded the old baseline. Compression
alone does not change the date token. Old counter-only state migrates using
the newest rotated archive's mtime relative to the last successful heartbeat.
Counter decreases remain a fallback for manual truncation without archives.
Unchanged logs with genuinely no new scans still warn. Post-rotation counts
cover the current log only, as the existing 'log rotated — counters reset'
label indicates; lost pre-rotation interval counts are not reconstructed.

The source repair is isolated on the production ops branch. It changes no
scanner settings, strategy/model inputs, alert ranking, live positions, feed
processes or cron schedules. No extra Telegram message is sent by verification,
and preview must not persist or consume heartbeat baselines.

Focused tests: 59 passed. New regressions cover equal-count copytruncate,
regrowth above baseline, compression without rotation, old-state migration,
and genuine zero-scan detection with an old archive. Full suite and deployment
verification are recorded in HANDOFF.md.
