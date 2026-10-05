# ETFE bounded action replay v2 — October 5, 2026

Component **ETFE.provider-action-replay** tests the action-timing route without
claiming that successful transport closes **ETFE.provider-action-timing**.
Existing capture roots and consumers remain unchanged. Fresh Alpaca only.

Four fixed UTC days: March 14, 2024; March 20, 2025; March 19, 2026; September 17,
2026. These are the days before known SPY quarterly ex-dates, using the selected
fresh REST inventory. Match any SPY/QQQ/VOO cash dividend by native action ID;
retain unrelated events only as transport evidence. The calendar selection does
not prove those days contain original announcements or complete revision history.

Query the documented corporate-action SSE route with US region and
`cash_dividend_corporateaction_event` type, explicit inclusive since/until.
Current reference: https://docs.alpaca.markets/us/reference/subscribetocorporateactionseventssse
The prior study captured this route successfully. No inferred symbol filter.

Each response cap is 2 MiB. At a byte/time cap, continue at the beginning of the last COMPLETE
event timestamp’s second inclusively, preserving every duplicate occurrence and raw page.
Verify identical repeated event IDs; reject conflicting IDs, clock reversal,
wrong type/region, out-of-window times, broken page chains and a continuation
with no new events. Never advance past a partial trailing block or add a
nanosecond to skip equal-time events. A giant equal-time group can stall within
the page budget; report incomplete rather than silently skip it. Transport errors
are retained but uncommitted; later resume retries after persisted cooldown.

One GET/second, 96 GETs and 15 active minutes per invocation. At most 32 MiB per
day, 128 MiB raw across all attempts and 192 MiB root, plus the established disk/
RAM reserves. Include failed/orphan attempts in budgets. Use the prior HTTP
reader's response-time cap and socket timeout. No automatic scope or budget
expansion. Actual one-page stop/resume preserves committed files.

Publish day-level EOF/bytes/occurrence/unique-ID counts separately from retention
and history-coverage flags. A welcome-only EOF is not a no-action certificate.
Retain ETF events with raw-source hashes and block ordinals. Cross-reference all
35 selected REST actions. Count pre-effective mutation witnesses before 09:30
New York on ex-date, and require exact symbol/ex-date and Decimal rate equality
to call a witness consistent with the current REST economics. An update witness
is evidence of that version at its emission, not original publication or proof
that it remained the latest version at a later decision. Delete observations do
not establish matching economics. Admission remains false throughout.

An independent line-oriented parser reconciles every complete event, overlap,
ETF field/link and witness classification to raw responses. Test caps, same-time
overlaps, missing cursors, nonprogress, conflicting IDs, bounds/filter mismatch,
EOF fragments, recovery and receipt tampering. Exit is bounded transport plus
reconciliation, or a retained failure with exact unresolved scope. No training,
feature rewrite, old-project data, broadened price window or bulk campaign.

## Observed continuation repair

The original r0 stopped on a strict interval violation: requested since
09:30:08.378721Z, received first event 09:30:08.378324Z on September 17. Preserve
its raw attempts, original source snapshots and REJECTION receipt. The server
behavior is consistent with a coarser cursor, but its exact implementation is
not inferred. V2 deliberately rounds the continuation down to a whole second.
All returned events must still lie inside the new exact request. Overlap is
retained and identical IDs are reconciled. No lower-bound tolerance is relaxed.
Prepare isolated `alpaca-fresh-action-replay-20261005-r1`, binding the rejection
as an input. Repeat the finite controls for this successor; original r0 remains
incomplete, and only a separately audited successor can close transport.
