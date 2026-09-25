# V7-3: proof-aware entry-demand scheduler validation

The resumable 591-security scheduler is implemented and four validation cases
pass. V7-3 remains open. This milestone produces pre-decision option-feature
requests; it does not establish complete option execution paths or readiness.

## Frozen-parent contract

`scripts/run_v7_entry_demand.py` reads the sealed V7-2 completion gate, verifies
its catalog gate and report hashes, and retains the exact 591 × 5/15/30 scope.
Every consumed feature/proposal summary must match its deep-audited receipt pair.
The original 415-security reuse manifest must agree with those pairs, and the
ten additional loader cases must match the separate equivalence report.

An explicit demand-only view carries current dependencies plus the original
proof files. Every historical store receipt and declaration is also bound by
the unchanged entry-demand parent collector. It never rewrites a feature store,
substitutes a new historical receipt, or changes global reader behavior.
The only admitted drift is the two exact reviewed source pairs: the historical
proposal loader for the 415+10 securities, and audit-only `catalog_reuse.py`
for the ten additional securities. Each pair checks both old and current SHA256.
All other inputs/sources and runtime remain strict. The existing producer,
StoredFeatures, StoredProposals and entry-demand implementation are unchanged.

## Scheduling and recovery

The CLI defaults to read-only planning. `--run` enables generation with a
required stage-byte allocation, 1–4 configurable outer workers, one inner
thread, and at least 100 GiB free disk. The controller takes a process lock,
queues only the configured number of workers, and writes atomic stage progress.
Each worker seals separate demand, request-export and completion-checkpoint
receipts. A worker failure stops new scheduling and is recorded with its log.
The disk guard counts partial evidence and conservatively includes concurrent
disk consumption. Completed securities are verified before reuse; interrupted
securities restart at the security boundary with their partial evidence retained.
This is not within-SQLite checkpoint recovery.

The output declaration always retains all 591 IDs. Explicit `--security-id`
arguments select validation work and cannot make the full-scope completion flag
true. The old 1,773-store catalog progress meter does not monitor this stage.
The scheduler source hash is itself a demand parent: preserve this version or
explicitly handle lineage before changing it after outputs have sealed.

## Measured validation

| Security | Proof route | Proposals | Requests | Contracts |
|---|---|---:|---:|---:|
| BBG004FPTZB8 (MTUM) | Current loader | 29,843 | 3,552 | 76 |
| BBG010FXVQ98 | Original reuse manifest | 2,913 | 1,392 | 20 |
| BBG000B9YJ35 | Additional loader equivalence | 65,179 | 2,730 | 43 |
| BBG000BF8TF5 | Reuse manifest, zero proposals | 0 | 0 | 0 |
| Total | Four validation securities | 97,935 | 7,674 | 139 |

Every security retained all 8,451 variants. The 7,674 unique requests union to
6,700 bounded capture windows. Preserved target outcomes include 11,000
`no_contract` and 75 `no_fresh_raw_spot`; neither manufactures requests.
SQLite integrity, proposal/selection/request counts, foreign links, decision
clocks and export membership passed. The new MTUM SQLite SHA256 is exactly the
original strict-reader pilot's SHA256, not merely an equal row count.

The same four-security command was rerun. All 12 demand/export/checkpoint
receipts remained byte-identical. Zero-request demand and its empty export are
valid completed security checkpoints. The first run retained about 37.5 MB,
well within its 2 GiB validation allocation. The filesystem had about 344.5 GB
free before the run. No downloads, V6 changes or frozen-store edits occurred.
The post-validation allocated project footprint is 421,285,347,328 bytes
(`du -sx --block-size=1 .`, about 421.3 GB). The older roughly 230 GB project
estimate is stale; the full-run budget must account for this actual footprint.
These small cases do not support a full-build ETA or provider-volume estimate.

Evidence:
- `nn_meta/validation/v7-3-scheduler-20260925`
- `nn_meta/validation/v7-3-scheduler-validation-20260925/report.json`
- `nn_meta/validation/v7-3-scheduler-validation-20260925/request-union.json`

Four focused regressions check narrow drift admission/rejection, changed proof
and parent rejection, unchanged proposal/demand behavior, receipt preservation,
and exact validation selection. Full suite: **2,405 passed, 18 subtests passed,
20 warnings**, 120.06 seconds (`./venv/bin/python -m pytest tests/ -q`).

## Reproduction

The command below performs the same validation and verifies/reuses sealed work:

```bash
./venv/bin/python scripts/run_v7_entry_demand.py \
  --completion nn_meta/validation/v7-2-completion-20260925 \
  --output nn_meta/validation/v7-3-scheduler-20260925 \
  --workers 2 --max-output-bytes 2147483648 \
  --security-id BBG004FPTZB8 --security-id BBG010FXVQ98 \
  --security-id BBG000B9YJ35 --security-id BBG000BF8TF5 --run
```

Remove `--run` for read-only planning. Inspect the output's `progress.json` and
`logs/<security_id>.log`. Omitting all security selectors requests all 591;
that full generation was not launched at this milestone. Its storage forecast
and total-project allocation must be established first, using actual full-scope
decision/request counts rather than this sparse validation sample. The 2 GiB
validation limit is not a total-project or full-run budget.

Then finish full entry demand and its request union, dated option-class hours
and standard references, followed by entry fills, marks, exits, rolls and
applicable physical-delivery windows. The 250 GB acquisition ceiling still
applies. V7-3 through V7-7 remain unfinished; no training readiness is claimed.
