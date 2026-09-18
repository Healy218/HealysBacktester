# V7 finite common-share rename treatments

Seven previously undated Alpaca name-change records now have explicit treatments
based on primary notices and adjacent original daily listings. They concern six
scoped securities. Every pair has the same composite FIGI and share-class FIGI;
this review creates no successor identity, price factor or cash entitlement.
The original provider records and process dates remain unchanged.

| Effective session | Transition | Primary evidence |
|---|---|---|
| 2022-06-09 | FB → META | [Meta May 31 notice](https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx) |
| 2023-06-07 | FISV → FI | Previously retained issuer/NYSE releases in the [source-routing review](2026-09-17-v7-6-1-source-routing.md) |
| 2024-08-22 | GPS → GAP | [Gap August 8 notice](https://investors.gapinc.com/press-releases/news-details/2024/Gap-Inc.-To-Change-Ticker-Symbol-to-GAP-on-August-22-To-Report-Second-Quarter-Fiscal-2024-Results-on-August-29/default.aspx) |
| 2025-01-21 | SQ → XYZ | [Block January 9 notice](https://investors.block.xyz/investor-news/news-details/2025/Block-Announces-Ticker-Symbol-Change-to-XYZ-To-Report-Fourth-Quarter-Results/default.aspx) |
| 2025-05-09 | GOLD → B | [Barrick May 6 notice](https://www.barrick.com/English/news/news-details/2025/barrick-announces-name-change-to-barrick-mining-corporation-and-election-of-directors/default.aspx) |
| 2025-11-11 | FI → FISV | [Nasdaq November 3 notice](https://nasdaqtrader.com/TraderNews.aspx?id=DTN2025-32) |
| 2026-06-24 | SATS → ECHO | [Issuer release distributed by Nasdaq](https://www.nasdaq.com/press-release/echostar-changing-stocker-ticker-sats-echo-marking-companys-next-era-earth-and-space) |

The unchanged-share conclusion comes from those finite notices together with the
exact identity witnesses; it is not a rule that any matching FIGI or CUSIP proves
all corporate-action terms. Barrick explicitly changes CUSIP with its name; its
captured common-share identity remains unchanged. Other changed-class cases are
not admitted. For date-only publications, the retained availability bound is
midnight after the stated publication day in New York, safely before the
applicable effective open. No exact publication time is invented.

## Code and source partition

`renames.compile_renames` verifies the finite original record reference, listing
hashes, adjacent sessions, selected stock routing, unchanged common-share
identity and continuity, and publication-before-effect ordering. The sealing
script additionally verifies all primary capture receipts and parent hashes.

The coverage auditor consumes the seven treatments separately from chart events,
retains `identity_event_id` on each effective session and reconciles the complete
original-record partition. Feature declarations retain consumed identity event
IDs through the bound coverage receipt. Simultaneous or unrelated unresolved
records continue to block admission.

The partition is now **10,428 =8,964 compiled cash/split records +90 unrelated
cash records +7 reviewed rename records +1,367 unresolved records**. Cash/split
actions remain 4,481; simple unresolved groups remain 504. Complex unresolved
records fall from 213 to 206, including 40 remaining name-change records.

History admission increases from 579,160 to **584,804 sessions**: 580,427 in the
no-price-event bucket (identity changes remain in their separate column) and
4,377 compiled price-event sessions. Unresolved action sessions fall to 29,803;
unresolved identity sessions remain 52,632. The other **660,465 history-grid
rows outside the six affected securities** have unchanged coverage fields. No
raw observations, membership, chart factors or existing action objects change.

## Actual consumer checks and held-stock implementation

The production proposal input loader and retained 15-minute one-variant feature
stores pass six two-session boundaries: META (780 raw minutes), FI (775), FISV
(780), GAP (778), XYZ (780) and ECHO (780), each with 52 feature observations.
Saved declarations retain the exact rename ID and the accepted no-event
assumption. These checks use captured inputs, not substituted price fixtures.
Barrick's boundary correctly remains blocked because the separate AMRK→GOLD
record still needs unrelated-instrument treatment.

`PhysicalLedger.apply_stock_rename` changes the symbol of settled inventory,
delivered stock and pending stock settlements at the exact effective clock. It
preserves shares, cash, cost basis, security identity and settlement commitments,
and records the reviewed event once. The portfolio scheduler processes it before
same-clock marks and updates the occupied symbol. Unexpired option positions
and unresolved merger phases reject a stock-only notice before mutation; their
option deliverables require separate evidence.

Held-stock checks use funded synthetic ledger fixtures to test pending inventory,
settled inventory, exercised-call stock, liquidation, costs, duplicate/early/late
application, rejected option handling and portfolio event ordering. **No actual
held market replay is claimed.** This implements a necessary component of 6-1;
it does not complete held-position admission, option execution or full readiness.

## Artifacts and validation

Finite reviews: `docs/specs/V7_COMMON_SHARE_RENAMES_20260917.json`.
Named missing-input requests and two timeout fallbacks are retained in
`V7_RENAME_MISSING_INPUTS_20260917.json`, `V7_RENAME_EVIDENCE_REQUESTS_20260917.json`
and `V7_RENAME_FISERV_FALLBACK_20260917.json`. Six new notices are retained under
`nn_meta/data_v7/rename-notices-20260917`; the earlier Fiserv notices are reused.
Shared acquisition usage: 63,056,786,455 bytes, zero reservations.

Current immutable artifacts under `nn_meta/validation/`:

- `v7-common-share-renames-20260917`
- `v7-action-coverage-20260917-renames`
- `v7-rename-consumers-20260917`, with the retained verifier and six bound feature stores

Focused regression: **59 tests passed**. Full suite: **2,093 tests and 18 subtests
passed**, 19 warnings, 168.78 seconds. Retained source bindings and log:
`v7-rename-tests-20260917`. The prior coverage artifact remains historical; its producer
source binding changed, so current consumers use the new coverage artifact.
Item 6-1 remains open; the seven accepted records do not resolve the remaining
identity, units, combined distributions, merger/spinoff or option-deliverable work.
