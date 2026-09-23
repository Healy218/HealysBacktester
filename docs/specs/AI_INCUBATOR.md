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
  --v6-index V6_DATA_INDEX.json --output-dir RUN/ \
  --checkpoint RUN/checkpoint.json
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

The current V6 forward snapshot is now a complete replay input for the actual
live GBT release: the 2026-09-22 pass publishes 304 rows with all 164 required
features under `incubator/artifacts/v6-live-20260922/`. GBT's native NaN policy
is recorded in the manifest. The 40-member bundle loaded successfully and
produced 304 read-only predictions with status `executed_pending_outcome`.
This is the V6 daily path. The older Keras bundle remains retired from V6 daily
use because its `prem_spot` contract does not match the causal live candidate
schema. The exact-identity outcome join remains required before any performance
score is reported.

The outcome joiner is implemented and requires exact
`symbol/strategy/dte/entry_ts` identity matches to an explicit `net_return`
source. The current V6 portfolio ledger has 48 cycles with allocation statuses
(`opened` and `unfilled`) but no candidate-level realized-return column, so the
2026-09-22 matrix remains pending and has not been scored.

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
   **V6 contract-aligned prediction-only validation is done; real scoring waits
   for candidate outcomes. V5 remains supported for its transition period and
   V7 remains gated.**
