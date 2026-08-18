# HANDOFF — state for the next session

Written 2026-08-18 ~00:05 CDT (= 05:05 UTC). Protocol: `CLAUDE.md`.
Previous handoffs: `handoff-history/`.

**The OS wipe is DONE and the box is fully restored.** No restore work is
pending; `popos_backup_2026-08-17/SETUP.md` on the MRHA drive has been
executed end to end and verified (details below). Ignore the restore warning
at the top of the previous handoff.

## Verification doctrine (unchanged — it earned its place)

Never report the cloud build's state from this file or memory — verify live:
job state + createTime (`gcloud batch jobs list` / `jobs describe`), fresh
task-log lines, and advancing bucket count/timestamps. Deleted jobs VANISH
from `jobs list`; the compute audit log (`instances.insert/delete`) is ground
truth. On 08-17 a morning resubmit ran the un-fixed image and kill-looped VMs
for 14h with zero output (~$5 wasted) while sessions believed it was fine.

## Where everything stands

- **Cloud v4 marks build RUNNING, live-verified 08-18 04:56 UTC: 49/118**
  symbols in `gs://healys-backtester/out/meta_rows/` (job
  `marks-build-54bd73d-202944`, healys-batch, us-central1, image `54bd73d`).
  Measured rate is **~7 symbols/hr, not the ~9 the last handoff assumed** —
  37@03:28Z → 44@04:42Z → 49@04:56Z. Revised ETA **~15:00-16:00 UTC ≈
  10:00-11:00 CDT Tue**, not 07:00 CDT. Quota `CPUS_ALL_REGIONS=32` caps it
  at 8 VMs (PENDING 22 is normal). Free trial ~$294 of $300 left.
- **Watcher armed** as a Monitor (hourly): bucket count + job state, with
  118/118, any terminal job state, job-vanished, auth failure and a
  count-stall as loud events. **Monitors die with the session — re-arm it.**
  Recipe: poll `gcloud storage ls gs://healys-backtester/out/meta_rows/ |
  grep -c '\.parquet$'` and `gcloud batch jobs describe
  marks-build-54bd73d-202944 --location us-central1 --project healys-batch
  --format='value(status.state)'`; a non-zero rc on describe means the job
  was DELETED, which is a loud event, not a blip.
- **`--marks` wired through `v4_finalize`** (commit `8c649dc`): both
  selection passes run the m2m ledger; fail-closed blockers check;
  `selection_basis` recorded in ensemble_config + manifest.
- **task.sh assemble bug fixed** (commit `7845325`): resume pull silently
  no-opped (missing mkdir before gsutil rsync). **Assemble MUST use image tag
  `7845325`**, not `54bd73d`.
- **Suite 390 green** on the rebuilt box (`CLAUDE.md` previously said 345;
  corrected).

## The restore, and what the guide got wrong

Done: secrets/`~/.ssh`/`~/.claude`, repo at `b5e61b7` matching
`git_head.txt`, `.env`, all 15 GB of data (v3/data 5.4G — exists nowhere else
— plus caches v3/v32/spx0 and artifacts_v31, every size an exact match),
venv, gcloud authed `matt@healylabs.io`, gh authed `Healy218`, systemd units
installed, 390 tests green.

Six things `SETUP.md` could not anticipate — all now recorded in `CLAUDE.md`:

1. **The box is CachyOS (Arch), not Pop!_OS.** Step 0's `apt` line is dead;
   use `pacman`. The user is `healy`, not `healylabs`.
2. **No `python312` package on Arch**, and system python is 3.14 which the
   pins reject. The venv is **3.12.14 via `uv`** (`uv python install 3.12`).
3. **No official gcloud package.** Installed as Google's rootless tarball at
   `~/google-cloud-sdk`; PATH sourced from `~/.config/fish/config.fish` and
   `~/.bashrc`.
4. **`pytest` was not in `requirements.txt`** — step 3 alone left step 7
   unrunnable. Fixed in `a2cd157`; pinned to 9.1.1.
5. **Git identity was in `~/.gitconfig`, which no backup captured.** Restored
   from the commit history as `Healy218 <mrhealy115@gmail.com>`. Worth adding
   to any future backup script.
6. **`fa/archive/` was in no backup either — and that one nearly cost data.**
   The archive is monthly parquet (`<source>/<yyyy-mm>.parquet`,
   `fa/config.py`), and `stocktwits_collect_push.sh` rsyncs local → server as
   a straight mirror. Its "the home box is the sole writer so a mirror is
   safe" assumption silently depends on the home box holding the full local
   history; after the wipe it held none, so the first timed run would have
   replaced the server's `2026-08.parquet` (1620 stocktwits + 3240 sentiment
   rows, 08-15 22:00 → 08-18 03:02 UTC) with just that run's messages.
   Averted by pulling the server's archive back down before the timer fired.
   **FIXED in `7a17524`**: the script now pulls the archive before collecting,
   so the mirror is safe by construction and a wiped local archive self-heals
   instead of truncating the server. Verified three ways (normal run; local
   archive deleted outright; server unreachable → exits 255 without collecting
   or pushing). **Any future backup should still include `fa/archive/`.**

Backup-script gaps to close, in one list: `~/.gitconfig`, `fa/archive/`, and
a note that the target OS may not be Pop!_OS. `pytest` is now in
`requirements.txt` (`a2cd157`), so a clean build can run the gate.

The systemd units hardcoded `/home/healylabs/...` and `User=healylabs`, so
they would have refused to start; retargeted and committed (`3a7d09c`).
Installed state matches the pre-wipe `systemd_units.txt` exactly:
boot-restart enabled, stocktwits service disabled + timer enabled.

## THE FINISH CHAIN (execute in order; standing goal: deploy on landing)

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
4. **Re-finalize**: `v4_finalize --marks ...` → fresh `model_final_v4/`.
   Force-add + commit.
5. **DEPLOY**: push main → server `git pull` → selftest → drop `--paper`
   from the v4_scan cron line → verify one pass → re-validate candidate
   parity (Option B step 4). Update EXPERIMENTS/TODO/DECISIONS.

## Carry-overs

- Re-enable CI at billing reset: `gh workflow enable tests` (gh is now
  authed with `workflow` scope, so this is unblocked).
- Monday open: watch all three server cron logs for Alpaca 429s → stagger.
- Claude Code login on this box repeatedly lost credentials pre-wipe
  (personal account, NOT the Workspace issue). Watch whether it recurs on
  the fresh OS — cause unknown.
- Next phase after deploy: wave 2 (`ROADMAP.md`) — EV head → spx0 pool
  wiring (data banked) → vol-regime on Batch → FA seat → dual-mode cadence.
- Future Batch jobs: size to 8 VMs (32-CPU quota, free trial can't bump);
  budget doctrine in claude-memory `gcp-free-trial-budget`.
- The Hetzner server was untouched by the wipe and kept running v3 +
  v4(paper) + v31(paper) throughout.
