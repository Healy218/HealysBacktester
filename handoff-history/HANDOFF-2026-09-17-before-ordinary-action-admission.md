# Handoff — V7 item 6-1: source routing landed; admission policy pending

## Current instruction

Make V7 ready to train under the seven-item sequence in [TODO](TODO.md).
**6-1 remains current and unchecked. Items 6-2 through 6-7 remain queued.**
The user asked to resume, then briefly interrupted and said to continue. That
continuation is not an answer to the outstanding corporate-action policy choice.
Preserve V6 paper operation and unrelated dirty work.

6-1 requires usable identity/action histories over every relevant security,
session and action, consumed by actual feature and held-position paths. An
inventory, selected-symbol check or component test does not close it.

## Completed this session

Added `nn_meta/v7/source_routes.py`, `scripts/compile_v7_source_routes.py`, the
reviewed `docs/specs/V7_SOURCE_ROUTES_20260917.json`, and eleven regression cases.
The compiler extends the existing alias artifact with a publication-backed
FISV/FI route on June 7, 2023. Both exact-day listings identify BBG000BJKPG0;
retained Nasdaq-distributed announcements precede the open. It selects FI's
385 observed minutes, preserves raw observations and missingness, and feeds the
unchanged full security-history builder through its existing `--aliases` input.
All 67 earlier alias rows are preserved. No membership or option-deliverable
admission is inferred.

Full rebuild: 667,239 rows, 591 securities, 1,129 sessions, 606 identity spans,
eight ticker transitions, 614,116 observed rows, **zero ambiguous listed-source
days**. The 186 eligible mismatches remain; the corrected day is outside entry
membership. Other-security data, the pre-transition prefix and subsequent raw
facts are unchanged. Old source-selection evidence hashes correctly change
because they bind the extended alias receipt; independent verification checks
those hashes separately.

[Review, commands and admission alternatives](docs/reviews/2026-09-17-v7-6-1-source-routing.md).
New artifacts under `nn_meta/validation/`:

- `v7-source-routes-20260917`: 68 reviewed routes.
- `v7-security-history-20260917-routes`: current routed full history.
- `v7-6-1-routing-verification-20260917`: full comparison, exact exception rows,
  grouped dates/counts, Fiserv boundary and retained verification source.
- `v7-source-routes-tests-20260917`: retained full-suite log and changed-code hashes.

Validation: 20 focused tests passed; **1,987 tests +18 subtests passed**, 18
warnings, 124.14 seconds. No production source changed after the suite. All
launched build/test commands finished. No acquisition, V6 runtime change,
deployment or training launch.

## Pending policy question — do not assume approval

An asynchronous question asked whether the 4,506 ordinary matching provider
cash/split groups may be admitted as explicitly assumed historical reconstruction
inputs from their effective sessions, or whether each event must retain its own
pre-event publication evidence. No answer has been received at this checkpoint.
The current stricter standard remains applied.

These comprise 4,409 cash and 97 split groups, including SPY's 36 records as 18
matching cash groups. Eighteen Apple groups already have separate publication
reviews. Accepting provider agreement as historical reconstruction would be a
material admission-policy amendment: record an explicit user choice in DECISIONS
and preserve missing publication vintage. Do not silently manufacture an
`available_at` claim from a retrospective capture. The review describes both
alternatives concretely.

Neither alternative resolves combined/complex actions, duplicates, unknown
units, changed FIGIs or no-event intervals. Alpaca requests are process-date
bounded; an absent provider record is not proof of no event. Continue independent
identity/lifecycle work while awaiting an answer. Do not broaden collection or
add issuer exclusions to make the gate pass.

## Exact remaining 6-1 work

1. Resolve dated identity and lifecycle treatments and consume them in feature
   and held-position paths. The 186 eligible mismatches span 16 symbols:
   104 conflicting FIGIs, 33 missing FIGIs (CCL/SWTX), and 49 absent listing/detail
   404 sessions. **133 have raw stock observations**; do not route these by ticker
   while bypassing identity. Exact grouped dates and source receipts are in the
   new verification artifact. The 59 zero-bar sessions overlap 53 mismatches,
   giving **192 distinct eligible exception sessions**, not 245. Retrospective
   explanations cover 41 cash-merger, 14 stock-successor and four halt sessions;
   held-position entitlements/fills/settlement remain unresolved.
2. Apply the agreed ordinary-action admission standard when answered. Complete
   scalable compilation using original IDs/dates/units and dated identities,
   retaining reviewed whole-group replacements exactly once. The prior compiler
   consumes 40 provider records into 19 cash events; 10,340 records remain
   unconsumed, including 213 complex records. Records are not distinct events.
   There are 524 simple groups outside the matching-single-event class.
3. Resolve combined actions, splits versus spin-off adjustment ratios, identity
   transitions and complete no-event coverage under explicit evidence rules.
   Additional captures must serve a named missing consumer input.
4. Connect completed histories to real causal features and held positions;
   reconcile the full scoped census and boundary behavior. Missing outcomes
   remain failures, not invented closes or assumed entitlements.
5. Only on full closure check 6-1, update the evidence/docs, and advance HANDOFF
   to 6-2. Full daily/feature production belongs to 6-2; full option/physical
   execution belongs to 6-4; only 6-7 establishes training readiness.

## Reuse existing sources and preserve scope

Active contract: `docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`;
full spec: `docs/specs/MULTITIMEFRAME_RESEARCH.md`. Source paths:

- Original history `v7-security-history-20260916` remains historical evidence;
  use `v7-security-history-20260917-routes` for the newly routed panel.
- `v7-daily-identity-panel-20260916`, `v7-identity-discrepancy-review-20260916`,
  `v7-lifecycle-no-otc-20260916` retain underlying identity/lifecycle evidence.
- `v7-action-inventory-20260916r2`: 10,380 records, 5,030 simple groups.
- `v7-compiled-cash-actions-20260916`: 18 AAPL events and one corrected DVN event.
- Raw daily/surfaces: `v7-stock-daily-20260916-midpoint` and
  `v7-surfaces-20260916-midpoint`. Retain original hashes and receipts.

March 15, 2022–September 14, 2026; Alpaca stocks, Massive options, no OTC.
BBBY/FRC/REV/SI remain excluded without replacement or reranking. Preserve all
20 families, 11,268 variant/timeframe combinations and 222 columns. Keep causal
inputs, chronological folds, raw execution prices, arithmetic option midpoints,
separate costs, V7 12.5% premium stops, strategy exits, ITM expiry cutoff 15 minutes
before regular option close, funded physical fallback and shared-capital limits.
At most four outer workers, one inner thread, 100 GiB reserve, 250 GB acquisition
ceiling. No acquisition this session; recheck quota before any needed capture.

V7 has no full training dataset or trained model. Latest readiness remains
`v7-readiness-20260917-entry-demand.json`: three foundational passes and eight
substantive stages unpassed. Preserve the uncommitted assembly implementation
(`assembly.py`, `dataset_inputs.py`, `build_v7_dataset.py`, `test_v7_assembly.py`)
and all unrelated V6 edits/untracked work. No blanket staging/reset/cleanup.
Known V6 issues remain in section 4 of the three-day report, outside this task.

Prior handoff archived as
`handoff-history/HANDOFF-2026-09-17-before-source-routing.md`.
