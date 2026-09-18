# V7 unrelated name-change record relevance

Three undated provider name-change records concern unrelated instruments that
reused scoped tickers. Finite primary-notice reviews and original adjacent
listing captures now resolve their relevance without excluding any scoped issuer:

| Record | Unrelated instrument | Scoped ticker belongs to |
|---|---|---|
| AMRK → GOLD, 2025-12-02 | A-Mark /Gold.com | Barrick |
| BNZI → PARA, 2026-08-07 | Banzai /Parabolic | Paramount |
| SPCX → SPCK, 2026-04-07 | SPAC and New Issue ETF | SpaceX |

The [A-Mark issuer notice](https://ir.gold.com/news-events/press-releases/detail/211/a-mark-precious-metals-to-become-gold-com-and-transfer-to-the-new-york-stock-exchange),
[Banzai issuer release distributed by Nasdaq](https://www.nasdaq.com/press-release/banzai-international-inc-unveils-agentic-platform-strategy-plans-change-its-name)
and [SPAC ETF issuer release distributed by Nasdaq](https://www.nasdaq.com/press-release/tuttle-capitals-spac-and-new-issue-etf-change-ticker-spck-2026-04-07)
provide the effective dates and named entities. Each unrelated pair has a
matching original composite/share-class identity, outside all 591 scoped IDs;
the scoped witness has a distinct captured share class. No merger, successor,
entitlement or option-deliverable relationship is inferred.

`other_renames.py` rejects scoped identities, differing rename legs, selected
history sources, missing positive listings, altered records and absent primary
review. The sealing script preserves the earlier 45 unrelated cash groups and
adds these three records. Coverage computes unresolved records from the original
compiled inventory minus all explicit treatments, independent of which treatment
artifact was built first; overlapping/missing/altered references still fail.

## Result and consumer evidence

The partition is **10,428 =8,964 compiled cash/split +93 unrelated +7 scoped
rename +1,364 pending records**. Cash/split actions remain 4,481; unresolved simple
groups remain 504. Complex unresolved records are now 203, including 37 remaining
name-change records.

The full coverage grid admits **586,830 sessions**, up 2,026: 582,440 no-price-event
sessions and 4,390 compiled-price-event sessions. Remaining action-blocked rows:
27,777; identity-blocked rows: 52,632. All raw histories, memberships and factors
are unchanged. Coverage fields outside the three scoped securities remain
unchanged; no earlier admitted row is withdrawn.

Real captured two-session proposal-input and 15-minute one-variant feature-store
checks pass for Barrick B, Paramount PARA and SpaceX SPCX. Barrick now consumes its
previously reviewed GOLD→B identity event. Saved declarations retain the accepted
no-event assumption. These are bounded consumer checks, not full production or
held market replay.

Full suite: **2,103 tests and 18 subtests passed**, 19 warnings, 201.56 seconds.
Ten focused relevance tests also pass. No V6 code, live deployment or training
campaign changes. Item 6-1 remains open.

Current artifacts under `nn_meta/validation/`:

- `v7-other-instruments-20260917-renames`
- `v7-action-coverage-20260917-relevance`
- `v7-relevance-consumers-20260917`, three bound `v7-relevance-feature-check-*` stores
- `v7-relevance-tests-20260917`

Finite reviews: `V7_UNRELATED_RENAMES_20260917.json`; named acquisition requests
and timeout fallbacks: `V7_UNRELATED_RENAME_*_20260917.json`. Three new notices
are retained under `nn_meta/data_v7/unrelated-rename-notices-20260917`. Both Banzai
issuer-domain attempts timed out; the captured exchange-hosted issuer release
provides the evidence. Shared acquisition usage is 63,057,207,992 bytes, with no
reservations. Earlier current-history and price-action artifacts remain valid;
use the new coverage output after the auditor source change.

## Separate cash-flow decision accepted

`V7_STOCK_CASH_LEDGER_PROPOSAL_20260917.json` records the concrete proposal for
held cash distributions. Of 4,392 compiled cash events, 4,337 have agreeing ex,
record and pay dates with no flagged due-bill chronology. The remaining 55 need
separate review (41 pay-date issues, 13 record-date issues and one date/due-bill
case). The user explicitly accepted the pre-tax receivable model with
spendable cash at the first captured regular open after the agreed pay date and
zero modeled withholding. The active policy is `V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`. This
separate decision is settled; implementation and consumer verification are next.
No cash entitlement has yet been executed under it at this milestone.
