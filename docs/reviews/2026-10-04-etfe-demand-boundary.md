# ETFE calendar demand and January options coverage

Continued the user's fresh Alpaca-only acquisition with 0–5 DTE purchases and
1–45 DTE context. Added a source-bound phase-A calendar inventory, all-returned-
symbol January history checks, and full-day January 18/19 option bars. No old
project market data, feature arrays, labels or models were imported.
[Study definition](../specs/ETFE_DEMAND_20261004.md),
[active-time continuation](../specs/ETFE_DEMAND_CONTINUATION_20261004.md).

## Demand inventory

The collected 691-session stock calendar produces 2,073 ticker-session records
and 190,716 expiry/status edges. Exact transport identity factors these into
6,300 discovery queries; 60 were already captured when the inventory was sealed.
Every civil expiry is retained, including weekends/holidays and expirations
beyond the fixed last observation date. Purchases use 0–5 DTE; daily context
uses 1–45. The catalog retains all twenty families and 25,353 ticker variants.

The January continuation supplies 372 additional queries in this inventory,
plus six January 1 padding queries outside it. Thus 432 inventory queries now
have capture receipts and 5,868 remain. This is calendar-level discovery demand,
not complete symbol/session surfaces or strategy demand. Phase-B causal signals,
feature/trade windows and phase-C holding/roll/stock paths remain explicit.

## Captured and reconciled

| New capture | Partitions / live GETs | New rows | Scope |
| --- | ---: | ---: | --- |
| January discovery | 378 / 378 | 21,966 records | Every civil expiry January 1–March 4, both statuses, all three ETFs; six prior queries reused |
| Earlier-history bars | 233 / 233 | 0 bars | All 23,176 discovered symbols over January 1–17 |
| January daily bars | 349 / 349 | 178,671 bars | All returned 0–45 DTE symbols on January 18/19; six symbol/day windows reused |

All **960 new live GETs returned HTTP 200**. One failed sandbox-network attempt
is retained separately. Every requested page chain reached a terminal token;
request-cap stops resumed from immutable committed pages. The three new roots
normalize to **960 partitions / 200,637 rows**. Independent audits reconcile
the complete ordered raw-row sequence, hashes, counts and quality counts for
every partition. No implemented normalization quality flags fired.

An additional independent audit reconciles all **34,660 symbol/day edges** with
physical jobs and reuse links. It includes 571 previously captured bars from six
symbol/day windows, giving 179,242 bars across the two-day requested inventory.
Those 571 rows are not counted as new capture or normalized twice.

| Session / ETF | Requested symbol/day windows | Windows with bars | Bars including reused windows |
| --- | ---: | ---: | ---: |
| January 18 / SPY | 7,692 | 1,476 | 31,699 |
| January 18 / QQQ | 9,328 | 1,416 | 20,471 |
| January 18 / VOO | 292 | 37 | 240 |
| January 19 / SPY | 7,708 | 1,941 | 73,128 |
| January 19 / QQQ | 9,348 | 1,935 | 53,096 |
| January 19 / VOO | 292 | 60 | 608 |

There are **27,795 symbol/day windows without returned bars**. These remain
unresolved absence, not proven no trading. Current listings are not complete
historical listings or point-in-time eligibility. No closing-price or outcome
filter selected the requested strikes; downstream admission remains separate.

## History boundary and remaining scope

Within the tested inventory, all three ETFs' first observed bar is
**January 18, 2024, 14:30 UTC (09:30 Eastern)**. January 1–17 returned no bars
for all 23,176 discovered symbols, including earlier-expiry listings. This is
substantially broader evidence than the original near-money samples, but it
does not establish usable or verified-complete history. Pre-January intervals,
longer expirations outside this discovery grid, omitted historical listings,
dated contract terms and publication/session provenance remain unresolved.
The current setup's verified usable start remains null; no synthetic history.

The total selected normalized ETFE inputs now contain **1,878,623 rows in 1,146
partitions**: 1,589,090 stock bars, 184,070 option bars, 75,799 option trades and
29,664 discovery records. Earlier stock coverage and twelve unresolved VOO
minute gaps are unchanged. Full option/context coverage, causal features,
integrated execution/resource pilot, freezes and training remain open.

## Budgets and validation

Preflights retain measured near-money density alongside all-empty and full
regular-minute scenarios; dense extrapolations exceed root limits and were never
promises of completion. Actual capture used about **959.3 seconds (16.0 minutes)**
of accumulated active time. Discovery used four invocations including the failed
sandbox attempt, boundary two, surfaces three. All request, invocation, root
storage and per-invocation limits stayed within their declared caps.

The initial one-hour study wall-clock budget elapsed during approval waits;
the second live discovery invocation began after its deadline. This orchestration
deviation is recorded, not retroactively labeled compliant. The explicit
continuation retains the same request/storage caps and permits at most one hour
of accumulated active capture time, excluding approval/idle waits. Original
plans, receipts and source snapshots remain unchanged; `CONTINUATION.json` binds
the successor and prior run hashes.

**95 focused tests passed**, covering civil-date demand, 0DTE/context boundaries,
batching, exact-query reuse, corrupted/incomplete inputs, duplicate vintages and
the existing ETFE components. The v4 setup verifier still passes. Independent
real-data audits additionally check all normalized occurrences and surface links.
No model fit or performance evaluation was performed.

[Machine receipt](2026-10-04-etfe-demand-boundary.json) records selected roots,
hashes, actual counts/resources and tests. The evidence ZIP includes metadata,
source snapshots, reports and a hash index; raw bodies and Parquet remain local.
