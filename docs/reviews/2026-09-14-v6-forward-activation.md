# V6 forward paper activation, September 14, 2026

The user authorized experimental paper alerts with expiry rolls triggered 15
minutes before the option's final regular-session close. Model weights, entry
selection, fractional sizing and underlying strategy exits remain frozen.

The frozen 40-member GBT release is `v6-cash-repair-20260913`, with 164 features
and 449 symbols. Release SHA256:
`3bc974679fff04044002f833cbb4c9246f63fd4d9370c04985f5f6ca7597764f`.
Model SHA256:
`cdacbea1bf6a07e573af46b8d266b1d82b5e3bf736945a06b929e46050fdbd6c`.

## Execution convention

Expiry uses the last covered exchange session on or before OCC expiry.
Ordinary equity options trigger at 15:45 Eastern, or 12:45 on an early close.
The eligible ETF/ETN classes, including SPY and QQQ, trigger at 16:00 Eastern,
or 13:00 on an early close, because their regular option session closes 15
minutes after the underlying equity session. These are trigger times; actual
quote receipt and paper execution time are recorded separately. Extended
sessions do not extend this regular-session convention. V6 excludes index
options, whose settlement schedules require separate treatment.

Sources checked September 14:
- https://www.nasdaqtrader.com/Trader.aspx?id=optionshours
- https://www.nyse.com/trade/hours-calendars

Paper entries mark the current ask; sales mark the current bid, plus the
frozen 0.15% modeled cost per side. Quotes require positive two-sided prices
and sizes, a SIP observation after the trigger, and age no greater than 30
seconds. No completed historical aggregate is represented as an executable
live fill. There are no broker orders.

Frozen policy: EV threshold .05, no drawdown brake, five positions, one per
symbol, 10% allocation cap, EV-weighted sizing and the original target-DTE
universe. Selected but unfillable entries remain unfilled; lower-ranked
candidates do not replace them. All entries must finish within five minutes
of signal close. The 5% underlying stop and original strategy signals remain
in force. Rolls retain original strategy and target DTE; a closed option leg
is persisted before attempting its replacement, with a 60-roll cap.

## Data and verification

Full original adjusted technical histories and raw price histories were
extended through September 11. The completed data manifest is
`d94a7e6595a4c634be059131a28d92da7fd976006eb4416a0f7ed8d437511969`.
Prior-session surface and beta context were rebuilt with the original rules.
Twelve adjusted histories required full restatement; the original history
origins were preserved. Five frozen names have no current intraday bars:
SATS, SAVA, SWTX, WBA and X. They remain in every universe inventory, with
explicit absence evidence. A missing current bar on a held symbol blocks
normal new allocation.

The forward feature path rebuilt three actual saved training cases from
original stock inputs and captured MASSIVE quote/trade bytes. All 164 features
matched exactly; prediction differences were at most floating-point rounding
(1.11e-16). Accelerated recurrences, sparse requested footprint/HTF observations
and complete original histories were independently compared against the
original implementations. External TradingView/Pine parity remains deferred.

A complete Friday-close replay made fresh MASSIVE REST requests and produced
888 candidate rows from 174 fresh signals, with zero errors, in 261.667 seconds
on the home host with 16 workers. This measures an observed complete pass,
not a guarantee that every future pass meets its deadline. Late passes fail
closed. The replay is retrospective, not a new holdout or a live paper trade.
The September 14 premarket adjusted/raw stock query and price-vintage check
passed in 4.91 seconds. Live option access is checked separately and before
every actual allocation.

177 runtime tests and 59 bridge/legacy dispatcher tests passed; 12 subsequent
expiry/operating checks passed after applying class-specific closing times.
Ten bridge/legacy dispatcher tests also passed on the server. Evidence is in
`nn_meta/validation/v6-forward-20260914/`; the deployment activation receipt
binds the evidence files and the installed runtime hashes.

## Operation

