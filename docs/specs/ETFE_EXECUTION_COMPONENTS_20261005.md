# Bounded ETFE option ledger — synthetic mechanics

Implements **ETFE-3.execution-components**, a supporting component of the
[full execution gate](../../ROADMAP.md#etfe-first-run-sequence). It consumes no
old project data and admits no real Alpaca path. The
[execution contract](ETFE_EXECUTION_20261003.md), amended by
[0–5 DTE rules](ETFE_0DTE_NORMALIZATION_20261004.md), remains authoritative.

## Implemented boundary

`nn_meta/etfe/execution_ledger.py` accepts explicitly synthetic fixtures only.
The fixture supplies contract identity known before the signal date, a positive
dated monetary multiplier, option sessions/expiry close and a complete mapping
from option sale dates to T+1 settlement clocks. Calendar correctness is a
fixture obligation; the component rejects nonfuture dates or clocks other than
09:30 New York, but does not infer holidays from weekdays.

At each caller-supplied observation it processes settlement, marks and risk
intents, pending exits, then deterministic entries. This is a bounded kernel,
not the full historical scheduler: callers must supply every required attempt,
minute risk observation and settlement event. Baseline order uses signal time,
symbol, variant, right, target and ID; learned ranking is not implemented.

- $100,000 initial settled cash, five slots, one position per underlying,
  integer contracts, 10% contemporaneous equity/settled-cash allocation.
- New purchases recheck actual 0–5 DTE, enabled targets, qualifying signal,
  inclusive signal+1s through +60s window, dated session and expiry cutoff.
- Newest known completed-minute VWAP only; no older-bar fallback for invalid,
  ambiguous or changed revisions. Availability is at least bar-end+1s and age
  at most 60s. Session and contract identities bound every capacity key.
- Shared floored 1% volume across buys/sells/retries; one entry fill, no top-up.
  Partial exits retain quantity and slot. Premium stop at 87.5% of entry VWAP
  latches through subsequent price recovery. Strategy exits share that clock.
- Float64 notional, 0.10% fee and 0.05% slippage separately retained. Cash events
  use decimal half-even cents and explicit rounding residuals. Sale cash is a
  receivable until the supplied settlement clock; no unsettled reuse.
- Missing current marks block valuation/new risk; last mark is audit context.
  Valid later marks restore valuation, but missing-capture/invalid-reference
  observations remain a data failure in the reported outcome. Quiet-market
  gaps with known coverage retain their own gap census.
- Missing settlement calendars retain unspendable receivables and unresolved
  outcomes. Expiry cutoff/physical/roll handling deliberately stops unresolved;
  this version neither manufactures zero-price sales nor classifies funding.

`finish_entry` requires an explicit whole-window coverage attestation. Individual
attempt coverage cannot establish a complete window. Known no-trade/size/guard
failures can be observed-unfilled; absent/invalid inputs remain unresolved.
The fixture scheduler is responsible for attempt completeness. `outcome` reports
cash and liabilities, with an explicit end-boundary projection flag. That flag
does not advance the observation clock or prove a full history was processed.
All observations at/after October 3, 2026 04:00 UTC are rejected. No labels or
training admission are produced, including for settled synthetic portfolios.

Snapshots bind the kernel, shared VWAP/DTE consumers and current scope. Restoring
against changed sources fails. The study additionally binds this specification,
runner, fixture and tests; checkpoint receipts hash bytes and audits replay each
prefix. Frozen predecessor sources and previous ETFE artifacts are untouched.

## Hand reconciliation and remaining work

The selected fixture enters 10 contracts at $2 with multiplier 100: debit
$2,003.00. A $1.70 stop reference with volume 400 sells four for $678.98.
The same bar cannot sell again. A later $2.10 reference with volume 600 sells
six for $1,258.11 despite price recovery. Cash before settlement is $97,997.00,
receivables $1,937.09; after settlement cash is $99,934.09. Net loss is $65.91.
The independent audit uses Decimal arithmetic and event quantities to reconcile
fees, cash, capacity and final balances, plus those hardcoded manual values.

Still required for **ETFE-3.execution**: admitted real examples; integrated
observation scheduler and label horizons; quote-based expiry classification;
OTM rolls and reserved slots/cash; dated exercise reference/deliverables;
funded calls, unfunded puts and competing reservations; historical equity
settlement transition; stock liquidation; full stress suite and shared-policy
baseline comparisons. This component closes none of those acceptance cases.
