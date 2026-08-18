# HANDOFF — state for the next session

Written 2026-08-18 ~07:15 CDT (= 12:15 UTC). Protocol: `CLAUDE.md`.
Previous handoffs: `handoff-history/`.

**This session ends at a reboot** (crash-capture cmdline change, below). The
box is healthy; nothing is mid-flight locally. The cloud build is unaffected —
it runs on GCP Batch, not here.

## Verification doctrine (unchanged — it earned its place, twice more today)

Never report the cloud build's state from this file or memory — verify live:
job state + createTime, fresh task-log lines, advancing bucket count. Deleted
jobs VANISH from `jobs list`; the compute audit log is ground truth.

Today added two more instances of the same lesson, both worth internalising:

- **Counts lie without their shape.** A first pass at the server 429 audit
  grepped bare `429` and reported 481 hits on `live_cron` — every one was the
  millisecond field of a log timestamp (`19:45:14,429`). `error` likewise
  matches the healthy `errors 0` status line. Always print sample lines beside
  a count. `scripts/server_health.sh` now does.
- **A dry run is not a formality.** The crash-capture script's first `--apply`
  reported `line 34: from: 34` on a 3-line file and silently no-opped. See
  "the anomaly" below — it is unexplained and worth knowing about.

## Where everything stands

- **Cloud v4 marks build RUNNING, live-verified 08-18 12:10 UTC: 93/118**
  symbols in `gs://healys-backtester/out/meta_rows/` (job
  `marks-build-54bd73d-202944`, healys-batch, us-central1, image `54bd73d`).
  Rate settled at **~6 sym/hr**, slightly better than the ~5 the last handoff
  assumed: 88@11:21Z → 93@12:10Z. At 6/hr the remaining 25 land **~16:15 UTC
  ≈ 11:15 CDT Tue**. Re-measure from the bucket; do not trust this line.
  Quota `CPUS_ALL_REGIONS=32` caps it at 8 VMs (PENDING 22 is normal).
- **WATCHER IS DEAD — RE-ARM IT.** It was a Monitor, and Monitors die with
  the session; the reboot ends this one. Recipe: poll every ~15 min
  `gcloud storage ls gs://healys-backtester/out/meta_rows/ | grep -c '\.parquet$'`
  and `gcloud batch jobs describe marks-build-54bd73d-202944 --location
  us-central1 --project healys-batch --format='value(status.state)'`. Loud on:
  118/118, any terminal state, non-zero rc on describe (= job DELETED, not a
  blip), auth failure, count unchanged for 3 consecutive polls.
- **`--marks` wired through `v4_finalize`** (`8c649dc`); **task.sh assemble bug
  fixed** (`7845325`) — **assemble MUST use image tag `7845325`**, not `54bd73d`.
- **Suite 390 green** on the rebuilt box, re-verified this session post-reboot.
- **Server healthy**, verified live: 40 days uptime, all three experts
  scanning, logs fresh, v4 reporting `scanned 118 · alerted 0 · errors 0`.

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
5. **DEPLOY**: push main → server `git pull` → selftest → drop `--paper` from
   the v4_scan cron line → verify one pass → re-validate candidate parity.

## The hard lockup (2026-08-18 03:19:21 CDT) and what came of it

The box **froze**, it did not power off — user found it wedged and held the
power button at ~06:19. Proven unclean stop: journal ends mid-line at
03:19:21 with no shutdown sequence, EFI partition dirty bit set, btrfs
tree-log replay on next mount. Ruled out: software shutdown, thermal, OOM,
MCE, watchdog reboot, suspend.

**Cause is still UNKNOWN.** The only lead is `BUG: Bad page state in process
kswapd0 pfn:438ee5, mapcount:-131072, "nonzero mapcount"` at 23:10:46 — a
corrupted `page` struct, four hours before the freeze, one occurrence, on a
kernel tainted `O` by the NVIDIA out-of-tree module. The box ran fine in
between (StockTwits succeeded at 00:01, 01:02, 02:03, 03:01).

It left no record because **three switches were independently off** — fixing
any one alone still yields silence:

1. `nowatchdog` on the kernel cmdline → hardlockup detector never armed, so a
   wedged CPU froze instead of panicking.