Calculations and the persistent paper portfolio run in the permanent home Git
checkout `/home/healy/Coding/HealysV6`, using the existing main venv and keys.
The server's separate `/home/mrhea/HealysV6` checkout receives generated state
and immutable paper-event files. Production `/home/mrhea/HealysBacktester`
delivers those events through its existing minute dispatcher and notifier.
V6 reports already allocated paper positions alongside the older experts;
it does not alter their four-expert top-five ranking or completion timing.

Home timers: `healys-v6-forward`, `healys-v6-relay`, `healys-v6-data`.
Quarter-hour decisions begin five seconds after close (updated at 16:04 UTC). Daily data refreshes run
at 09:00, 11:00 and 12:00 UTC, with an atomic pointer published only after a
complete verified dataset. The relay retries every minute and preserves
immutable events. Persistent event keys prevent normal retry duplicates;
notification delivery retains the existing provider's at-least-once limitation.

Server timer: `healys-v6-watch`, replacing the old observer that waited for
an unimplemented snapshot producer. It checks current result deadlines and
pending alert delivery, including the final bar after the stock close.
Operating-failure notifications are deduplicated to at most hourly. This is
separate from the completed-training watcher, whose Telegram setting stays off.

No synthetic test alert was sent. Real V6 paper events are authorized once
activation passes; actual market access, timing and quote checks still apply.
No new training or separate short-DTE experiment was started.

Installation receipts and completed deployment verification are recorded in
the current HANDOFF. Final runtime commit is `d6660af`; production bridge is
`093c117`. Home activation passed at 16:04:10 UTC on September 14. The existing dashboard is
https://stonks-22367.web.app; its publisher has not yet been extended to show
the new forward portfolio.

## First live observations

The scheduled 13:45:20 UTC opening pass passed current option quote/trade
access. It generated 920 proposals and took 379.983 seconds; the five-minute
guard rejected allocation and opened no positions. Subsequent passes completed
within the deadline. By 15:05 UTC the portfolio had six entries, one frozen
strategy exit and five open positions. Seven paper-event files were relayed
to the server. Source evidence is `live-verification.json` under the validation
directory. `server-final.json` confirms all seven notices were sent, zero
were pending, and the watcher was healthy. Nine allocation cycles had completed
by the 16:00 pass, still with five open positions and one closed.


## Final performance verification and context handoff

Exact reuse of eight unchanged indicator calculations is scoped to one symbol
and returns detached outputs. The key includes numerical inputs, index and
attributes rather than pandas internal storage. Timestamp normalization keeps
proposal and feature calls equivalent. Captured adjusted/raw stock panels are
retained with hashes for exact replay. When all five slots remain occupied
after causal exits, candidate work is skipped because no allocation is possible.

A saved opening-query replay produced 4,722 candidates from 921 proposals in
275.047 seconds with zero errors. All 164 features, both predictions and the
entire parquet are byte-identical before/after this optimization (SHA256
`34df662507143333fe7d4b3412046e3820c68c21e40a4e27fa2923b60b72efdf`).
This saved retrospective query differs by one proposal from the first actual
live pass; no equality claim is made across those different API vintages.
The final activation binds 177 runtime + 59 bridge/legacy + 110 focused passing
test executions, 346 total with overlapping coverage, plus this parity evidence.
Runtime hashes include numerical sources, signals, activation and installer.

The home checkout and server V6 checkout received `d6660af` through Git. The
home timer now starts at +5 seconds while the existing five-minute entry
cutoff remains unchanged. The 16:00 pass completed before this update in
219.226 seconds with no errors; the first scheduled updated pass is 16:15:05.
An observed replay duration does not guarantee future load or network latency.

The user requested a full notes update before clearing chat and returning for
separate <10-DTE V6 training. That new campaign has not started. Its spec
requires actual expiry of 1–9 calendar days and separate artifacts; the current
broad-DTE model and paper portfolio stay frozen. See
[the next-run spec](../specs/V6_SHORT_DTE_EXPERIMENT.md).
