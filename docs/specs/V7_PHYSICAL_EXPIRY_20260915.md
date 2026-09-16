# V7 funded physical exercise and stock delivery

User-selected research policy, September 15, 2026. Supersedes the earlier
unresolved-only expiry choice. **Declared, not yet implemented or validated.**
The original frozen evaluation and historical pilots remain unchanged.

## Required behavior

Continue attempting eligible observed option exits under the declared hours,
latency and costs. An unsold expiration proceeds to an evidence-bound exercise
decision. It must never be represented as a synthetic sale at intrinsic value.

1. Verify the dated option identity, strike, deliverable, expiration and
   exercise rules. Corporate-action-adjusted and merger contracts require
   their actual deliverables; a generic 100-share assumption is insufficient.
2. Determine exercise eligibility from the appropriate official expiration
   reference and declared instructions. The OCC clearing-member threshold is
   $0.01 in the money; broker instructions may differ. Declare the research
   rule and preserve its evidence instead of assuming every no-bid option is
   exercised. Out-of-the-money nonexercise needs verified reference evidence
   and an explicit terminal expiration event, not a fabricated zero-price fill.
3. Check resources in the shared portfolio at the event time, after pending
   commitments. A call consumes strike cash and receives shares. A put delivers
   shares and receives strike cash. Future liquidation proceeds cannot fund an
   earlier exercise. A put lacking shares remains unresolved unless a separately
   specified, evidence-backed borrow/margin path is implemented; do not create
   a free short-stock position. Reserve resources to prevent simultaneous
   exercises or option entries from spending them twice.
4. Record exercise, stock delivery, receivables/payables and settlement as
   distinct ledger events. Apply the historical settlement calendar, including
   the T+2 to T+1 transition on May 28, 2024. Broker-specific early liquidation
   eligibility must be explicit; absent such evidence, require settled delivery.
5. Liquidate received long shares at an eligible observed Alpaca stock bid;
   any supported short-stock cover requires an observed ask. Bind the raw quote
   captures, security identity, timestamps, session, latency, size and costs.
   Underlying minute closes or option quotes are not stock execution evidence.
   Specify stock/exercise fees, slippage and any borrowing costs before admission.
6. Keep the position, funding commitments and portfolio slot until all required
   stock legs finish. Mark held shares from causal stock quotes. Carry stale
   marks as explicit valuation gaps and preserve the entry-blocking safeguard.
7. Extend label horizons and fold purging through actual stock liquidation and
   cash settlement availability. Reconcile the full option/stock cash ledger;
   injected exercise capital cannot become strategy profit. Standalone proposal
   labels cannot substitute hypothetical capital for shared-portfolio funding.

Existing fractional-paper sizing requires explicit treatment in the new engine:
retain a clearly declared pro-rata research convention or reject unsupported
quantities. Do not imply that fractional option contracts can be physically
exercised at a broker. No sizing change has been implemented by this declaration.

Missing funding, shares, dated metadata, exercise reference, settlement evidence
or eligible stock liquidation prices leaves the affected outcome unresolved and
blocks evaluation admission. Missing outcomes must not be silently dropped.

## Implementation and admission checklist

- Exercise/stock ledger and shared funding/inventory reservations.
- Dated exercise references and settlement calendars; corporate-action routing.
- Alpaca stock quote capture/verification and observed liquidation/mark adapter.
- Tests for calls, puts, insufficient resources, competing reservations, missing
  quotes, settlement transition/holidays, fractional policy and complete cash P&L.
- Replay both the fixed SPY call and representative funded stock-delivery paths.
- Bind the new evaluation amendment, policy and source/data hashes in launchers.
- Pass complete-universe admission before freeze/build/training.

## Primary sources checked

[OCC equity-option specifications](https://www.theocc.com/clearance-and-settlement/clearing/equity-options-product-specifications)
describe physical share delivery and standard deliverables.
[OIC exercise FAQ](https://www.optionseducation.org/referencelibrary/faq/options-exercise)
explains exercise-by-exception, funding and broker-dependent stock-sale timing.
[OCC settlement conversion memo 54436](https://infomemo.theocc.com/infomemos?number=54436)
dates the T+2/T+1 transition.
[Alpaca options overview](https://docs.alpaca.markets/us/docs/options-trading-overview)
describes the buying-power check for calls and available-share check for puts.
Current broker documentation is context, not proof of a historical broker policy.
