# Handoff — V7 daily artifacts rebuilt; causal daily calculations verified

Updated September 16, 2026. Read TODO.md then this file. No subagents. Work on
main, preserve unrelated dirty/untracked V6 work and use `./venv/bin/python`.
The full V7 readiness goal remains active and unfinished; no training launched.

## Latest V7 progress

Previous goal turn made progress (midpoint implementation/deployment); this turn
rebuilt all affected daily parent artifacts and implemented/tested causal daily
calculations. Read [current review](docs/reviews/2026-09-16-v7-causal-daily.md).

Use these fresh outputs for downstream integration:
- `nn_meta/validation/v7-stock-daily-20260916-midpoint`: all 2,966 raw shards,
  669,749 calendar rows and 339,640 eligible rows; all old values identical.
- `nn_meta/validation/v7-surfaces-20260916-midpoint`: all 1,129 days and 339,640
  eligible rows; all old values/missingness identical, with new parent hashes.
- `nn_meta/validation/v7-daily-rebuild-verification-20260916`: all-row comparison,
  current input/source bindings and preserved exact verification source.

`nn_meta/v7/causal_daily.py` replaces the previously parked draft. Seventeen
new tests cover the ten daily features, effective actions, gaps, identity spans,
nullable identities, market beta and availability. Full suite **1,851 tests +18
subtests**, 18 warnings, 97.13s (`/tmp/v7-causal-daily-final-tests.log`).
`scripts/validate_v7_causal_daily.py` completed actual AAPL 40-session validation
at `nn_meta/validation/v7-causal-daily-aapl-20260916r2`: 39 independent return
comparisons (max error 7.8236e-16), all 40 prefixes unchanged. Original issuer,
provider, raw-stock payloads and source/runtime hashes are bound. Initial r1 is
preserved; use r2. No full-market identity/action admission is claimed.

All launched processes finished successfully; no build/test jobs remain. V6
runtime was untouched this turn. No acquisition quota was used. Readiness still
has eight missing substantive stages; do not launch training or call the goal
complete. Next is full identity/action evidence and causal context integration,
then remaining quote, physical execution, assembly, trial and resource gates.

## Latest explicit user direction overrides the earlier V6 freeze

After read-only replay proved rapid underlying-strategy exits with large option
spread losses, the user explicitly requested **one midpoint price for both
simulated option buys and sells in V6 and V7**. Use a valid supplied mid/midpoint
when present; otherwise average bid and ask. The user also mentioned `last`;
we clarified that it is reference data, not a substitute midpoint, and kept the
agreed midpoint convention. The earlier instruction to leave V6 unchanged was
superseded for this pricing change. No new spread cap or midpoint stop was added.

Read [midpoint implementation, evidence and deployment](docs/reviews/2026-09-16-midpoint-paper-pricing.md).
Shared helper `options/paper_pricing.py`, policy `option-midpoint-paper-v1`.
Entries, exits, both roll legs and option equity marks share the same base price;
quote sides and price source are retained, simulated fills labeled explicitly.
Existing 0.15% per-side total costs stay separate. Same unchanged quote gives
about -0.29955% after both sides, not the bid/ask spread loss. Model, strategy,
underlying stops, quote freshness and physical-stock pricing are unchanged.

## V6 production state

Tested candidate branch `ops/v6-midpoint-20260916`, commit
`4fe7e5fff512e3147f6dc5d17b04f61ea791f1ed`, was pulled into home runtime
`/home/healy/Coding/HealysV6` from previous `5787909`. Candidate checkout remains
`/tmp/healys-v6-midpoint-20260916`. All **1,574 tests +18 subtests** passed there,
16 warnings, 64.21s; copied-live-ledger migration and unchanged-quote tests passed.
The source-only activation amendment accepts exactly the reviewed quote/portfolio
modules plus the new helper; every other previously bound runtime source must
match. Activation SHA `dccdd2d167e18d28a23d53cd005e2d3161e9adc8f90cc863f41117f114fcfd56`.

