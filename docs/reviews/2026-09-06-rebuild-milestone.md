# Rebuild and live-data milestone — September 6, 2026

The corrected data and source foundation has started a fresh local pilot.
The expanded v6 model is **not trained or deployed**. Historical option quotes
and trades are now captured and validated in a real bounded pilot, but are not
yet features in a trained model. Existing server sockets can supply near-live
observations once the compatible source, bundle and feed checks are deployed.

The user confirmed that the full v6 freeze/build must contain **all thirteen
selected TradingView indicator scopes plus quote/trade features**. The running
SPY/IBKR pilot only checks the repaired core. Full-universe freezing waits for
those additions and their verification; an existing-family-only run is not
the requested full rebuild.

## What changed

| Workstream | Completed work | Evidence / remaining boundary |
|---|---|---|
| Audit repairs | All 51 original findings and four additional concerns repaired and merged: causal signals, splits, marks/cash/costs, PIT selection, provenance, live state and failure handling | [Remediation](2026-09-05-remediation.md); historical performance is not corrected performance |
| Research isolation | Named campaigns, exact shard merges, immutable source/data/runtime fingerprints, two-way calendar coverage, candidate seals and scope-checked resume | Old v6's 211/441 partials and old v5 rows are preserved and ineligible |
| Stock history | Refreshed all 453 names in raw and all-adjusted 15-minute form: **6,887,003 matching timestamps** per basis, 602 warmup/history sessions and 500 model-window sessions | [Data repair](2026-09-06-data-repair.json); explicit listing/zero-volume/halts, partial sessions and terminal dates are retained rather than fabricated |
| Option selection/context | Raw stock spot for strikes and implied volatility; adjusted prices for technical/return features; each roll uses a known close then a later option fill bar | Contract advanced to `2026-09-06-raw-spot-v3` |
| Option archive | Preserved **5,214,222 all-observed contracts** and 500 option dayframes; rederived **33,597,149 daily option rows** using raw spot | [Filter audit](2026-09-06-option-daily-basis-audit.json); this is OHLCV/context repair, separate from tick history |
| TradingView | Ranked all 74 exposed listing pages; pinned the top ten supplied-listing scripts plus top three Editors' Picks; implemented scoped numerical/state calculations for all thirteen | [Selection and scopes](../specs/TRADINGVIEW_EXPANSION.md); **zero admitted** until actual exported fixture checks pass; some graphical/native modes remain outside the ports |
| Indicator consistency | Keltner and BB-width formulas documented and checked across all four frames against sweep/replay behavior | [Semantics](../specs/V6_KELTNER_BBW_SEMANTICS.md); existing twelve-family v6 pool remains the pilot pool |
| TradingView fixture intake | Validates exact chart inputs, complete-bar/history assertions, original CSV hashes, pinned Pine/runtime identities, numerical tolerances and exact event timestamps | [Runbook](../specs/TRADINGVIEW_FIXTURE_RUNBOOK.md); synthetic local tests do not establish TradingView parity |
| Massive tick history | Authenticated, paginated, hashed capture; nanosecond timestamps; missing-ID trade multiplicity preserved; causal spread, size, freshness, volume and VWAP features | [Actual pilot](2026-09-06-option-tick-pilot.json), [current replay](2026-09-06-option-tick-replay.json); no model admission or execution-fill claim |
| Existing live sockets | V6 expert/campaign bundle paths; weekly DTE parity; calendar-aware closed bars; raw SIP reconnect backfill; freshness/refusal behavior; opt-in OPRA quote/trade journal | [Journal runbook](../specs/OPTION_TICK_JOURNAL.md); full-session comparison and coordinated deployment remain pending |
| Contract preview | Captured-chain resolver checks receipt time, quote age, OCC, delta and liquidity with a reproducible preview | Deliverables/reference verification and quote-based execution accounting remain open |

## Actual options quote/trade pilot

The historical capture downloaded **35,325 quotes and 2,454 trades** for
`SPY260824C00766000` and `SPY260824P00766000`, August 24, 2026,
13:30–13:45 UTC. All four requests completed; compressed payloads total
592,803 bytes. The captured raw files are retained separately from the OHLCV
candidate and verified again on replay.

The feature layer can describe the bid/ask spread, quoted sizes/imbalance,
quote age/validity, reported trade count/volume and VWAP. Quote-test signed
volume is explicitly gated: unknown conditions, ambiguous same-time quotes
and stale observations cannot silently become buyer/seller labels. An
[official condition snapshot](2026-09-06-option-condition-209.json) maps code
209 to Automatic Execution with regular aggregation eligibility; it does not
encode aggressor direction. A separate [sensitivity replay](2026-09-06-option-condition-replay.json)
using only that condition classifies 46.79% of call volume and 40.16% of put
volume by the quote test. Other conditions and all chronology/quality gates
remain restrictive; default policy and model admission are unchanged.
Additional data may improve liquidity filters and
execution estimates; predictive benefit still requires a controlled comparison.

