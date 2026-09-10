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
