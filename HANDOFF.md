# Handoff — diagnose recurring V6 error first; V7 remains unready

Updated September 16, 2026 at the user's request before clearing the session.
Read TODO.md then this file. No subagents. Work on main, preserve unrelated dirty
V6 work, consult DOCUMENTATION.md Traps before fixes, use `./venv/bin/python`.

## Immediate next task: V6 incident

User: “the v6 keeps giving an error despite starting the morning off ok.”
**New incident, not yet diagnosed.** Obtain the actual latest error and compare
successful morning versus failing cycle timestamps. Trace active home producer,
input refresh, relay, server consumer and dashboard before changing anything.
Read the V6 forward activation/runbook and ops scripts; do not assume the older
September 15 missing Massive option-minute file explains this new failure.
Preserve activated runtime and existing dirty files. No V6 settings or deployment
were changed in this V7 continuation. No test alerts/messages were sent.

## Latest V7 milestone

Previous pushed commits: `bc800f8` (no-OTC scope), `2c5273a` (dated sectors and
bounded preprocessing). This checkpoint adds causal feature/action epochs and
an actual AAPL dividend pilot; see
[complete review and exact commands](docs/reviews/2026-09-16-v7-causal-feature-pilot.md).

- New `nn_meta/v7/causal_features.py`: completed-minute, cold-start, action-aware
  chart prefixes, all TV/technical features and bounded per-epoch strategy
  signals. `bars.py`, `features.py`, `proposals.py` integrate shared aggregation,
  required source subsets and cross-action proposal stops. Execution remains raw.
- Real AAPL March 15–May 10, 2022: all 20 families, all 11,268 variants over
  1/5/15/30 minutes, all 13 TV feature groups; **757,465 proposals**.
  Output `nn_meta/validation/v7-causal-aapl-pilot-20260916`, all receipts verified.
  Captured original Apple announcement and pre-event identity; May 6 $0.23
  dividend factor uses prior raw Alpaca $156.81 close. No future cumulative factor.
- This pilot contains 111 feature columns, not the full 222-column assembly,
  quote labels, physical execution or training. All reports say not ready.
  Epoch recomputation per variant batch is still a throughput limitation.
- Full suite **1,786 tests +18 subtests passed**, 18 warnings, 91.01s.
  `/tmp/v7-causal-features-20260916-full-tests.log`. Includes existing dirty V6
  work. No code changes after that suite/pilot, only checkpoint documentation.
- Settlement research captures FINRA 2022/2023/2026 documents; four DTCC raw
  URLs returned 404. No implemented settlement calendar yet. Exact paths and
  candidate canonical URLs are in the review; trading calendar is insufficient.
- All jobs started by this continuation ended. Persistent V6/ops services are
  separate. Shared quota `nn_meta/data_v7/quota.json` is
  **62,556,214,251 /250,000,000,000 bytes**, reservations empty. Never reset it.
- Code/input/source bindings are strict. Preserve pilot history if future code
  changes invalidate bindings; do not overwrite or relabel immutable outputs.

## User constraints and fixed scope

**Alpaca-only stock prices/quotes; no OTC.** Massive remains the options source.
Drop entire BBBY/FRC/REV/SI security histories, no replacement or reranking.
This is a user-directed ex-post study restriction, not PIT-known eligibility.
Original unrestricted captures remain preserved.

March 15, 2022–September 14, 2026 inclusive; cold-start prices March 15, no
March 8–14 active price/options. Earlier references/membership and full exchange
calendar remain. Keep all 20 families, 2,817 variants per timeframe, four
1/5/15/30-minute timeframes, 222 columns, 13 TV scopes and 10 tick features.
Actual 1–9 DTE purchases with targets 1/2/4/5/7; observed execution/marks;
five shared slots, 10% equity premium and one symbol across timeframes.
Funded physical delivery and observed stock liquidation; missing funding/shares/
evidence stay unresolved, never free financing or synthetic intrinsic sales.
At most four outer workers, 100 GiB disk reserve, 250 GB shared acquisition cap.
Protect V6. No full training until every readiness gate passes; alert user then.

