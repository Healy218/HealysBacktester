# V7 cash-publication audit and full-window Apple corroboration

The complete active cash inventory now has 286 amount-publication matches from
the retained Alpaca news archive, up from 256. Separately, all eighteen captured
Apple dividends have original-issuer term checks and dated news corroboration
of the cash amount across the full requested window. These are component
evidence; **V7 is not ready to train**. No full-universe stage was admitted.

## Full cash audit

`nn_meta/v7/publication_body.py` checks the reported per-share cash amount,
explicit-year record date and payment date in one HTML paragraph. Article
creation must fall on the declaration date, with the captured version's update
time before the effective date. The generic matcher requires a single issuer
and rejects ambiguous classes, annual/special/variable distributions, foreign
currency markers, negation and conflicting amounts or dates. Inline tags are
allowed; separate paragraphs and hidden scripts cannot supply missing fields.

`scripts/audit_v7_cash_publications.py` verifies the full action inventory,
news acquisition, receipts, payloads and code bindings. Identical article
duplicates are counted once; conflicting versions fail. Matching articles retain
their source payload and article hashes. This describes a news report, not an
original issuer release or proof of complete action/identity semantics.

Current output `nn_meta/validation/v7-cash-publications-20260916r2`:

| Measure | Count |
| --- | ---: |
| Massive cash candidates, including GAP alias records | 4,975 |
| Captured article observations / unique articles | 21,814 / 21,268 |
| Matched actions | 286 |
| Headline matches / body matches | 256 / 31 |
| Additional actions from body text | 30 |
| Unmatched actions | 4,689 |
| Action/article publication records | 289 |

All 31 matching body paragraphs were inspected. Receipt SHA256:
`2ac8d56d589c06f4128998cf9f177fbcf85fd08e6731ce0fbbff6621338046a3`.
All 2,569 input/code bindings reverified after the run. Preserved r1 predates
the output-location guard; use r2. Original-issuer and research-ready flags
remain false. The generic matcher intentionally does not infer missing years.

## Eighteen Apple announcements and dated corroboration

Captured all eighteen quarterly releases corresponding to the retained AAPL
dividends, from April 28, 2022 through July 30, 2026, under
`nn_meta/data_v7/aapl-publications-20260916`. The request manifest sits alongside
that directory as `aapl-publications-20260916-requests.json`. Each capture has
original bytes, HTTPS request/final URL, retrieval clock and receipt. No stock
prices were acquired from a new source.

The exact dividend paragraphs were inspected for every release. All eighteen
cash amounts, record dates and payment dates agree with both captured providers.
All eighteen provider ex-dates also agree, but the issuer paragraphs do not
independently state ex-dates. No ex-date is inferred from record date.

Issuer review `nn_meta/validation/v7-aapl-publications-review-20260916`, receipt
`abdd12c8ff7452a1888b877835616c1ec8f144bae15aa9dbdd56cc60fd0ed058`, binds all
356 inputs and exact one-off verification source. It checks canonical URLs,
publication metadata, USD common-share cash terms and both providers' records.
All eighteen pages carry August 19, 2026 modification timestamps, later than
their respective ex-dates. This does not show that the dividend text changed,
but the current HTML alone does not prove the historical page version.

To corroborate the terms contemporaneously, eighteen specific earnings reports
were manually inspected in the already captured Alpaca news archive. All state
the matching dividend amount; seventeen also state matching record/payment
month-and-day pairs. The May 4, 2023 report states the 24-cent amount only.
Article update clocks, including the February 2024 next-day update, are retained
as conservative publication availability and all precede the related ex-dates.

This finite manual review resolves abbreviated/yearless dates against the fully
dated issuer release and article's declaration year. It does not loosen the
generic matcher. The eighteen exact article IDs, inspected paragraphs, amount
phrases and date comparisons are retained in
`nn_meta/validation/v7-aapl-news-corroboration-20260916`; receipt
`efb178b62bc0153883e10419fbe4878e7199cf926d55da8f560000db7e1ae583`, 398 verified
bindings. Both reviews retain `verification.source.txt`. Historical issuer-page
version, complete action inventory and security-continuity flags remain false.
The separate Apple review must not be added blindly to the generic audit counts.

## Checks and next work

Fifteen new regression cases passed. Full suite: **1,878 tests +18 subtests**,
18 warnings, 93.11 seconds; `/tmp/v7-cash-publications-tests.log`. Production
source did not change after that run. Both audit and all captures are terminal.
Quota: 62,561,193,933 /250,000,000,000 bytes, no reservations. V6 untouched.

Next, consume reviewed publication evidence with full-security action/no-event
and identity continuity. Revalidate historical AAPL component source bindings
if reused, and cite the new corroboration rather than silently assuming the
current issuer HTML's original vintage. Continue full causal market/sector
integration, quote demand/capture, physical execution, assembly and resource
gates. Existing readiness still has eight missing substantive stages; no
training was launched.
