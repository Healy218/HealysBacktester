# Expanded v6 inputs and freeze

The full v6 scope is 20 proposal families (the existing twelve plus eight
source-default TradingView families), all thirteen selected source feature
groups (96 columns), and ten historical option quote/trade columns.
Five sources supply features without an invented directional strategy.
The research contract is `2026-09-06-tv13-option-ticks-v4` when
`NN_META_V6_EXPANDED=1`. The existing core pilot uses `raw-spot-v3` and
cannot supply expanded freeze checkpoints, rows or bundles.

## Current admission state

The user explicitly deferred the external TradingView comparison on September
6 while retaining all thirteen indicator groups. Research may use
`NN_META_V6_PARITY_POLICY=deferred` with the distinct contract
`2026-09-06-tv13-option-ticks-unverified-v1`. Verified mode remains the default.
This deferral does not claim parity or change the 106-column/20-family scope.

Actual TradingView output captures are absent. Only a two-contract,
one-window tick store has been materialized. A full expanded freeze has
**not started**. Fixture templates and synthetic tests are preparation,
not external parity evidence. The capture harnesses need actual review
and compilation in TradingView before use.

For the deferred path, omit `parity_pack` from the sealed manifest and add:

```json
"external_comparison": {
  "status": "deferred",
  "research_only": true,
  "reason": "User requested skipping external TradingView comparison while retaining all 13 groups on 2026-09-06"
}
```

Also set `feature_contract_version` to the unverified contract above and add
`feature_schema` from `tradingview_features.feature_schema(...)` using the actual
minimum tick, session policy and VWAP mode. Context must match that complete
schema. Supply the externally recorded manifest hash as usual. A verified
loader rejects this contract; the deferred path never returns a passing parity
report. Hash-bound context, history, causality and exact tick-store checks still
apply. The next phase is context materialization and request planning; external
comparison is no longer its prerequisite on this path.

The [capture intake specification](TRADINGVIEW_INSTRUMENTED_FIXTURES.md)
explains original versus instrumented sources, retained history and terminal
Bar Replay snapshots. POC and Footprint require terminal snapshots; historical
CSV values cannot substitute for last-bar execution. The parity pack verifier
recompares retained files and requires 127 raw feature/proposal fields,
including 44 proposal events. Numeric fields require finite observations;
missingness observations are preserved separately. Exact source defaults,
proposal registry, source versions, outputs and runtime are bound. User
capture/review attestations do not establish authenticated external origin.

## Ordered completion

The capture intake CLI generates the current source-default checklist and an
explicitly unreviewed pack. It does not generate chart values or approve reviews:

```bash
./venv/bin/python -m scripts.prepare_v6_parity_pack prepare \
  --minimum-tick 0.01 --output /absolute/path/to/new-capture-intake --run
```

Use the actual instrument minimum tick; the default context policy is
`source_literal` with observed VWAP. The generated `capture_checklist.json`
lists all 127 required fields, 44 proposal events, exact parameters and the two
terminal-snapshot sources. Populate `pack.DRAFT.json` with actual retained
file references/hashes and completed reviews, adding fixture records for
additional states/sessions as needed. Review fields start blank/false and
reference hashes start blank, so the draft cannot pass admission. Capture CSV
metadata still follows the [fixture runbook](TRADINGVIEW_FIXTURE_RUNBOOK.md);
the checklist is not a substitute for that metadata or a local producer.

After saving a completed pack and recording its SHA256 separately:

```bash
./venv/bin/python -m scripts.prepare_v6_parity_pack verify \
  --pack /absolute/path/to/completed-pack.json \
  --expected-sha256 <separately-recorded-pack-sha256> \
  --output /absolute/path/to/new-verification --run
```

Without `--run`, preparation only previews; verification still performs every
comparison but writes nothing. Written verification retains the full comparison
report and writes its completion manifest last, after rechecking evidence and
verifier hashes. Existing output directories are refused. A passing report is
scoped parity evidence, not full context/tick coverage or freeze readiness.

1. For verified mode, obtain the actual source-default chart outputs and matching context streams;
   review/compile any plot-only instrumentation. Include active states and
   proposal exits as well as raw indicator fields. Recompare all thirteen
   scopes using `nn_meta.v6_admission.verify_parity_pack`.
2. Materialize exact 15-minute context for each underlying: fixed history
   origin, observed 2D boundary flags, verified VWAP anchor or observed VWAP,
   instrument minimum tick and session policy. No inferred 2D grouping or
   invented overnight/reset bars. Bind the OHLCV digest and context files.
