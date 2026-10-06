# ETFE full coverage and dated-input validation — October 5, 2026

User explicitly selects full coverage and dated-input validation. This permits
the complete finite discovery acquisition below, superseding the prior
126-query continuation size for this new study only. All older roots and bound
sources stay unchanged. Market data remains Alpaca-only; no legacy dataset.

## Full discovery transport

Use Alpaca's [documented expiration range filters](https://docs.alpaca.markets/us/reference/get-options-contracts),
checked October 5, to cover January 2, 2024 through November 16, 2026 inclusive.
This is the union of all required expiries in the 691-session calendar inventory,
including 0–5 DTE purchases/rolls and 1–45 DTE context. Later expiry metadata
does not extend the October 2, 2026 market-price boundary. Fetch each of SPY,
QQQ and VOO with both active/inactive status, all types/strikes and raw
deliverables: six logical queries, page limit 1,000, every continuation token.
Current status is an acquisition filter, not historical eligibility.

Finite study limits: 2,048 total durably reserved attempts, 1,024 per invocation,
30 minutes per invocation, one-second minimum spacing, 32 MiB/page, 1 GiB raw
root. The preceding 690 exact-expiry queries measured about 48 KiB/query and
roughly 710 bytes/record; the remaining daily-query payload scenario is hundreds
of MB. Range pagination consolidates empty civil-expiry queries. Limits are
hard ceilings, not coverage estimates. Preserve existing disk/RAM reserves and
record actual payload, metadata, normalized and temporary-storage requirements.
No uncapped retry or automatic market-data campaign follows transport completion.

Validate exact raw page chains, expiration bounds, status and ETF identity.
Normalize every occurrence with raw JSON and page/ordinal/receipt lineage.
Reconcile all returned symbols against the previous eleven selected raw roots
and every logical calendar expiry/status query. A terminal range query covers
its exact-expiry transport partitions, including empty ones; it does not prove
that deleted/transformed historical listings are present. Keep prior vintages
and any missing/conflicting symbols explicit rather than merging them silently.

## Dated-input validation

Report evidence separately for: route transport, symbol observation, historical
listing completeness, dated contract terms/deliverables, option session cutoffs,
corporate-action original/revision availability, ETF identity, source/size units,
official exercise references, settlement dates and complete market windows.

Current `status`, `tradable`, `multiplier`, `size`, `deliverables`, and settlement
fields cannot be backdated. `close_price_date` and `open_interest_date` date those
observations only; they do not establish when contract terms became effective
or public. Capture time is not historical publication time. A current record's
T+1 delivery text for a pre-transition expiry must not override the declared
historical settlement contract. Invalid/zero economics remain raw and flagged.

Each required input needs source bytes, effective interval, historical available
time and a linked subject/purpose. An absent required proof remains unresolved.
Transport completeness, normalized data or a passing checker does not itself
admit execution/features. Historical action revisions and official reference
records must be supported by actual dated evidence, not inferred from prices.

After discovery, compute the full symbol/session census and required bar/trade
and execution window unions; reconcile measured budgets before full market
capture. The quote pilot's 1.32 TB blanket-window scenario prevents assuming a
whole-calendar quote pull fits locally. Preserve invalid/missing states and the
fixed end. Freeze requires the full declared input set to pass, not a narrowed
dataset chosen because its evidence happened to be available.
