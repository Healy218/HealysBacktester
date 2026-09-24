# AI Artifact Incubator — initial contract

## Status

Read-only implementation with bounded campaigns. The runner verifies and
dry-runs bundles; it does not send alerts, place orders, or mutate source
artifacts. V5/V6 bundle execution has been tested in the disabled sandbox,
including the real Keras replay entrypoint. V7 onboarding remains a
compatibility decision after V7 readiness.

## Bundle contract

Each `.tar.gz` must contain exactly one `manifest.json` and the files listed in
that manifest. Paths are relative POSIX paths; symlinks, hard links, duplicate
members and traversal paths are rejected. Every payload file has a byte size
and SHA-256 digest. The manifest itself has a canonical-content digest.

Required manifest fields:

- `schema_version`
- `artifact_id` and `artifact_version`
- `artifact_kind`
- `created_at`
- `compatibility.forward_data_contract`
- `files`
- `read_only: true`

Artifact IDs must be unique in a run. A missing, incompatible, malformed or
duplicate artifact is refused; no partial result is emitted.

## Current commands

```text
./venv/bin/python scripts/ai_incubator.py pack SOURCE OUT.tar.gz \
  --artifact-id v5-... --artifact-version ...
./venv/bin/python scripts/ai_incubator.py verify BUNDLE.tar.gz
./venv/bin/python scripts/ai_incubator.py dry-run BUNDLE.tar.gz RECEIPTS/
./venv/bin/python scripts/ai_incubator.py discover BUNDLE_ROOT/ --output registry.json
./venv/bin/python scripts/ai_incubator.py inspect-forward V6_DATA_INDEX.json --as-of YYYY-MM-DD
./venv/bin/python scripts/ai_incubator.py sandbox-run BUNDLE.tar.gz REQUEST.json RECEIPTS/
./venv/bin/python scripts/ai_incubator.py campaign BUNDLE_ROOT/ \
  --request REQUEST.json --output-dir RUN/ --checkpoint RUN/checkpoint.json \
  --run-id close-YYYYMMDD
./venv/bin/python scripts/ai_incubator.py metrics RESULTS.jsonl
./venv/bin/python scripts/ai_incubator_after_close.py --bundle-root BUNDLES \
  --v6-index V6_DATA_INDEX.json --v6-candidates-root V6_PASSES/ \
  --v6-model-config V6_MODEL/ensemble_config.json \
  --feature-root ARTIFACTS/daily --output-dir RUN_ROOT/ \
  --as-of YYYY-MM-DD
```

The dry-run writes `status=verified_not_executed` receipts. The forward adapter
verifies the published V6 pointer, snapshot manifest, file hashes and causal
`through` boundary before producing a replay request. The sandbox runner is
execution-disabled unless explicitly enabled and refuses bundles without a
manifest entrypoint. The Keras replay entrypoint loads the sealed ensemble
configuration, scalers and models, reads only the requested immutable snapshot,
and writes `results.jsonl`; successful output is scored by the shared metrics
adapter and included in the receipt. A 128-row real V6 replay smoke test now
loads all 40 members and completes under the thread-limited sandbox. Discovery is
fail-closed on invalid bundles, duplicate artifact IDs and incompatible
forward-data contracts. The systemd service and timer are committed but
deliberately not enabled; they require a populated `incubator/artifacts/`
directory and an explicit activation decision.

The V6 data index is a verified context snapshot, not itself a complete
candidate feature matrix. The daily capture selects the named session's
`passes/YYYYMMDDT*/candidates.parquet`, verifies entry dates and model columns,
and seals a distinct `incubator/artifacts/daily/v6-YYYYMMDD/` matrix. The
2026-09-22 pass publishes 304 rows with all 164 required features. GBT's native NaN policy
is recorded in the manifest. The 40-member bundle loaded successfully and
produced 304 read-only predictions with status `executed_pending_outcome`.
This is the V6 daily path. The older Keras bundle remains retired from V6 daily
use because its `prem_spot` contract does not match the causal live candidate
schema. The exact-identity outcome join remains required before any performance
score is reported.

The outcome joiner is implemented and requires exact
`symbol/strategy/dte/entry_ts` identity matches to an explicit `net_return`
source. The 2026-09-23 join matured one of the 304 rows from the 2026-09-22 V6
pass: DUOL/macd/30 DTE at 19:15 UTC, with
`net_return=-0.12458142055209864` derived from the closed paper position's
recorded return factor. The other 303 rows remain pending, so the matrix is
replay-ready but the performance/readiness gate remains pending. The curated
daily registry excludes the duplicate old Keras replay bundles and retains the
live GBT artifact. A separate V5 Keras/EV bundle is now packaged; the active
server configuration hash matches the packaged configuration. Its corrected
replay helper uses the magnitude head and saved `std` scaler. The 304-row V5
compatibility smoke test used V6-origin rows and is **not** V5 paper evidence.
The V5 server currently saves a trade ledger, not full candidate features, so
the daily runner records V5 as input-blocked until a genuine V5 capture is
published with `generation=v5` and passed via `--v5-feature-dir`. V6 rows must
never be substituted.

The daily runner routes each artifact to its own sealed request, writes
per-artifact attempt directories and receipts, a date-scoped checkpoint,
`after-close-summary.json`, and a compact `performance-log.json`. Changing
execution mode, budget, bundle, or requests invalidates checkpoint reuse.
Pending outcomes record prediction counts only; no performance is fabricated.
The timer remains disabled, and the shipped service has no `--allow-execution`.
Activation requires the TODO.md V7 gate and explicit paper-data-boundary
approval. The service's eventual activation configuration must also include
OS-level network isolation and resource cgroups; the current subprocess
limits alone are not a production isolation claim.

Retention: keep bundles, sealed matrices, request provenance, receipts and
performance logs immutable for at least 90 days after their last relevant
outcome matures, and confirm a recoverable backup before any manual pruning.
No automatic deletion is performed. Treat a changed source or bundle as a new
version, never overwrite an existing seal.

The curated executable registry is `incubator/artifacts/active/`. Historical
bundles elsewhere under `incubator/artifacts/` are preserved but not passed to
the scheduled runner. Both current V5 and V6 artifacts are EV-mode: the common
`prediction` field is their decision EV; V6 additionally records `p_win`.
Older V6 smoke output used P(win) in `prediction` and must not be scored as EV.

## Next implementation slices

1. Inventory and package the actual V5/V6 sealed model directories. **Done for
   local V5 and home V6 smoke tests.**
2. Add a registry/discovery layer with duplicate-ID and compatibility checks.
   **Done.**
3. Add a read-only forward-data adapter and sandboxed execution interface.
   **Done for V6 snapshot verification and execution-disabled receipts.**
4. Add common metrics, per-artifact receipts, checkpoint/resume and resource
   budgets. **Done, including campaign, memory, CPU, output and wall-clock
   bounds.**
5. Add the after-market-close scheduler only after dry-run and failure tests
   pass. **Done; committed but disabled by default.**
6. Validate against V5/V6 paper data, then onboard V7 through the same contract.
   **V6 daily prediction-only validation is done; real scoring waits for
   candidate outcomes. V5 bundle compatibility is verified but genuine daily
   feature capture is outstanding. V7 and production activation remain gated.**
