# ETFE execution and outcome contract

Declared for ETFE-0.execution-contract. These rules complete the modeled ledger
semantics; ETFE-3 must implement and reconcile them. Prices and liquidity are
research assumptions, not historical broker fills. Source blockers in the
[source contract](ETFE_CONTRACT_20261003.md) remain binding.

## Candidate selection and clocks

Keep the frozen catalog's twenty families and every parameter variant. Default
DTE targets are 1/5. The inherited weekly extension is **symbol eligibility**,
not a separately defined family grid: `nn_meta/weekly_expiry.py` extends all
registered families for eligible symbols. The ETFE scope's phrase "family
eligibility" does not establish extra family restrictions. Do not inherit the
unfinished V7 entry-demand loop that applies all five targets indiscriminately.

Declare SPY/QQQ weekly targets 2/4/7 only for dated periods with exchange listing
evidence of Monday/Wednesday/Friday expirations; VOO retains 1/5 absent such
evidence. The dated eligibility table is part of R1, not inferred from future
180-day listings. Keep every strategy family in each eligible symbol/target
combination and report ineligible target combinations separately.

Use only contracts whose existence was observed on a strictly earlier trading
date, with dated identity/adjustment evidence valid at decision. Within actual
1–9 calendar DTE, sort expiries by (absolute distance to target, earlier expiry),
then select nearest raw-spot strike, tie to lower strike, then lexical contract
ID. Require strike in [0.85S,1.15S]; if absent, try the next sorted expiry.
No delta, current open interest, latest chain or future first-seen date selects a
contract. Check actual 1–9 DTE again at every purchase, including rolls.

Signal close is `t`; entry attempts are within [t+1s,t+60s], inclusive,
strictly before dated option close. Freeze the signal-close features and score.
At an attempt use the newest completed one-minute option bar known then:
availability=max(end+1s, known historical publication time if present), age
from end <=60s, finite positive VWAP, volume/count >=1, valid bar provenance.
A newer invalid bar invalidates the reference; never search backward through it.
Do not add signal latency twice. A valid reference can fill at availability even
though the reference's trades precede the modeled order. Record that modeling
assumption explicitly with separate reference and execution timestamps.

For example a 09:31 signal may execute at 09:31:01 against the 09:30 bar. If
that bar is absent, the 09:31 bar becomes available at 09:32:01, after the
09:32:00 deadline; it cannot rescue entry. Any eligible reference already
available at t+1s must still satisfy freshness and the participation budget.
Known complete but unfillable windows yield `observed_unfilled`, not a loss
label. Transport/coverage failures yield `input_unresolved` and block admission.

## Size, costs and shared capital

Research capital starts at $100,000, five shared slots, at most one position
per underlying, with SPY and VOO kept distinct and correlated in reporting.
Allocate at most 10% of contemporaneously valued total equity and available
settled cash per new position. **Whole option contracts only**; this resolves
the inherited fractional research ambiguity for physical exercise. No implicit
margin, borrow, capital injection or immediate reuse of unsettled proceeds.

At reference P and dated monetary multiplier M, unit buy debit is
M*P*(1+0.001+0.0005). Quantity is floor(min(budget/unit_debit, available
participation)). Base participation is **1% of the reference minute's traded
contract volume**, floored to integer contracts. Sum all simulated buys/sells
using the same contract/bar in a portfolio against one shared capacity; do not
multiply volume by the number of strategies or retries. Independent baseline
portfolios have their own capacity accounting. Entry accepts the available whole
quantity once; no later entry top-up. Zero quantity is `size_ineligible`.

Base sell credit is q*M*P*(1-0.001-0.0005). Record reference gross notional,
fee and slippage as separate ledger amounts; no double subtraction. Compute
in float64, round cash events to cents with decimal half-even, and reconcile
rounding residuals explicitly. The volume cap describes a conservative modeled
participation limit, not proof of executable quantity after the bar ended.

Sell up to remaining capacity; carry residual whole contracts and slot to the
next valid minute. Stop/exit intent latches until fully sold or expired. Selling
cannot reuse the same bar volume again. Mark quantities at reference VWAP without
fee/slippage; report liquidation-value sensitivity separately.

At each event time process settled cash/delivery events, marks and risk intents,
pending exits, roll eligibility, then new entries. Sort ties by original signal
time, symbol, variant ID, right and target DTE (model rank precedes that tie key
only among simultaneous entry candidates). Allocation is computed anew after
each ledger mutation. Pending exits/exercise reserve cash, shares and slots.

## Stops, missingness and expiry

Evaluate option risk at completed-minute availability clocks. The premium-stop
denominator is the **purchased leg's entry VWAP before costs**, fixed until that
leg is closed. Trigger at current VWAP <=0.875*entry_VWAP. A roll resets the
denominator for the new leg. Stop loss can exceed 12.5% after a gap or partial
exit. High/low cannot create a stop timestamp. Underlying strategy exits remain;
there is no generic 5% underlying stop. Risk and strategy intents observed at
the same clock share the next eligible execution reference without double lag.

Missing held marks never become zero or an invented interpolated price. Preserve
the last mark solely as stale audit context, mark current equity unknown and
block new entries and additional risk until all held assets have eligible marks.
Retry held marks and pending exits each minute. A later valid mark may restore
valuation; the intervening drawdown is unknown and must be reported. A missing
capture is a data failure; a fully captured quiet market is real sparse liquidity.
Do not select evaluation windows by removing those gaps.

