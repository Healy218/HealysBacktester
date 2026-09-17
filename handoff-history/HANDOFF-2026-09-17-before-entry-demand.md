# Handoff — compact proposal and stored-row milestone verified

Updated September 17, 2026. Main; no subagents. Goal remains active and incomplete.
No training launched. All current test/build/audit/resume jobs are terminal. No
new downloads or V6 runtime changes this turn. Preserve unrelated dirty V6 work;
never blanket-stage, revert or reset this checkout.

## User intent and fixed scope

Finish V7 until ready to train, then alert the user. User acknowledged progress;
do not imply the remaining work is only one final check. March 15, 2022 through
September 14, 2026 inclusive; cold start March15, no March8–14 active prices.
All20families,2,817variants×1/5/15/30m =11,268;222columns,13TVscopes,10tickfeatures.
Alpaca-only stocks/quotes; Massive options. Entire BBBY/FRC/REV/SI excluded, no
OTC, no replacements or reranking.250GB is an acquisition ceiling, not a target.
Max4outerworkers,1innerthread,100GiB disk reserve; preserve V6 coexistence.

Arithmetic (bid+ask)/2 for option paper buys/sells/marks. V6/V7 option midpoint
loss stops7.5%/12.5% from purchased-leg entry midpoint; costs0.15%/side separate.
No generic5% underlying stop for held exits. Strategy signals retained. ITM expiry
exit15minutes before dated option-class regular close. A valid trigger quote
supplies sale midpoint directly; quote gaps remain explicit and retry. Original
quote and observation/execution clocks remain distinct. Existing OTM rolls and
funded physical-expiry fallback remain in scope. User already confirmed these.
Actual1–9DTE; targets1/2/4/5/7;5sharedslots,10%equity premium,one symbol acrossTF.
Folds2024H2,2025H1/H2;finalJan1–Sep14,2026;10session embargo through settlement.

## Completed this milestone

Review: docs/reviews/2026-09-17-v7-compact-proposals.md.

- Typed ZSTD Parquet proposal batches, v7-compact-proposals-v2, replace repeated
  JSONL. Complete variant/policy dictionary; deterministic IDs/clock fields;
  bounded streaming writes/reads, including zero-entry variants. Exact public
  fields preserved, including censored rows, signal gaps and dated exit tickers.
- Captured-input builder binds coverage/membership and execution-aware active
  manifest. PIT entry admission only; exits after membership ends remain. It
  still rejects unresolved source identity/actions. No ranking replacements.
- StoredFeatureRows joins saved causal observations to all222columns using
  explicit daily, dated-sector and selected-contract tick inputs. Exact saved
  raw-unit moving averages preserve pre-epoch warmup and direct arithmetic.
  One epoch cached; future assembly should process by epoch and verify bindings
  at completion. This adapter does not itself build daily/tick data or labels.
- Source bindings now include options helpers; original raw producer/manifest
  bytes remain unchanged. Do not invalidate raw receipts for execution changes.

Current-policy AAPL March15–May10,2022 build:
`nn_meta/validation/v7-compact-proposal-build-20260917/BBG000B9XRY4/{1,5,15,30}`.
11,268variants,757,595proposals (598,931/108,336/34,238/16,090 by timeframe).
All757,595public rows matched a separate fresh simulation from stored channels,
with independent dated membership application. This is simulator/storage parity,
not an independent proof of simulator correctness. AAPL had zero membership
exclusions here; filtering, late availability and retained exits are unit-tested.

Proposal payload9,896,112bytes vs807,083,883bytes for identical current-policy
JSON rows:98.7738% smaller. Total feature/proposal output108,089,486bytes. Slowest
build174.71s;peak worker RSS918,820KiB. Resume4.05–4.15s/worker preserved all736
receipts. Component tests compare all222features exactly, including explicit
first-post-split MA feature probe, warmup NaNs, raw spot and dated sectors.
Full suite1,967tests+18subtests,18warnings,154.81s. No additional suite needed
unless code changes. Four bounded workers used; no full-history/resource claim.

Evidence `nn_meta/validation/v7-compact-proposal-verification-20260917`, receipt
`2ddac7740426c8fb411f97ab5bf5cb39096a5eee4fc11fbd752f68ea605a30ad`.
Contains exact audit source, build/resume/comparison/test logs, XML, measured
counts and source/receipt hashes. Audit scripts also remain at
`/tmp/verify_v7_compact_20260917.py`, `/tmp/finalize_v7_compact_evidence.py`.
Actual handles51215tests,89072build,7642exact,73903resume all exited0.

## Next work — full context/demand/labels integration

Current `nn_meta/validation/v7-readiness-20260917-compact.json`: three basic
input/membership/coverage checks pass; all8 substantive stages remain missing:
lifecycle,causal prices,daily context,quotes,physical execution,assembly,trials,
integrated pilots. Do not mark any full gate done based on this bounded pilot.

1. Connect captured daily/history/surfaces to all10 causal daily/market features,
   exact dated sectors and the stored-row adapter. `causal_daily.py` already has
   returns/context/missingness components. `validate_v7_causal_daily.py` proves
   AAPL40session returns only; it is not a full market/context builder. Do not
   use old `daily.daily_context` adjusted/filled path. Preserve unresolved action
   and identity evidence, and initial warmup NaNs.
