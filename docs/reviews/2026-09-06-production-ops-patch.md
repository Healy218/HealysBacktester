# Production compatibility patch and end-of-day panel

Based on deployed 9351d01, isolated from the active main/v6 campaign.
No model files, frozen specs, feature formulas, strategy grids or gate settings
are replaced. Full regression: 545 tests and 18 subtests passed (10 warnings).

Changes: current-bar freshness rejection; final-close passes through C+3m;
captured exchange calendar (holidays/early closes); complete minute aggregation
and REST fallback for missing stream coverage; first-received-bar heartbeat,
reconnect backfill, and corrected-bar subscriptions; durable legacy outbox;
isolated preview state; bounded downloader futures and failure propagation.
The downloader fix addresses a concrete unbounded memory retention issue;
the original process's kill cause is not confirmed.

The EOD panel has separate state under nn_meta/live/eod_preview. Confirmed
recap means threshold-qualified earlier closed-bar signals, not confirmed
Telegram delivery or a current entry recommendation. Experimental rows are
unvalidated model scores on unfinished bars and can disappear before close.
Only elapsed minute observations enter each preview. Missing minutes refuse
that symbol; missing/late experts are explicitly reported. Normal alert/digest
state and paper ledgers are not consumed or updated.

`python -m scripts.eod_panel_tick --run` from minute cron uses the captured
session close. Workers prewarm from close minus 14 minutes; snapshot target is
close minus six minutes; delivery occurs at close minus five minutes. E.g.,
normal session: 15:46 prewarm, approximately 15:54 snapshot, 15:55 panel, New York.
The snapshot capture-finish timestamp is reported. Its data window is distinct
from delivery time. The sender never waits for preview completion. A resource
check can omit previews while still sending the recap. Full-universe preview
coverage and coexisting scan memory/latency must be measured in a live session.

This does NOT change normal quarter-hour scan cadence. Minute bars arrive only
after their minute closes and may be corrected later. Faster finalized normal
alerts require measured receipt/processing latency, not treating an incomplete
bar as final. The OPRA stream is not turned into an expert input by this patch.

Deployment: fetch the explicit ops/server-alert-readiness-20260906 branch,
preserve production HEAD/branch/crontab and operational state first, switch to
the reviewed revision, capture `nn_meta/live/exchange_calendar.json` using
`scripts.capture_live_calendar`, then verify model hashes and synthetic scoring.
Restart only the recorded stock stream PID to load corrections. Add one minute
cron invoking scripts.eod_panel_tick --run, logging to logs/eod_panel.log.
No synthetic signal or test Telegram message is needed for deployment.

Resume the v5 refresh WITHOUT --refresh-recent-days: the failed Sunday job
already pruned recent entries; repeat pruning would redownload completed work.
Use --bars-and-surface-only to reuse the completed manifest, then build_surface
only after successful download/compaction. Observe memory and durable exit codes.

Rollback: restore the saved branch/commit and crontab, restart the recorded new
stock stream PID using the restored source. Retain all state and new captures.
Rollback cannot retract delivered messages. Do not pull all of main onto old
models; this temporary compatibility branch must be reconciled at the later
coordinated source/model deployment.
