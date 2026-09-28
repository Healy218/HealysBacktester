# V6 independent paper orders — September 28, 2026

The user approved a 120-second order timeout, buy limits at midpoint × 1.02
rounded up to cents, sell limits at midpoint × 0.98 rounded down to cents,
and independent broker-order processing. Deployed at 12:01 Central from
implementation commit `6e63358`. [Deployment receipt](2026-09-28-v6-independent-orders.json).

## Selected policy and scope

`midpoint-concession-2pct-120s-v2` is selected in the paper manifest. New orders
use the fresh bid/ask midpoint for execution, regardless of any provider mark.
Valuation, premium-stop marks, the frozen model and simulator projections retain
their existing meanings. Adjusted limits are fixed after submission; they can
cross a narrow spread but do not guarantee execution. Buy quantity uses the
adjusted limit, existing fraction limit, available option buying power and
shown ask size. Sell quantity cannot exceed the held whole contracts or bid size.

Cancellation is requested on the first broker poll at/after 120 seconds from
planning, followed by terminal-state confirmation. Legacy journaled orders
retain their original 60-second policy. No entry is blindly retried; exit slices
can resume after confirmed cancellation/fill and reconciliation. The five-minute
new-entry submission deadline is unchanged and is not an order-fill deadline.

Independent orders can be outstanding simultaneously. POSTs remain serialized
under the existing bridge lock, with reconciliation after each submission.
A pending order blocks the same contract or position, including dependent rolls
and competing closes; unrelated entries/exits proceed. Unknown broker state or
an ambiguous POST still blocks submission globally. Partial fills remain real
holdings. Pending cancellation retains both its dependency and cash reservation.

Available purchase funds are the minimum of broker option buying power and
cash less outstanding unfilled buy commitments; holds are not subtracted twice
from reported buying power. A separate per-poll budget prevents reuse of a
recent buy's money when account updates lag. No same-poll credit is assumed for
sale proceeds or cancellation releases. A 20-second processing budget defers
remaining events to later timer polls. Rejected/stale individual candidates do
not stall unrelated candidates; authentication/reconciliation failures do.

## Validation and deployment

Forty-five focused tests passed, including both old and new lifecycle variants,
120-second boundary, partial fills, pending cancellation, cancellation/fill race,
independent simultaneous orders, same-contract and roll dependencies, multiple
close sources, sizing at adjusted prices, delayed buying-power updates, rejection,
stale quotes, ambiguous POST recovery, restart and foreign-state refusal.
Systemd validation passed. Original source files remain hash-bound and unchanged.

The orders service now runs `scripts.run_v6_alpaca_runtime_v2`; the scanner stays
on its selected v3 launcher. New bridge/pricing/dispatcher sources were added to
the existing activation manifest without replacing old source hashes. The prior
manifest and service are archived beneath the paper state at
`runtime-revisions/orders-v2-20260928/`. Original activation/account, broker
journal, data snapshot and frozen model were preserved. Selected manifest SHA:
`644f5c33c3da377d44adccb28209fa9d320f5db555fbd81c253466e5e2b5df3d`.

Authenticated preflight observed zero positions/pending orders and $100,000
option buying power/cash. Preview and real service polling succeeded; the timer
remained enabled. Existing expired/superseded signals were withheld. This is
implementation/deployment verification, not an actual V2 fill or performance
verdict. Observe subsequent eligible prospective orders through live receipts.

[Current state](../CURRENT_STATE.md) · [Tasks](../../TODO.md) ·
[Earlier readiness repair](2026-09-28-v6-paper-readiness.md).
