# Handoff — corrected data, option ticks and v6 pilot

September 6, 2026, Chicago. Work remains on `main` in the primary checkout.
The user authorized all six workstreams, multiple agents, richer Massive
option quote/trade history, reuse of existing server sockets, and a v6 rebuild
if possible tonight. They requested an overview when done.
[Full change overview and ordered next steps](docs/reviews/2026-09-06-rebuild-milestone.md).
[TODO](TODO.md) remains the active checklist.

**The expanded v6 model is not trained or deployed.** A fresh SPY/IBKR
corrected-pipeline pilot is running. Thirteen TradingView ports remain outside
active pools, and captured option tick features have not been joined to model
rows. Source/data readiness is not evaluated performance.

**Latest user steering:** the full v6 freeze/build must include all thirteen
selected TradingView indicator scopes and quote/trade features. The current
SPY/IBKR run is a pipeline pilot only. Do not scale it to a full-universe
existing-family-only rebuild; finish the additions, their data coverage and
validation before the full freeze. This scope takes priority over earlier
suggestions to scale a corrected baseline first.

## Active job — inspect before editing research source

Campaign `raw-options-20260906-r2/v6`, data candidate
`audit-repair-20260905-final`. Launched around 05:39 UTC with two dynamically
selected workers, stages freeze → build → assemble. The model window remains
2024-08-26 through 2026-08-24. It uses all twelve configured v6 families.
No evaluate/finalize stage was selected.

[Running snapshot](docs/reviews/2026-09-06-replacement-pilot-status.json),
05:50 UTC: both workers active, 1,102 campaign cache files, no completed freeze
shards yet. Candidate inventory and sampled hashes match, all source hashes
and runtime versions match launch. This is bounded status evidence; the
launcher performs full byte checks at stage boundaries.

Later progress at 05:54 UTC: IBKR's freeze shard exists and covers IBKR under
the current raw-spot contract; SPY is still extracting option histories.
The combined freeze has not merged, and build/assembly have not started.

Entry point: `bash scripts/run_raw_options_pilot_20260906.sh`.
The wrapper locks before clearing the exit marker and writes the actual result
at `scripts/.jobstate/raw_options_pilot_20260906.exit`: empty means started
without recorded completion; 0 means success; nonzero means failure.
A recovery descriptor is committed, but the recovery systemd unit was
previously observed absent. Do not invoke the generic dispatcher to inspect
state: its relaunch paths can notify.

- Main log: `logs/raw-options-20260906-r2-pilot.log`.
- Per-stage logs: `nn_meta/campaigns/raw-options-20260906-r2/v6/runs/logs/`.
- Scope: `nn_meta/campaigns/raw-options-20260906-r2/v6/campaign_scope.json`.
- Outputs: `nn_meta/campaigns/raw-options-20260906-r2/v6/artifacts/`.
- Writable slices: `nn_meta/campaigns/raw-options-20260906-r2/v6/runs/provider_cache/`.

The launcher checks data, source and runtime before and after stages, including
the freeze merge. **Do not edit fingerprinted source or inputs during the campaign.**
Required runtime fixes demand another campaign name; docs/tests and commits
alone do not change runtime inputs. Inspect current logs/marker before
reporting progress. A full-universe run needs a different name because this
scope pins exactly SPY/IBKR.

## Aborted first pilot and recovery

The first campaign, `raw-options-20260906`, started at 05:02:48 UTC and exposed
an inherited provider writing 1,299 option contract cache files into the sealed
candidate. IBKR completed freeze; SPY was stopped and the parent failed.
No build/assembly/evaluation from that attempt completed. Its IBKR shard is
preserved as **ineligible history**.

All 123,471 original sealed payloads were verified unchanged before the
added files (17,815,393 bytes) were moved to the old campaign's
`runs/provider_cache/quarantine/`. A per-file hash journal records recovery.
Exact original inventory and unchanged manifest/seal were restored at
05:24:06 UTC. [Recovery evidence](docs/reviews/2026-09-06-pilot-cache-restoration.json).

