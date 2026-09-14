# V6 neural repair, execution validation and forward shadow

The September 12 campaign stays immutable. These commands create separate
research evidence; they do not promote a scanner or send alerts.

## Neural repair

`neural_validation.py` fits means/deviations on labeled training rows only.
An entirely missing training column gets mean 0, deviation 1, and an explicit
`inactive` entry. Its standardized value stays zero during validation and
inference, even if that column subsequently becomes observed. Constant and
single-observation columns get deviation 1. NaNs in other columns use their
training mean. Infinities, float32 overflow, invalid labels, non-finite losses,
weights and predictions stop the fit before a success receipt. GBT retains
native NaN handling. A failed NN family must not be described as a healthy
model that lost to GBT.

The two original all-missing columns are the ICT Asia/London range features.
The preserved input history contains RTH bars; default ICT Asia/London sessions
are outside RTH. Preserve those missing observations and the declared research
session policy. Do not synthesize overnight history to make columns finite.

Prepared arrays and seed receipts now bind the preprocessing implementation.
The reference evaluator, finalizer, parallel seed workers and disk/live readers
share the policy. Existing defective receipts are rejected, never rewritten.

The replacement `v6-cash-repair-20260913` completed under
`healys-v6-cash-repair-20260913.service`, September 13, 18:04–19:47 UTC.
All three evaluation folds, 40 final GBT seeds, 32 aggregate execution
comparisons and the readiness inventory completed. Scanner promotion remains
blocked on actual quote/roll, forward, parity and operating review evidence.
The prior `v6-neural-repair-20260913r2` scope is preserved after its fold-3
funding rejection. See the [cash-repair review](../reviews/2026-09-13-v6-cash-repair.md).
Do not launch a duplicate. The durable pipeline command used was:

```bash
./venv/bin/python -m scripts.v6_training_pipeline \
  --parent v6-local-20260906 \
  --campaign v6-cash-repair-20260913 \
  --reuse-completed v6-train-20260912r2 \
  --workers 2 --threads 2 --launch
```

This verifies/copies derived artifacts, reuses only compatible assembly and
objective-comparison outputs, and reruns evaluation/finalization in the fresh
scope. It does not reuse old NN evaluation, weights or prepared arrays. Source
or input drift refuses resume. Earlier failed/prepared repair scopes are
preserved and must not be relaunched with the changed source.

The pipeline automatically follows successful finalization with all 32 frozen
aggregate execution comparisons for the new model, then writes an evidence
inventory. `--launch` uses the home host's CPU topology (CPUs 2–7/10–15), a
600% CPU quota, nice 10, 24 GiB memory and 2 GiB swap limits. Two workers and
two threads retain the existing three-fold/40-final-seed budget. Omitting
`--launch`/`--run` previews commands. `--run` is the foreground entry point.

Inspect `nn_meta/campaigns/v6-cash-repair-20260913/v6/runs/`:

- `pipeline/status.json`: overall running/failed/complete stage.
- `continuation/latest.json` and `continuation/evaluate.log`: current training.
- `seed-jobs/*/*/complete.json`: verified per-seed health and artifact hashes.
- `pipeline/readiness.json`: inventory produced after training and validation.
- `training-service.log`: supervisor log.

The execution report will be under
`nn_meta/validation/v6-cash-repair-20260913-execution/`. Completed pipeline
stages resume only with matching receipts. Partial failed validation outputs
are preserved and require a fresh output location for a new validation attempt.
Source changes during training or the pipeline cause failure; do not modify
the bound code while the service runs. A pipeline completion is a research
completion; the readiness inventory cannot authorize scanner alerts.

Read current evidence without importing models or changing scanner state:

```bash
./venv/bin/python -m scripts.v6_readiness \
  --campaign-root nn_meta/campaigns/v6-cash-repair-20260913/v6
```

Supply `--execution-root` and `--forward-root` when those reports exist. The
auditor verifies output and source hashes, model identity, both neural heads,
expected fold seeds, final ensemble budget and independent quote ledgers. It
reports missing/stale evidence explicitly. External parity and the scanner
operating review remain separate requirements; no JSON success flag grants
promotion.

Unfundable candidate books are reported as ineligible; the ledger continues
to refuse borrowing or invented fills. Invalid accounting data remains fatal.
Cost reports can retain a funding rejection only when an independent ledger
rejects the same entry with matching balances. No return/drawdown is assigned
to that book. Aggregate revalidation retains the original policy's drawdown
brake and freezes its position fractions; it does not recompute counterfactual
brake decisions. Braked quote replay requires separate causal sizing support.

