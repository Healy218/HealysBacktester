# Handoff — 2026-09-24 — Alpaca paper state prepared; V7-2 building

Read `TODO.md` first. Prior handoff archived at
`handoff-history/HANDOFF-2026-09-24-before-alpaca-paper.md`. Main is the
Backtester operating branch. The worktree has extensive pre-existing dirty
files; stage exact owned changes only. V7-1 is complete, V7-2 is building,
V7-3 has not started. Preserve V7-2 source and review artifact hashes while
its workers run. Do not start a second builder.

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

At the last check V7-2 `healys-v7-catalog-build.service` was active under
PID 3128252 with zero restarts. Earlier watcher progress was 427/591
securities and 1,285/1,773 stores at 18:42 CDT; refresh for current count.
Monitor with `./venv/bin/python -m scripts.watch_v7_catalog --follow
--interval 5` in a separate terminal. Full 7-2 verification remains due
after sealing; do not advance to 7-3 before it passes. See
`docs/reviews/2026-09-24-v7-last45-repair.md`.

The Stonks V6 Paper tab already has the realized P/L timeline and dated,
newest-first trades, deployed at `https://stonks-22367.web.app/`. It is the
simulator projection, not Alpaca paper broker state. Prior details and
deployment receipts remain in the archived handoff.