2. `CONFIG_EFI_VARS_PSTORE_DEFAULT_DISABLE=y` → pstore compiled in but inert
   without `efi_pstore.pstore_disable=0`. `dmesg | grep pstore` was empty.
3. `systemd-pstore.service` disabled → a captured record would never be
   harvested out of NVRAM.

`scripts/crash_capture_setup.sh` fixes all three plus `kernel.panic=30`,
`panic_on_oops=1`, `hardlockup_panic=1` (`softlockup_panic` left 0 on purpose
— it false-positives under sustained IO/CPU and a spurious reboot mid-build
would be worse than the bug). It also drops `quiet splash` so a panic is
legible on screen, and installs `memtest86+-efi`.

**NEXT ACTION ON THIS: run memtest86+ overnight** — several hours, not one
pass. That `Bad page state` makes RAM the first suspect and the cheapest to
eliminate. If clean, the NVIDIA module is next.

Also unresolved: `limine-update` regenerates snapshot boot entries too;
confirm the `Snapshots` entries still boot after the cmdline change.

### The anomaly (unexplained — do not assume it is gone)

The first `--apply` printed `line 34: from: 34` for a 3-line file: the line
number leaked into the value slot, and `sed -i` targeting line 34 no-opped.
The dry run one minute earlier, and a direct `grep -nE` afterwards, both
correctly returned line 2; the source differed only in a logging string. **No
explanation was found.** The file was verified byte-identical to its backup,
so nothing was damaged.

The fix was to delete the mechanism rather than trust a theory: step 1 now
uses a python keyed substitution (no line numbers, no shell field-splitting,
no `sed -i`), then **re-reads the file from disk** and asserts five invariants
— `root=UUID`, `rootflags=subvol`, pstore param present, `nowatchdog` gone,
`ESP_PATH` intact. Any failure restores the backup, skips `limine-update`, and
exits non-zero. All five gates were tested against deliberately broken files.

## Carry-overs

- **Monday-open Alpaca 429s: RESOLVED, no staggering needed.** Zero genuine
  rate-limit hits across all six server logs. (The 481/132/66 counts from the
  first pass were timestamp milliseconds — see doctrine above.)
- **NEW: `fa_cron` is hitting Reddit 500s** —
  `requests.exceptions.HTTPError: 500 Server Error` on
  `oauth.reddit.com/r/options/new`. Upstream, not our bug, but the FA
  discovery loop is losing that source. Not yet triaged.
- **Fixed this session**: the `~/.claude/settings.json` SessionStart hook
  pointed at `/home/healylabs/.claude/hooks/herdr-agent-state.sh` — dead since
  the rebuild, failing silently every session. Repointed to `$HOME/...` (a
  variable, so the next rename cannot break it). Restore gap #7, same family
  as the systemd units.
- **StockTwits lost three collections** (04:00, 05:00, 06:00 CDT) while the
  box was wedged. The 06:20 post-boot run proved `7a17524` works: it pulled
  before pushing, so the server's month grew 1620→1830 rows instead of being
  truncated. The guard held under exactly the condition it was written for.
- `.claude/settings.local.json` (gitignored) now allows
  `Bash(./venv/bin/python -m pytest *)` and `Bash(./scripts/server_health.sh)`.
  Deliberately NO broad ssh allow rule: a permission rule matches a command
  prefix, so `ssh … <host> *` would grant writes as readily as reads, which
  contradicts the `soft_deny` posture in `~/.claude/settings.json`. The
  read-only remote command is pinned in the wrapper instead.
- Re-enable CI at billing reset: `gh workflow enable tests`.
- Backup-script gaps still open: `~/.gitconfig`, `fa/archive/`, and a note
  that the target OS may not be Pop!_OS. Add `scripts/crash_capture_setup.sh`
  and the three crash-capture switches to any rebuild doc.
- Next phase after deploy: wave 2 (`ROADMAP.md`) — EV head → spx0 pool
  wiring → vol-regime on Batch → FA seat → dual-mode cadence.
- Future Batch jobs: size to 8 VMs (32-CPU quota). Free trial ~$294 of $300.
- **/ultrareview window still open**: `main` is held behind the branch; run it
  from the DESKTOP session before merging to main and deploying.
