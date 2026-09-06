# Handoff — expanded v6 integration; full freeze blocked on real inputs

September 6, 2026, Chicago. Work is on `main` in the primary checkout.
The user authorized finishing the remaining steps and starting the full v6
freeze, including all thirteen selected TradingView scopes and quote/trade
features. No additional launch permission is needed once the real gates pass.
[Expanded milestone](docs/reviews/2026-09-06-expanded-v6-milestone.md),
[ordered input workflow](docs/specs/V6_EXPANDED_INPUTS.md), [TODO](TODO.md).

**The full expanded freeze has NOT started.** Actual TradingView output captures
and full historical option tick coverage are absent. The full launcher was
invoked with the new campaign/candidate and correctly refused the missing
reviewed feature input manifest. No external parity, trained model or deployment
is claimed. An earlier async question about which browser is signed into
TradingView remains unanswered. There is no browser automation tool; templates
are not observed chart values. Do not replace these gates with synthetic CSVs.

## Implemented expanded path

- All thirteen pinned sources project into 96 fixed causal feature columns.
  Exact input history, 15-minute closed bars, minimum tick, observed 2D flags,
  VWAP context and session policy are required. Price/range normalization is
  Pine ATR14; unavailable values remain NaN. Source-literal RTH behavior is
  explicit; no invented Setup overnight reset. Full 15,000-bar computation
  benchmark was 43.90 seconds per symbol, not a live latency validation.
- Eight fixed-default directional families join the existing twelve when
  `NN_META_V6_EXPANDED=1`; five selected sources remain features. Setup retains
  six typed identities and source priority. No unverified parameter sweep grid
  is introduced. Source proposal events are independently bound in the gate.
- Ten immutable tick features use exact predecision-selected contracts/windows.
  Shared label/feature selection uses raw spot and chains observed by the
  previous UTC date; current snapshot Greeks are excluded. Point-in-time
  provider capability and catalogue evidence for renamed OCC roots are required.
  Historical SIP availability is distinct from actual live receipt latency.
- Fixture intake supports original versus reviewed append-only plots, terminal
  Bar Replay snapshots, and explicit missingness. All-13 parity packs rerun
  retained comparisons and require 127 source fields, including 44 proposal
  events. Numeric fields require actual finite evidence; missingness-only
  observations cannot admit later active values. Three capture harnesses remain
  deliberately uncompiled/unreviewed drafts.
- `ExpandedInputs` binds context, source/default/proposal scope, parity files,
  tick tasks/stores, policies and transitive campaign hashes. Builder and
  historical candidate replay use the same row projection. Candidate audit
  contract/request/status fields survive scoring input construction. Missing
  coverage or drift raises instead of silently filling zeros/dropping a family.
- Local request planning is implemented in `scripts.plan_v6_option_requests`: all
  twenty families, identical underlying TRAIN selection/caps and weekly DTEs,
  no option bars/outcomes/downloads. Planning context is sealed separately from
  final tick stores; actual full inventory still awaits real source/context.
- Expanded contract: `2026-09-06-tv13-option-ticks-v4`. Core default remains
  `2026-09-06-raw-spot-v3`. The full local freeze launcher now requires the
  expanded input manifest and fresh campaign, rejecting additive/partial scope.

## Preserved core pilot — no longer running

`raw-options-20260906-r2/v6` completed both SPY/IBKR freeze shards and the merged
12-family spec. IBKR also completed 8,910 rows (6,066 executed), 95,159 marks,
and all five standard DTEs. SPY retained a 984-row MA partial with 83,824 marks
and its eight weekly/standard DTEs. The SPY build worker was deliberately
terminated before integrating changed source. Wrapper exit marker is **1**;
this is a stopped run, not a completed build/assembly.

Full final verification BEFORE source integration matched all **123,711**
original inputs exactly: zero changed, added or removed; runtime, scope and
candidate seal matched. [Stop evidence](docs/reviews/2026-09-06-core-pilot-stop.json).
The recovery descriptor is preserved as `.retired`, outside the dispatcher's
`*.sh` glob. Do not run the generic dispatcher: it can send notifications.
Do not resume this campaign with new source or reuse its artifacts for expanded
v6. The old 211/441 untracked `nn_meta/artifacts_v6/` partials are also preserved.

## Real selected-contract tick evidence

New capture `nn_meta/option_tick_captures/spy-20260824-v6-decision-v2` contains
SPY260825C00762000/P00762000 for August 24, 2026, 13:30–13:45 UTC. Selection used
that bar's corrected raw close 762.19 and prior-date catalogue evidence; both
contracts were first observed August 12. No option outcomes selected the sample.

Call: 9,683 quotes, 98 reported trades, 45 eligible code-209 trades.
Put: 8,131 quotes, 550 reported trades, 314 eligible code-209 trades.
All ten numeric features are present and both exact requested windows join.
Unknown/unadmitted conditions stay excluded from eligible trade statistics;
raw counts remain audit evidence. Quote-test signing is not aggressor truth.
[Store evidence and current anchors](docs/reviews/2026-09-06-v6-selected-tick-store.json).
The first sandboxed `...-v1` path is an incomplete transport attempt; retain it
as incomplete. Earlier same-day 766-strike capture is preserved separately and
correctly fails this selector's coverage requirements.

## Validation and next work

Final main-checkout integration validation passed **1,390 tests and 18 subtests**,
11 warnings in 45.43 seconds. Shell syntax and diff checks also pass.
The first combined draft regression had 1,367 tests; the prior raw correction
milestone had 1,143. No CI or evaluated-model result is inferred from this.
Use `PYTHONDONTWRITEBYTECODE=1`, the project venv, and `/tmp` NumPy/plot caches.

Obtain actual reviewed TradingView captures and exact context first. Then run
the local pre-outcome request planner, download/verify the full required tick
windows, materialize and seal the expanded inputs, and execute the fresh full
freeze. Source/API readiness is not historical coverage. Complete build,
marks, assembly, evaluation and a new bundle afterward. No tonight completion
estimate is established for the full coverage/research workload.

The server still needs coordinated source+bundle rollout and a validated
Massive/Alpaca condition-and-receipt adapter, closed-bar reconnect replay and
full-session comparison. Candidate parity here is historical replay of sealed
inputs, not an operating richer live feed. No server source, subscriptions,
orders or notifications were changed. Prior server source observation remains
9351d01ee487299ae208393cfad021da0330950b. Deploy by git pull, never scp.