## Frozen execution revalidation

Run under the original expanded V6 configuration (`NN_META_POOL=v6`,
`NN_META_V6_EXPANDED=1`, the original `NN_META_V6_INPUTS` and SHA256 anchor,
and `NN_META_V6_PARITY_POLICY=deferred`). The original environment is retained
in `nn_meta/expanded_inputs/v6-local-20260906/resume.json`; the final manifest
and its SHA256 file are under that directory's `full-run/` folder.

```bash
./venv/bin/python -m scripts.validate_v6_execution \
  --campaign-root nn_meta/campaigns/v6-train-20260912r2/v6 \
  --output nn_meta/validation/NEW-EXECUTION-RUN
```

The command verifies completed source-campaign receipts, fixes the existing
ensemble policy and population, and compares its selected positions with the
frozen-DTE baseline from that same population. Both sides use the same marked
cash ledger. A second event/cash implementation checks the entire equity curve
and maximum drawdown. Each side is also checked with 60/300/900-second entry
limits, measured after the 15-minute signal closes, and four declared costs.
Rejected fills never backfill or reschedule the original selected positions.
Actual-fill symbol/slot conflicts are reported explicitly.

This is **final selection/revalidation**, overlapping earlier test windows.
It is not another test of the ensemble. Aggregate spread assumptions are
sensitivity scenarios, not measured bid/ask fills. No threshold is retuned.

For quote replay add `--quotes tape.parquet --quote-evidence evidence.json`.
The tape needs `contract`, timezone-aware `quote_ts` and `available_at`, `bid`,
`ask`, `bid_size`, `ask_size`. Evidence needs `quotes_sha256`, `source`,
`availability_basis` (`receipt` or `sip`) and `coverage_limitations`. A SIP tape
does not establish historical local receipt latency. Duplicate/conflicting
receipt timestamps require a source export with unambiguous ordering.

Each scenario buys the ask, sells the bid, charges dollar commission per
100-share contract, and optionally adds adverse slippage. Do not add another
synthetic spread to these quote prices. An invalid new quote supersedes older
valid quotes; a late older event cannot replace newer market state. The first
fillable quote must arrive within the declared entry-delay limit. Missing
initial entries reject positions. Missing exit quotes retain the loss, with
an explicit conservative zero valuation and audit event. An unavailable roll
entry retains prior proceeds as cash through the planned terminal timestamp.

Rolled positions require `--legs legs.parquet`: one row per frozen leg with
`trade_id`, contiguous zero-based `leg_index`, `contract`, `entry_decision_ts`,
`exit_decision_ts`, and `expiration_ts`. All timestamps must have a timezone.
Leg counts must equal the preserved execution counts. Without a leg export,
only genuinely single-leg positions can be replayed. Never silently discard
rolled positions. Original labels expose only the first contract.

Quote scenarios screen for positive displayed sizes but use fractional
contracts. They do not establish market-impact capacity. Marks include quote
events and a weekday RTH cadence; exchange calendar/early-close coverage is
not certified by that cadence. Missing scheduled quotes are explicitly
conservative observations, not claimed market prints.

Outputs include a frozen scope, selected rows, scenario equity curves,
rejection/audit files, `results.json`, and hash-bound `complete.json`. Output
directories must be fresh and outside the completed campaign.

## Live inputs and shadow collection

The expanded V6 scanner is currently **shadow-only**, including when `--paper`
is supplied. Ordinary existing expert paths keep their own behavior.
Shadow writes an isolated SQLite journal, dedupe state and summaries. It never
opens paper positions or drains any notification outbox.

Build a `v6-live-snapshot-v1` draft with `captured_at`, `parity_policy`, and
exact `{path, sha256}` references for:

| Reference | Required evidence |
| --- | --- |
| `expanded_inputs` | Existing expanded-input schema, full technical history/context and fixed original history origin; verified parity pack or the explicit deferred research contract |
| `bars` | `symbol,timestamp,available_at,Open,High,Low,Close,Volume`; timezone-aware UTC bar/receipt timestamps, closed bars only |
| `raw_bars` | Separate raw 15-minute panel with existing raw-price provenance attributes, tz-naive UTC `timestamp` and timezone-aware `available_at` |
| `surface` | Raw-spot surface provenance, unique `underlying,date`, receipt `available_at`, surface features |
| `daily_context` | Unique `underlying,date`, receipt `available_at`, `market_iv,rv_iv_spread,beta_60d` |
| `chain` | `symbol,contract,first_observed_at,available_at`; actual contract availability must precede the requested UTC date |
| `condition_mapping` | Frozen historical-policy hash, `alpaca_opra_string` namespace, explicit allowed string conditions and hash-bound supporting references |
| `execution_quotes` (optional) | The canonical quote-tape schema above, for subsequent forward execution evidence |