## Authoritative active inputs

`docs/specs/V7_ACTIVE_INPUTS_20220315.json` binds active artifacts.

- Universe `nn_meta/validation/v7-universe-no-otc-20260916`: 593 tickers,
  591 identities, 16,549 research membership rows.
- Plan `nn_meta/research_plans/v7-20220315-20260914-no-otc/plan.json`:
  6,681,924 ticker×variant combinations, exact active catalog.
  Hash `fa982cc6d715d277c8d204fd8b36e0ef789ecda146111e86a070ec9396184f1f`.
- Coverage `nn_meta/validation/v7-coverage-no-otc-20260916`: 339,640 eligible
  sessions, 126 original zeros, 67 aliases resolved, 59 remaining zeros.
- Lifecycle `nn_meta/validation/v7-lifecycle-no-otc-20260916`: 59 retrospectively
  explained (41 cash merger, 14 WBD successor, four halts); execution/PIT and
  held-position admission remain false.
- Sectors `nn_meta/validation/v7-sectors-20260916-final`: all 339,640 sessions,
  317,561 classified, 22,079 explicit unknown, no missing prior identity reference.
  Coarse dated SIC/business/fund groups, not GICS; provider reconstruction is
  not original publication proof. `SectorStore`/`DatedSectors` keep nine columns
  and provenance; full builder must consume them.
- Raw working root `nn_meta/data_v7/start-20220315`; chain
  `nn_meta/validation/v7-chain-start-20220315`. Conservative captures include
  excluded issuers: every downstream active job must filter active membership.
- Evaluation `docs/specs/V7_EVALUATION_20220315_PHYSICAL.json`: expanding
  2024H2/2025H1/2025H2 folds, final Jan 1–Sep 14, 2026; 10-session embargo,
  full settlement label ends. These periods were previously inspected.
- Last readiness checkpoint
  `nn_meta/validation/v7-readiness-20260916-sectors-checkpoint.json`: three
  input/inventory checks pass; eight substantive stage artifacts remain missing.
  Re-run `scripts/v7_readiness.py --output NEW.json` when new stage evidence exists.
- Corporate captures `nn_meta/data_v7/corporate-actions-20260915/{dividends,splits}`
  and `nn_meta/data_v7/alpaca-actions-20260915`.
- News `nn_meta/data_v7/dividend-news-20260916`: 1,047 complete requests.
  Audit `nn_meta/validation/v7-dividend-publications-20260916`: 256/4,967 amount
  matches, 4,711 unmatched; matches alone do not prove complete action semantics.
- Fold selection/loader and `preprocessing.py` implement immutable bounded reads,
  global duplicate checks, settlement purge, train-only moments/quantiles/weights
  and exact resume. `scripts/prepare_v7_training_fold.py` prepares inputs only;
  runnable model trials and complete training runner remain outstanding.

## Remaining work after V6 diagnosis

1. Apply aliases/lifecycle effects, WBD bridge and cash-merger/halts held-option
   execution; consume dated sectors in full history.
2. Complete original split/dividend/combined/spin-off evidence across securities;
   extend the now-piloted causal engine and cold-start daily/context integration.
3. Build real option quote/trade demand, dated option hours/weeklies and feasible
   capture under quota. Existing envelopes are conservative, not final admission.
4. Finish funded physical context, historical settlement calendar, Alpaca stock
   quote adapters and official expiration references; replay actual shared expiry.
5. Assemble full-history factorized rows/labels/marks and executable NN/GBT trials,
   predeclared seeds/objectives/calibration/weights, baseline and multiple-testing
   diagnostics. Old SPY-only daily/context pilot is not admitted full evidence.
6. Measure full binned memory, recovery, four-worker behavior and V6 coexistence;
   produce all eight stage artifacts and pass readiness before launching training.

No training campaign launched. V7 readiness goal remains unfinished; user asked
for this checkpoint so they can clear the session. First-week maturity review
remains due on/after September 21.

Prior state archived at
`handoff-history/HANDOFF-2026-09-16-before-causal-feature-pilot.md`.
Older dated-sector and no-OTC reviews retain additional provenance.
