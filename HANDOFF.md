# HANDOFF — state for the next session

Written 2026-09-01 ~14:15 CDT. Protocol: `CLAUDE.md`.
Previous handoff (freeze complete, build stage opening):
`handoff-history/HANDOFF-2026-08-29-v5-freeze-complete.md`.

## The one-paragraph state

**v5 freeze: DONE.** 453/453 symbols, merged spec published at
`gs://healys-backtester/artifacts_v5_in/baseline_spec.json` (441 frozen,
12 skipped-thin, all 10 families represented). **v5 dataset BUILD: in
flight, 144/441 rows** (`out/v5/meta_rows/` + matching `meta_marks/`).
Three producers run concurrently and coordinate ONLY through the bucket
skip-check (`out/v5/meta_rows/<sym>.parquet`): two cloud fleets and the
home box. Nothing else in the campaign is running; the live scanner
(V118 on `main`) is untouched by all of this.

## What is running right now

| Producer | Job / how | Notes |
|---|---|---|
| Cloud fleet A | `marks-build-5a76e1c-011718` (c2d-highmem-8 SPOT) | c2d pool went dry ~07:00Z Tue; job alive, 0 workers, will refill if c2d returns |
| Cloud fleet B | `marks-build-5a76e1c-104922` (n2-highmem-8 SPOT) | the twin; grabbed all 20 slots within 10 min of submit |
| Home box | `scripts/run_build_v5_local.sh`, detached, `logs/build_v5_local.log` | 3–4 autosized workers, walks the spec BACKWARDS (Z→A) to meet the fleets in the middle |

Both fleets use image **`5a76e1c`** and `PARALLEL=60`; the global
`CPUS_ALL_REGIONS=32` caps total concurrency at ~20 packed tasks, so
running both costs nothing extra — it just removes single-spot-pool
dependency (proven: n2 filled while c2d was dry).

Restarting any of them is safe and cheap — see "If you need to relaunch".

## What survives a session clear (checked 2026-09-01)

SURVIVES: both cloud fleets (they run in GCP), the home-box builder (it
was launched `setsid nohup`, so it outlives the CLI), and the server
dead-man (a systemd *user* timer with linger enabled).
DIES: every in-session Monitor — the 30-min build watchdog with its
stall and mass-failure Telegram alarms. **Re-arm a watchdog early in the
next session**, or the first sign of a wedged fleet will be a stale row
count. Never re-derive job state from memory: `gcloud batch jobs list`
plus `gsutil ls out/v5/meta_rows/` is the ground truth.

## The two mechanisms that make this work

1. **Per-family checkpoints** (`build_symbol_rows(..., partial_dir=)`,
   commit `b995b35`). A v5 symbol is ~8h (10 families × DTE grid) and
   spot preemption used to lose ALL of it. Each finished family now
   writes `<sym>.<strat>.rows.parquet` (+ `.marks`), atomically,
   marks-before-rows; a rerun resumes at the first unfinished family.
   task.sh pulls a symbol's partials before building and pushes every
   4 min in the background. Preemption now costs ~30–60 min.
   Validated by kill/resume on ZS before rollout.
2. **Bucket-as-coordinator.** Every producer skip-checks the bucket
   before a symbol and publishes there after. Worst case for a
   near-simultaneous start is one duplicated symbol.

## If you need to relaunch

```
# cloud (either family; ALWAYS build the image first — submit.sh now
# fails closed if the tag has no manifest)
bash deploy/gcp/build_image.sh                     # tags $(git rev-parse --short HEAD)
TASK_MODE=build NN_META_POOL=v5 IMAGE_TAG=<tag> PARALLEL=60 \
  MACHINE=n2-highmem-8 PROJECT=healys-batch BUCKET=gs://healys-backtester \
  bash deploy/gcp/submit.sh 441

# home box (detached — harness background tasks get killed on this box)
setsid nohup scripts/run_build_v5_local.sh > logs/build_v5_local.log 2>&1 &
```

## When the build finishes

1. **Reconcile**: diff `out/v5/meta_rows/` against the spec's 441
   symbols and resubmit stragglers (one task died permanently in an
   earlier fleet when preemption exhausted its retries).
2. **Assemble**: `TASK_MODE=assemble NN_META_POOL=v5 IMAGE_TAG=<tag> …
   bash deploy/gcp/submit.sh 1` — `--membership` defaults ON for v5.
3. Then the evaluate/finalize ladder (PBO + deflated Sharpe are already
   wired) — the actual verdict on whether the wide pool beats v31.

## Hard-won facts (do not relearn these)

- **Spot machine families are not interchangeable.** e2 churned 3× in 5h;
  n2 and c2d each run clean for ~12h then sweep during US business
  hours. Run a twin fleet on a second family instead of betting on one.
- **Batch packs by `cpuMilli` and overcommits `memoryMib`.** 8 tasks/VM
  put 8×10GB of cache on a 64GB VM → page-cache thrash → one symbol in
  11h. `CPU_MILLI=1500` pins it to 5/VM.
- **PD throughput scales with disk SIZE.** A 70GB pd-balanced boot disk
  is ~20MB/s; staging five 10GB copies through it cost ~1.4h per slot
  cycle. Fixed by the local-SSD scratch shared per VM (`/mnt/disks/ssd`
  host → `/mnt/ssd` container; **COS root is read-only, host mounts MUST
  live under /mnt/disks/**).
- **Never trust `gcloud builds list` to confirm an image.** A silent
  Dockerfile-copy failure + a stale list entry launched a 441-task fleet
  on a nonexistent tag → 148 instant failures. `submit.sh` now verifies
  the manifest with `artifacts docker images describe` and refuses to
  submit otherwise.
- The 12 skipped-thin symbols are RESULTS; the build only shards the
  spec's 441.

## Quotas & budget (verified 2026-09-01)

- `CPUS_ALL_REGIONS = 32`, still the binding cap. Google has twice
  routed the increase request to a "get a Sales POC" dead end (cases
  #74792265 and the 64-CPU follow-up); the user is pursuing a contact.
  Regional SSD quota is no longer a constraint (freeze-mode disks are
  `pd-standard`; build fleets use small pd-balanced + local SSD).
- Console showed **$138 consumed / ~$162 credit remaining** on 08-28
  (billing lags ~1–2 days). Build stage to date ≈ $35 including ~$20 of
  dead-end fleet iterations. Remaining build + assemble + training
  projects $50–90 → lands inside credits with margin.

## Other live state (unchanged by the campaign)

- **Production server recovered.** 2026-08-27 13:32Z → 08-28 20:20Z it
  was dark: a billing lapse null-routed the IP while the box kept
  running, so cron fired into a void and only two missed noon heartbeats
  showed it. Scanners failed CLOSED (zero stale alerts). A **reverse
  dead-man** now runs on the home box as a *user* systemd timer (linger
  enabled): hourly SSH probe, Telegram page after 2 misses, recovery
  notice. `deploy/systemd/healys-server-deadman.*`.
- `boot_restart.sh`'s per-boot Telegram heartbeat now defaults **off**
  (user decision — the Ryzen box is stable); relaunch notices still send.
- Post-campaign cleanup still owed: delete stale Artifact Registry tags
  (keep only the tag the last fleet used and anything live).
