# Handoff — actual proposal tick-feature demand verified

Updated September 17, 2026. Main; no subagents. Goal active and incomplete.
No training launched. All tests/build/audit/resume jobs from this turn exited
successfully. No new provider downloads or V6 runtime changes this turn.
Preserve the many unrelated dirty/untracked V6 files; never blanket-stage/reset.

## Latest milestone

Review: docs/reviews/2026-09-17-v7-entry-demand.md.

New `nn_meta/v7/entry_demand.py` and `scripts/build_v7_entry_demand.py` consume
actual compact, PIT-filtered proposal stores. SQLite collapses repeated strategy
entries into shared contract selections, retaining all five target identities
and the complete proposal/timeframe census. Raw spot must be causally available
and at most 60 seconds old; contract first observation must precede the decision
date. Missing spot/contract is explicit, never a fabricated row or future fill.
The index keeps one root's chain resident and uses bounded SQL/streamed reads.

For each selected contract/timeframe, quote and trade feature windows include
30 seconds of seed history, bounded by the session opening, and end exclusively
at the decision. Identical request scopes are shared. Export batches contain at
most 10,000 windows and keep each contract/day together. They are compatible with
`scripts/capture_v7_quotes.py` and its shared quota. Build and export bind all
parent payloads, sources and runtime. Completed outputs resume without proposal
reprocessing. `EntryDemand.lookup` connects a proposal/target to its selection
and requests; `request_batches`/`export_requests` provide capture inputs.

**This is pre-entry feature demand only.** Entry fills, minute marks, exits,
rolls and physical delivery still need demand integration. Do not call these
exports complete execution coverage, admit labels from them, or launch broad
capture before reconciling those other necessary windows.

## Real AAPL integration and evidence

March 15–May 10, 2022, all 11,268 variants and 757,595 proposals:

- 19,702 distinct feature decisions retaining timeframe.
- 16,279 shared selection decisions; 81,395 selected records for all five targets.
- 197,020 feature links; 55,126 distinct quote/trade requests; 107 contracts.
- Six bounded export batches; 7,472 non-overlapping capture intervals.
- 603.15 hours per tape (quotes and trades), after union. Not yet downloaded.
- Build 28.03 seconds, peak RSS 429,828 KiB. Resume 8.35 seconds, 237,108 KiB.
- All 13 files unchanged on resume. Total output 82,035,332 bytes, including a
  63,922,176-byte SQLite index. Full-history storage/resource gate remains open.
- Independent audit recounted every parent proposal, exhaustively checked every
  selected contract and tie rule, matched raw prices/clocks, checked every
  feature link, and verified exact export census plus non-overlapping unions.
- Full suite: 1,970 tests +18 subtests, 18 warnings, 115.58 seconds.

Artifacts:
`nn_meta/validation/v7-entry-demand-20260917`,
`nn_meta/validation/v7-entry-demand-exports-20260917`,
`nn_meta/validation/v7-entry-demand-verification-20260917`.
Verification receipt:
`0f2a0f8a2143a65edd74f221365610b417b54d56d10b8a4aeecd225e3a178e9c`.
Exact command/audit sources, logs/XML, hashes and measurements are retained there.
Scripts remain `/tmp/run_v7_entry_demand_20260917.py` and
`/tmp/audit_v7_entry_demand_20260917.py`. Terminal handles: 49013 full tests,
9599 build, 68110 audit, 39122 resume. No live job to restart or wait for.

Input proposal root:
`nn_meta/validation/v7-compact-proposal-build-20260917/BBG000B9XRY4`.
CLI takes --proposal-root, --output and --export; active manifest defaults to
`docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`.
No need to repeat completed tests unless code changes.

## Next work toward the actual full goal

Current `nn_meta/validation/v7-readiness-20260917-entry-demand.json` passes three
basic scope/membership/coverage checks. All eight substantive stages remain
missing: lifecycle, causal prices, daily context, quotes, physical execution,
assembly, trials and integrated pilots. No full-universe readiness claim.

1. Extend actual selected-contract demand to observed entry/exit fills, held
   minute marks, roll frontiers and physical delivery, using dated class hours
   and contract references. Merge necessary intervals before capture. Existing
   `plan_v7_quote_demand.py` is an all-minute conservative envelope, not this
   actual-proposal consumer. Capture only specifically required missing inputs.
2. Connect complete causal daily/market context and dated sectors to
   `StoredFeatureRows`; then join captured tick features. `causal_daily.py` has
   returns/context/missingness components; old `daily.daily_context` uses the
   wrong adjusted/filled path for this build. Do not substitute unadjusted market
   returns. SPY ID BBG000BDTBL9 has all 1,129 captured history sessions and daily
   surfaces, but 36 provider cash-action records remain unresolved; the existing
   saved amount-publication matcher has no SPY match. That is a specific market
   reference dependency, not a reason to restart broad issuer/news acquisition.
