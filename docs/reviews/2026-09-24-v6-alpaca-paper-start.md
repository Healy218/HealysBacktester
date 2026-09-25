# V6 to Alpaca paper: read-only start, September 24, 2026

## Requested scope and current result

The user wants to restart V6 against a newly added Alpaca paper account,
using the account's available options buying power as the sizing base. The
restart must use a fresh V6 state: completed simulator trades and its four
currently open positions remain archived in the old ledger and must not be
backfilled as broker orders or represented as broker fills. Keep the current
runtime operating until the new path can execute and reconcile orders; then
switch over once, without duplicate alerts or scanners.

A read-only Alpaca request with the locally configured key succeeded against
the paper endpoint. The verified credentials have been given separate
`ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_API_SECRET` aliases in the local
mode-600 `.env` (ignored by Git). No credential value appears in this report.

The new `scripts.v6_alpaca_paper_preflight` command is incapable of order
submission. It reads the active V6 portfolio via SQLite read-only mode and,
with `--account`, uses Alpaca's paper-only TradingClient to GET account,
positions, open orders and at most five listed option contracts. Its local
output is `/tmp/v6-alpaca-paper-account-preflight-20260924.json` (mode 600).
At 2026-09-25 00:27:54 UTC the account was ACTIVE, unblocked, level 3
approved and enabled for options, with $100,000 options buying power, zero
positions and zero open orders. All four current V6 contracts were listed,
active, tradable and had 100-share multipliers. The V6 portfolio held four
simulator positions, all explicitly tagged historical-only in the report.

At a $100,000 paper buying-power base, their historical entry prices imply
10 AAOI, 64 CELH, 121 CLF and 9 TTWO whole contracts for a 10% allocation
each. These figures demonstrate whole-contract conversion only. They are
**not** order quantities: prices are historical, the quote size/liquidity is
unverified for broker execution, and there are no matching broker positions.
The especially large CLF count shows why a fresh quote, liquidity cap and
broker-state check are required before any pilot order.

At 2026-09-25 00:35:32 UTC, the separate
`/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper` state was prepared
from the hash-verified frozen V6 release and current data index, using a
fresh empty-account preflight. It contains only mode-600 activation, data
index and restart-manifest files; there is no portfolio database. The
manifest binds the account fingerprint and explicitly disables scanning and
order submission. The old V6 ledger and timers continue to run. This is a
prepared restart, not a live Alpaca V6 deployment.

## Execution bridge to build next

1. Keep the existing V6 daily data-refresh timer as the input producer for
   the new state's current data pointer. Preserve the old portfolio
   byte-for-byte. The prepared manifest records the account fingerprint and
   preparation time; define an activation timestamp at cutover so no
   pre-existing V6 event can be submitted. Consume structured V6 entry/exit/roll evidence from the
   new state, with a stable client-order ID per event and an append-only
   broker attempt/response journal. Never parse notification prose as an
   order instruction.
2. Reconcile Alpaca paper positions and open orders before each action.
   Calculate integer contracts from the selected V6 size fraction and
   current options buying power and a fresh validated provider mark when
   available, otherwise the fresh bid/ask midpoint. Use that mark as the
   initial limit price, capped by displayed ask size; retain last trade as
   context and use actual Alpaca fills for broker P/L. Never substitute a
   stale last for the mark. Then
   refuse zero contracts, unsupported or nontradable contracts, stale quotes,
   missing buying power and duplicate events. Use a fresh decision-time
   limit price and record the market/quote/order timestamps separately.
3. Handle partial fills, rejections, cancellations, exits, rolls, expiry and
   exercise/assignment using broker order/position state as truth. Keep
   V6's simulated ledger unchanged and show broker fills/P&L separately in
   Stonks. A disconnected or ambiguous broker state must block new entries.
4. Run the new state and bridge in preview mode through representative
   future signals and reconcile every intended versus actual paper event.
   Only after the preview passes should order submission be explicitly
   activated and the old V6 timers retired. Keep live-account credentials
   and URLs absent from this integration.

The existing V6 pipeline was not modified, no paper order was submitted,
and V7-2 remains an independent build. Alpaca documents paper-only keys and
endpoint, whole-contract options, and order status events at:

- https://docs.alpaca.markets/us/docs/paper-trading
- https://docs.alpaca.markets/us/docs/options-trading-overview
- https://docs.alpaca.markets/us/docs/websocket-streaming
