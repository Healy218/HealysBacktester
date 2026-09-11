# FA schedule activated on isolated home runtime

September 10, 2026. User authorized configuring inputs and activating schedules.
Durable runtime `/home/healy/Coding/HealysAutomation` is deployed through git
from `ops/fa-automation-20260910`; development checkout remains
`/tmp/healys-fa-automation`. Do not merge its FA source into the main checkout
while the v6 campaign pins source. Do not transplant only scheduling code into
the older live-production FA branch.

Seven user timers are enabled: archive sync, StockTwits collect/push, daily
Alpaca SIP prices, monthly prospective freeze, daily tracking, weekly backup,
and hourly receipt/capture health. First archive/StockTwits/prices/tracker
services passed. All 120 price symbols validated; StockTwits added 90 rows.
First prospective freeze is October 1 UTC, no historical cohort manufactured.
See docs/reviews/2026-09-10-fa-activation.md for inputs, schedules, backup scope
and verification evidence. Initial 7.2 GB packed backup upload is running;
full backup verification is pending, not complete. An existing SPY object
restore passed. The new packed snapshot automatically restores a shard before
publishing its manifest; `healys-fa-activation-check.service` is queued to run
health afterward. Check `logs/job-health/{cache-backup,backup-restore,fa-activation-check}`
in the durable runtime for completion. Archive and StockTwits timers have
already fired automatically and succeeded. No further manual start is needed.

Prior implementation contracts are in docs/reviews/2026-09-10-fa-automation.md.
Live-accounting and heartbeat fixes remain on the independent production ops
branch. The user's PTON sale remains pending; FA scheduling does not depend on
that sale and does not place trades.


## September 10 Chicago — FA enrichment deployed and scheduled

User authorized steps 1–4: provider news; fundamentals/events/positioning;
immutable features; bounded baseline comparison. Source `94ba6b2` is deployed
on the same isolated runtime. Four additional user timers are enabled (11 FA
and ops timers total); first capture, snapshot, evaluation and health passed
September 11 03:45 UTC. See docs/reviews/2026-09-10-fa-enrichment.md for source
contracts, exact coverage, artifact paths, schedules and validation.

Current coverage: 300/300 short interest and short volume, 232 financials,
228 float. First snapshot has 3,800 unique news stories, sentiment for 215,
and technical features for the existing 120 price symbols. HTTP 429 throttling
and date-only pagination omissions were fixed before publishing the snapshot.
New snapshots are experimental; official ranking/production weights unchanged.
Evaluation reports awaiting-forward-outcomes, with no fabricated performance.
End-of-month review can inspect the collected data, but 40 training plus 10
test sessions need more forward history. No new subscriptions or keys needed.

Correction to the earlier backup paragraph: the packed backup and restore
finished September 10 20:06:44 UTC, dependent health passed 20:06:46 UTC.
Full suite passed 1,498 tests +18 subtests; final 29 focused tests passed after
provider pagination/schema corrections. Main remains documentation-only.