Condition mappings bind to SHA256 of the historical tick-feature-policy object
serialized with sorted keys and compact separators. Massive integer conditions
must never be applied directly to Alpaca string conditions. The live adapter
keeps the provider/receipt distinction visible; this mapping alone is not
external feature parity or scanner admission.

`tick_windows` maps each exact decision request ID to `ticks` and `coverage`
file references. Ticks are the existing raw-payload-preserving journal JSONL
records. Their normalized fields are rechecked against the original msgpack
payload. Coverage uses `v6-receipt-coverage-v1` and binds the contract, receipt
clock, start/end nanoseconds, tick-file hash, reviewer, source references, zero
declared gaps/errors and `reviewed_complete_capture` status. A heartbeat or
subscription request does not establish complete capture. Do not generate that
status from the heartbeat. Missing evidence causes a recorded failed scan.

Pre-subscribe before the signal window; subscribing after selecting a contract
cannot recover its preceding 15 minutes of live receipt history. Keep original
technical history and local-calendar grouping anchors; rolling-window rebasing
is rejected. The shared feature constructor supplies all expanded fields before
scoring. Snapshot and raw-spot receipts must exist by the actual scan time.

```bash
./venv/bin/python -m scripts.seal_v6_live_snapshot \
  --draft ACTUAL-INPUTS.json --output NEW-SNAPSHOT-DIRECTORY \
  --training-inputs ORIGINAL-EXPANDED-MANIFEST.json \
  --training-inputs-sha256 ORIGINAL-EXTERNAL-SHA256

./venv/bin/python -m nn_meta.live.v4_scan --once --shadow --workers 1 \
  --shadow-dir nn_meta/validation/NEW-FORWARD-SCOPE \
  --bundle nn_meta/campaigns/v6-train-20260912r2/v6/model_final \
  --live-snapshot NEW-SNAPSHOT-DIRECTORY/snapshot.json \
  --live-snapshot-sha256 SEALED-SNAPSHOT-SHA256
```

Use the same original expanded configuration as revalidation. The shadow
scope binds model artifacts, policy, portfolio budget, baseline and sources.
Changed sources/policy require a new scope. First recorded predictions are
immutable. All DTE variants and both candidate/frozen-baseline decisions remain
inspectable. A scored selection is not automatically an executed position.

To resolve actual forward records:

```bash
./venv/bin/python -m scripts.replay_v6_shadow \
  --database FORWARD-SCOPE/shadow/observations.sqlite3 \
  --legs FROZEN-EXITS.parquet --exit-evidence EXIT-RECEIPTS.json \
  --exit-evidence-sha256 EXTERNAL-EXIT-EVIDENCE-SHA256 \
  --output NEW-FORWARD-REPLAY
```

Exit evidence binds `legs_sha256`, `exit_policy: frozen-mechanical-signals`,
and actual `source_receipts`. Leg entry decisions must match the original
scoring observation, and the first contract must match the recorded selection.
`exit_decision_ts` must equal the actual `exit_observed_at`; bar starts cannot
be substituted for known exit times. Unresolved selections suppress that
side's performance report, avoiding a resolved-only survivorship result.
Frozen signal-time reservations and sizing are applied before quote replay;
failed fills do not backfill those reservations. No forward results exist yet.

## Private dashboard integration

`integrations/dashboard/v6-followup.patch` contains the tested publisher
integration for the separate dashboard checkout. `v6_followup.py` uses only
bounded JSON reads; it never imports a model or reads the SQLite/raw tape.
The existing Training table renderer displays its tables without a frontend
schema change. Configured execution reports must bind the displayed campaign's
model and successful completion receipt. Shadow summaries bind the same model
and show stale status after 30 minutes without a pass.

Optional publisher environment settings:

```text
V6_EXECUTION_ROOT=nn_meta/validation/v6-execution-20260913r3
V6_SHADOW_ROOT=nn_meta/validation/ACTUAL-FORWARD-SCOPE/shadow
```

Paths resolve inside `TRAINING_ROOT`; external/symlinked paths are refused.
Leave the shadow setting unset until an actual forward scope exists. Installing
code does not configure these paths, start collection, or publish new evidence.
