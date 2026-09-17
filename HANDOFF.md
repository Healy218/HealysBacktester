# Handoff — new option-risk rules; V7 proposal build integrated

Updated September 16, 2026. Main; no subagents; preserve unrelated V6 work.
Goal active and incomplete. No training launched. No build/download jobs live.

## Latest user execution instruction — implementation next

The user now explicitly requires V6 and V7 simulated option entries/exits at
(bid+ask)/2. Close on the strategy sell signal or on an option-premium midpoint
loss versus entry midpoint of **7.5% for V6, 12.5% for V7**. Replace the generic
5% underlying-stock stop; retain strategy sell signals. Costs are separate from
the midpoint return used for the threshold; retain the existing 0.15% per-side
bookkeeping allowance pending any further user change. User confirmed closing
ITM options **15 minutes before the option's regular close on expiration day**
when no earlier exit occurred. No guaranteed stop execution price is implied.

Acknowledged these semantics; implementation/deployment has NOT happened yet.
Do not mistake the existing midpoint-only deployment for this new risk policy.
Existing helper prefers a provided midpoint; the new explicit arithmetic-average
instruction needs a policy amendment. Completed paper history must remain intact.
V6 is explicitly in scope for this repair despite earlier preserve-V6 directions.
No need to ask the expiry timing again. Latest user also clarified useful data
work is welcome; the complaint was about unclear progress toward training, not
an instruction to discard necessary safeguards. Continue explaining outcomes and
remaining blockers, and avoid open-ended acquisition expansion.

Relevant code: options/paper_pricing.py; nn_meta/live/v6_portfolio.py;
nn_meta/live/v6_forward_inputs.py (currently simulator _SIM_KWARGS includes 5%
stock stop); scripts/run_v6_forward.py (currently rolls at expiry cutoff);
nn_meta/v7/proposals.py, execution.py, replay.py, portfolio.py. V6 runtime pricing
branch/checkouts and previous guarded deployment are documented below. Main has
unrelated/untracked V6 changes; production candidate must remain isolated.

## Completed V7 build integration

`nn_meta/v7/proposal_store.py` stores causal features once per action epoch and
bit-packs full variant signals. Bounded simulator batches consume the saved
signals with continuous strategy-stop state. It saves raw selection prices
separately, retains zero-signal variants and open/censored proposals, supports
dated entry/exit ticker routing, and checkpoints epochs and proposal batches.
`scripts/build_v7_proposals.py` consumes existing security histories, compiled
actions and raw Alpaca data; rejects unresolved action/identity inputs. Default
full-window dates, all four timeframes, four single-threaded workers maximum.
This stage still lacks PIT entry filtering, daily/sector/tick joins, selected
option demand, labels and full-universe admission. The serialized JSONL proposals
are too verbose for scaling; compact typed/factorized storage is the next storage
integration task. Do not scale this pilot's 888 MB JSONL layout blindly.

Actual AAPL March15–May10,2022 run `nn_meta/validation/v7-proposal-build-20260916r2`
completed all **11,268 variants**, producing **757,465 proposals**:
1m 598,944 /5m 108,354 /15m 34,156 /30m 16,011. Workers took
114.92 /37.60 /27.05 /24.15 seconds, peak RSS 896,120 /614,200 /581,084 /575,820 KiB.
Completed-run resume took 2.95–3.34 seconds per worker; all **736 receipts stayed
byte-identical**. Output 887,697,704 bytes. This proves component integration,
not full-history/universe readiness or new option-risk semantics.

Verification `nn_meta/validation/v7-proposal-build-verification-20260916`, receipt
`5aabbe6a7c23f43dc3f0315e3366562f74750a015562252ede44674192c916ff` retains all
receipts, source bindings, logs and exact verification source. Six new tests
cover all-family parity, dated rename routing, corrupted inputs, budgets and
injected interruption/recovery. Full suite **1,918 tests +18 subtests passed**,
18 warnings,107.65s. Log /tmp/v7-proposal-build-final-tests.log retained in evidence.
No production code edits after that passing run at this checkpoint.

