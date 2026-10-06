# ETFE full-window demand computation — October 6, 2026

The user selects exact option bar/trade and holding-path windows followed by
historical-input gap resolution. This study performs offline demand computation
on fresh Alpaca artifacts. It does not authorize an unbounded network campaign.
All original feature, execution, context, 0–5 DTE and fixed-end rules remain.

Generate the full calendar daily-context request inventory for every returned
contract at 1–45 calendar DTE, both rights/all strikes, regular stock session.
This is exact transport demand over the observed symbol census, not historical
eligibility. Preserve adjusted symbols. Represent symbol membership in batches
of <=100 with exact half-open nanosecond bounds; split purposes from execution
admission. Do not substitute daily candles including extended hours for summed
regular minute volumes or use closing premiums to discard unobserved contracts.

Compute the 20-family catalog's four signal channels on the complete collected
stock history at 1/5/15 minutes. Store packed per-variant boolean memberships,
source/calendar hashes, complete chart clocks and per-family checkpoints. Raw
prices remain unadjusted diagnostics. Never bridge a missing stock bin: retain
the uninterrupted valid prefix and label every following bin unresolved because
recursive state has not been proven recoverable. This is incomplete signal
coverage, not a legitimate absence of signals. Do not silently reset indicators.

Factor feature and entry windows from signal memberships and strictly prior-date
observed candidate contracts. Preserve every unresolved-selection clock. Targets
0/1/5 are unconditional; 2/4 remain explicitly unresolved dated weekly targets.
Feature bounds at signal t and timeframe m are [t-(m+1)min,t-1min); entry reference
bounds are [t-1min,t). Physical requests may union overlapping/adjacent windows
and reuse only complete hash-verified transport, without promoting missing bars
to valid no-trade. Signal/execution timestamps remain separate from bar starts.

Holding demand is an incremental state dependency: acquire the completed bar
required at each observation while an option remains held or an exit is pending;
request fresh stock quotes for expiry classification, roll selection, stock marks
and liquidation; request dated official exercise reference separately. A missing
window yields an unresolved frontier, never a terminal outcome. Stop extending
only after ledger evidence of exit/settlement or fixed-end censoring. Do not call
a possible hold-to-expiry envelope an exact realized holding path. No hypothetical
fill creates a real historical holding path while admission is unresolved.

One serial compute process, at most 180 family checkpoints, 4 GiB output and
30 minutes per invocation, bounded signal batches <=32 with existing 128 MiB
array-width guard. Keep disk >=max(100 GiB,20%) plus 1 GiB, available RAM
>=max(2 GiB,20%) plus 1 GiB. Bind pure mathematical source kernels only, no old
market data. Record actual wall time, RSS, output size, family/variant/event
census and interrupted restart. Before source binding, verify new interval and
holding-frontier kernels with endpoint, missingness and expiry/roll cases.
