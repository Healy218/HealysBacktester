# HANDOFF — state for the next session

Written 2026-08-18 ~07:15 CDT (= 12:15 UTC). Protocol: `CLAUDE.md`.
Previous handoffs: `handoff-history/`.

Reboot DONE 07:14 CDT; crash capture verified live (see below). The cloud
build is unaffected — it runs on GCP Batch, not here.

**THIS BOX IS UNDER SUSPICION.** Three memory-corruption events in ~7 hours
across two different OS installs (detail below). Do not treat a local hang,
oops, or odd result as a software bug until memtest86+ has run.

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
- **WATCHER: re-armed 12:20 UTC after the reboot killed it.** Monitors die
  with the session — re-arm on every new session. Recipe: poll every ~15 min
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

**Cause narrowed to TWO candidates by a recovered pre-wipe crash record.**
Enabling pstore harvested three `dmesg-efi_pstore-*` chunks that had been
sitting in UEFI NVRAM since **Aug 17 20:45** — a kernel oops from the
**Pop!_OS** install (system76_io/system76_acpi modules present), two hours
before CachyOS first booted. Decoded:

    RIP: jbd2_journal_grab_journal_head+0x10/0x80
    RDI: 0000000000000000     <- buffer_head argument was NULL
    Oops: 0002                <- kernel-mode WRITE to a non-present page
    Comm: kswapd0   Kernel: 7.0.11-76070011-generic

`jbd2_journal_try_to_free_buffers` handed `grab_journal_head` a NULL
buffer_head and it did a locked bit-set on address zero. That list was corrupt.

Set beside the CachyOS event, the pattern is the finding:

| | Aug 17 20:45 (Pop!_OS) | Aug 17 23:10 (CachyOS) |
|---|---|---|
| Process | kswapd0 | kswapd0 |
| Path | shrink_node > shrink_one > try_to_shrink_lruvec > evict_folios > shrink_folio_list | identical |
| Failure | NULL buffer_head in journal list | mapcount:-131072, corrupt page struct |
| Kernel | 7.0.11 (System76) | 7.1.8 (CachyOS) |
| Filesystem | **ext4 / jbd2** | **btrfs** |

Same process, same reclaim path function-for-function, across a different
kernel AND a different filesystem. An ext4/jbd2 bug cannot reproduce on btrfs;
a 7.0.11 bug need not exist in 7.1.8. What survives both changes:

1. **The hardware** — same box, same DIMMs.
2. **The NVIDIA proprietary driver** — nvidia_drm/modeset/uvm(OE) then,
   nvidia(O) now; out-of-tree in both, and nvidia_uvm does page-level memory
   management.

Caveat that must not be dropped: kswapd is the kernel's busiest memory-toucher,
so it is the most likely thing to *encounter* corruption whoever caused it.
These traces prove memory got corrupted; they do not name the corrupter.

Revised timeline — worse than the one-off it first looked like:
- 20:45 Pop!_OS oops in kswapd (27h into that boot)
- 22:51 CachyOS installed, first boot
- 23:10 corrupt page struct in kswapd — **15 minutes into a brand-new OS**
- 03:19 silent hard freeze

**MEMTEST86+ OVERNIGHT IS THE NEXT ACTION AND IT DISCRIMINATES CLEANLY**:
dirty RAM ends the investigation; clean RAM promotes the NVIDIA module to
prime suspect. Cost of running it: the box is offline, so StockTwits loses
those hourly collections (the cloud build is unaffected — it runs on GCP).

It left no record because **three switches were independently off** — fixing
any one alone still yields silence:

1. `nowatchdog` on the kernel cmdline → hardlockup detector never armed, so a
   wedged CPU froze instead of panicking.
2. `CONFIG_EFI_VARS_PSTORE_DEFAULT_DISABLE=y` → pstore compiled in but inert
   without `efi_pstore.pstore_disable=0`. `dmesg | grep pstore` was empty.
3. `systemd-pstore.service` disabled → a captured record would never be
   harvested out of NVRAM.

**A FOURTH switch was found during post-reboot verification**: dropping
`nowatchdog` flips `kernel.watchdog` 0->1 but leaves `kernel.nmi_watchdog` at
**0**, and on this CONFIG_HARDLOCKUP_DETECTOR_PERF kernel that sysctl is what
actually gates the hard-lockup detector — so `hardlockup_panic=1` was inert.
Fixed in `ffb7c24` (`kernel.nmi_watchdog = 1` in the drop-in). Verify with
`sysctl kernel.nmi_watchdog` after any change here; a cmdline that merely
*looks* right is not enough.

`scripts/crash_capture_setup.sh` fixes all four plus `kernel.panic=30`,
`panic_on_oops=1`, `hardlockup_panic=1` (`softlockup_panic` left 0 on purpose
— it false-positives under sustained IO/CPU and a spurious reboot mid-build
would be worse than the bug). It also drops `quiet splash` so a panic is
legible on screen, and installs `memtest86+-efi`.

**NEXT ACTION ON THIS: run memtest86+ overnight** — several hours, not one
pass. See the two-candidate analysis above for why it is now the decisive
test rather than merely the cheapest one.

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
