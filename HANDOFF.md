# HANDOFF — state for the next session

Written 2026-08-26 ~00:15 CDT (overnight session). Protocol: `CLAUDE.md`.
Previous handoff (v5 data layer complete):
`handoff-history/HANDOFF-2026-08-25-v5-data-layer-complete.md`.

## The one-paragraph state

**The v5 freeze campaign is IN FLIGHT on Batch.** Three single-symbol
pilot jobs (AAPL / X / BYND, jobs `v5-freeze-0f132b6-2257{07,10,12}`) are
running on the final fleet shape — n2-highmem-8 SPOT, 1-core/12GiB tasks,
8h leash, image `0f132b6` — after the first pilot was kill-looped by the
old 3–4h leash (AAPL alone is ~4.3h on one e2 vCPU; box measurements
under-predict cloud ~5x). User decisions 2026-08-26: go WIDE not deep
(freeze is single-threaded; 8-cores-per-symbol rejected), and AUTO-LAUNCH
the 453-task fleet as soon as the pilots validate. Checkpoints land in
`gs://healys-backtester/out/freeze_specs_v5/` (one json per symbol; dead
members like X publish a spec with the symbol under "skipped" — that is a
result, not a failure).

## The fleet launch (do this when all 3 pilots SUCCEED)

1. Verify: 3 jsons in `gs://healys-backtester/out/freeze_specs_v5/`, and
   AAPL.json has real strategy entries (spot-check against
   `nn_meta/artifacts_v5/freeze_smoke_DKNG.json` for shape).
2. Submit (SHARDS must be exactly 453 = len(config.UNDERLYINGS) for
   one-symbol-per-task; already-frozen symbols skip instantly):
   ```
   TASK_MODE=freeze NN_META_POOL=v5 IMAGE_TAG=0f132b6 PARALLEL=60 \
     PROJECT=healys-batch BUCKET=gs://healys-backtester \
     bash deploy/gcp/submit.sh 453
   ```
3. Watch via `bash deploy/gcp/watch_job.sh` (binds to `.last_job`).
4. When all tasks end: `TASK_MODE=freeze-merge NN_META_POOL=v5
   IMAGE_TAG=0f132b6 PROJECT=... BUCKET=... bash deploy/gcp/submit.sh 1`
   publishes the merged spec to `artifacts_v5_in/baseline_spec.json`.

Expected: ~20 concurrent symbols (global quota, see below), ~2 days wall,
~$40–60 credits total. A few late tasks may need a resubmit if spot
preempts near the 8h leash — checkpoints make that free.

## Quota reality (verified live 2026-08-26)

`CPUS_ALL_REGIONS = 32` (project-global, free trial, unbumpable) is the
BINDING cap — regional reads (N2 200, CPUS 200) are a mirage. 4×
n2-highmem-8 = 32 CPUs = 20 packed tasks max. The fleet is submitted with
PARALLEL=60 so if the user upgrades billing (credits carry over) and bumps
the quota mid-run, Batch widens automatically. Memory
`gcp-free-trial-budget` updated.

## What landed tonight (all pushed)

1. **task.sh pool paths** (`f4e787a`): non-v31 pools publish under
   `out/<pool>/`. Before this, a v5 build would have skip-checked against
   v31's 118 `out/meta_rows` files (franken-dataset), a v5 assemble would
   have overwritten v31's live `out/meta_dataset.parquet`, and v5
   evaluate/finalize would have staged from/published to hardcoded v31
   dirs (outputs dying with the VM). Freeze paths untouched → the freeze
   fleet still runs on image `0f132b6`; REBUILD + pin IMAGE_TAG before the
   BUILD stage (`scratch_build_image.sh` is the runbook step).
2. **submit.sh freeze sizing v2** (`7673b59`): 8h leash, n2-highmem-8,
   BOOT_GB=100 (five packed containers each rsync their own ~10GB cache
   copy; the 30GB default would ENOSPC the VM). New `BOOT_GB` knob wired
   into the job JSON for all modes (default 30).
3. **DECISIONS.md**: the wide-vs-deep decision + quota reality, dated
   2026-08-26.
4. First pilot job `v5-freeze-0f132b6-184938` was CANCELLED (kill-looped,
   nothing published) — ignore it in job listings.

## Standing warnings (delta)

- The freeze is SINGLE-THREADED — do not "speed it up" by giving tasks
  more cores; width is the only lever (and it's quota-capped).
- X/SWTX/WBA-class dead members freeze as "skipped" — a spec json with
  the symbol in `skipped` is CORRECT output, not a failure to fix.
- The surface NaN / renamed-listings caveats from the previous handoff
  still stand; see `handoff-history/HANDOFF-2026-08-25-*`.
- Local monitors for the pilots live in this session only; if the session
  is gone, re-derive from `gcloud batch jobs list` + the checkpoint dir
  (never from memory — job names above are the binding IDs).

## Next after the freeze (unchanged plan)

Dataset build fleet (needs image rebuild for the pool-path fix) →
assemble (`--membership` ON) → evaluate/finalize on Batch. Then: Drive
backup migration (user OAuth step first), monthly PIT/FA timer on the box.