Failed initial real build (`v7-proposal-build-20260916`, exec56880 terminal1)
computed features but reader compared JSON lists with runtime tuples. Fixed
using canonical runtime identities. Initial failing test logs preserved. Corrected
build60725 and fullsuite95467 terminal0; resume14303 terminal0. Do not restart them.
See docs/reviews/2026-09-16-v7-proposal-build.md.

## Previous build-priority and artifact context

## Latest user correction — controls the next work

The user challenged the endless additional data downloads: 250 GB is a ceiling,
not a target. We acknowledged that preparation had expanded into open-ended
reference audits instead of completing the build/training integration.

**No broad reference/news/issuer acquisition next.** All current downloads are
terminal. Use captured inputs to connect the full feature/proposal build, actual
quote demand, execution/labels, factorized assembly and training runner. Further
acquisition must fill a specifically identified required build input. Do not
substitute another inventory or audit for the executable full pipeline. Do not
silently waive causal correctness, missing labels, agreed features or validation.

Work order:
1. Integrate existing identity, action, sector and daily components into the full
   feature/proposal builder, preserving explicit unresolved cases. Resolve known
   exceptions using retained evidence. Do not require exhaustive issuer-web-page
   collection merely because the audit can be extended.
2. Derive actual selected-contract quote/trade intervals from those proposals;
   capture only missing required intervals, within the cap.
3. Complete execution/labels and bounded factorized assembly, connect the
   predeclared trials to the full training runner, and measure recovery/memory.
4. Run the integrated readiness checks; report readiness only when demonstrated.

## Completed data jobs — no live handles to resume

- Full daily listed-identity capture completed: 1,129 sessions, 5,645 shards,
  13,184,850 records. Root `nn_meta/data_v7/daily-identities-20260916`.
  Summary receipt `7e92e44cd8a7dee831bfdb5649bf1c4e01e94a44ceaf1a992bd4ad01edc39f4f`.
  Prior exec session 96839 is terminal successful; do not restart it.
- Full identity panel: `nn_meta/validation/v7-daily-identity-panel-20260916`.
  Receipt `f7705f7d5b721c239ff49f1155dccfce3075bb1136f6f98d7bf45b0200454a73`.
  669,749 raw rows, 632 listed IDs. Of 339,640 eligible rows, 339,454 match
  frozen membership IDs and 186 remain unresolved.
- Full stitched security histories: `nn_meta/validation/v7-security-history-20260916`.
  Receipt `4811ee662c712b532c663dda15b731f378f999e61a5f14b308ad9e121a3ee7da`.
  591 securities ×1,129 sessions =667,239 rows; 607 continuity spans;
  seven dated ticker changes; 614,115 observed rows, 53,084 no listed source,
  39 listed/no observations, one ambiguous source. These are full-calendar
  counts, not all eligible missing training rows. No action adjustment applied.
- Exact-day identity discrepancy review is retained at
  `nn_meta/validation/v7-identity-discrepancy-review-20260916`: 104 rows where
  daily/detail endpoints both differ from frozen membership, 33 missing FIGIs,
  49 absent listings/detail 404s, across 16 symbols. No automatic ID rewrites.
  All requests finished. Do not start a new broad identity capture.
- The one ambiguous history date is FISV/FI June7,2023. Both Nasdaq-hosted
  May25/June7 releases are already captured under
  `nn_meta/data_v7/public-actions-20260916/fiserv-20230525-nasdaq-release` and
  `fiserv-20230607-nasdaq-release`. They corroborate the switch to FI on June7.
  Use these existing sources if adding the full-history routing override; the
  old 67-row alias review is specifically eligible-session coverage and should
  remain unchanged. A new full-history routing review may include this extra day.
- Actual FB→META and GPS→GAP windows preserve eight raw closes, continuous
  identity and pre-rename prefixes using the existing reviewed alias mappings:
  `nn_meta/validation/v7-listed-rename-history-20260916`.
