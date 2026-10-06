# ETFE full discovery and dated-input validation — October 6, 2026

**Full discovery transport passes. Full market coverage and dated-input admission
remain open.** This is a whole-calendar census for SPY/QQQ/VOO, not another
expiry sample. It does not replace the required full signal/path acquisition,
real execution, dataset build or training gates. Market prices still end on
October 2, 2026; entries/rolls stay at 0–5 calendar DTE including qualifying 0DTE.

[Machine receipt](2026-10-06-etfe-full-coverage.json),
[evidence index and receipts](2026-10-06-etfe-full-coverage-evidence.zip),
[source-bound acquisition contract](../specs/ETFE_FULL_COVERAGE_20261005.md).
The campaign began October 5; this completion review is dated October 6.

## Full discovery result

Six range queries cover active/inactive SPY, QQQ and VOO contracts expiring
January 2, 2024–November 16, 2026, the complete required calendar-expiry union.
All pagination reached terminal responses: 455 successful GETs and **452,347
unique contracts**, normalized into 455 page Parquets. The later expiry bound
supports 45-DTE context and does not extend the fixed market-price end.

| Underlying | Active observations | Inactive observations | Total |
| --- | ---: | ---: | ---: |
| SPY | 5,016 | 213,261 | 218,277 |
| QQQ | 5,174 | 207,946 | 213,120 |
| VOO | 984 | 19,966 | 20,950 |

All **6,300 / 6,300** required expiry/status partitions have complete transport;
4,756 return no current records. Empty partitions do not prove historical
nonexistence. All 45,470 earlier discovered symbols are present with matching
stable identities; there are no missing prior symbols, conflicts or duplicates.

Across 2,073 ticker-sessions, the returned-symbol envelope contains 14,049,776
symbol/session pairs, including 1,832,006 at 0–5 DTE. Naive session batching is
141,489 bar requests before pagination/reuse; one row per regular minute would
be 5,460,024,840 rows. These are gross scenarios, not exact signal/path demand,
listing-time evidence, required payload forecasts or permission for bulk capture.

Raw payload: 321,293,281 bytes; raw root including receipts/runs: 366,739,081.
Typed Parquets: 41,203,637 bytes. The main resumed invocation took 1,166.22 seconds
and 454 GETs after the first-page stop. Seven original files were preserved;
completion restart made zero GETs and preserved 1,828 raw files. Normalization
restart preserved 917 files. An independent auditor reconciled every occurrence,
critical typed field, missing adjusted identity, query count and session count.
Five adjusted `1SPY` observations retain null parsed identities and explicit
flags; their raw metadata remains intact. They are not silently excluded or
promoted into historical eligibility.

## Dated-input findings

| Required evidence | Actual result | Admission verdict |
| --- | --- | --- |
| Contract effective/available intervals | All 452,347 current observations lack both terms clocks | Unresolved; capture time and price/OI dates cannot supply them |
| Multiplier and deliverable economics | 43,720 invalid/nonpositive raw multipliers; five adjusted identities outside the original standard-symbol parser | Unresolved; no replacement with `size=100` or silent standard-contract assumption |
| Historical physical settlement | 53,634 pre-May-28-2024 expiries report T+1 delivery in current metadata | Contradictory to the declared pre-transition T+2 rule; current terms cannot be backdated |
| Full-window action observations | 33 dividend announcements, eleven per ETF; all prior in-window actions matched | Transport and cross-endpoint action inventory pass; historical completeness not proven |
| Action availability/revisions | All 33 have declaration dates before ex-date; no full original/revision timeline | Unresolved; date granularity and revision ambiguity remain |
| Action payable terms | QQQ March 18, 2024: announcement says April 30 payable, newer data endpoint says May 1 | Explicit conflict; preserve both and resolve before cash timing admission |
| ETF/adjusted identity and class hours | Full census observes current identities; dated eligibility/class exceptions not supplied | R1/R2 remain open |
| SIP size representation and official exercise reference | Previous 54-window quote pilot preserves raw sizes; no dated size conversion or official-close source established | Unresolved; quote midpoint is not the declared official exercise close |
| Historical bar/trade publication and corrections | Existing route observations establish capture/market timestamps, not full original publication/revision order | P1 remains open |
| Stock minute coverage | Existing complete-window stock audit: SPY/QQQ complete expected grids, twelve VOO gaps | Gaps remain unresolved; this campaign did not repeat stock capture |
| Option/context/holding-window coverage | Discovery complete; full phase-B/C exact window inventory and downloads absent | Full market coverage fails; current January diagnostics remain bounded |
| Usable history boundary | January 18 first observed in earlier scoped bar audit | Not a verified usable start; this discovery campaign does not establish bar availability |

The contradiction counts flag affected current records, not a claim that every
possible exercise date on those contracts follows one uniform settlement date.
Historical calendars and transition exceptions still apply.

## Announcement endpoint result

The [deprecated Alpaca announcement route](https://docs.alpaca.markets/us/reference/get-v2-corporate_actions-announcements-1)
returned dated declarations in six initial March-2024/September-2026 controls.
The successful full capture uses 36 disjoint symbol/date queries, each at most
89 inclusive days, January 1, 2024–October 2, 2026. All return HTTP 200, covering
`dividend,merger,spinoff,split`; all returned records are cash dividends.
An independent comparison checks ex-date identity, amount, record and payable
terms against the earlier data-API main/tail captures. No prior action is missing;
the one payable-date conflict is retained. Completion restart preserved 76 files
and made no requests.

Rejected r0 remains preserved: 36 HTTP 422 responses rejected a request including
`Reorg`, despite its appearance in the route documentation. Successor v2 uses
the four types named by the live API and stops immediately on non-200. A complete
set of error responses is not complete data transport. This was a request defect,
not evidence that the ETFs had no corporate actions.

The [related announcement schema](https://docs.alpaca.markets/us/v1.1/reference/getcorporateannouncements-1)
allows a declaration date to represent either initial details or a later term
update. Consequently, neither the field nor pre-ex-date ordering establishes
original intraday publication or the latest terms available at each past decision.
No midnight timestamp was fabricated. QQQ's March record also carries a different
CUSIP from the newer data-API observation; dated identity mapping remains open.

## Verification and next dependency

All **320 focused ETFE tests pass**, with two existing protobuf deprecation
warnings. Source-bound predecessors remain intact. This result closes
**ETFE-1.full-discovery** only. It records a failed dated-input admission check
with concrete affected records; it does not waive R1/R2/P1, freeze inputs, emit
scientific labels, train, deploy or place orders. No capture process remains.

Next, factor exact full-window signal/context/trade and holding/roll/exercise
windows using this census, keeping adjusted/undated contracts unresolved; budget
raw, typed and temporary storage before capture. The earlier 1.32 TB blanket
stock-quote scenario makes a whole-calendar quote pull inappropriate. Resolve
dated terms/hours, historical size representation, official exercise references
and the QQQ action conflict through fresh source evidence before real admission.