Named historical providers now write only under campaign runs, read sealed
contract bars as read-only fallbacks, reject path escapes and use unique
atomic temporary files. Lifetime indexes avoid repeated full-universe scans
while retaining renamed-root metadata fallback. Independent review and a
forced concurrent double miss passed. Replacement caches are cold: neither
quarantined slices nor the old IBKR shard were seeded.

## Code and validation

The audit's 51 findings and four additional concerns were repaired and merged.
The first TradingView/readiness batch was pushed through `fb28ab7`
and passed 790 tests plus 18 subtests. This continuation includes:

- `819ad94`: remaining five TradingView scoped ports.
- `29578ad`: raw stock spot for option selection/IV and context derivation.
- `47113e6`: verified Massive ticks and causal descriptive features.
- `dc1b7ca`: v6 calendar/feed readiness and opt-in OPRA quote/trade recording.
- `7639f01`: Keltner/BBW sweep/replay semantics and regressions.
- `84481a0`: full stock repair, raw option context and candidate seals.
- `60ee899`: strict captured TradingView fixture intake/comparison.
- `a7c7143`: separate provider caches and recovery evidence.
- `bbeebd3`: dated pilot launcher and recovery descriptor.

Full local suite after provider changes: **1,143 tests and 18 subtests passed**,
with 11 warnings in 36.00 seconds. Registry, affected shell syntax and diff
checks pass. Use the project venv; test with `PYTHONDONTWRITEBYTECODE=1`,
`NUMBA_CACHE_DIR=/tmp/healys-plan-numba` and `MPLCONFIGDIR=/tmp/healys-plan-mpl`.
Check final push/Actions status against the actual commit; an absent Actions
run does not establish green CI. No evaluated model verdict was added to EXPERIMENTS.

## Repaired input data

Current contract: **2026-09-06-raw-spot-v3**. Old freezes, v5 rows/bundles and
untracked `nn_meta/artifacts_v6/` (211/441 paused partials) are preserved and
ineligible. Never relabel old provenance.

Candidate `nn_meta/data_candidates/audit-repair-20260905-final/cache` contains
fresh raw/all-adjusted 15-minute panels for 453 stocks with exactly 6,887,003
shared timestamps, 602 history/warmup sessions and 500 model sessions.
Listing/issuer/early-close exclusions, CLSK halt and SBET zero-volume exceptions
are explicit. Partial sessions and terminal histories are reported, not filled.
Original cache bytes are unchanged.

The broad 5,214,222-contract all-observed universe and 500 option day files are
retained. Raw-spot filtering rederived 33,597,149 daily option rows in 13 parts.
The adjusted daily panel and surface each have 266,905 rows; raw daily has
267,409 rows, including 504 additional BITF rows. Raw spot for the old SQ/FI/BITF
roots is explicit. The captured calendar has 943 sessions covering
April 1, 2024 through December 31, 2027.

Manifest SHA256:
`1463af69ef956cea0829a6f0fc98464bc7a5ac77b4cc940236c28ae8dc78e05c`.
Unchanged/restored seal digest:
`489781bc546994ad1e433e8191bee093d9c99c9817f6f3ea74484ceb4b3fc04c`.
[Repair evidence](docs/reviews/2026-09-06-data-repair.json) is a prelaunch
snapshot; its old source fingerprint and `campaign_launched: false` describe
that moment. Use the replacement campaign scope for current source identity.

Adjusted history supplies technical/return features; separate validated raw
panels supply strike selection and IV spot. Each roll selects after a known
close and fills in a later option bar. The complete observed chain is retained;
daily surface summaries had the incorrect adjusted-spot filter. Generic legacy
dashboard scalar selection is not claimed fully migrated to raw panels.

## TradingView and historical tick boundary

