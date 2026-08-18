# HANDOFF — state for the next session

Written 2026-08-17 ~22:35 CDT (= 08-18 03:30 UTC) at session close. Protocol:
`CLAUDE.md`. Previous handoffs: `handoff-history/`.

**⚠ THIS BOX MAY BE ON A FRESH OS.** The user is wiping/reinstalling. If the
repo is freshly cloned, the restore guide is
`/media/healylabs/MRHA (exFAT drive) → popos_backup_2026-08-17/SETUP.md` —
follow it top to bottom (secrets → repo → venv → data → gcloud) before
anything else. Everything below assumes the restore is done.

## Verification doctrine (learned the hard way this session)

Never report the cloud build's state from this file or memory — verify live:
job state + createTime (`gcloud batch jobs list`), fresh task-log lines, and
advancing bucket count/timestamps. Deleted jobs VANISH from `jobs list`; the
compute audit log (`instances.insert/delete`) is ground truth. On 08-17 a
morning resubmit ran the un-fixed image and kill-looped VMs for 14h with
zero output (~$5 wasted) while sessions believed it was fine.

## Where everything stands

- **Cloud v4 marks build RUNNING and VERIFIED progressing**: job
  `marks-build-54bd73d-202944` (project healys-batch, us-central1, image
  `54bd73d`), submitted 08-17 20:29 CDT after the per-symbol-publish fix.
  **37/118 symbols** in `gs://healys-backtester/out/meta_rows/` at 03:28
  UTC, ~9 symbols/hr fleet-wide → done ~07:00 CDT Tue. Quota
  `CPUS_ALL_REGIONS=32` caps it at 8 VMs (PENDING 22 is normal). Free-trial
  budget: ~$294 of $300 left; this run ≈ $4-5 total.
- **`--marks` wired through `v4_finalize`** (commit `8c649dc`): both
  selection passes (cheap-seed family pick + ensemble operating point) run
  the m2m ledger; fail-closed blockers check; `selection_basis` recorded in
  ensemble_config + manifest. Suite **390 green**.
- **task.sh assemble bug fixed** (commit `7845325`): resume pull silently
  no-opped (missing mkdir before gsutil rsync) — an assemble would have
  folded EMPTY dirs; now mkdir'd + refuses to assemble zero row files.
  **Fixed image BUILT + PUSHED: tag `7845325`** — assemble MUST use it.
- **Backups COMPLETE + verified** (OS-wipe prep): bucket holds all three
  nn_meta caches (v32 4.8 GB, v3 3.6 GB, spx0 883 MB); MRHA drive
  `popos_backup_2026-08-17/` holds v3/data (5.7 GB tar — exists NOWHERE
  else), all caches, artifacts_v31, .env, ~/.ssh, ~/.claude, git bundle,
  SETUP.md. All tars verified readable, bundle verified complete.
- **gcloud auth durably fixed**: Workspace "Google Cloud session control"
  set to never expire (user, 08-17; DECISIONS logged; SA key rejected).

## THE FINISH CHAIN (execute in order; standing goal: deploy on landing)

0. Re-arm the watcher per the verification doctrine above (hourly count →
   terminal at 118 + job terminal states + auth failure as loud events).
1. At 118/118: **assemble** —
   `TASK_MODE=assemble MACHINE=n2-standard-4 IMAGE_TAG=7845325
   PROJECT=healys-batch BUCKET=gs://healys-backtester bash deploy/gcp/submit.sh 1`
2. Download:
   `gcloud storage cp gs://healys-backtester/out/meta_dataset.parquet
   gs://healys-backtester/out/meta_dataset.marks.parquet nn_meta/artifacts_v31/`
   (meta_dataset.parquet is TRACKED — commit it with verified re-run results.)
3. **Ledger re-runs** (local, NN_META_POOL=v31):
   `v4_evaluate --ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators
   600 --embargo 1D --marks nn_meta/artifacts_v31/meta_dataset.marks.parquet`
   then same with `--folds 3`. Compare vs stage-0 tables in
   `docs/specs/V4_OUTLINE.md`; log verdict in `docs/EXPERIMENTS.md`.
4. **Re-finalize**: `v4_finalize --marks ...` (wiring DONE this session) →
   fresh `model_final_v4/`. Force-add + commit.
5. **DEPLOY**: push main → server `git pull` → selftest → drop `--paper`
   from the v4_scan cron line → verify one pass → re-validate candidate
   parity (Option B step 4). Update EXPERIMENTS/TODO/DECISIONS.

## Carry-overs

- Monday open: watch all three server cron logs for Alpaca 429s → stagger.
- Re-enable CI at billing reset: `gh workflow enable tests`.
- v32/spx0 bucket backup: DONE 08-17 (both verified size-matched).
- Claude Code login on this box repeatedly lost credentials (personal
  account, NOT the Workspace issue) — cause unknown; diagnose if it recurs
  post-reinstall.
- Next phase after deploy: wave 2 (`ROADMAP.md`) — EV head → spx0 pool
  wiring (data banked) → vol-regime on Batch → FA seat → dual-mode cadence.
- Future Batch jobs: size to 8 VMs (32-CPU quota, free trial can't bump);
  budget doctrine in claude-memory `gcp-free-trial-budget`.
