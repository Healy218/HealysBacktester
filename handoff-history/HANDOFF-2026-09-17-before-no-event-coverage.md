# Handoff — V7 item 6-1: exact-date identity resolutions consumed

## Current instruction and settled policy

Make V7 ready to train through the seven-item sequence in [TODO](TODO.md).
**6-1 remains current and unchecked; 6-2 through 6-7 remain queued.** Close 6-1
only when every relevant security/session/action has an explicit resolved
treatment consumed by actual feature and held-position paths.

The user explicitly accepted **matching provider terms as historical reconstruction
inputs, applied only from the effective session, with the assumption retained
and conflicts/complex actions separately reviewed**. This question is settled:
do not ask again or require individual historical publication captures for these
ordinary matching groups. The policy does not admit unknown identities, combined
or complex actions, no-event completeness or inferred stock/option entitlements.
See DECISIONS and `V7_ORDINARY_ACTION_ADMISSION_20260917.json`.

Preserve V6 paper operation and unrelated dirty work. No blanket staging/reset.

## Completed at this milestone

Retained original daily listing captures contain share-class FIGIs omitted from
the normalized panel. `share_class_history.py` and
`scripts/resolve_v7_share_class_history.py` apply **27 finite exact-date reviews
across 14 symbols**, matching an earlier scoped listing's share class, ticker,
exchange, type, market, locale, currency and issuer CIK. Original composite FIGIs
and record/capture hashes remain separate from canonical identities. No future
anchor, changed share class, absent listing or price filling is accepted.

The full history remains **667,239 rows /591 securities /1,129 sessions** with
598 continuity spans. It restores 23 observed dates and recognizes four listed
zero-observation dates; the other **667,212 raw rows** remain unchanged. There
are 614,139 observed rows, 53,057 without a selected listed source and 43 listed
rows without stock observations. Eligible identity matches improve by 24;
**162 mismatches remain (previously 186)**.

Recompiling the authorized ordinary-action policy admits four more splits:
BOIL 2024-11-07, LABU/TMF 2023-12-04 and YINN 2022-05-31. The new total is
**4,433 events /315 security IDs**: **4,414 reconstructed (4,325 cash /89 splits)**
plus **19 publication-reviewed events**. All **18 SPY distributions** remain.
**8,868 of 10,380 original provider records** are consumed; **1,512 remain
explicit**. Every prior 4,429 factor and clock is unchanged. Restored continuity
rebinds 47 event IDs without changing factors. The Devon correction still wins
exactly once. Effective-open availability remains an assumption, not publication.

All four new splits pass independent decimal daily-return checks and real-minute
causal feature/prefix checks. BOIL additionally builds a retained bounded feature
store. Prior all-4,429 numerical checks and SPY/NVDA feature checks remain valid
and preserved. None of these boundary checks constitutes full feature production
or a held-position ledger.

Focused tests: **33 passed**. Full suite: **2,034 tests +18 subtests passed**,
18 warnings, 125.01 seconds. No production code changed after the suite. All
launched commands finished. No acquisition, V6 change, deployment, full research
campaign or training launch occurred.

[Full evidence, dates, commands and limits](docs/reviews/2026-09-17-v7-share-class-identities.md).

## Current artifacts and integration rules

All names below are under `nn_meta/validation/` unless specified:

- **Current history:** `v7-security-history-20260917-share-class`; includes prior
  FISV/FI routing and the 27 resolutions. Output retains `provider_composite_figi`,
  `resolved_share_class_figi`, `identity_resolution` and its evidence hash.
- **Current actions:** `v7-ordinary-actions-20260917-share-class`; all 5,030 simple
  group treatments and 1,512 unresolved original records/reasons are retained.
  Use `ordinary_actions.price_action` to preserve policy/publication fields.
- `v7-share-class-consumers-20260917`: full raw-grid and old-action comparison,
  four real split checks, exact remaining eligible exceptions, retained verifier
  source and bound BOIL feature-store subreceipts.
- `v7-share-class-feature-check-20260917-BOIL`, `v7-share-class-tests-20260917`.
- `docs/specs/V7_SHARE_CLASS_IDENTITIES_20260917.json`: finite review source.
  Rebuild from **original** `v7-security-history-20260917-routes` plus cumulative
  reviews. The resolver rejects an already resolved baseline to avoid erasing
  older resolution evidence. Recompile dependent actions after history changes.
- Retain `v7-ordinary-action-consumers-20260917`, SPY/NVDA feature stores and
  `v7-ordinary-actions-tests-20260917` as prior consumer evidence.