- Quota snapshot: 63,043,400,695 bytes used; **zero reservations**. 250 GB cap.
  No acquisition or test process is running. Failed original issuer/SEC Fiserv
  attempts are preserved; Nasdaq copies succeeded. No need to repeat downloads.

New consumer files: `nn_meta/v7/security_history.py`,
`scripts/build_v7_security_history.py`, `tests/test_v7_security_history.py`.
See [review](docs/reviews/2026-09-16-v7-security-history.md).
Full suite **1,912 tests +18 subtests passed**, 18 warnings, 93.92 seconds.
Log `/tmp/v7-security-history-tests.log`, retained with source hashes in
`nn_meta/validation/v7-security-history-tests-20260916`. No production code edits
after this passing run. V6 source/runtime unchanged this session.

## Preserved action/publication progress

- `validation/v7-action-inventory-20260916r2`: 10,380 records, 5,030 groups,
  213 complex events; full inventory review retained. Process-date absence is not
  no-event proof, and provider split ratios can encode spin-off adjustments.
- `validation/v7-cash-publications-20260916r2`: 286/4,975 cash actions matched,
  30 additional body matches, 4,689 unmatched. Article version clocks and exact
  source paragraphs are retained; generic body parser never infers missing years.
- All 18 AAPL issuer announcements captured. Dated news corroborates all 18 cash
  amounts and 17 record/pay pairs; May2023 news has amount only. Current issuer
  pages have later modification clocks. Full details in cash-publication review.
- `validation/v7-normalized-cash-reviews-20260916` and
  `validation/v7-compiled-cash-actions-20260916`: 19 reviewed events from 40
  provider records, 10,340 unresolved. Whole event group replaced once; exact
  prior Alpaca close and adjacent security IDs required. No full-security admission.
- DVN September13,2024 correction is **$0.44 total**, not one or three $0.22
  entries. Its factor is 0.9890027493126718 against prior $40.01 close.
- `validation/v7-cash-event-returns-20260916`: all 19 actual event returns and
  pre-event prefixes verified, max decimal-oracle error 5.915407053080912e-16.
  See [cash integration](docs/reviews/2026-09-16-v7-cash-action-integration.md).

## Current daily artifacts

Use `nn_meta/validation/v7-stock-daily-20260916-midpoint` (2,966 shards,
669,749 raw calendar rows, 339,640 eligible) and
`nn_meta/validation/v7-surfaces-20260916-midpoint` (1,129 days, 339,640 eligible).
All original values/missingness matched under new active-parent bindings:
`nn_meta/validation/v7-daily-rebuild-verification-20260916`.
`nn_meta/v7/causal_daily.py` has seventeen tests for ten daily features, effective
actions, gaps, nullable identity spans, beta and availability. Actual AAPL
40-session replay `nn_meta/validation/v7-causal-daily-aapl-20260916r2` passed
39 independent return comparisons and all 40 prefixes. Its earlier broad source
manifest is historical after adding the new action-inventory code; preserve,
revalidate if reused, never relabel. [Daily review](docs/reviews/2026-09-16-v7-causal-daily.md).

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

Current readiness `nn_meta/validation/v7-readiness-20260916-action-inventory.json`:
three input/membership/coverage checks pass; **eight full-universe stages remain
missing**. No full training, full no-swap/resource or V6-coexistence claim.
Acquisition quota is changing during the live daily-identity capture; see the
latest process snapshot above and `nn_meta/data_v7/quota.json`.

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
  `nn_meta/validation/v7-readiness-20260916-action-inventory.json`: three
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

Follow the build-first order at the top of this handoff. Existing causal/action,
lifecycle/physical, full quote, assembly/trial and integrated resource requirements
remain unfinished. Eight stage evidence artifacts are missing; an inventory or
successful download does not complete those stages. The original full campaign
runner is still absent. Implement and test the consumers instead of continuing
open-ended source collection.

No training campaign launched. V7 readiness goal remains unfinished; continue
autonomously until all gates pass and then alert the user. First-week maturity review
remains due on/after September 21.

Prior state archived at
`handoff-history/HANDOFF-2026-09-16-before-build-focus.md`.
