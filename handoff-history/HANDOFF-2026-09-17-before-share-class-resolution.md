# Handoff — V7 item 6-1: ordinary-action policy implemented

## Current instruction and authorized policy

Make V7 ready to train through the seven-item sequence in [TODO](TODO.md).
**6-1 remains current and unchecked. Items 6-2 through 6-7 remain queued.**

The user explicitly answered the admission question: **accept matching provider
terms as historical reconstruction inputs, applied only from the effective
session; retain the assumption explicitly and separately review conflicts/complex
actions.** The question is resolved; do not ask again or impose individual
publication capture on these ordinary matching groups. The decision is recorded
in DECISIONS and `docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json`.
This does not approve missing identities, duplicates, combined/complex events,
no-event intervals or inferred stock/option entitlements.

6-1 closes only when every relevant security/session/action has an executable
resolved treatment consumed by real feature and held-position paths. An event
compiler or selected-boundary check alone does not finish it. Preserve V6 paper
operation and unrelated dirty work.

## Completed this session

`nn_meta/v7/ordinary_actions.py` and `scripts/compile_v7_ordinary_actions.py`
compile the authorized policy from retained original sources, full selected
security histories and existing publication reviews. `ReconstructionAction`
subclasses `PriceAction`; the existing causal prices, daily returns, feature
and proposal-basis consumers accept it. Its effective-open availability is
explicitly assumed, with null publication availability and
`publication_verified=false`. Persist the additional policy/basis fields;
`ordinary_actions.price_action` loads envelopes without erasing them.

Full inventory result: **4,429 events /315 security IDs**, comprising **4,410
reconstructed events (4,325 cash, 85 split)** plus **19 unchanged publication-
reviewed events**. All **18 SPY distributions** compile. **8,860 of 10,380 original
provider records** are consumed exactly once; **1,520 remain explicit**. The
reviewed Devon $0.44 correction wins once; no source records are summed into it.

All 4,429 events passed actual adjacent daily-return/as-of-price checks against
50-digit decimal calculations; maximum absolute error 1.2351231148954867e-15.
All pre-event prefixes are unchanged. Real SPY March 18, 2022 and NVDA June 10,
2024 minute-data checks each consume 780 observed minutes, build two 15-minute
feature epochs and persist the assumption in the feature-store declarations.
These are boundary checks, not full daily/context or feature production.

Focused tests: 37 passed. Full suite: **2,010 tests +18 subtests passed**, 18
warnings, 125.10 seconds. No production code changed after the suite. All
launched commands finished. No acquisition, V6 change, deployment, full research
campaign or training launch occurred.

[Review, census, commands and limits](docs/reviews/2026-09-17-v7-ordinary-action-admission.md).
New artifacts under `nn_meta/validation/`:

- `v7-ordinary-actions-20260917`: policy, actions, all 5,030 group treatments,
  1,520 unresolved original records/reasons and verified source bindings.
- `v7-ordinary-action-consumers-20260917`: all 4,429 numerical/prefix checks,
  record partition, retained verification source and boundary integration report.
- `v7-ordinary-action-feature-check-20260917-SPY` and `...-NVDA`: actual bounded
  feature stores; all ten subreceipts and declared code sources reverified.
- `v7-ordinary-actions-tests-20260917`: retained full-suite log and changed-code hashes.

## Exact remaining 6-1 work

1. **Identity/lifecycle treatments.** The full selected history still has 186
   eligible identity/source mismatches across 16 symbols: 104 conflicting FIGIs,
   33 missing FIGIs (CCL/SWTX) and 49 absent listing/detail-404 sessions. Of these,
   133 have raw observations. Do not route them by ticker while bypassing identity.
   The 59 zero-bar sessions overlap 53 mismatches: **192 distinct eligible
   exception sessions**. Retrospective explanations cover 41 cash-merger,
   14 stock-successor and four halt sessions; held-position treatment is not
   yet executable. Reuse `v7-6-1-routing-verification-20260917` for exact dates,
   grouped counts and source receipts.