This two-contract, one-window result does not estimate the cost, download time
or completeness of a full-universe tick archive. It also does not turn quoted
prices into observed fills.

## Pilot incident and validation

The first campaign, `raw-options-20260906`, started the SPY/IBKR freeze. It
exposed an inherited provider behavior that materialized option contract bars
inside the sealed input directory. The run was stopped. Every one of the
123,471 original sealed payloads verified unchanged; 1,299 added files
(17,815,393 bytes) were preserved in the aborted campaign's quarantine.
The exact original inventory and unchanged manifest/seal were restored.
[Restoration evidence](2026-09-06-pilot-cache-restoration.json).

The fix writes named historical contract caches under campaign `runs/`, reads
sealed legacy caches as read-only fallbacks, rejects path escapes, uses unique
atomic temporary files, and indexes lifetimes per underlying. The aborted
IBKR freeze shard remains ineligible. The replacement uses a new campaign,
`raw-options-20260906-r2`, with cold writable caches.

The replacement launched around 05:39 UTC with two dynamically selected
workers. It passed the initial seal and 500-session coverage checks and is
running the freeze stage. Its dated wrapper records completion/failure in
`scripts/.jobstate/raw_options_pilot_20260906.exit`; detailed progress is in
`logs/raw-options-20260906-r2-pilot.log` and the campaign's per-stage logs.
The recovery descriptor is committed; the recovery systemd unit was previously
observed absent, so unattended reboot recovery is not established.

The [05:50 UTC status snapshot](2026-09-06-replacement-pilot-status.json)
records both active workers, 1,102 growing campaign cache files, unchanged
sealed inventory and matching source/runtime identities. No freeze shard had
completed at that snapshot. The status check samples current data hashes;
the launcher performs full byte verification at stage boundaries.

At 05:54 UTC, IBKR's current-contract freeze shard had completed; SPY was still
extracting option histories. Combined freeze merge, build and assembly were
still pending. These are pipeline progress observations, not model results.

Full local validation after this fix: **1,143 tests and 18 subtests passed**,
11 warnings, 36.00 seconds. Registry identities and `git diff --check` pass.
These checks exercise synthetic regressions; the separate capture/repair
reports provide actual provider and local archive evidence.

## What finishes the requested rebuild

1. Finish the corrected SPY/IBKR freeze → rows/marks → PIT assembly pilot and
   inspect coverage, raw-spot selection and ledger reconciliation. Record
   measured runtime/memory for the eventual expanded full-universe run. This
   pilot has twelve existing families and no tick-model
   features; it is not the expanded final model.
2. Capture actual TradingView numerical/event exports, match the pinned
   settings/history and resolve discrepancies. Admit only supported scopes;
   feature-only tools still need explicit feature integration or mechanical
   proposal rules. Freeze the final expanded feature schema before training.
3. Create a point-in-time contract/window manifest for richer history. Start
   with the contracts selected by the corrected policy and representative
   liquidity/DTE/regime windows, then backfill the required decision, entry,
   exit and roll windows. Preserve rejected/unavailable coverage as explicit
   data, and never choose historical contracts using later profitability.
4. Join tick features at their actual decision-time availability, distinguish
   exchange/SIP clocks from live receipt clocks, normalize the provider's
   documented condition namespace and define quote-based costs. Freeze a new
   input/schema identity and run baseline, indicators-only, ticks-only and
   combined comparisons on identical admissible windows.
5. Once all thirteen scoped indicators and quote/trade features are integrated
   and validated, launch the full v6 freeze/build with that complete schema.
   Rebuild complete rows and marks; train/evaluate on
   post-freeze windows with PIT membership and corrected costs. Inspect gates
   and finalize only a passing, fully verified bundle. Conditional evaluation
   with a globally frozen generator is not fold-local refreezing.
6. Stage source, matching bundle, raw context and captured calendar together
   for the server. Exercise isolated previews, a full-session stream/REST
   comparison and restart/backfill behavior before enabling the v6 expert.
   Reuse the existing SIP/OPRA daemons; delivery stays `git pull`, never scp.

The initial near-live target is **decisions after completed 15-minute bars**,
with quotes/trades updating between decisions. Moving the decision model to
one-minute/tick cadence would require matching historical features and another
evaluation. Automatic execution also requires offline contract-selection
parity, deliverable verification and quote-based entry/exit/roll accounting.

## Deployment and remaining operations

No server source, model, cron, subscription, notification or order was changed.
The last read-only server observation was pre-audit commit
`9351d01ee487299ae208393cfad021da0330950b`. Deploying corrected source ahead of
compatible models can stop existing experts because old bundles are rejected.
An off-hours healthy socket is not full-session feed evidence.

Broader archive recovery (FA/full v3/SPX0), timer installation, prospective
FA cohorts, volatility, SPX0 reevaluation, stacking and RL retain their ordered
gates in [TODO](../../TODO.md) and [ROADMAP](../../ROADMAP.md). The richer v6
request does not turn those independent workstreams into completed work.
