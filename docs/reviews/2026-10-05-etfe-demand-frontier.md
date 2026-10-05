# ETFE demand frontier and March discovery — October 5, 2026

Completed **ETFE-1.demand-frontier**: a measured acquisition envelope and one
bounded discovery continuation. Full **ETFE-1.demand** remains open.
[Machine receipt](2026-10-05-etfe-demand-frontier.json),
[evidence ZIP](2026-10-05-etfe-demand-frontier-evidence.zip),
[contract](../specs/ETFE_DEMAND_FRONTIER_20261005.md).

The new module verifies every selected input page chain and separates successful
response payloads from total root storage. It enumerates returned-symbol surfaces
for all 691 sessions / 2,073 ticker-sessions. Missing expiry queries stay explicit;
current contract records are discovery-only. Independent reconstruction from raw
bodies reconciles both the pre-capture r0 and selected post-capture r1 frontiers.

The finite batch covered March 5–25, 2024 civil expiries for SPY/QQQ/VOO,
both active/inactive statuses, both rights and all returned strikes. **126 HTTP
200 responses added 8,462 normalized records** in 126 partitions. Ninety-five
queries returned empty lists, which do not establish historical nonexistence.
One earlier sandbox transport failure is retained separately. Live capture took
125.14 seconds. Payloads total 6,028,348 bytes; the raw root occupies 7,378,772
bytes and normalized output 1,607,963 bytes at review time.

The selected raw roots now complete **558 / 6,300** calendar discovery queries;
**5,742 remain**. Six January 1 padding queries are outside that denominator.
There are 38,126 returned symbols, yielding a gross envelope of 963,898
symbol/session edges, including 156,122 at purchase DTE 0–5. Grouping 100
symbols per ticker/session gives 9,888 gross requests before pagination or reuse.
One bar per regular minute gives 375,538,620 rows as a density scenario only.
These are neither exact signal-conditioned demands nor proven historical listings.

The remaining discovery payload scenarios are 276,473,870 bytes at the observed
mean and 2,563,510,158 bytes if every query matches the observed largest query.
Neither is an upper bound, and neither includes normalization, temporary files
or frozen copies. Full phase-B/C request/storage budgets remain null. The batch
enforces 128 attempts/run, 256/study, 512 MiB/root and existing resource reserves;
durable reservations precede networking so a crash cannot reset request usage.

The phase-C requirements now explicitly include hold/exit bars, fresh stock
quotes at every roll retry, replacement eligibility at actual 0–5 DTE, official
exercise references, dated deliverables and settlement calendars, and sized
stock quotes through liquidation. All 2,073 stock sessions are possible quote
windows, totaling 805,230 regular minutes, not a measured quote-row estimate.
Market capture stops at the fixed October 2 boundary; later cash-only settlement
clocks cannot authorize later market observations. The synthetic scheduler's
missing-input paths do not supply real quote/exercise data or path counts.

All **294 focused ETFE tests pass**, including five new boundary, corruption,
restart and study-budget tests. Raw-to-normalized occurrence reconciliation
passes for every new row. A separate-process restart used zero GETs and preserved
510 files. Both frontier audits verify all 2,073 session counts and the exact
next discovery batch. The evidence ZIP includes metadata/source snapshots and
an index hashing all 793 local files; large raw bodies and Parquets remain local.

Selected normalized inputs now total **1,375 partitions / 1,964,142 rows**.
No option market history was added by this discovery-only batch, so January's
first-observed/usable boundary is unchanged. No capture remains running.
Next: continue measured discovery, measure missing stock-quote/exercise sources,
and derive exact full-window signal/holding demand before full acquisition and
the real integrated pilot. No dataset freeze, training, orders or deployment.