2. **Remaining matching groups.** Of 4,506 ordinary matching groups, 4,410 are
   reconstructed, 18 retain Apple publication reviews, 70 lack a selected
   effective-day identity and eight lack adjacent continuity. Exact groups are
   in the new compiler's `groups.json`. The 70 include B/BMNR/BOIL/FB/FIG/FIGR/
   GAP/GOLD/LABU/SBET/SIRI/SPCX/TMF/UVIX/XOM/YINN; inspect dated identity and
   lifecycle scope before using a ticker's event for the wrong security.
   Five adjacent cases are APLD/BYND/LAZR/SOXS/SST. Three are KSS/LRCX/TMO cash
   events on March 15, 2022, whose prior day lies outside the selected history
   panel. Resolve actual consumer need; do not expand acquisition automatically.
3. **Other action groups.** Remaining simple groups total 601: the 78 above,
   354 unreviewed units/terms, 68 single-provider, 57 requiring combined review
   and 44 mismatches. There are also 213 complex records. Provider records are
   not distinct events; preserve the full original-record partition and review
   whole event groups. New ordinary matching policy does not admit these cases.
4. **No-event and held-position paths.** Finish explicit coverage over required
   histories and executable stock entitlements, payment/settlement clocks,
   split and option deliverables, and lifecycle continuity. Alpaca queries are
   process-date bounded; an absent record is not proof of no event. A chart
   factor is not a cash ledger. Missing outcomes remain visible failures.
5. Reconcile all scoped security/session/action treatments in actual consumers.
   Only with full completion evidence check 6-1 and advance HANDOFF to 6-2.
   Full daily/features belong to 6-2; full option/physical execution to 6-4;
   only 6-7 establishes training readiness.

## Reuse prior sources and preserve scope

Active contract: `docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`;
full spec: `docs/specs/MULTITIMEFRAME_RESEARCH.md`.

- `v7-security-history-20260917-routes`: current full selected history, 667,239
  rows /591 securities /1,129 sessions, 606 spans, eight ticker transitions,
  614,116 observed rows and zero ambiguous listed-source days. Retains the
  reviewed FISV/FI June 7, 2023 correction outside entry membership.
- `v7-source-routes-20260917`: 68 reviewed routes; all 67 earlier routes retained.
- `v7-daily-identity-panel-20260916`, `v7-identity-discrepancy-review-20260916`,
  `v7-lifecycle-no-otc-20260916`: retained original identity/lifecycle evidence.
- `v7-action-inventory-20260916r2`: original 10,380 records /5,030 simple groups.
- `v7-normalized-cash-reviews-20260916`, `v7-compiled-cash-actions-20260916`:
  retained 18 Apple publication reviews and one corrected Devon event.
- Raw daily/surfaces: `v7-stock-daily-20260916-midpoint` and
  `v7-surfaces-20260916-midpoint`. Do not overwrite historical artifacts.

March 15, 2022–September 14, 2026; Alpaca stocks, Massive options, no OTC.
BBBY/FRC/REV/SI remain excluded without replacement/reranking. Retain 20 families,
11,268 variant/timeframe combinations, 222 columns, causal inputs, chronological
folds, raw execution prices, arithmetic option midpoints, separate costs, V7
12.5% premium stops, strategy exits, ITM expiry cutoff 15 minutes before regular
option close, funded physical fallback and shared-capital limits. At most four
outer workers, one inner thread, 100 GiB reserve, 250 GB acquisition ceiling.
No acquisition this session; recheck quota before any named necessary capture.

V7 has no full dataset or trained model. Saved readiness remains
`v7-readiness-20260917-entry-demand.json`: three foundational passes and eight
substantive stages unpassed. Preserve the uncommitted assembly implementation
(`assembly.py`, `dataset_inputs.py`, `build_v7_dataset.py`, `test_v7_assembly.py`)
and unrelated V6 edits/untracked files. No blanket staging/reset/cleanup.
Known V6 issues remain outside this task in the three-day report's section 4.

Prior handoff archived as
`handoff-history/HANDOFF-2026-09-17-before-ordinary-action-admission.md`.
