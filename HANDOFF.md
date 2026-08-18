# HANDOFF — state for the next session

Written 2026-08-17 morning at session close (context limit). Protocol:
`CLAUDE.md`. Previous handoffs: `handoff-history/`.

## Where everything stands (all verified, all committed, main == branch)

- **Datasets COMPLETE at home**: `data_cache_v32/flatfiles_15m` (300-equity
  universe + SPX/SPXW/NDX/NDXP, 500/500 days, 4.5 GB — 5 skipped days
  backfilled); `data_cache_spx0/flatfiles_1m` (index 1m, 500 days, 843 MB)
  + `underlying_1m/{SPY,QQQ}.parquet`. spx0 stage-0 data = 100% banked.
- **Option B selection wiring MERGED**: `choose_policy(mark_stream=...)`
  scores candidates AND baseline through the m2m ledger; flip regression
  test in `tests/test_v4_evaluate.py`; no-stream path bit-identical.
  Suite 388 green.
- **Cloud v4 build resubmitted 2026-08-17 20:29 CDT (= 08-18 01:29 UTC)**
  with per-symbol incremental publish — NOT "this morning": nothing ran
  between Sun ~20:00 CDT (28 symbols banked) and the Mon-evening resubmit;
  the fix commit `54bd73d` itself only landed Mon 20:20 CDT. (The Sunday
  12-wide run kill-looped: 8-symbol tasks outran the 4h maxRunDuration and
  end-only publish reset every retry — fixed in `deploy/gcp/task.sh`, image
  rebuilt, resubmitted SHARDS=30 PARALLEL=12 n2. Live-log verified 08-18
  01:39 UTC: tasks skip banked symbols and build new ones.) NOTE:
  `CPUS_ALL_REGIONS` quota = 32 caps the job at 8 concurrent VMs (not 12);
  ~6-8h to finish at 8-wide. **Progress = `gcloud storage ls gs://healys-backtester/out/meta_rows/
  | wc -l` toward 118** — now meaningful mid-task. gcloud auth is FRESH
  (user re-logged 08-17 morning; Workspace policy may expire it again).

## THE FINISH CHAIN (execute in order; standing goal: deploy on landing)

0. Re-arm the watcher (Monitor, hourly): bucket count → terminal at 118.
1. At 118/118: **assemble** — ⚠ do NOT use IMAGE_TAG=54bd73d: that image's
   task.sh has a broken resume pull (missing mkdir → gsutil rsync no-ops →
   assemble would fold up EMPTY dirs; fixed + fail-closed guard added
   2026-08-18, needs an image rebuild at the fix commit first — build cmd in
   `deploy/gcp/README.md` line ~93). Then:
   `TASK_MODE=assemble MACHINE=n2-standard-4 IMAGE_TAG=<fix-sha>
   PROJECT=healys-batch BUCKET=gs://healys-backtester bash deploy/gcp/submit.sh 1`
   (build job: marks-build-54bd73d-202944 — the BUILD tasks are unaffected
   by the bug: their skip check hits the bucket directly.)
2. Download:
   `gcloud storage cp gs://healys-backtester/out/meta_dataset.parquet
   gs://healys-backtester/out/meta_dataset.marks.parquet nn_meta/artifacts_v31/`
   (meta_dataset.parquet is TRACKED — it will show modified; commit it with
   the re-run results once verified.)
3. **ONE remaining code task**: wire `--marks` through `nn_meta/v4_finalize.py`
   — `choose_policy` already accepts `mark_stream=`; finalize's two
   choose_policy call sites (cheap-seed family pick + ensemble operating
   point) need the pass-through + a `--marks` CLI arg mirroring
   `v4_evaluate.py:500`. ~20 min + tests.
4. **Ledger re-runs** (local, box is idle; NN_META_POOL=v31):
   `v4_evaluate --ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators
   600 --embargo 1D --marks nn_meta/artifacts_v31/meta_dataset.marks.parquet`
   then same with `--folds 3`. Compare vs stage-0 tables in
   `docs/specs/V4_OUTLINE.md`; log verdict in `docs/EXPERIMENTS.md`.
   Reports now tag ledger-selected rows 🄻.
5. **Re-finalize** with --marks (post step 3) → fresh `model_final_v4/`
   (verifiable manifest). Force-add + commit.
6. **DEPLOY**: push main → server `git pull` → `NN_META_POOL=v31
   ./venv/bin/python -m nn_meta.live.v4_scan --selftest` → edit server
   crontab: remove `--paper` from the v4_scan line (bundle must then verify
   + be gate-eligible — the scan enforces it) → verify one pass.
   Re-validate candidate parity (Option B step 4) → closes the last
   first-implementation gate item. Update EXPERIMENTS/TODO/DECISIONS.

## Carry-overs

- Monday open: watch all three server cron logs for Alpaca 429s → stagger.
- Re-enable CI at billing reset: `gh workflow enable tests`.
- SA-key decision (unattended gcloud immunity) — user call, in DECISIONS.
- SSH/herdr one-liner for the box is in the previous handoff (user has it).
- Next phase after deploy: wave 2 (`ROADMAP.md`) — EV head → spx0 pool
  wiring (data DONE) → vol-regime on Batch → FA seat → dual-mode cadence.
- v32/spx0 caches: back up to the bucket when convenient
  (`gcloud storage rsync -r`), and the tracked-alert-state defusal is done.