- Source inventory/reviews: `v7-action-inventory-20260916r2`,
  `v7-normalized-cash-reviews-20260916`, `v7-compiled-cash-actions-20260916`.
- Identity/lifecycle sources: `v7-daily-identity-panel-20260916`, original captures
  at `nn_meta/data_v7/daily-identities-20260916`,
  `v7-identity-discrepancy-review-20260916`, `v7-lifecycle-no-otc-20260916`,
  `v7-source-routes-20260917`, `v7-6-1-routing-verification-20260917`.
- Raw data: `v7-stock-daily-20260916-midpoint`, `v7-surfaces-20260916-midpoint`.
  Preserve historical immutable artifacts; do not relabel or overwrite them.

## Exact remaining 6-1 work

1. **Identity and lifecycle.** The 162 eligible mismatches span ATVI 12, BLK 22,
   CCL 16, DISCA 14, DKNG 18, RKLB 4, SGEN 10, SIRI 15, SWTX 17, TWTR 1, VMW 5,
   X 7 and XOM 21. Exact rows are in the new consumer artifact's
   `remaining_eligible_identity_exceptions.parquet`. There remain 59 zero-bar
   sessions, overlapping 49 mismatches: **172 distinct eligible exception
   sessions**. CCL/SWTX have no matching share-class witness; remaining changed
   share classes cannot use this resolver. Prior explanations cover cash mergers,
   stock successors and halts; explanations alone do not execute held outcomes.
2. **Matching groups still blocked.** Of 4,506 matching ordinary groups, 4,414
   are reconstructed, 18 retain Apple reviews, **66 lack effective-day identity**
   and **eight lack adjacent continuity**. Exact groups are in current `groups.json`.
   These include ticker reuse/succession questions, not merely missing aliases.
   Seven GAP cash groups in 2025–2026 lack raw GAP history: retained GAP shards
   cover 2024 only, while GPS 2025/2026 have zero observations. Assess that named
   missing input before targeted acquisition; do not substitute GPS by ticker.
   Adjacent cases are APLD/BYND/LAZR/SOXS/SST and KSS/LRCX/TMO cash events at the
   March 15, 2022 study boundary. The latter need a prior session outside the
   selected panel. Resolve actual consumer need before expanding capture.
3. **Other action groups.** Remaining simple groups total **597**: the 74 above,
   354 unreviewed units/terms, 68 single-provider, 57 combined-review and 44
   mismatches. Also **213 complex records** remain. Records are not distinct
   events. Review whole event groups and preserve the full original partition;
   matching-ordinary policy does not admit these separate cases.
4. **No-event and held-position paths.** Finish coverage over required histories
   and executable stock entitlements, payment/settlement clocks, splits, option
   deliverables and lifecycle continuity. Alpaca queries are process-date
   bounded; an absent record is not proof of no event. A chart factor is not a
   cash ledger. Missing outcomes stay visible failures.
5. Reconcile the full scoped security/session/action treatments in actual
   consumers. Only then check 6-1 and advance to 6-2. Full context/features are
   6-2; full option/physical execution is 6-4; only 6-7 establishes readiness.

## Scope and workspace

Active contract: `docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`;
full spec: `docs/specs/MULTITIMEFRAME_RESEARCH.md`.
March 15, 2022–September 14, 2026; Alpaca stocks, Massive options, no OTC.
BBBY/FRC/REV/SI stay excluded without replacement/reranking. Preserve 20 families,
11,268 variant/timeframe combinations, 222 columns, causal inputs, chronological
folds, raw execution prices, arithmetic option midpoints, separate costs, V7
12.5% premium stops, strategy exits, ITM expiry cutoff 15 minutes before regular
option close, funded physical fallback and shared-capital limits. At most four
outer workers, one inner thread, 100 GiB reserve, 250 GB acquisition ceiling.
Recheck quota before any named necessary capture; no broad collection campaign.

V7 has no full dataset or trained model. Saved readiness remains
`v7-readiness-20260917-entry-demand.json`: three foundational passes and eight
substantive stages unpassed. Preserve uncommitted assembly files (`assembly.py`,
`dataset_inputs.py`, `build_v7_dataset.py`, `test_v7_assembly.py`) and unrelated
V6 edits/untracked files. Known V6 issues remain in the three-day report section 4.

Prior handoff archived as
`handoff-history/HANDOFF-2026-09-17-before-share-class-resolution.md`.