2. Generate actual compact-proposal-driven contract/tick/mark/exit/roll demand,
   taking only necessary missing inputs. Existing `plan_v7_quote_demand.py` is
   a conservative all-minute envelope, not this actual-demand consumer.
   `tick_features.features` needs complete causal quote/trade windows plus dated
   standard-contract metadata; `StoredFeatureRows` consumes its covered output.
3. Connect amended midpoint/premium-stop/ITM expiry replay, physical execution,
   outcomes and labels to bounded factorized assembly and purged training folds.
   Existing physical funding/stock liquidation/reference exceptions remain.
4. Finish runnable predeclared trials, resource/storage/recovery/coexistence
   measurement on full-history inputs, and full-universe readiness. No broad
   reference/news/issuer acquisition expansion; target actual required gaps.

Current source consumers:
`nn_meta/v7/{proposal_store,compact_proposals,entry_eligibility,stored_rows}.py`,
`proposals.py`, `scripts/build_v7_proposals.py`; tests of matching names.
`load_inputs` now returns six values, adding EntryEligibility. Builder --active
is OPTION_RISK by default. StoredFeatures verifies bound sources/runtime/inputs;
source edits can invalidate reuse. Never relabel old receipts to bypass it.

## Existing data and limitations

Active `docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`; policy
`V7_OPTION_RISK_20260916.json`. Original `V7_ACTIVE_INPUTS_20220315.json` stays
immutable for raw producer bindings. Readiness verifies non-execution scope.
AAPL input consumer:15,600rawminutes,40sessions,18compiled actions; source
`nn_meta/data_v7/start-20220315`, history
`nn_meta/validation/v7-security-history-20260916`, actions
`nn_meta/validation/v7-compiled-cash-actions-20260916`, ID BBG000B9XRY4.
Use those arguments with `scripts/build_v7_proposals.py`, --start2022-03-15
--end2022-05-10 --workers4 and the current build output for exact resume.

Full history591IDs,593tickers,1,129sessions,667,239history rows. Eligible339,640
sessions;339,454identity matches,186unresolved. Minute bars present339,581;
59zero sessions have41cash-merger/14successor/4halt explanations. This is session
presence, not every-minute completeness. Coverage answer evidence:
`nn_meta/validation/v7-stock-coverage-answer-20260916.json`.
Daily `v7-stock-daily-20260916-midpoint`, surfaces `v7-surfaces-20260916-midpoint`,
dated sectors `v7-sectors-20260916-final`. Reviewed cash events19 (18AAPL+DVN);
10,340provider records unresolved. Preserve FISV/FI June7,2023 identity evidence.
Historical old proposal pilot757,465rows/887.7MB used superseded generic stock
stops; do not reuse as new execution/label evidence.

## V6 — preserve verified deployed experiment

Runtime `/home/healy/Coding/HealysV6` at
`d252c5190c3ca261136966ffe43432b160adfc84`, isolated pushed branch
`ops/v6-option-risk-20260916`. Activation SHA
`d7ce5e3ebbcc58ddb894564b113cc35c210d0d35f4558123944f8cacf8c02f34`.
Deployment preserved13closed/0open,realized equity0.6867286044611687; empty-book
service test succeeded, timers resumed. Empty-book test at deployment; the live FIG stop is verified below.
Final candidate tests1,610+18subtests,16warnings,65.15s (corrects prior handoff's
stale1,609count). Evidence `nn_meta/validation/v6-option-risk-20260916/roll-guard`.
V6 frozen entry simulator remains unchanged; held strategy exits use signal-only
configuration and option risk. Expected-leg transactional guards cover stop,
ITM and OTM decisions against concurrent replacement. Do not globally change the
entry simulator and silently alter frozen model features. Candidate
`/tmp/healys-v6-option-risk-20260916` has an untracked venv symlink; never stage it.

Archived predecessor:
`handoff-history/HANDOFF-2026-09-17-before-compact-proposals.md`.

## User-supplied V6 alerts, inspected after the V7 milestone

V7 compact milestone committed and pushed as `1d45b31`. User then supplied a
V6 unresolved-monitoring alert and a FIG option-stop exit. Read-only inspection
confirmed current runtime source hashes still match the activated risk policy.
FIG entered at midpoint $1.485 on September17 14:04:34 UTC and exited at $1.37
at17:15:36 UTC, approximately3h11m later. Raw midpoint loss7.7441%; net paper
loss8.02046% including0.15% per-side costs. Entry bid/ask1.39/1.58;exit1.31/1.43.
This is an actual inspected live-paper stop using the requested midpoint rule,
not a repeat of ask-entry/bid-exit accounting. Stop threshold was $1.373625.

Forward status17:30 reported no fresh post-decision option quote for AMPX and
SOXX. The17:37 minute risk worker successfully assessed COHR and SOXX but still
recorded AMPX's missing quote. `execution_quote` only queries the latest30seconds
and rejects an empty result. Open positions remain retained; unresolved checks
withhold new entries. No arbitrary stale mark, quote-age relaxation, runtime
patch, restart or ledger mutation was performed. These data-availability gaps
remain unresolved; do not claim the runtime is fully healthy.

Retained evidence `nn_meta/validation/v6-live-midpoint-check-20260917`, receipt
`028f3c0b123f086d969bc418876d8e69463e7170979130b69346a88dc8f5e71f`: saved statuses,
FIG ledger record, numerical checks and activation/source verification. Three
open positions at inspection:AMPX,COHR,SOXX;16closed total. Original V7 objective
remains active; continue the context/demand/label integration above.

Additional archived predecessor:
`handoff-history/HANDOFF-2026-09-17-before-live-stop-check.md`.