Actual deployment stopped the forward timer, waited for any active pass, held
its lock, backed up SQLite/activation, pulled via Git, checked all hashes and
resumed the timer. All positions had closed before deployment: **zero live
entries needed repricing**. Closed history stayed byte-identical; realized paper
equity stayed 0.6867286044611687, with 13 closed records, 35 cycles and 26 exported
outbox items. No equity reset, broker order or manual test notification occurred.

Evidence `nn_meta/validation/v6-midpoint-20260916` contains copied-ledger reports,
actual before/after backups, activation and transition receipts, Git pull log,
exact one-off audit/deployment sources and complete test logs/XML. Migration is
idempotent and only rebases outstanding paper legs from their retained original
quote; previously completed legs/history/equity stay intact. Unmigrated legacy
open legs fail closed, avoiding an old-ask/new-midpoint comparison.

The post-deployment 20:00 UTC home pass **completed successfully** in 235.25s,
status `recorded`, phase `complete`, no error. All five selected entries were
unfilled, so no actual midpoint entry occurred during this pass. It recorded
cycle36, preserved 13 closed trades and the same equity/outbox, and reports the
midpoint execution policy. Saved `deployment/post-deployment-status.json` is the
terminal application evidence. The timer was resumed. The existing home relay
exports activation/status and original alert payloads; server expert/feed
settings were not changed by this producer-pricing deployment.
Read-only server verification also confirmed receipt of the new midpoint policy,
runtime commit `4fe7e5f`, successful cycle36 status and unchanged equity/history.

The generic alert reason `frozen underlying strategy/5% stop exit` is still not
an exact cause classifier. Previous replay of CELH/SIL/RH/AFRM/SNDK showed true
strategy exit signals and no generic 5% stock-stop breach. See
[read-only diagnosis](docs/reviews/2026-09-16-v6-late-exit-replay.md).
Pricing correction does not promise profitability or change those exit signals.

## V7 implementation and binding changes

Midpoint now flows through `QuoteTape.first_fill`, `QuoteTape.mark`, `CashLedger`,
`replay`, shared `portfolio_replay`, and physical-ledger option valuations.
Stock delivery/liquidation continues with observed Alpaca stock prices.
`QuotePolicy` declares `option_price_basis=option-midpoint-paper-v1`.
New `docs/specs/V7_PAPER_PRICING_20260916.json` is bound by active inputs;
readiness checks the policy against code and includes its hash in stage scope.
Previous evaluation folds remain fixed; the new quote-price policy supersedes
the older evaluation JSON's quote-price defaults.

Main full suite **1,834 tests +18 subtests**, 18 warnings, 91.33s:
`/tmp/midpoint-main-final-tests.log`, copied into midpoint evidence. No pricing
code changed afterward. The main checkout's untracked V6 source/tests were
updated to match the runtime candidate; preserve unrelated changes. Their
production commit is on the isolated runtime branch. Shared helper, V7 sources,
activation utility/test, policy and documentation are committed on main.

Current readiness `nn_meta/validation/v7-readiness-20260916-causal-daily-final.json`:
three input/membership/coverage checks pass; **eight full-universe stages remain
missing**. No full training, full no-swap/resource or V6-coexistence claim.
Acquisition quota remains **62,558,385,604 /250,000,000,000**, reservations empty.

The midpoint-related stock/surface parent-binding rebuild is complete in the
new paths above; all old outputs remain historical. Old ask/bid execution paths,
marks, labels and portfolios must still be recomputed, never relabeled.

The causal daily calculation module is now tested and the AAPL original-action
replay passed. It still requires reviewed full-security continuity and complete
original action/no-event evidence. Integrate these with market context and dated
sectors before claiming the daily stage. Preserve initial missing observations.
Do not route new full-history builds through historical `daily.daily_context`.

## Preserved component data (use new daily outputs above)

