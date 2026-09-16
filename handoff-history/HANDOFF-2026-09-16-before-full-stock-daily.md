# Handoff — continue V7; leave the V6 experiment unchanged

Updated September 16, 2026 after the bounded model-trial milestone.
Read TODO.md then this file. No subagents. Work on main, preserve unrelated dirty
V6 work, consult DOCUMENTATION.md Traps before fixes, use `./venv/bin/python`.

## Latest user direction

The recurring V6 incident was diagnosed; see
[incident and SEDG explanation](docs/reviews/2026-09-16-v6-pending-exits.md).
Pending fresh exit quotes blocked entries; the observed 16:30–17:15 UTC
passes recovered. SEDG exited on its BBW stock signal, not its 5% underlying
stop. The user accepted the explanation and directed us to leave V6 as it
is and keep getting V7 ready. No proposed spread policy was adopted.

## Stock quote / settlement milestone

Committed `d4252dc` adds the bounded Alpaca SIP quote capture/replay adapter
and actual AAPL May 5, 2022 pilot (20,628 quotes). See
[implementation, evidence and outstanding settlement sources](docs/reviews/2026-09-16-v7-stock-quotes.md).
It includes dated round-lot/share conversion, exact clocks, receipt/identity
checks, size/condition guards and bounded archive reuse. Full demand and
funded physical replay remain unfinished. The subsequent settlement fix
accepts covered trading events on bank holidays without moving T forward.
Full suite passed **1,804 tests +18 subtests**, 18 warnings, 87.43s:
`/tmp/v7-settlement-event-20260916-tests.log`.

Readiness `nn_meta/validation/v7-readiness-20260916-stock-settlement-checkpoint.json`
still has eight missing stage artifacts. Official calendar is unfinished:
FINRA/DTCC 2023 Veterans Day conflict, unavailable DTCC original bytes, and
a nominally 2025 Nasdaq URL now serving a 2026 PDF must be resolved.
Do not admit a calendar from URL year or search snippets.

The bounded model-pilot runner is now implemented below. No full training launch.

## Runnable model trial milestone

Added `nn_meta/v7/trials.py`, `scripts/run_v7_model_pilot.py` and the predeclared
`docs/specs/V7_MODEL_TRIALS_20260916.json`: 21 initial trials (three objectives,
constant baselines, GBT/NN seeds 11/29/47). See
[model runner review](docs/reviews/2026-09-16-v7-model-trials.md).
Runs use identical purged folds, train-only preprocessing/weights, no calibration
or validation early stopping, fixed budgets, finite checks, exact model reload
predictions, immutable attempt records and verified resumption. Component binding
avoids recursive artifact-tree scans; full-campaign binding is unchanged.

Focused 15 tests passed; **full suite 1,813 tests +18 subtests**, 18 warnings,
92.31 seconds: `/tmp/v7-model-trials-20260916-full-tests.log`. This includes
actual NN/GBT fits for all objectives on synthetic test fixtures, not historical
performance. All test jobs ended. The pilot CLI limits each split to 65,536 rows;
full scheduling, 2024/2025 fold integration, calibration/threshold decisions,
portfolio baselines, multiple-testing diagnostics and resource gates remain open.
The old factorized v1/March-7 pilot was inspected and NOT reused or relabeled.

Next work: finish historical settlement-source coverage and funded observed
physical replay, or continue independent full-history daily/context integration.
No full training started. Shared quota now **62,557,919,862 /250,000,000,000
bytes**, reservations empty. Do not reset quota or overwrite immutable pilots.

Previous causal milestone (`2e8ac37`) remains preserved: all 11,268 variants
produced 757,465 proposals in actual AAPL March 15–May 10, 2022 action-aware
features. It had 111 columns, not full 222-column rows/execution. See
[causal review](docs/reviews/2026-09-16-v7-causal-feature-pilot.md).
Stock quote/settlement checkpoints `d4252dc` and `010134e` were pushed to main.

## Official calendar source follow-up

Model-runner checkpoint `8097c08` is committed and pushed. Then located original
OCC annual notices 49729/51460/53701/55737/57897 (2022–2026), special January
2025 notice 55826 and final T+1 notice 54580. Read
[exact source findings and failed capture status](docs/reviews/2026-09-16-v7-occ-calendar-sources.md)
before repeating research. Seven raw OCC downloads returned Cloudflare HTTP 403;
no browser is available. Web-reader text is not a local original PDF receipt.
FINRA January 3, 2025 contrary-cutoff HTML did capture successfully (91,562 bytes).
Request list `nn_meta/validation/v7-occ-calendar-requests-20260916.json`; output
`nn_meta/data_v7/occ-calendars-20260916`. All attempts ended. No calendar admitted.

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
  bounded pilot model trials are now runnable; the full campaign runner remains outstanding.

## Remaining V7 work

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

No training campaign launched. V7 readiness goal remains unfinished; continue
autonomously until all gates pass and then alert the user. First-week maturity review
remains due on/after September 21.

Prior state archived at
`handoff-history/HANDOFF-2026-09-16-before-occ-calendar-sources.md`.
Older dated-sector and no-OTC reviews retain additional provenance.