3. Wire option premium stops/ITM expiry, rolls and physical outcomes into labels,
   factorized bounded assembly, purged folds and the runnable predeclared trials.
4. Finish remaining identity/action exceptions and full-history resource/storage,
   recovery, no-swap and V6-coexistence checks, then full-universe readiness.

The prior compact-store/row-adapter milestone is committed as `1d45b31`;
subsequent V6 observation notes as `c8d5e52`. Compact proposals preserve all
public fields; full real reconstruction and 736-receipt resume passed. Exact
222-column row parity includes split warmup and raw option-selection prices.
That row adapter still requires supplied daily/sector/tick context, not fixtures
in the full dataset. New consumers can use the existing verified parent stores;
source edits/recomputed glob manifests can invalidate producer resume. Never
relabel old receipts or weaken binding checks to reuse changed calculations.

## Fixed scope and data

March 15, 2022–September 14, 2026 inclusive, cold start March 15. No March 8–14
active prices. Twenty families, 2,817 variants across 1/5/15/30 minutes, all 222
columns, 13 TradingView scopes and 10 tick features. Actual 1–9 calendar DTE;
targets 1/2/4/5/7; five shared slots, 10% equity premium, one symbol across TF.
Max four outer workers, one inner thread, 100 GiB disk reserve. Acquisition
ceiling 250 GB, never a target. Alpaca-only stocks/quotes; Massive options.
Entire BBBY/FRC/REV/SI excluded without replacement/reranking; no OTC.
Folds 2024H2, 2025H1/H2; final Jan 1–Sep 14, 2026; 10-session embargo through
settlement. Funded physical delivery and observed Alpaca liquidation remain
required where applicable; no invented intrinsic-value sale or free financing.

Execution: arithmetic (bid+ask)/2, separate 0.15% per-side costs. Option premium
loss stops from purchased-leg entry midpoint: V6 7.5%, V7 12.5%. Strategy exits
retained; no generic 5% underlying stop for held positions. ITM expiry exit
15 minutes before the dated option-class regular close. Valid trigger quote
supplies sale midpoint directly; missing/invalid quotes stay explicit and retry.
Original quote timestamp and observation/execution clock remain distinct.

Raw predecessor `V7_ACTIVE_INPUTS_20220315.json` and raw producer bytes remain
immutable; execution-aware OPTION_RISK manifest has the same non-execution scope.
Raw source `nn_meta/data_v7/start-20220315`; history
`nn_meta/validation/v7-security-history-20260916`; compiled actions
`nn_meta/validation/v7-compiled-cash-actions-20260916` (19 reviewed events,
18 AAPL + DVN; 10,340 provider records still unresolved).
Daily `v7-stock-daily-20260916-midpoint`; surfaces `v7-surfaces-20260916-midpoint`;
sectors `v7-sectors-20260916-final`. History 591 IDs, 593 tickers, 1,129 sessions.
Eligible identity matches 339,454/339,640; 186 unresolved. Minute bars present
in 339,581/339,640 sessions; 59 zero sessions have merger/successor/halt
explanations. This is session presence, not proof of every minute's completeness.

## Preserve V6; user alerts already diagnosed

Runtime `/home/healy/Coding/HealysV6` at
`d252c5190c3ca261136966ffe43432b160adfc84`, isolated pushed branch
`ops/v6-option-risk-20260916`. Activation SHA:
`d7ce5e3ebbcc58ddb894564b113cc35c210d0d35f4558123944f8cacf8c02f34`.
V6 frozen entry simulator remains unchanged; held exits use separate signals
and option-risk rules. Expected-leg guards protect concurrent replacements.
Candidate tests 1,610 +18 subtests, 16 warnings, 65.15 seconds. Candidate temp
worktree has an untracked venv symlink; never stage it.

The user supplied a September 17 FIG stop and unresolved-monitoring alert.
Read-only verification showed FIG midpoint $1.485 to $1.37 over about 3h11m:
7.7441% premium loss, 8.02046% net including costs, crossing $1.373625 stop.
This was the requested arithmetic midpoint behavior. Separately, 17:30 forward
status lacked fresh quotes for AMPX/SOXX; at 17:37 SOXX/COHR passed but AMPX
remained unresolved. New entries withheld; positions retained for retry. No
quote-age relaxation, runtime patch or ledger mutation. Do not claim recovery
without checking newer state. Evidence `v6-live-midpoint-check-20260917` under
nn_meta/validation. Details in the September16 option-premium-risk review.

Archived predecessor: handoff-history/HANDOFF-2026-09-17-before-entry-demand.md.
