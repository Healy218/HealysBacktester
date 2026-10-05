# ETFE expiry and delivery component — bounded synthetic continuation

Supports **ETFE-3.expiry-components** under the
[execution contract](ETFE_EXECUTION_20261003.md) and
[0–5 DTE amendment](ETFE_0DTE_NORMALIZATION_20261004.md). The frozen
[option component](ETFE_EXECUTION_COMPONENTS_20261005.md) is unchanged.
`nn_meta/etfe/expiry_ledger.py` accepts a verified synthetic option-prefix
snapshot before the expiry cutoff and a separate dated synthetic lifecycle
fixture. It records the prefix hash and uses a new schema/source identity.
Unresolved prefixes cannot be relabeled. No old market data or metadata is used.

## Mechanics and clocks

The caller supplies each observation; the component processes cash settlement
and delivery, marks/risk/expiry intents, option exits or exercise, stock exits,
then roll selection/purchases. Events are ordered by original proposal tie key.
The caller supplies complete dated contract terms, stock sessions and settlement
calendar coverage; missing facts stay unresolved. Ordinary fresh entry scheduling
after continuation remains outside this component. Atomic frames roll back on
malformed inputs; source-bound snapshots restore the entire lifecycle state.

At option close minus 15 minutes, positive, noncrossed SIP stock bid/ask and
sizes with age <=30 seconds establish moneyness. Quote event/availability clocks
must be causal and within the dated regular stock session. Actual share/cash
deliverable value is compared with the actual strike payment. Missing moneyness
retains a pending input reason and retries. ITM exit and non-ITM roll intents
latch; ordinary stops/strategy exits take priority and suppress new rolls.
All option fills retain the parent's completed-minute VWAP and shared volume
rules. No option fill is allowed at/after class close.

At unsold expiry, require the dated official exercise reference and known terms.
Standard contracts use exact decimal $0.01 per-share exercise threshold;
adjusted share/cash deliverables require an explicit official normalized exercise
value and exercise basis. Integer adjusted deliverables and cash are supported.
Unresolved fractional-share cash-in-lieu stays blocked, never rounded to 100.
Nonexercise is an expiry event, never a zero-price sale.

Calls reserve the entire strike debit plus declared exercise fees before any
later settlement credit. Puts require settled shares and any cash deliverable.
Competing exercises and settled roll budgets share cash reservations; no future
liquidation can fund an earlier exercise. Failures retain the option liability
and `funding_unresolved`. The baseline exercise fee is zero, with $5/contract
tested separately. Equity includes pending delivery assets/payables only with
fresh stock marks; unknown marks cannot support additional risk.

Option proceeds use the next supplied business date. Equity delivery and stock
sale use the second supplied business date before May 28, 2024 and the next
business date thereafter. Explicit dated transition exceptions override the
equity mapping. Availability is 09:30 New York on the settlement date. The
calendar is a fixture coverage assertion, not a inferred weekday/holiday rule.

Settled call shares have a liquidation intent from their delivery clock plus
one second. Sales use fresh SIP bids and the supplied documented size-to-shares
conversion. A quote identity is consumed once; repeated IDs cannot replenish
size and changed content for one ID is unresolved. Partial liquidation retains
shares and slot; final stock cash settlement releases the slot. Fees/slippage
remain 0.10%/0.05%, with separate amounts and half-even cash rounding residuals.

Rolls retain the original slot, wait for all old-leg proceeds to settle and
reserve those proceeds against other commitments. A caller-supplied regular
observation starts a fresh 60-second attempt; selection freezes then and the
purchase can occur only at signal+1s through +60s. The complete synthetic
candidate set is sorted by expiry distance, earlier expiry, nearest raw-spot
strike, lower strike and lexical identity. Require prior-date existence,
dated terms, [0.85S,1.15S] strike, enabled target and actual 0–5 DTE; repeat the
DTE/session/cutoff checks at purchase. Budget is the minimum of old settled
proceeds, available cash and 10% fresh equity. Whole quantities and shared bar
participation still apply. A new leg resets the stop denominator. Strategy exit
cancels the roll, retaining settlement liabilities. At 60 completed rolls no
further roll is initiated. Failed attempts remain in the event history.

## Outcome and evidence boundary

Funding failures, missing inputs and end censoring are distinct; complete
liability details remain inspectable. Unknown source coverage records a data
failure even if a later reference permits mechanical progress. Known quiet
markets retain missing-mark observations. `at_boundary` projects the present
liability state; it does not certify that every historical observation occurred.
Market observations at/after October 3, 2026 04:00 UTC are rejected. All outputs
remain synthetic and `training_admitted=false`; no model labels are emitted.

Four hand scenarios bind expected cents, quantities and dates in
[the fixture file](ETFE_EXPIRY_HAND_FIXTURES_20261005.json): funded call with
partial stock liquidation; unfunded put; competing call reservations; settled
proceeds roll. Tests cover additional missing inputs, fee, adjusted deliverable,
early/no quote, partial option exit, cancellation, maximum rolls and settlement
transition cases. Independent arithmetic audits and saved-prefix replay support
this bounded milestone, not admitted real execution or the integrated pilot.

Remaining full execution work includes complete observation scheduling, funded
put inventory paths, real dated evidence and capture integration, all stress
combinations, full label horizons/purged dataset construction and shared-policy
baseline comparisons. Fractional deliverables need resolved cash-in-lieu inputs.