3. Produce the full predecision request inventory from the configured proposal
   parameters and DTE grids, before inspecting option outcomes. `scripts.plan_v6_option_requests` performs the exact underlying TRAIN
   sweep and capped TRAIN/full-window proposal paths, including weekly DTEs.
   It reads no option outcomes or option bars; later option/DTE gates may reject
   some candidate families. The CLI is implemented but no full inventory has
   been computed without the required real context. Deduplicate overlapping requests,
   review capture volume, download and verify all required windows, and
   materialize the tick stores. The small completed pilot is not that coverage.
4. Seal the expanded input manifest below with a separately recorded SHA256,
   run the full preflight and then a fresh expanded freeze. Build joins fail
   on missing exact requests, policy drift or differing selected contracts.
5. Rebuild rows/marks, assemble, evaluate, select, and validate a new bundle.
   Existing server sockets can supply observations, but the richer live
   condition/receipt adapter and full-session replay comparison remain required
   before deployment. The shared candidate interface currently supports exact
   historical replay of the sealed inputs; no realtime latency claim is made.

## Input manifest

`nn_meta.v6_expansion.ExpandedInputs(path, expected_sha256)` reads a JSON
manifest with these fields:

- `schema`: `v6-expanded-inputs-v1`.
- `feature_contract_version`: `2026-09-06-tv13-option-ticks-v4`.
- `feature_names`: exact ordered `v6_expansion.EXTRA_FEATURES` (106).
- `selection_policy`: `previous-date-raw-moneyness-v1`.
- `moneyness`: must equal the executor target (currently zero).
- `tick_feature_policy`: exact `option_tick_dataset.feature_policy(...)`,
  with explicitly admitted conditions and retained condition reference files.
- `parity_pack`: `{path, sha256}` referring to an actual reviewed capture pack.
- `symbols`: per-symbol objects described below.

Each symbol binds `bars_sha256` from `v6_expansion.bars_sha256`,
`timeframe_flags` as `{path, sha256}` for an aware-index parquet frame,
optional `vwap_observations` with the same reference shape, `context`,
and `tick_store: {directory, task_sha256, store_sha256}`.
Context contains `minimum_tick`, `session_policy`, `as_of` and
`dependency_metadata` as specified in [the feature contract](V6_TRADINGVIEW_FEATURES.md).
The parity pack and actual context must have identical feature settings.
The RTH research policy is explicit `source_literal`, preserving source
membership transitions; it does not synthesize daily Setup ORB resets.

For request planning, retain a separately hashed planning manifest with actual
parity/context/policy; its tick stores may be absent. Planning does not bind
tick stores. After capture/materialization, create a new final manifest with
the required store anchors rather than overwriting the planning evidence.

Paths may be absolute or relative to the manifest. Symlinks are rejected.
Stores, raw captures, evidence, context and source/runtime hashes become
transitive campaign inputs. Mutation invalidates the run. Missing measurements
remain nullable; no selected contract is an explicit `unselected` state.
`decision_contract`, request ID and status survive the candidate interface.

The shared selector uses prior-date observed chains and current raw spot,
with a declared point-in-time provider. It avoids present-day Greeks and
refreshes the moneyness band at each decision. Renamed OCC roots require
explicit prior-date catalogue membership. Labels use the same selector.

## Request planning after context exists

Under the expanded pool/campaign/input environment, preview or execute local
request planning. This stage writes no option outcomes and starts no downloads:

```bash
./venv/bin/python -m scripts.plan_v6_option_requests \
  --symbols SPY,IBKR --output /absolute/path/to/new-request-plan
# Add --run to perform the underlying sweeps and write the inventory.
```

The output includes requests, per-family eligibility/cap/parameter provenance,
root aliases, canonical Pine/Python/config/runtime hashes and a final manifest.
Feed requests, selection provenance, manifest and aliases into
`prepare_option_tick_features` as documented in the tick feature runbook.
A request inventory is not a completed baseline freeze.

## Launch after the inputs exist

```bash
export NN_META_CAMPAIGN=v6-expanded-20260906
export NN_META_DATA_CANDIDATE=audit-repair-20260905-final
export NN_META_V6_INPUTS=/absolute/path/to/inputs.json
export NN_META_V6_INPUTS_SHA256=<separately-recorded-manifest-sha256>
bash scripts/run_freeze_v6_local.sh
# The printed plan is a preview. Execute the admitted full freeze:
bash scripts/run_freeze_v6_local.sh --run
```

The launcher always selects the expanded scope and a fresh full freeze.
It no longer inherits old v5 artifacts or sweeps only Keltner/BBW. A partial
family override or additive base is rejected. Runtime/dependency exceptions
fail the expanded worker instead of silently dropping a requested family.
A source may still legitimately produce no eligible proposal under declared
training/activity rules; that is distinct from a missing feature dependency.