Ranking covers the literal supplied URLs: 42 general listing pages containing
1,000 recent scripts and 32 Editors' Picks pages containing 758 scripts. This
is not an all-time general ranking.
All thirteen public sources and scoped Python calculations are pinned.
[Selection/scopes](docs/specs/TRADINGVIEW_EXPANSION.md).
Emre box arrays remain unported; native Footprint is unsupported; intrabar modes
need observed inputs; HTF/session flags must be explicit. Unused RelativeValue/3
remains documented pending. **Zero new families admitted.**

Actual chart exports are missing. The strict CSV workflow binds exact chart
inputs/history/source/runtime, completed bars, numerical tolerances and event
timestamps. Built-in calculation supports Gaussian/Fibonacci/Uptrick; other
ports accept bound precomputed outputs.
[Fixture runbook](docs/specs/TRADINGVIEW_FIXTURE_RUNBOOK.md).

Actual Massive capture: SPY August 24, 2026 expiry, 766-strike call/put,
13:30–13:45 UTC; **35,325 quotes and 2,454 trades**, totaling 592,803 compressed bytes.
Raw capture `nn_meta/option_tick_captures/spy-20260824-open-v2` is preserved and
verified on replay. [Pilot](docs/reviews/2026-09-06-option-tick-pilot.json),
[current-policy replay](docs/reviews/2026-09-06-option-tick-replay.json).
Nanoseconds and missing-ID trade multiplicity are retained. Descriptive
features cover spreads/sizes, quote age/validity and trade volume/VWAP.
Unknown conditions remain unsigned; ambiguous/future/stale quotes cannot supply
aggressor estimates. This is one bounded sample, not full coverage, model
integration, observed fills or demonstrated predictive gain.

An [official condition reference](docs/reviews/2026-09-06-option-condition-209.json)
now identifies Massive options trade code 209 as Automatic Execution, OPRA I,
with normal price/volume aggregation eligibility. It does not identify
aggressor direction. The active conservative replay policy remains unchanged.
A separate [research sensitivity replay](docs/reviews/2026-09-06-option-condition-replay.json)
allows only code 209 while keeping quote/correction gates. It classifies about
47% of reported call volume and 40% of put volume in this small capture;
this remains a quote-test estimate with model admission false.

## Server and next steps

V6 has expert/campaign bundle paths, weekly DTE parity, captured calendars,
closed-bar checks, raw SIP reconnect backfill and stricter freshness.
The OPRA opt-in `--record-ticks` preserves decoded messages, event/receipt clocks,
bounded admission and visible failure/restart evidence.
[Journal runbook](docs/specs/OPTION_TICK_JOURNAL.md).
Massive condition integers and Alpaca strings/clocks need a validated adapter.

The near-live target remains decisions after completed 15-minute bars, with continuously
updated observations. Existing server SIP/OPRA daemons can be reused.
No server source, model, cron or subscription change was deployed; no notification
or order was sent. Last server observation: pre-audit
`9351d01ee487299ae208393cfad021da0330950b`.
Source-only deployment can stop experts: old bundles are rejected. Stage
compatible source, bundles, raw context and calendar together, git pull only,
never scp. Full-session stream/REST and restart/backfill evidence remains open.

Next: complete/inspect the pilot and ledger coverage; obtain actual Pine
fixtures and admit supported scopes; freeze point-in-time historical contract/
window selection and trade-condition policy; broaden tick history and join
matching decision-time features; compare corrected baseline, indicators, ticks
and combined models; evaluate/finalize passing models and coordinate rollout.
A running core pilot does not establish a complete expanded rebuild tonight.

Contract preview still needs deliverable/reference verification, offline
selection parity and quote-based entry/exit/roll accounting before paper
execution. Shared alert-format approval applies to a concrete production
change. Deeper FA/v3/SPX0 recovery, missing backup/StockTwits timers, prospective
FA cohorts, volatility, stacking and RL retain their existing gates.

Previous handoff archived before replacement:
[HANDOFF-2026-09-06-before-rawspot-milestone](handoff-history/HANDOFF-2026-09-06-before-rawspot-milestone.md).
