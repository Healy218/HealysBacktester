# V6 Alpaca paper activation — September 27, 2026

The fresh V6 Alpaca paper runtime is activated for Monday September 28.
This supersedes the earlier same-day readiness audit's disabled-state finding.
Implementation commit: `f669d43`. [Safe deployment evidence](2026-09-27-v6-alpaca-activation.json).

## What is running

- Fresh state: `/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper`.
  Activated at `2026-09-27T20:46:18.846408+00:00`. Scanner and paper submission
  flags are both true. No historical positions or trades were imported.
- `healys-v6-alpaca-scanner.timer`: prospective frozen V6 scans each 15 minutes.
  Workers derive from available RAM, with the frozen scanner's 16-worker API
  ceiling, a 10 GiB hard memory limit and no swap. Daily input pointer follows
  the existing `healys-v6-data.timer` producer on every invocation.
- `healys-v6-alpaca-orders.timer`: broker polling every 15 seconds during the
  scheduled window, with the broker/calendar determining market eligibility.
  Dedicated paper keys and `TradingClient(..., paper=True)` only.
- Each real prospective order receives a preview, a second reconciliation,
  current buying-power sizing, and a fresh quote validation before submission.
  No historical replay or Sunday order is used as a substitute for a new signal.
- Read-only account monitor now reports actual runtime enablement and status.
  Incubator after-close input now follows the fresh scanner's passes and index.

Both services were started and exited successfully on Sunday. Scanner status
is `idle / outside_market_hours`, with data through September 25; broker status
is `market_closed`, next open September 28 at 09:30 New York. Measured startup
peaks were 1.58 GB scanner and 80 MB broker; this is an idle startup observation,
not a claim about the full market-hours feature-build peak.

Authenticated account monitoring confirmed ACTIVE, level 3, $100,000 options
buying power, zero positions and zero open orders. Fresh portfolio tables,
source-entry ledger and broker journal all have zero rows after startup.

## Monday schedule (Chicago)

| Time | Action |
| --- | --- |
| 04:00 | First scheduled daily context refresh |
| 08:00 | Broker polling and read-only account monitor begin |
| 08:00:05 | Scanner schedule begins; premarket checks remain idle |
| 08:30 | Regular market opens |
| 08:45 | First completed 15-minute bar can produce a new V6 decision |
| 15:30 | V5/V6 after-close incubator |

An eligible signal, valid quote and broker acceptance are required; a trade
is not promised at 08:45. The first actual paper fill remains unverified until
the market opens and a qualifying prospective signal arrives.

## Lifecycle and recovery

SQLite triggers retain every initial entry and roll entry atomically with the
fresh scanner's own transaction. All subsequent legs can be reconstructed
without parsing alert prose or reading old simulator positions. Existing model,
feature and scanner source hashes remain bound to the frozen V6 activation.
New bridge code/dependencies are hash-bound in the paper activation manifest.

Orders use durable event/attempt-derived client IDs. Intent is saved before
POST; an ambiguous response is looked up by that same ID and is never blindly
resubmitted. Pending orders are polled. After 60 seconds they are canceled;
replacement waits for confirmed terminal state. Whole-contract partial fills
remain real broker holdings. Exits can use multiple displayed-liquidity-sized
orders, with fresh reconciliation between attempts. Rolls wait for the previous
broker leg to close. A previous trade's close cannot sell a later position in
the same contract. Settled historical orders are cached in the journal instead
of re-fetching every order on every poll.

Broker premium stops use actual Alpaca average entry price and a fresh mark,
with a 12.5% premium stop. Stop instructions persist through price rebounds and
are reflected as exit instructions in the prospective simulator. Expiry exits
use the captured calendar and equity/ETF option cutoff, including eligible ETF
late closes. Actual fills remain separate from simulated midpoint projections.
Unknown positions (including unexplained exercise/assignment deliveries),
ambiguous order state and reconciliation mismatches block submission for review;
this deployment does not invent fills or automatically trade unidentified stock.
Invalid/stale market data blocks the affected order. Stale daily context blocks
new scanner passes but does not disable broker risk polling.

Alpaca's documented paper options, whole-contract order requirements and
next-day visibility of paper non-trade activities informed these checks:
[options API](https://docs.alpaca.markets/us/docs/options-trading),
[order lifecycle](https://docs.alpaca.markets/us/docs/orders-at-alpaca).

## Cutover and validation

Retired home timers: old `healys-v6-forward`, `healys-v6-option-risk`,
`healys-v6-relay`, `healys-v6-broker-ledger`, and `healys-v6-session-updates`.
The old server `healys-v6-watch.timer` is disabled. Old ledgers are preserved;
the old simulator's Stonks projection is historical, not the new account's
broker fill history. The daily data producer and account monitor remain enabled.
V5 services and V7 capture were not changed. The V7 meter remained running and
advancing after activation.

Validation: full suite 2,512 passed, one skipped, 18 subtests passed; 18 focused
paper tests passed, with the ten bridge/lifecycle tests rerun after the final
terminal-order caching change. Bash syntax and systemd verification passed.
Checked partial fill/cancel/restart, bounded exit slices, roll-close ordering,
multi-roll transaction durability, actual signal deadlines, persisted stops,
unknown positions and preventing an old close from selling a new trade.
Real authenticated closed-market startup and enabled timer checks passed.

## Operating notes

Inspect `broker-status.json`, `scanner-dispatch-status.json`, `latest-preview.json`
and `broker-orders.sqlite3` under the fresh state. Read broker journal/portfolio
with SQLite read-only connections. Do not rerun the installer to reset an active
account: it intentionally rejects a second activation or existing portfolio.

To pause new scanner decisions while retaining broker risk management:
`systemctl --user stop healys-v6-alpaca-scanner.timer`.
To stop all paper order automation, also stop the orders timer/service; any
existing broker holdings and orders then need explicit account supervision.
Never delete the journal, reset the activation timestamp, copy historical
positions, or re-enable the old simulator as part of recovery. Unit backups
are in the fresh state's `retired-units/`. These are operational procedures,
not additional work to repeat before Monday.
