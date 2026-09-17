# Handoff — V7 item 6-1: finish usable identity/action histories

## Goal and current instruction

Make V7 ready to train for March 15, 2022–September 14, 2026 under the agreed
feature, execution, source and resource constraints. The user reviewed the
[three-day report](docs/reviews/2026-09-17-three-day-goals-and-progress.md) and
selected its section 6 as the sequential plan. Read [TODO](TODO.md) first.
**Work on 6-1 now. Items 6-2 through 6-7 remain queued and unchecked.**

This replaces the September 17 review pause with the user's numbered workflow.
This session only reorganized documentation; it did not finish 6-1, launch a job,
or resume the old broad campaign. Older autonomous/parallel work instructions
must not expand the current item. Preserve V6 paper operation.

## 6-1 deliverable and completion evidence

**Complete usable identity/action histories under an agreed admission policy.**
Closure requires every relevant security/session/action to have an explicit
resolved treatment, consumed by the actual feature and held-position paths.
An inventory, additional source download, selected-symbol pilot, or passing
component test alone does not finish this item.

Start with report sections 3A and 3B and existing implementation. Use the
current worktree and saved artifacts as evidence; do not restart the full audit.

1. Reconcile the existing exception sets and their affected consumers: the 186
   eligible identity/source mismatches, relevant lifecycle/rename boundaries,
   59 explained zero-bar sessions, unconsumed action records, and SPY actions.
   Group shared causes so fixes address classes of cases rather than repeating
   individual investigations. Include the captured FISV/FI June 7, 2023 routing
   evidence where needed for continuity outside entry membership.
2. State the applied admission rules, including ordinary cash/splits, duplicate
   provider records, combined/complex actions, identity continuity and no-event
   intervals. Use existing contracts and evidence first. Record a real policy
   decision in DECISIONS; do not silently weaken causality, exclude more issuers,
   or impose new broad publication-collection requirements. If a material scope
   choice requires the user, identify that exact choice and affected records.
3. Finish scalable compilation and dated identity/action treatment over the
   required scope. Retain original source IDs, dates, units and missingness.
   Do not fill absent prices or treat an absent provider record as proof of no
   action. Additional capture must serve an exact missing required input.
4. Connect the resulting history to the real causal-feature and held-position
   consumers so their treatment is executable. Exercise boundary cases and
   reconcile a full scoped census: totals, consumed groups, explicit treatments,
   remaining unsupported cases and their effects. A failure must stay visible;
   labeling it explained or unresolved alone is not closure. Full daily/feature
   production belongs to 6-2; full option/physical execution belongs to 6-4.
5. Verify 6-1's stated scope and consumer behavior, run checks appropriate to
   the changes (including the repository suite for code changes), and save
   reproducible evidence in a dated 6-1 review. If a prerequisite is still missing,
   keep 6-1 open and name it precisely.

## Existing evidence and paths — reuse these

- Active contract: `docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`.
  Scope: `docs/specs/MULTITIMEFRAME_RESEARCH.md`.
- Security histories: `nn_meta/validation/v7-security-history-20260916`;
  591 securities, 593 tickers, 1,129 sessions, 667,239 history rows.
  339,454/339,640 eligible sources match; 186 remain explicit.
  Stock session presence is 339,581/339,640; 59 absences have retrospective
  explanations, not automatic execution admission.
  [Security-history review](docs/reviews/2026-09-16-v7-security-history.md).
- Action inventory: `nn_meta/validation/v7-action-inventory-20260916r2`;
  10,380 provider records, 5,030 symbol/day cash-or-split groups, 213 complex
  records. Compiled cash: `nn_meta/validation/v7-compiled-cash-actions-20260916`;
  19 events (18 AAPL and one DVN), consuming 40 provider records.
  The other 10,340 records are not 10,340 distinct events. SPY has 36 unresolved
  cash-provider records. [Inventory review](docs/reviews/2026-09-16-v7-action-inventory.md)
  and [cash integration](docs/reviews/2026-09-16-v7-cash-action-integration.md).
- Main modules: `nn_meta/v7/security_history.py`, `identity_panel.py`,
  `identity_review.py`, `action_inventory.py`, `cash_actions.py`,
  `causal_prices.py`, `causal_features.py`, `causal_daily.py`, `lifecycle.py`.
  Their matching scripts/tests already exist; inspect the relevant consumers.
- Read DOCUMENTATION's Traps and V7 identity/action sections before changing
  apparent anomalies. Raw daily/surface/sector and retained publication sources
  are indexed by the report; do not reacquire completed inventories.

## Constraints and preserved implementation

Alpaca-only stocks; Massive options; no OTC. BBBY/FRC/REV/SI remain excluded
without replacement or reranking. Preserve all 20 families, 11,268 variant/TF
combinations, 222 columns, chronological folds and raw execution prices.
Preserve arithmetic option midpoint pricing, costs, V7 12.5% premium stops,
strategy exits, ITM 15-minute expiry cutoff and funded physical fallback.
At most four outer workers and one inner thread; retain 100 GiB disk reserve.
The 250 GB acquisition limit is a ceiling, not a target. Last verified quota
was 63,043,400,695 bytes with no reservations; recheck before a needed acquisition.

V7 has no full training dataset or trained model. Latest saved readiness:
`nn_meta/validation/v7-readiness-20260917-entry-demand.json`, three foundational
passes and eight substantive stages unpassed. Do not claim training is close
from partial progress. Full readiness is item 6-7.

Preserve uncommitted assembly implementation: `nn_meta/v7/assembly.py`,
`nn_meta/v7/dataset_inputs.py`, `scripts/build_v7_dataset.py`,
`tests/test_v7_assembly.py`. It is not a full production build. Its
[review](docs/reviews/2026-09-17-v7-dataset-assembly.md) records the last full suite:
1,976 tests +18 subtests passed, 18 warnings, 122.33 seconds. Those are historical
results, not validation of future edits. Preserve other dirty/untracked V6 work;
no blanket staging, reset or cleanup.

The last host check found no running V7 jobs. Old research units were terminal;
the old short-DTE progress timer was disabled/stopped. No jobs were started by
this docs update. Existing V6 monitoring remains separate. Its known fresh-quote
problem and sent-notice findings are in report section 4; no side-track repair,
policy change or notice resend is part of 6-1.

## Finish the item, then advance the handoff

When 6-1 passes its full completion evidence: check 6-1 in TODO, link the evidence
review, update ROADMAP/DOCUMENTATION and DECISIONS if needed, archive this HANDOFF,
and write a fresh handoff for **6-2: complete causal daily/market context and full
feature/proposal stores**. Commit/push only scoped changes on main. Repeat this
pattern through 6-7; do not advance on an incomplete item or launch later work
before documenting the current closure. A context limit keeps the handoff on
6-1 with exact remaining work; it does not justify declaring completion.

The prior overlapping TODO and review-pause handoff are archived as
`handoff-history/TODO-2026-09-17-before-report-sequence.md` and
`handoff-history/HANDOFF-2026-09-17-before-report-sequence.md`.
The report remains an unchanged dated record of the review, not live task state.
