# ETFE shared scheduler and horizon component

Implements **ETFE-3.integration-components** within bounded synthetic fixtures,
under the [execution contract](ETFE_EXECUTION_20261003.md) and
[0–5 DTE amendment](ETFE_0DTE_NORMALIZATION_20261004.md). Preserves the frozen
[option](ETFE_EXECUTION_COMPONENTS_20261005.md) and
[expiry](ETFE_EXPIRY_COMPONENTS_20261005.md) components and their artifacts.
The successor `nn_meta/etfe/integration_ledger.py` combines ordinary entry with
expiry/roll/delivery using one cash, participation, slot and liability ledger.
No previous project market data/metadata or model artifacts are inputs.

## Observation completeness within the fixture

The scheduler accepts an immutable, explicitly synthetic tape with an inclusive
start and exclusive end no later than October 3, 2026 04:00 UTC. It generates
signal observations, every second of the inclusive signal+1 through +60 entry
window, regular minute clocks, configured completed-bar availability, source
publication clocks, dated expiry cutoff/close, strategy exits and all calendar
cash/delivery settlement clocks, including one-second stock-liquidation latency.
It processes the final pre-end observation without inventing end liquidation.
Minute clocks come from the supplied dated stock and option sessions; activity
outside those sessions cannot produce fills. The study uses miniature synthetic
sessions, not a claim about real exchange hours or full research history.

At each clock the phase order is settlement/delivery, marks/risk/expiry intent,
option and stock exits, roll selection/purchase, then ordinary selection/entry.
Pending delivery and roll reservations constrain all new risk. All liabilities
retain their underlying slot through settlement in this conservative component.
SPY/QQQ/VOO remain distinct; five slots and at most one active path per underlying.
Selection freezes at the signal clock from the complete synthetic candidate set,
fresh SIP midpoint and dated terms; missing potentially eligible terms cannot be
misclassified as an empty chain. Purchases recheck actual 0–5 DTE, target,
session, cutoff, qualifying signal, fresh marks, settled cash and integer size.

Ordinary entry attempts are retained until filled once or classified at the
deadline. Tape coverage assertions are explicit for the entire interval; they
are not inferred from nonempty bars. Missing/invalid inputs remain unresolved.
Known complete no-trade/size/occupied-slot windows remain observed-unfilled.
Unknown capture during a held path conservatively invalidates portfolio
diagnostics even if subsequent references permit mechanical progress.

Automatic rolls preserve the prior window's inclusive deadline before opening
the next regular minute's window; no alternating-minute retry gap. They use
settled old-leg proceeds and share participation/cash with ordinary entries.
The stop denominator resets on each purchased leg. A not-yet-published official
exercise reference records a pending input reason, preserves the liability and
blocks new risk; publication can resolve that wait. It is never a zero-price
sale or inferred nonexercise. No input/model admission follows from this behavior.

## Terminal horizons and diagnostics

Every registered proposal receives an explicit status: settled, observed-unfilled,
input-unresolved, funding-unresolved, open, or right-censored at the fixed end.
The terminal horizon is the first clock with no remaining option/stock/roll/
delivery/cash liability; a stock-sale settlement can extend it beyond exercise
and liquidation. A short fixture's open path stays open; only a fully processed
tape ending at the fixed boundary may report right-censoring. Census totals
must match all proposals. Saved scheduler cursor, source and immutable tape hash
bind restart and reject a changed input, schema, source or inconsistent clock.

Known cash flows and settled synthetic P&L are diagnostic only. Every model
target is null and `training_admitted=false`. Shared-portfolio cash flows are
not isolated proposal labels. Isolated-account label generation, fold purging,
real admission and full historical build remain separate requirements. The
baseline starts with cash only; mandatory call-stock liquidation and the
single-underlying-slot rule do not establish a funded-put inventory path.
Unfunded puts remain explicit; shares/capital are never injected to create one.

## Finite stress matrix

The same six tapes run against 27 profiles: baseline; cost multipliers 2/3;
publication lags 5/30/60 seconds; participation 0.5%/0.1%; minimum volume
10/100 and count 2/5; every tenth valid-activity bar removed within each
contract/session; each of six five-minute blocks in the first and last
half-hour removed separately; $5 exercise fee; and the combined conservative
profile using all edge blocks, every tenth removal and the strongest settings.
In miniature thirty-minute sessions first/last half-hours overlap intentionally;
this is mechanics coverage, not independent real-market stress observations.

Availability=max(bar-end+configured lag, supplied publication clock). Size
thresholds inspect the newest reference without searching backward. Costs apply
to both option and stock sides, and to ordinary/roll sizing. Removal ranks are
fixed by chronological input contract/session bars, not by realized outcomes.
Known revision pairs are not present; revision sensitivity stays unmeasured.

The [six fixtures](ETFE_INTEGRATION_FIXTURES_20261005.json) cover ordinary
round-trip, mixed symbols, funded call/stock settlement, roll, unfunded put and
fixed-end unsettled proceeds. Baseline cents/census are hand declared. The
independent audit replays saved outputs and checks Decimal costs/rounding,
cash/share/quantity conservation, participation, reservations and census/null
targets across all 162 case/profile combinations. Full real stress acceptance,
resource-scale scheduling, capture integration and scientific labels remain open.
