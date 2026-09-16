# Handoff — continue V7; leave V6 unchanged

Updated September 16, 2026 after the full daily option-surface build.
Read TODO.md then this file. No subagents. Main branch; preserve unrelated dirty
V6 files. Use `./venv/bin/python`; consult DOCUMENTATION.md Traps before fixes.

## User direction and goal

Continue autonomously until full-scope V7 is ready, then alert the user. The
persistent readiness goal is still active and unfinished. The user accepted
[the V6 incident/SEDG explanation](docs/reviews/2026-09-16-v6-pending-exits.md)
and explicitly directed us to leave the V6 experiment alone. No midpoint stops,
spread policy, runtime settings or deployment changes were adopted. Do not
restart that investigation. No full V7 training campaign has launched.

## Latest completed milestone: full option surfaces

Implementation: `nn_meta/v7/surfaces.py`, `scripts/build_v7_surfaces.py`.
Read [full build, assumptions and verification](docs/reviews/2026-09-16-v7-full-surfaces.md).
Output `nn_meta/validation/v7-surfaces-20260916r2`:

- 1,129 completed day shards; 669,749 raw ticker/date rows.
- All 339,640 eligible sessions and 591 identities reconcile exactly.
- 339,517 rows with admitted options, 59 missing stock observations,
  49 observed-stock/no-option rows and 15 with no qualifying tenor/premium.
- Missing near IV 30,447, far IV 44,678, put/call ratio 177; no filling.
- Exact active raw option receipt/audit lineage, original stock facts and all
  next-session integer clocks verified; 58 scalar parity checks over 12 dates.
- Summary SHA256 `c5ae589033a8262d0b914a3fd1e0553cff52232aa0e12193540db4c957d3da0e`.
  Full completed resumption left it byte-identical.

Audit: `nn_meta/validation/v7-surfaces-verification-20260916.json`; exact source,
build/resume/test logs and resource observations are retained beside the output.
Build, audit, resume and tests all ended successfully. **No jobs remain running
from this continuation.** Full suite: **1,824 tests +18 subtests**, 18 warnings,
108.99 seconds, `/tmp/v7-surfaces-20260916r2-tests.log`; no code changed afterward.

The first invocation failed before any option-day output because the stock
calendar ended September 14. Its completed stock index is retained at
`nn_meta/validation/v7-surfaces-20260916`, with an old source binding; don't reuse
it under the new code. Fresh Alpaca calendar capture:
`nn_meta/data_v7/exchange-calendar-20260916` (1,464 sessions, 2021–October 2026).
Raw API records exactly match the original calendar throughout shared coverage.
The extended capture supplies September 15 availability for September 14 facts;
it adds no out-of-scope stock/options data or labels. Original bytes, request,
capture metadata and exact source retained. This is an **exchange calendar,
not settlement/physical-exercise calendar evidence**.

Latest shared quota **62,558,385,604 /250,000,000,000 bytes**, reservations empty.
Do not reset it. Derived surface output approximately 101 MiB before logs.
Four workers, one inner thread; host samples >23 GiB available RAM. Swap-in rose
and swap-out stayed constant between samples, but attribution is unknown.
No full no-swap/resource or V6-coexistence gate is claimed.

Surface assumptions remain declared fixed European BS proxies (1–45 DTE,
minimum $0.20, abs log moneyness <0.01, near <=20DTE, r=.0425/q=.012).
They are not observed IV, executable prices, or option deliverable/alias proof.
Literal raw ticker facts outside membership have no inferred security identity.
Receipts retain `research_ready: false`; full daily-context admission is open.

## Preceding stock daily milestone

Pushed commit `cddede8` built `nn_meta/validation/v7-stock-daily-20260916`:
2,966 symbol/year shards, 594 source tickers, 669,749 raw calendar rows; all
339,640 eligible sessions/591 identities, 67 verified aliases and 59 zeros.
[Review and complete command](docs/reviews/2026-09-16-v7-full-stock-daily.md).
Raw Alpaca regular-session OHLCV; close is last observed minute, not official
auction. Exact nullable observation clocks; no missing-day fills or inferred
identity outside membership. Independent full audit and completed resume passed.
Summary SHA `e59e2259259c95c524bc493a889663a5a897f156400e0d6a316de2f54d94e8ea`.
Audit `nn_meta/validation/v7-stock-daily-verification-20260916.json`.

**Next concrete daily work:** implement causal daily-return/context integration
from these raw facts and reviewed action/identity evidence. Full-security
surfaces now exist. `scripts/build_v7_daily.py` is an old SPY-only adjusted-price
pilot and must not stand in for the causal/full-universe builder. Keep initial
March 15 warmup missing; do not infer pre-membership identity from raw ticker
history. Market/sector alignment and all 222-column assembly remain unfinished.

## Other implemented components and unresolved sources

- Causal feature/proposal pilot `2e8ac37`: real AAPL March 15–May 10, 2022,
  all 11,268 variants, 757,465 proposals, 111 TV/technical columns. Original
  Apple April 28 $0.23 dividend announcement and prior $156.81 raw close.
  [Review](docs/reviews/2026-09-16-v7-causal-feature-pilot.md). Full-universe action
  evidence and integrated throughput still open; never relabel this as 222 columns.
- Alpaca quote adapter `d4252dc`: actual AAPL May 5, 2022 pilot, 20,628 quotes;
  exact clocks, SIP asof=-, firm R quotes, size/tie guards, latency/deadline,
  bounded archive reuse. [Review](docs/reviews/2026-09-16-v7-stock-quotes.md).
  Historical round-lot/share units require dated evidence. Full demand and
  funded physical replay remain open. `010134e` fixed bank-holiday event T
  handling; do not move covered trading T forward before counting settlement days.
- Model runner `8097c08`: `nn_meta/v7/trials.py`, CLI `run_v7_model_pilot.py`,
  `V7_MODEL_TRIALS_20260916.json`; 21 predeclared initial trials (three objectives,
  constant baseline, NN/GBT seeds 11/29/47). Train-only preprocess/weights,
  immutable source/runtime binding, model reload parity, verified resume;
  validation does not early-stop/select/calibrate. [Review](docs/reviews/2026-09-16-v7-model-trials.md).
  Synthetic tests only; bounded pilot <=65,536 rows/split, full runner missing.
  Old March-7 factorized v1 pilot is outside active scope; never reuse/relabel.

Official settlement/expiration calendar is still unfinished. Read
[OCC capture findings](docs/reviews/2026-09-16-v7-occ-calendar-sources.md) before
repeating failed attempts. OCC annual notices 49729/51460/53701/55737/57897,
special January 2025 55826 and T+1 54580 were readable through web text but all
seven raw PDF requests hit Cloudflare 403. No browser available; no raw original
receipts. FINRA Jan 3, 2025 contrary-cutoff HTML did capture (91,562 bytes).
DTCC original URLs returned 404; FINRA/DTCC 2023 Veterans Day conflict remains.
A nominal 2025 Nasdaq URL currently serves 2026 PDF; don't infer vintage from URL.
No calendar admitted. Requests `v7-occ-calendar-requests-20260916.json`, captures
`nn_meta/data_v7/occ-calendars-20260916`. All acquisition attempts ended.

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
`handoff-history/HANDOFF-2026-09-16-before-full-surfaces.md`.
