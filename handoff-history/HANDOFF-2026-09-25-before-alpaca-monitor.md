# Handoff — 2026-09-25 — V5/V6 incubator nightly replay active

Read `TODO.md` first. Prior handoff archived at
`handoff-history/HANDOFF-2026-09-25-before-incubator-activation.md`. Main is the
Backtester operating branch. The worktree has extensive pre-existing dirty
files; stage exact owned changes only. V7-1 is complete, V7-2 is building,
V7-3 has not started. Preserve V7-2 source and review artifact hashes while
its workers run. Do not start a second builder.

## V5/V6 incubator activation

The user clarified that nightly updates mean running the existing frozen V5
and V6 bundles on each new market day's genuine candidates and saving dated
predictions. It does **not** mean retraining model weights. V7 remains out of
the active registry until built and validated. The September 24 V5 server day
was copied to home: 26 complete calendar bars, 8,190 rows, all manifests and
Parquet hashes verified. Eight V6 passes supplied 5,085 rows. Both direct and
installed isolated-service replays succeeded: two complete receipts, zero
blocked/failed inputs, 8,190 V5 and 5,085 V6 pending-outcome predictions.
The dated installed receipt is
`incubator/runs/after-close/close-20260924/after-close-summary.json`.

`healys-ai-incubator-after-close.timer` is enabled and next fires Friday,
September 25 at 15:30 CDT / 16:30 ET. Its required V5 staging service copies
the closed day from Hetzner and checks complete calendar bars before the
network-isolated, CPU/memory-bounded replay. Late starts select the last fully
closed covered market session. A temporary September 24 date override used for
the installed test was removed before enabling the timer. Confirm the first
scheduled September 25 result and V7 coexistence; failure should leave
source bundles untouched. Pending outcomes mean no performance verdict.
Review and rollback: `docs/reviews/2026-09-25-incubator-nightly-activation.md`.

## Massive billing decision due October 2

The user can decide whether to keep Massive Options Advanced through
**2026-10-02** and accepts one additional month if replacement evidence is
incomplete. Prepare a recommendation before that date; do not cancel the
subscription automatically. V6's frozen option features still use Massive
tick data, and V7's March 2022–early 2024 option history is outside Alpaca's
published February 2024+ coverage. A read-only Alpaca OPRA snapshot probe
with the existing paper credentials returned SPX and NDX example contracts
with latest quotes and trades. This proves current access, not full V8
historical coverage. V8's planned last-two-year SPX/NDX artifact can be
designed around Alpaca OPRA after exact window and feature checks; Alpaca
does not provide underlying index levels, and NDX broker trading is not
currently supported. By the deadline, check V7 historical capture status,
representative two-year Alpaca quote/trade coverage and a V6 provider
feature/decision comparison. If any remain open, recommend renewing Massive
once and reassessing before the following renewal. See the updated TODO and
`docs/reviews/2026-09-24-v6-alpaca-paper-start.md`.

## V6 Alpaca paper restart

The user directed a fresh V6 start in their Alpaca **paper** account, using
current options buying power for sizing. Do not backfill four open V6
simulator positions as broker trades. A valid provider mark is the entry
limit; if absent, use a fresh bid/ask midpoint. Last trade is context; actual
Alpaca fills define broker P/L. The live V6 simulator and Stonks projection
continue independently until the broker path passes preview and cutover.

Read-only Alpaca preflight succeeded with dedicated aliases in ignored
mode-600 `.env` (`ALPACA_PAPER_API_KEY`, `ALPACA_PAPER_API_SECRET`). Paper
account was active, options level 3, $100,000 options buying power, zero
positions/orders; four old V6 contracts are listed/tradable. No secret or
full account ID is in tracked files. Preflight receipt is local
`/tmp/v6-alpaca-paper-account-preflight-20260924.json`; refresh it before
future decisions. The dedicated integration uses `TradingClient(...,
paper=True)` only for GET calls so far.

The isolated state
`/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper` was prepared at
2026-09-25 00:35 UTC from the verified V6 frozen release/data index. It has
only activation, data-index and paper-restart JSON files (mode 600), no
portfolio database, scanner, orders or broker process. Its restart manifest
binds a hashed account ID and explicitly disables scanning and order
submission. The original V6 ledger was untouched. Source and evidence:
`integrations/alpaca_paper/`, `scripts/v6_alpaca_paper_preflight.py`,
`scripts/prepare_v6_alpaca_paper_state.py`, and
`docs/reviews/2026-09-24-v6-alpaca-paper-start.md`.

Next: implement structured future V6 event-to-order translation with stable
client IDs and an append-only broker journal; reconcile broker orders and
positions before actions; validate fresh mark or midpoint, displayed size,
buying power and whole contracts; handle fills, exits, rolls and expiry.
Run a prospective preview and compare expected versus observed events before
enabling paper submission. Do not parse alert prose, reuse old simulator
positions, or launch the new state via the old installer (it hardcodes the
old state). Broker P/L needs separate Stonks display.

Focused integration tests: 8 passed. Full suite: 2,392 passed, 18 subtests,
20 warnings. No Alpaca paper order was submitted.

## V7-2 and Stonks

V7-2 stopped at 05:32 UTC September 25 after `BBG00HW3TQG4` rejected its
already sealed 5-minute feature declaration: the 5-minute store had an older
input binding, while its 15/30-minute stores used the current binding. An audit
of all 549 securities with three declarations found this was the only mixed
set. The stale 5-minute directory was moved intact to
`nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30-superseded-20260924/BBG00HW3TQG4-5-stale-inputs-20260925`.
An exact controller preflight passed all 43 remaining production loaders,
verified 415 reused and 133 newly sealed securities, and found no deferred
securities. The service was restarted at 07:11 CDT September 25 under PID
3386401; it passed its own 43/43 loader preflight and began new feature work
at 07:13 CDT. At 07:13:47 CDT it was 548/591 securities and 1,647/1,773
proposal stores, with 1,648 feature stores sealed. Refresh for current count.
Monitor with `./venv/bin/python -m scripts.watch_v7_catalog --follow
--interval 5` in a separate terminal. Full 7-2 verification remains due
after sealing; do not advance to 7-3 before it passes. See
`docs/reviews/2026-09-24-v7-last45-repair.md`.

The Stonks V6 Paper tab already has the realized P/L timeline and dated,
newest-first trades, deployed at `https://stonks-22367.web.app/`. It is the
simulator projection, not Alpaca paper broker state. Prior details and
deployment receipts remain in the archived handoff.
