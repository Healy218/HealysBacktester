# Draft decision-time option tick features

This isolated implementation produces research inputs from exact selected-contract windows. It does not admit a model, establish predictive value, change the global trade-condition policy, or download history. The active main-checkout pilot remains separate.

## Selection and coverage

`DecisionContractSelector.request()` selects using the raw underlying close at the decision and contracts observed by the previous UTC date. It queries no option fills or outcomes. Its request includes `symbol`, bare `contract` OCC, integer nanosecond `window_start_ns`, `window_end_ns`, and `decision_close_ns`, plus selection/raw-price/chain availability timestamps and consumer IDs. Each feature window is `[start, end)` with `end <= decision_close`. The selector's initial expiry boundary is decision date plus one day, even for target DTE 0.

`create_task_manifest()` accepts these requests and preserves selector policy/right/DTE contexts. Exact repeated requests share a stable SHA256 `request_id`; strategy consumers are combined. Conflicting selection evidence for the same key is refused. Unselected requests retain a null contract, explicit reason and null features. A hash preserves evidence; it cannot establish whether a caller invented a selection. Bind the actual selection evidence and raw/chain inputs in the parent campaign.

`plan_capture_windows()` combines overlapping or touching windows for the same contract. It does not bridge gaps unless explicitly configured. The local CLI additionally groups identical bounds into batches of at most ten contracts. Coalescing changes capture organization, never the requested feature windows. One verified capture must cover each complete requested window; partial captures are not stitched, and multiple suitable captures are refused as ambiguous.

## Numeric contract

`nn_meta.option_tick_dataset.NUMERIC_FEATURES` fixes these ten nullable floating-point columns:

| Column | Meaning |
| --- | --- |
| `opt_tick_spread_bps` | Valid-time weighted bid/ask spread relative to midpoint, basis points |
| `opt_tick_size_imbalance` | Valid-time weighted `(bid_size - ask_size) / (bid_size + ask_size)` |
| `opt_tick_valid_quote_fraction` | Valid quote duration divided by window duration |
| `opt_tick_quote_age_seconds` | Last observed quote event age measured at decision close; quote quality is reported separately |
| `opt_tick_quote_updates_per_second` | Observed quote updates divided by window seconds |
| `opt_tick_trade_count_per_second` | Eligible valid trade observations divided by window seconds |
| `opt_tick_trade_volume_per_second` | Eligible contract volume divided by window seconds |
| `opt_tick_trade_vwap_mid_bps` | Eligible window VWAP relative to the final quote midpoint when valid and fresh at window end, basis points |
| `opt_tick_signed_volume_fraction` | Quote-test signed eligible volume divided by eligible volume; null when none classified |
| `opt_tick_classified_volume_fraction` | Quote-test classified eligible volume divided by eligible volume |

Null means unavailable measurement and is never imputed. A genuinely empty, fully captured window may have zero observed counts and zero quote coverage; missing capture coverage fails instead. A wider window ending before the decision remains a historical window: quote age includes the additional lag; spread, VWAP and midpoint describe that window. The initial selector always ends its window at the decision close.

The canonical engine's `reported_*` statistics include valid reported prints even when their conditions are unapproved. The store separately computes eligible statistics from an actually filtered trade view. Every condition on a print must be explicitly admitted; missing, empty, unknown or mixed unapproved conditions are excluded. Quote order and original capture hashes remain intact. Corrected/invalid prints and quote-signing ambiguity gates remain excluded by the canonical engine. Reported, eligible and condition-excluded counts/volumes are retained as audit columns, separate from the model features.

`feature_policy()` defaults to no admitted trade conditions. An explicit `[209]` research policy requires a hashed condition reference such as [the captured Massive mapping](../reviews/2026-09-06-option-condition-209.json). That reference supports regular aggregation of code 209; it does not determine aggressor direction or guarantee historical mappings. Historical SIP availability does not establish historical local receipt latency. `compute_feature_row(reported, metadata, eligible=...)` can normalize equivalent canonical receipt-based live results later; callers must supply a genuinely filtered eligible result.

## Immutable artifacts and API

`create_task_manifest(requests, selection_reference_paths=[...], feature_policy=...)` returns the bound task. `load_task_manifest(path, expected_task_sha256=...)` verifies a saved task against its separately recorded review hash. Inputs use explicit noncredential evidence files. Source bytes for feature calculation, capture verification, selector/provider and price-basis helpers, plus Python/NumPy/pandas/PyArrow versions, are pinned.

`materialize_store(task, capture_directories, output_dir)` requires a new output directory and verifies the original Massive compressed bytes, canonical records, contract identities, pagination completeness and bounds. It writes `task.json`, `features.parquet` and a completion `manifest.json`, published last. Changes to task/source/reference/capture bytes fail closed. Outputs are never overwritten or resumed in place.

`load_feature_store(directory, expected_task_sha256=..., expected_store_sha256=...)` verifies both external anchors, file inventory, original captures, policy/source references, exact row keys and full required-window coverage. Record both returned hashes in the parent campaign at creation; blindly obtaining expected hashes from the same artifact at read time is not an external integrity check.

`join_decisions(frame, directory, expected_task_sha256=..., expected_store_sha256=...)` requires `request_id` and all five exact key columns. It preserves repeated consumer rows and order. Missing keys, shifted timestamps and ambiguous contracts fail; there is no nearest-time fallback. `allow_unselected=True` explicitly preserves unselected rows with null features and status. The default refuses them so the caller must decide how to handle exclusion.

The implementation loads the supplied bounded captures and result table into memory and rechecks original bytes on read. Partition full-history work into bounded tasks/stores. It does not yet provide a distributed capture scheduler or a verification bypass for large archives.

## Local CLI

Create `requests.json` as an explicit request list and `policy.json` from `feature_policy()`. Supply actual selection evidence separately. Preview is the default:

```bash
./venv/bin/python -m scripts.prepare_option_tick_features prepare \
  --requests /tmp/review/requests.json --policy /tmp/review/policy.json \
  --selection-reference /tmp/review/selection.json \
  --output /tmp/review/prepared
```

Add `--run` to write the immutable task and capture plan locally. Requests and policy files themselves are also bound as references. The printed task hash is the review anchor. No command in this module downloads data or loads credentials.

Once separately authorized captures exist, verify and materialize them using that recorded hash:

```bash
./venv/bin/python -m scripts.prepare_option_tick_features materialize \
  --task /tmp/review/prepared/task.json \
  --expected-task-sha256 RECORDED_TASK_SHA256 \
  --capture /absolute/verified/capture \
  --output /tmp/review/store --run
```

Without `--run`, materialization only previews paths and verifies the task; it explicitly reports that capture contents have not yet been checked. It never substitutes the old same-day SPY pilot for a different contract selected by the new policy.
