# Production alert fixes and combined end-of-day panel — deployed September 6

User authorized operational repair and selected both an experimental partial-bar
view and a confirmed closed-bar recap. Changes were prepared in the isolated
worktree /tmp/healys-server-alert-readiness from deployed 9351d01, keeping the
running main/v6 campaign's causal source and inputs unchanged.

Production now tracks ops/server-alert-readiness-20260906 at a315034 (initial
patch 6d83a67). It is deliberately NOT the current research main/model contract.
Existing models, frozen specs, strategy grids, feature formulas and thresholds
were retained. Deployment verified v4/v5 bundle hashes and all existing alert
state hashes before activation. Earlier review verified finite predictions for
all 160 deployed members; this patch does not replace model/scorer code.

Full compatibility-branch regression: 545 tests and 18 subtests passed, 10
warnings. Follow-up retry/cutoff patch: 10 focused tests passed, two warnings.

## Activated

- Recent-bar rejection on serial and parallel detection results, including
  handling missing frames; retain original strategy/model semantics.
- Final close scans allowed through close+3 minutes, using an official captured
  exchange calendar for holidays and early closes.
- Complete minute buckets/current-session coverage before using the stream;
  otherwise force REST. Reconnect backfill, first-bar heartbeat evidence and
  corrected-minute-bar subscriptions.
- Durable v3/v31 send retry outbox; isolated dry-run state for normal scans.
- Bounded downloader futures, releasing completed response payloads instead of
  retaining over a million futures/results; failures stop before surface build.
- Separate combined EOD panel, using minute cron and captured session close.
  Standard session: prewarm 15:46 ET, snapshot target 15:54, panel at 15:55.
  Recap lists earlier threshold-qualified closed-bar signals, not new entry
  recommendations or proof of Telegram delivery. Provisional section labels
  partial-bar scores unvalidated and shows symbol coverage/errors/as-of time.
  Missing/stale/late previews are visible, not filled with old values. The sender
  does not wait for a complete preview and retries delivery up to three times.
  All EOD state lives in nn_meta/live/eod_preview; normal alerts, watchlists and
  ledgers are not consumed by preview scoring or recap rendering.

The preview is intentionally experimental: no historical/forward gain or
calibration on partial bars is established. Timing and full-universe coverage
need observation under actual simultaneous expert/feed load. Its resource check
can skip previews if insufficient memory; the closed-bar recap still runs.

## Production evidence and running refresh

Rollback snapshot:
/home/mrhea/HealysBacktester/logs/ops/alert-fix-20260906T222537Z/
Contains old branch/HEAD, original crontab, state copies and hashes, deployment
record. Original branch was main at 9351d01. Final deployed follow-up is a315034.

Stock stream restarted from recorded PID 339599 to 394370. At 22:25:51 UTC it
reported zero bars/actual_data_received=false/connecting, as expected for the
Sunday probe; this is NOT proof of successful market-session streaming.
OPRA remains an idle quote collector with no subscribed contracts; it is not
introduced as a new expert input.

Captured calendar has 1,004 sessions covering 2024–2027. Actual server checks:
September 7 has no session; September 8 19:46 UTC selects prewarm and 19:55 UTC
selects send. Minute cron is installed and Sunday runs log action=closed.
No synthetic trading alert or EOD test message was sent.

v5 refresh supervisor PID 394442, initial download worker PID 394443.
Durable root:
/home/mrhea/HealysBacktester/logs/ops/v5-refresh-20260906T222750Z/
Commands, per-stage logs/results, process identity and memory samples are there.
It resumes without repeating --refresh-recent-days pruning, uses eight download
workers, and starts build_surface only after download/compaction succeeds.
A sampled guard interrupts if available RAM falls below 1 GiB. Last observed:
5,000/208,684 remaining downloads completed at ~76/s, 5.6 GiB available RAM.
The surface was NOT yet rebuilt at handoff. Check result.json and surface dates
before marking the stale-v5-context finding resolved. The exact cause of the
original Killed process remains unverified.

## Remaining acceptance

- Finish and verify v5 surface refresh and coverage.
- Observe Tuesday's complete live session: current/closed bars, missing-minute
  fallback, reconnect/backfill, final-close passes and actual Telegram delivery.
- Measure combined EOD/normal-scanner memory, preview coverage, processing time
  and delivery time. Experimental scores remain separate from normal signals.
- Reconcile this compatibility branch when regenerated current-contract models
  are deployed. Do not blindly pull research main against pre-audit bundles.

Alpaca minute bars are emitted after their interval and can be revised for late
trades at the half-minute mark. Current quarter-hour cron cadence is retained;
we do not promise zero-delay alerts or feed an unfinished bar as a completed bar.
Official reference: https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data
