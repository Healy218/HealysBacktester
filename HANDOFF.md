# Handoff — active dividend completion, recovery checkpoint

The user explicitly asked to finish the dividend portion and authorized necessary checks and edits. Work is ongoing: do not mistake this recovery checkpoint for completion. Main only; preserve unrelated V6/assembly changes. Prior handoff is handoff-history/HANDOFF-2026-09-18-before-primary-dividends.md.

## Current verified state

Current combined action/cash artifact: nn_meta/validation/v7-primary-dividends-20260918-r6. It contains 4,835 cash payment leaves for all 4,777 cash price events. 87 review items remain, all uncompiled groups; zero missing-date cases. All 10,428 original records reconcile. New 289 primary price boundaries use actual captured history. Multiple payments share one price adjustment, with individually dated cash releases. All leaves pass source/amount/clock/settlement verification and the actual empty portfolio replay creates no cash. Funded multi-payment fixture passes; not historical ADR fills.

Full suite September 18: 2,277 tests plus 18 subtests, 19 warnings, 211.49 seconds; /tmp/v7-dividend-tests-dates-20260918.log. No V6 policy changes or training. History coverage has NOT yet been rebuilt. Item 6-1 remains open.

## Frozen inputs and implementation

Primary resolution policies/reviews: docs/specs/V7_DIVIDEND_RESOLUTION_POLICY_20260918.json and V7_DIVIDEND_PRIMARY_REVIEWS_20260918{,_R2}.json. Do not mutate these or their bound producers after receipt creation. R1 through R6 and nominal-date reviews are frozen and bound by receipts. New modules dividend_resolution/dividend_components and producer registry dividend_producer_versions preserve exact historical producer snapshots. CLI scripts/compile_v7_dividend_resolutions.py binds original inventory, primary captures, finite authorized proposal, actions/cash, history, calendar/settlement, rename and unrelated treatments. Current artifacts inputs.json are the authoritative bindings.

Baseline history v7-security-history-20260917-gap-r2; inventory v7-action-inventory-20260917-tail; baseline actions v7-cash-units-20260917; baseline cash v7-stock-cash-dates-20260918-r2; renames v7-common-share-renames-20260917; unrelated v7-other-instruments-20260917-renames; settlement v7-reported-settlement-20260917/settlement_calendar.json. All under nn_meta/validation. Trading calendar nn_meta/data_v7/exchange-calendar-20260916/calendar.json.

Primary captures: nn_meta/data_v7/dividend-finish-20260918. JPM public feed /jpmadr-public/v1/dr/dividends/CUSIP supplies gross ratePerDr, dated payments, status and underlying currency. Filter manually to Final/Amended Final: announcementFilter=final still returns Initial. Citi PDFs, issuer tables and Q4 feeds also captured. Ford Q4 historical amounts appear adjusted, so do NOT admit them blindly. Named small documents only; no bulk acquisition.

## Immediate continuation

All seven dates compiled in v7-dividend-dates-complete-20260918 with nominal pay-date qualifiers preserved. New dividend_dates module and compile_v7_remaining_cash_dates CLI reuse the frozen legacy validator, preserve multi-payment leaves, and keep option adjustments separate. R3 adds HL/AMR/PBR/SHEL/QQQ; R4 AG; R5 FANG/PXD/AMKR/AG; R6 BX/GM/CF/F/ETHE/ITB/MTUM/FXI/SOXS. Exact inputs and counts are in each receipt/report. Actual primary price boundaries tested on every batch. History coverage still needs rebuilding after final closure.

R7 preparation /tmp/v7-r7-terms.json currently has seven Direxion distributions read from the captured product page __NEXT_DATA__. props.pageProps.ssrData.funds contains all funds: filter ticker and original effective date. Values are historical unadjusted and agree with duplicate original rows. Ford 2023/2024 and KKR Q1 2022 issuer PDFs are being captured. DKS March2024 SEC and SIMO Oct2023 primary notices found. MSTX issuer correction provides exact $14.42760884. Preserve all source records and individual payments; never sum duplicate same distributions.

Recovery helpers copied to docs/reviews/dividend-preparation-20260918 (historical preparation, not automatic overwriting of sealed reviews). Named primary evidence only. Current worklist is R6/uncompiled.json. Two PBR future distributions have provisional USD conversion terms; SU/CCJ native CAD amounts need explicit FX treatment. SIRI/XOM identity cases, first-scope KSS/LRCX/TMO, aliases GOLD/ELV, erroneous/canceled/other-instrument FIGR/TE/AMC/DFS/MSTR and mixed HD/OKE need finite reviewed routing rather than invented cash. Remaining straightforward issuer/fund source reviews continue. Do not claim completion or advance past 6-1 until full consumer audit.
