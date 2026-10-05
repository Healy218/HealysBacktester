# ETFE acquisition frontier — October 5, 2026

Successor to the calendar inventory, not a replacement for the full phase-B/C
signal/path census. All input page chains must be complete and hash verified.
Reuse compares route and parameters, not purpose. Multiple query vintages or
duplicate returned symbols require explicit selection, never silent overwrite.

For each fresh-calendar session and ETF, count returned symbols at 0–45 calendar
DTE, including both rights and all strikes; separately count 0–5 DTE purchase
candidates. Unknown discovery queries remain counted even when other queries
return zero symbols. These are gross envelopes over returned current listings,
not historical listing coverage, causal eligibility or exact additional demand.
The gross bar request count groups up to 100 symbols per ticker/session and
does not subtract prior captures. One bar per regular minute uses each actual
stock session's length, including early closes; it is a scenario, not a bound
on option hours or provider pagination. Every phase-C stock session is a
possible quote window; quote counts/bytes remain null until measured.

Phase-C requirements include all hold/exit observations, every roll retry's
fresh underlying quote, dated 0–5 DTE replacement eligibility, official exercise
references, deliverables, settlement calendars and stock quote sizes through
liquidation. Removed/stressed exits can activate physical fallback. Cash-only
settlement clocks may extend beyond the fixed market-data cutoff; no market
capture extends beyond October 2. The synthetic scheduler establishes required
input types, not real path counts or source coverage.

Measure successful committed response payload bytes, pages, rows, empty queries
and maximum observed query size by route, separately from all root files.
Remaining discovery mean/max scenarios are empirical and are not guaranteed
bounds. They exclude normalization, temporary files and frozen copies. Full
phase-B/C storage/request budgets stay null until discovery, exact signal/path
demand and missing-route measurements support them.

The next finite capture selects at most 126 missing queries sorted by expiry,
ticker and status. Both active/inactive statuses and every civil expiry remain.
Use the existing serial fresh downloader: at most 128 GET attempts per run,
256 total attempts per study (durably reserved before networking, including crashes),
30 minutes per run, one second minimum request spacing, 32 MiB/page and
512 MiB/root. Pagination and errors consume the cap. Existing reserve guards
remain. Exhaustion requires a separately reviewed successor; no automatic loop
or bulk campaign. Normalize and independently reconcile the completed batch,
prove a zero-request restart, then write a new frontier without overwriting the
pre-capture frontier. Fresh rows remain discovery-only and unadmitted.