- Raw stock daily `nn_meta/validation/v7-stock-daily-20260916`, commit `cddede8`:
  2,966 symbol/year shards, 594 source tickers, 669,749 raw calendar rows;
  all 339,640 eligible sessions/591 identities, 67 aliases and 59 missing sessions.
  Summary SHA `e59e2259259c95c524bc493a889663a5a897f156400e0d6a316de2f54d94e8ea`.
  [Review](docs/reviews/2026-09-16-v7-full-stock-daily.md).
- Option surfaces `nn_meta/validation/v7-surfaces-20260916r2`, commit `0db94c9`:
  1,129 day shards, 669,749 raw ticker/date rows and all 339,640 eligible rows.
  339,517 observed-option rows, 59 missing-stock, 49 no-option and 15 outside
  tenor/premium filter; missing near IV30,447/far IV44,678/PC ratio177, no fill.
  Summary SHA `c5ae589033a8262d0b914a3fd1e0553cff52232aa0e12193540db4c957d3da0e`.
  All-row audit, 58 scalar checks and completed resume passed.
  [Review](docs/reviews/2026-09-16-v7-full-surfaces.md).
- Captured extended Alpaca exchange calendar
  `nn_meta/data_v7/exchange-calendar-20260916`: 1,464 sessions, 2021–October2026,
  exact agreement with original shared coverage; raw bytes/request/source kept.
  Enables September15 availability of September14 facts; no out-of-scope prices.
  This is **not settlement/exercise-calendar evidence**.
- Causal AAPL40-session pilot `2e8ac37`: 11,268 variants, 757,465 proposals,
  111 TV/technical columns; original April28 $0.23 dividend and prior $156.81 close.
  [Review](docs/reviews/2026-09-16-v7-causal-feature-pilot.md).
- Alpaca quote adapter `d4252dc`: actual May5,2022 AAPL20,628 quotes; exact
  clocks, conditions/sizes, bounded archive and dated lot/share-unit requirements.
  [Review](docs/reviews/2026-09-16-v7-stock-quotes.md). `010134e` corrected event-T
  bank-holiday handling. Full funding/settlement replay remains open.
- Model runner `8097c08`: 21 declared initial trials, three objectives,
  constant baseline, NN/GBT seeds11/29/47; train-only preprocess, reload parity,
  verified resumption. [Review](docs/reviews/2026-09-16-v7-model-trials.md).
  Synthetic tests only, <=65,536 rows/split pilot; full campaign runner incomplete.
  Old March7 factorized v1 pilot is excluded; never reuse or relabel.

Official settlement/expiration source work remains incomplete. Read
[OCC findings](docs/reviews/2026-09-16-v7-occ-calendar-sources.md) before retrying.
OCC annual notices 49729/51460/53701/55737/57897, special 55826 and T+1 54580 returned
Cloudflare403 for all raw originals; no browser available. Reader text is not a
local PDF receipt. FINRA Jan3,2025 contrary-cutoff HTML captured, DTCC originals
returned404, VeteransDay2023 conflict unresolved, nominal Nasdaq2025 URL serves
2026 PDF. No settlement calendar admitted or acquisition job left running.

## User constraints and fixed scope

**Alpaca-only stock prices/quotes; no OTC.** Massive remains the options source.
Drop entire BBBY/FRC/REV/SI security histories, no replacement or reranking.
This is a user-directed ex-post study restriction, not PIT-known eligibility.
Original unrestricted captures remain preserved.

March 15, 2022–September 14, 2026 inclusive; cold-start prices March 15, no
March 8–14 active price/options. Earlier references/membership and full exchange
calendar remain. Keep all 20 families, 2,817 variants per timeframe, four
1/5/15/30-minute timeframes, 222 columns, 13 TV scopes and 10 tick features.
Actual 1–9 DTE purchases with targets 1/2/4/5/7; observed quotes with modeled midpoint option fills/marks;
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
  `nn_meta/validation/v7-readiness-20260916-causal-daily-final.json`: three
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
`handoff-history/HANDOFF-2026-09-16-before-causal-daily.md`.