On expiration day, the cutoff is dated **option-class close minus 15 minutes**.
Classify ITM from a fresh observed Alpaca SIP stock quote midpoint (noncrossed,
positive bid/ask/size, age <=30s), not an option trade or stale daily close.
For calls S>K; puts S<K; ATM follows the non-ITM branch. ITM latches expiry
sale intent. Non-ITM latches an OTM roll intent while the strategy remains on:
sell the old leg under the same capacity/cost rules, then select the new leg
causally. Unknown moneyness retains liability and retries, never defaults OTM.
No trade at/after dated option close; the last minute bar is not available in
time for a pre-close sale. An earlier eligible reference may still be used.

Roll purchase waits for old-sale proceeds to settle, and uses at most those net
settled proceeds, remaining cash and 10% current equity. Keep the original slot
reserved while pending. At each subsequent regular observation initiate a fresh
60-second roll attempt, with actual 1–9 DTE and a new causal contract selection.
Cancel pending roll on strategy exit; release the slot only after all settlement.
Maximum 60 completed rolls; after the 60th, sell when otherwise due and terminate
without another purchase. This is a predeclared finite research safety limit,
not an outcome-dependent censoring choice. Every failed attempt remains counted.

## Physical delivery and settlement

An unsold expiration invokes the inherited [physical policy](V7_PHYSICAL_EXPIRY_20260915.md).
Bind dated exercise-by-exception reference and rules; threshold is $0.01 ITM per
underlying share under the declared OCC rule, with no discretionary contrary
instructions or voluntary early exercise modeled. Record nonexercise as a
terminal expiry event, never a zero-price sale. Missing official exercise
reference or dated deliverable makes the outcome unresolved.

Calls reserve full strike cash, then receive the actual deliverable. Puts must
already own and reserve the required settled shares. Insufficient resources
remain unresolved; do not force a fictional sale, waive exercise or create short
stock. A proposal label's isolated account cannot establish shared-portfolio
funding. Adjusted/nonstandard contracts follow actual dated monetary multipliers,
share/cash deliverables and fractional-share cash-in-lieu rules; unidentified
terms block the affected path rather than defaulting to 100 shares.

Option premium sales settle T+1 business day throughout this research window
([OIC settlement explanation](https://prd-web.optionseducation.org/news/understanding-t-1-conversion)).
Equity exercise/delivery and stock-sale settlement use T+2 before May 28, 2024,
T+1 from that date, with the actual settlement calendar and transition exceptions
from [OCC memo 54436](https://infomemo.theocc.com/infomemos?number=54436).
Make settled funds/delivery available at 09:30 New York on the dated settlement
day as an explicit conservative research convention. Unknown calendar/reference
coverage blocks that event; today's metadata does not override historical rules.

After settled call delivery, liquidate stock at the first eligible regular-session
Alpaca SIP bid, age <=30s, one-second intent latency, positive size and noncrossed
book. Maximum quantity is the reported bid size after converting documented
provider size units to shares; retries require new quote identities. Partial
sales retain stock and slot. Stock fees/slippage use the same 0.10%/0.05% of
notional per side; exercise service charge is $0 in the research baseline,
separately stressed at $5 per exercised contract. These are modeled costs, not
broker fee history. Mark held stock at fresh stock midpoint with the same gap
guard. No short-stock path or broker early-liquidation privilege is admitted.

## Labels and final boundary

Keep an isolated $100,000 account for each proposal path, with the same 10%
allocation, integer size, costs, participation and settlement rules. Its net
cash P&L excludes unspent starting capital and counts every option/stock/fee leg.
Model targets use this path, while acceptance reruns decisions in the actual
shared ledger; standalone labels cannot supply capital to the shared account.

The terminal horizon is the latest cash settlement/delivery/liquidation event,
not the option sale date. No market observation after October 2 or artificial
October 2 liquidation is allowed. Preserve all proposals to the fixed end.
Paths still open, pending roll, unsettled or requiring later observations are
`right_censored_end`; they get no win/return target. Other missing outcomes are
`input_unresolved` or `funding_unresolved`, never silently censored as boundary.

Report every boundary path, its invested capital, known cash flow and remaining
liability. Do not treat the completed subset as an unbiased whole-window return.
Shared-ledger performance with unresolved terminal liabilities cannot pass
acceptance. Marked terminal equity is supplemental and requires fresh marks;
it cannot substitute for the specified settled terminal labels.

## Reconciliation and stress acceptance

ETFE-4.pilot and ETFE-3 require hand-worked plus real-data examples: one filled
entry, no-trade deadline, participation rejection, partial sell, fee arithmetic,
gap-through stop, same-minute priority, OTM roll, funded call, unfunded put,
competing exercise reservations, historical settlement transition, early close,
invalid/newer bar, missing stock liquidation and right-censored boundary.
Check cash/asset conservation to one cent, quantities/deliverables exactly,
and deterministic event ordering. Synthetic edge cases test mechanics only.

Run baseline plus each isolated stress and their combined conservative case:
cost multiplier 2 and 3; publication lag 5/30/60 seconds; participation 0.5%
and 0.1%; minimum bar volume 10/100 and trade count 2/5; deterministic removal
of every tenth eligible bar and every consecutive five-minute block at the
session's first/last half-hour; exercise charge $5/contract. A 60-second lag
may make a minute signal unfillable: retain that result. Known revisions use
both preserved versions; without vintage pairs report revision sensitivity
unmeasured. No invented distribution of revisions counts as measured evidence.
