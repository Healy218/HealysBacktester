# Production data and alert review — September 6, 2026

Read-only SSH review beginning 21:45 UTC. Server ubuntu-8gb-hel1-2,
62.238.20.66, checkout /home/mrhea/HealysBacktester. Deployed HEAD remains
9351d01ee487299ae208393cfad021da0330950b. Main's subsequent audit repairs
and expanded v6 are not deployed. Local v6 research jobs were untouched.

## Conclusion

Scheduling, Telegram transport and authenticated SIP REST access work.
An end-to-end alert-readiness all-clear is NOT supported: Friday's scans had
widespread data failures; v5's Sunday refresh was killed; deployed source lacks
current freshness, final-close and legacy delivery protections. Weekend checks
cannot establish live-session freshness, coverage or full signal parity.

## Observed schedules and expert decisions

All times below are minute-of-hour, every hour, with a code-level RTH gate.
- v3: :03/:18/:33/:48, one detector worker, 55 frozen symbols,
  40 neural-network members, live probability threshold 0.60.
- v31: :02/:17/:32/:47, two detector workers, 118 frozen symbols,
  40 neural-network members, live probability threshold 0.55.
- v4: :02/:17/:32/:47, two detector workers, same 118-symbol frozen spec,
  40 GBT members, EV threshold 0.05.
- v5: :01/:16/:31/:46, three detector workers, 441 frozen symbols,
  40 neural-network members, EV threshold 0.05.

v3/v31 detect the frozen best strategy at its frozen DTE, build technical,
option-provider and surface/context features, average member probabilities,
and apply the threshold. Their ensemble configs say rank, but deployed live
scoring is a per-signal probability filter, not portfolio ranking.

v4/v5 detect configured frozen family signals, expand DTE candidates, construct
features, score win probability and EV, keep the best DTE per symbol/strategy,
and threshold EV. Eligibility flags belong to the pre-audit bundles and do not
establish a corrected performance verdict. Alerts suggest approximate ATM and
DTE, not an executable quote-verified order. All four seats are alerts only.

The deployed v4/v5 outbox enqueues before marking the signal and acknowledges
successful sends. Current outboxes contain 36 and six acknowledged entries,
respectively, with no pending entries. An acknowledgement alone does not prove
Telegram delivery because console/dry-run notifiers also return success.
The deployed v3/v31 path persists dedupe before sending and ignores notifier
failure, so a failed send can lose that signal. No alert-state files were edited.

## Data receipt and refresh

Stock stream PID 339599: 443 subscriptions, ~245 MiB RSS. SIP 1-minute bars
are stored by symbol/day and resampled to 15 minutes. It backfills the current
date at startup. Its heartbeat remains September 5 23:37 UTC, zero bars,
`connecting`. In this version heartbeat updates occur only every 50 received
bars; the weekend observation does not establish that the process is dead or
that it is connected successfully.

The deployed bar loader uses cached history through yesterday and streamed
today bars when heartbeat age is <=3 minutes, otherwise forced current-day REST.
A direct, authenticated SIP REST request for SPY/AAPL on September 4 returned
HTTP 200 and 27 bars each from 13:30 through 20:00 UTC inclusive. This confirms
current credentials/data access; it is not an all-symbol live-session test.

Option stream PID 336389: ~232 MiB RSS, current heartbeat, zero contracts and
quotes. No option watch file was observed. The deployed expert/provider source
has no QuoteStore consumption or watch registration; OPRA collection is not
currently driving these expert decisions.

Both feed processes have reboot cron entries and five-minute process-existence
watchdogs. Watchdogs do not detect a live but stalled connection.

Sunday universe refreshes completed for v3/v31/v5. v3 and v31 surface refreshes
completed with maximum date September 4. v5 refresh stopped at about
1,107,500/1,316,184 contract tasks with literal `Killed`; no refresh process was
running at inspection. Cause of kill is unverified. Its surface still ends
August 24, although its underlying daily table now ends September 4.

## Delivery and readiness evidence

- All four cron logs were updating and exiting outside RTH on Sunday.
- Server Telegram notifier logged successful Scanner heartbeat delivery
  September 6 at 17:00:26 UTC. No test message was sent during this review.
- Latest actual send records in expert cron logs: v3 September 3 13:32 UTC;
  v31 September 2 13:33 UTC; v4 September 3 13:34 UTC. v5 cron has no recorded
  live-session delivery yet (deployed over the weekend).
- September 4/5 dated logs contain thousands of data/scan errors and Alpaca
  401 evidence. The final Friday v4 health snapshot recorded zero scanned and
  118 errors. Today's working REST credentials do not retrospectively make
  those passes healthy.
- v4 and v5 passed deployed strict bundle/hash/eligibility loading plus finite
  synthetic probability and EV scoring with every member (40 each). Tests ran
  sequentially with numerical thread limits, not a scan, and sent no alerts.

- v3 and v31 also loaded and produced finite synthetic predictions for all
  40 members each, using their deployed prediction path. This establishes
  loadability, not live feature/contract parity or delivery reliability.

## Source-level gaps in deployed 9351d01

1. `closed_bars` removes forming bars but neither serial nor parallel detection
   enforces a recent-bar age. If today's fetch fails but cached history exists,
   the loader can return old bars; last-available-bar detection alone does not
   establish freshness. It also raises on None in `closed_bars`.
2. `is_rth` stops strictly before 16:00 New York. Staggered passes at 16:01,
   16:02 and 16:03 are skipped, omitting the final 15-minute bar. Its weekday/
   clock gate also has no exchange holiday or early-close calendar.
3. v3/v31 dedupe-before-send has no durable retry outbox.
4. The stream heartbeat/process checks do not verify complete current-session
   coverage. OPRA running with no subscriptions is not evidence of option data.
5. v5's surface refresh is incomplete, leaving older option context.

Relevant deployed sources reviewed with `git show 9351d01:<path>`:
`nn_meta/live/{run_live,scanner,parallel,v4_scan,v4_candidates,scorer,notifier,state,heartbeat}.py`,
`nn_meta/live/feeds/{stock_stream,option_stream,quotestore}.py`,
`nn_meta/{config,providers,v4_loader,select_meta}.py`.

## Follow-up boundary

Repair/complete the v5 refresh with measured server memory, prepare compatible
production fixes for freshness/close/delivery, and validate a complete market
session against REST and actual signal/delivery timestamps. Do not pull all of
main blindly: current corrected loaders can reject these pre-audit models.
No source deployment, cron change, feed restart, refresh restart, trade, alert,
digest, or alert-state mutation was performed by this review.
