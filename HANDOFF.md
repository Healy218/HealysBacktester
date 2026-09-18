# Handoff — active dividend completion, recovery checkpoint

The user explicitly asked to finish the dividend portion and authorized necessary checks and edits. Work is ongoing: do not mistake this recovery checkpoint for completion. Main only; preserve unrelated V6/assembly changes. Prior handoff is handoff-history/HANDOFF-2026-09-18-before-primary-dividends.md.

## Current verified state

Current combined action/cash artifact: nn_meta/validation/v7-primary-dividends-20260918-r2. It contains 4,744 cash payment leaves for 4,710 cash price events; 4,717 cash price events total. 154 review items remain: 147 uncompiled groups and seven date cases. All 10,428 original records reconcile. New 289 primary price boundaries use actual captured history. Multiple payments share one price adjustment, with individually dated cash releases. All leaves pass source/amount/clock/settlement verification and the actual empty portfolio replay creates no cash. Funded multi-payment fixture passes; not historical ADR fills.

Full suite September 18: 2,271 tests plus 18 subtests, 19 warnings, 124.26 seconds; /tmp/v7-dividend-tests-20260918.log. No V6 policy changes or training. History coverage has NOT yet been rebuilt. Item 6-1 remains open.

## Frozen inputs and implementation

Primary resolution policies/reviews: docs/specs/V7_DIVIDEND_RESOLUTION_POLICY_20260918.json and V7_DIVIDEND_PRIMARY_REVIEWS_20260918{,_R2}.json. Do not mutate these or their bound producers after receipt creation. R3 review is UNSEALED and editable. New modules dividend_resolution/dividend_components and producer registry dividend_producer_versions preserve exact historical producer snapshots. CLI scripts/compile_v7_dividend_resolutions.py binds original inventory, primary captures, finite authorized proposal, actions/cash, history, calendar/settlement, rename and unrelated treatments. Current artifacts inputs.json are the authoritative bindings.

Baseline history v7-security-history-20260917-gap-r2; inventory v7-action-inventory-20260917-tail; baseline actions v7-cash-units-20260917; baseline cash v7-stock-cash-dates-20260918-r2; renames v7-common-share-renames-20260917; unrelated v7-other-instruments-20260917-renames; settlement v7-reported-settlement-20260917/settlement_calendar.json. All under nn_meta/validation. Trading calendar nn_meta/data_v7/exchange-calendar-20260916/calendar.json.

Primary captures: nn_meta/data_v7/dividend-finish-20260918. JPM public feed /jpmadr-public/v1/dr/dividends/CUSIP supplies gross ratePerDr, dated payments, status and underlying currency. Filter manually to Final/Amended Final: announcementFilter=final still returns Initial. Citi PDFs, issuer tables and Q4 feeds also captured. Ford Q4 historical amounts appear adjusted, so do NOT admit them blindly. Named small documents only; no bulk acquisition.

## Immediate continuation

R3 currently has 16 reviews (HL10, AMR1, PBR3 amended-final, SHEL1 amended-final, QQQ Sept2022). First Majestic AIF captured as ag-aif-2023; pages 15–20 describe eight 2022/2023 USD dividends and record/pay dates. Add these after visual inspection, retain on/about qualifiers. AG Aug2026 still needs evidence. Do not rerun earlier generators over sealed R1/R2 review files. Temporary preparation scripts /tmp/v7-build-primary-review-batch{,2,3}.py have durable recovery copies in docs/reviews/dividend-preparation-20260918/.

Seven missing dates now have primary evidence: CMA (cma-july-web, cma-nov-web), FIX (fix-web-extraction), QQQ (qqq-indexed-primary-history plus existing OCC#53847 special cash notice), PG pg-20240409 and RILY rily-20240515 under cash-date-notices-20260917. Web-tool extractions explicitly retain extraction provenance, not original HTTP bytes. PG on/after May15 and RILY on/about June11 need qualifiers retained under nominal-payment model, no actual broker posting claim. Old stock_cash_dates compiler only accepts single leaves; use a new wrapper/consumer, preserve frozen producers. QQQ special cash affects option strikes separately; do not claim option deliverable readiness from stock-cash treatment.

Two PBR 2026 distributions have genuinely provisional future USD conversion terms (June3 ex with Sept28 second payment; Aug25 ex with Dec payments). Do not invent final amounts or silently drop scope. Finish independent cases first. Remaining detailed worklist is current artifact uncompiled.json and missing_held.json. FIGR historical CUSIP327891107 is First National Bank of Groton, unrelated to listed Figure; TE H84989104 is TE Connectivity, not T1 Energy. Prove finite record identity before unrelated treatment. MSTR594972408 is actual common share, so do not call it a preferred share without evidence. SIRI/XOM missing selected identities and scope-first-day KSS/LRCX/TMO need explicit treatment. Existing broader non-dividend blockers remain as prior handoff.

Fixed acquisition and modeling constraints remain in TODO.md and preceding handoff. No real policy relaxation, scope narrowing, or training authorization implied by dividend completion request.
