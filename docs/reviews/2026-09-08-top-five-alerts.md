# Top-five entry notifications and optional remainder summary

User requested only five highest-probability alerts during bursts, followed by a
count of remaining alerts and a yes/button action to view the remainder.

Production compatibility branch only; home research sources must not change.
Four expert sources (v3, v31, v4, v5) enqueue qualifying entry notifications into
one SQLite queue keyed by their 15-minute scan cycle. Ranking uses each model's
reported P(win), descending, with stable key tie breaking. Existing thresholds,
scoring, paper ledgers and watchlists remain in place. This compares model scores;
it does not recalibrate them or establish a new probability guarantee.

Dispatcher waits for all four expert completion markers, with a maximum wait of
five minutes from first arrival and a deadline twelve minutes after cycle close.
It sends at most five distinct selected entries per cycle. Late arrivals are
retained for inspection and cannot create a second burst; entries/retries older
than the next quarter hour expire. Rankings cover candidates received by cutoff.
Original outboxes acknowledge only after durable shared-queue acceptance.
Unrankable legacy entries remain in original outboxes. Deployment check found no
pending entries in the existing production outboxes.

For overflow, one extra note identifies the set of bars and remaining count.
Telegram button callbacks bind both batch ID and notice message ID. A yes reply
to the note selects that batch; standalone yes selects the latest notice within
24 hours. Only the configured chat is accepted. Summaries list expert, symbol,
strategy, call/put, DTE and probability, sorted descending; long summaries split
into compact messages. Reply offsets and sent chunks persist across restarts.
As with existing transport, an interrupted send before acknowledgement can replay.
Normal EOD recap/watchlist/heartbeat notifications are separate from entry limits.

Enable with scripts/configure_top_alerts.py --run on production after deployment;
cron is backed up before updating. NN_META_ALERT_TOP_N=5 activates entry routing.
The minute dispatcher also polls replies; no persistent heavyweight model process
is added. Telegram getWebhookInfo was checked: no webhook is configured.

Validation: 550 compatibility tests and 18 subtests passed before cron helper.
Focused tests cover cross-expert 100-to-5 ranking, no suppressed replays, retries,
missing-expert deadlines, stale expiry, notice/button/yes routing, wrong chats,
duplicate updates and summary length. No fabricated trading alert was sent.
