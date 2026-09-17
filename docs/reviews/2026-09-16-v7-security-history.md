# V7 dated security histories and reviewed rename overlaps

`nn_meta/v7/security_history.py` constructs one complete exchange-calendar panel
per security from exact-day listed identities and raw Alpaca daily observations.
It preserves missing history and rejects unrelated reused-ticker identities.
Adjacent dates with the same security identity may continue across a rename;
no corporate-action adjustment is implied by that continuity.

Multiple listed sources for one security/date stay ambiguous unless a retained
exact-day alias review chooses the source. An override must identify this same
security, name an observed listed source and retain its evidence identity.
It cannot pick an absent symbol or override a mismatched security ID. The output
preserves the original candidate count and separate selection evidence, so a
reviewed overlap remains visible. There is no automatic preference for the first
row, higher price, larger volume or populated source.

Missing or ambiguous identities break continuity. A listed security with no stock
observations keeps its identity but has explicit missing prices; causal returns
will still break across the missing observation. Integer nanosecond timestamps
retain nullable integer storage. All-unknown securities use the same output schema
as known securities. Only identity-span identifiers propagate within uninterrupted
known runs; prices are never filled.

`scripts/build_v7_security_history.py` verifies the complete identity panel, raw
daily shards, captured extended calendar and original alias-review sources. It
assembles the entire active-security/calendar grid and compares the selected raw
source against every previously frozen eligible source. Full identity and source
comparison reports are required before downstream use. Action adjustments and
full research admission remain separate requirements.

## Actual rename evidence

The dated provider lists both FB and META on June 9, 2022 under the same FIGI;
only META has observed regular-session stock bars. GPS/GAP has the same overlapping
listing pattern on August 22, 2024. Treating every equal-FIGI source as unique
would incorrectly mark these dates ambiguous; selecting by price availability
alone would lack the explicit alias review.

The existing `v7-gap-alias-resolution-20260915` review resolves those exact dates.
Four-session windows around both transitions now preserve one security continuity
span, choose OLD/OLD/NEW/NEW, retain all eight raw closes exactly and preserve
the two-session pre-rename prefix. Each window includes two reviewed alias dates
and one overlapping listed day. The earlier assertion that each security had
exactly one listed source failed before the reviewed override was connected;
no artifact was sealed by that failed check.

Evidence: `nn_meta/validation/v7-listed-rename-history-20260916`, receipt
`5e55cbf5181e788fd6d616cbda07df1bbc1e5dce4f60cdab3f91bc44eb5d7bf0`.
All 269 bindings reverified. Exact one-off verification source is retained.
This validates identity/source routing for the two reviewed windows; it does not
claim complete action/no-event history or option-deliverable continuity.

Nine focused tests cover renames, ticker reuse, overlap ambiguity, reviewed
selection, missing days, known halts, nullable schemas, clocks and raw-price
consistency. Full-suite and full-window acquisition/build results are recorded
in the current handoff. No V6 source/runtime change or training launch.

## Full-window result and revised priority

All capture/build jobs are terminal. The full history contains 667,239 rows for
591 securities and 1,129 sessions, with seven resolved ticker changes. 339,454
of 339,640 eligible sources match; 186 identity/lifecycle cases remain explicit.
One noneligible history day, FISV/FI June7,2023, needs an additional reviewed
routing entry using already captured release evidence. No action adjustments
or full research admission are claimed. The complete suite passed 1,912 tests
and 18 subtests in 93.92 seconds, with 18 warnings.

The user's latest instruction stops broad acquisition expansion. This consumer
is a completed integration step; the next work is the full feature/proposal and
training pipeline using existing data. The 250 GB quota is only a ceiling.
Do not extend the source audit indefinitely before building the consumers.
