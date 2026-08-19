# HANDOFF — state for the next session

Written 2026-08-18 ~07:15 CDT (= 12:15 UTC). Protocol: `CLAUDE.md`.
Previous handoffs: `handoff-history/`.

Reboot DONE 07:14 CDT; crash capture verified live (see below). The cloud
build is unaffected — it runs on GCP Batch, not here.

## !! STOP: DO NOT RUN THE LEDGER RE-RUNS OR v4_finalize ON THIS BOX !!

**Single-bit memory corruption is PROVEN on this machine, with a dated
artifact preserved at `docs/incidents/corrupt-pyc-2026-08-18.pyc.bin`.**

On 2026-08-17 23:41:52 CDT, Python compiled a gcloud bytecode cache and one bit
flipped while the CPU was writing it. The module name `user_request_args_factory`
was written to disk as `usev_request_args_factory`:

    r  0x72  01110010
    v  0x76  01110110   xor = 0x04 -- exactly ONE bit

The correct spelling is in the source 13 times and across 33 files in the SDK;
the corrupted spelling existed in exactly one place on the whole disk, that
.pyc, at byte offset 215. It broke `gcloud storage` (`gcloud batch` was
unaffected), which is the ONLY reason we noticed. Fixed by purging all 1833
.pyc files under ~/google-cloud-sdk; `gcloud storage` and `gsutil` now agree.

**What this means for the project — this is the important part.** The corruption
is SILENT unless it happens to land somewhere that fails loudly. A bit flipped
in a training array, a parquet buffer, a model weight, or a serialized bundle
would produce a WRONG ARTIFACT WITH NO ERROR. Finish-chain steps 3 (ledger
re-runs) and 4 (re-finalize) currently run locally and their output is committed
and deployed to production. **Do not run them on this box until the hardware is
resolved.** Options, in order of preference:
  a. Run the evaluate/finalize on GCP Batch, as the marks build already does.
  b. Fix the hardware first, then run locally.
  c. If neither: run twice on different hardware and compare hashes. Never
     deploy a bundle this box produced alone.
The marks build itself is SAFE — it runs on GCP, not here.

**Also treat with suspicion**: anything this box wrote since 2026-08-17 22:51
(the CachyOS first boot). That includes the restored 15 GB of caches if any were
rewritten, and any local artifact built since. Checksums against the server or
the D: backup are the cheap check.

Three corruption events on the 22:55 boot alone:
  23:10:46  BUG: Bad page state in kswapd0 (corrupt page struct)
  23:41:52  single-bit flip written into a .pyc (the one above)
  03:19:21  silent hard freeze

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

- **MARKS BUILD COMPLETE 2026-08-19: 118/118, job SUCCEEDED.** Assemble also
  SUCCEEDED (`marks-assemble-7845325-225241`). Dataset verified before spending
  a training job on it: `meta_dataset.parquet` **489,255 rows x 69 cols, 118/118
  symbols none missing**, entry_ts 2024-08-01..2026-07-02, both `label` and
  `label_excess` present; `meta_dataset.marks.parquet` **6,200,510 rows**;
  `option_b_blockers` returns NONE, so the ledger can run.
- **BOTH LEDGER RE-RUNS SUBMITTED on GCP** (image `58c2e5b`, n2-standard-8,
  STANDARD, 12h cap): `v4-evaluate-58c2e5b-231618` (`--ablation`) and
  `v4-evaluate-58c2e5b-231626` (`--folds 3`). Outputs land in
  `out/evaluate-<UTC stamp>/` with SHA256SUMS.txt. **NEXT GATE: compare against
  the stage-0 tables in `docs/specs/V4_OUTLINE.md` before finalizing.** The
  numbers are expected to move; if they move the wrong way the correct action is
  to STOP, not to finalize and deploy.
- *(historical)* Cloud v4 marks build RUNNING, live-verified 08-18 12:10 UTC: 93/118
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

## TRAP: the Docker image BAKES the repo — code changes need a rebuild

`deploy/gcp/Dockerfile` ends with `COPY . /app`, so an image is a frozen
snapshot of the repo at its build commit. Image `7845325` therefore did NOT
contain the evaluate/finalize modes added in `58c2e5b`, and submitting
`TASK_MODE=evaluate` against it would have fallen through to the *build* path
and silently done the wrong thing. Caught 2026-08-19 with:

    git show <tag>:deploy/gcp/task.sh | grep -c 'MODE" = "evaluate'

**Any change to `task.sh`, `nn_meta/`, or anything the tasks execute requires a
new image before it takes effect on Batch.** Build from a static `git archive`
(never the live working dir) per `deploy/gcp/README.md`; the tag is the git SHA,
which is what gives artifacts their provenance. Verify the archived file has
your change BEFORE submitting the build.

## THE FINISH CHAIN (execute in order; standing goal: deploy on landing)

1. At 118/118: **assemble** —
   `TASK_MODE=assemble MACHINE=n2-standard-4 IMAGE_TAG=7845325
   PROJECT=healys-batch BUCKET=gs://healys-backtester bash deploy/gcp/submit.sh 1`
2. Download:
   `gcloud storage cp gs://healys-backtester/out/meta_dataset.parquet
   gs://healys-backtester/out/meta_dataset.marks.parquet nn_meta/artifacts_v31/`
   (meta_dataset.parquet is TRACKED — commit it with verified re-run results.)
3. **Ledger re-runs — ON GCP, NOT LOCALLY** (wired 2026-08-18; the home box has
   proven silent memory corruption, see the STOP block at the top):
   ```
   TASK_MODE=evaluate PROJECT=healys-batch BUCKET=gs://healys-backtester \
     EXTRA_ARGS='--ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D' \
     bash deploy/gcp/submit.sh 1
   ```
   then again with `EXTRA_ARGS='--folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D'`.
   Outputs land in `gs://healys-backtester/out/evaluate-<UTC stamp>/` with a
   `SHA256SUMS.txt`. Compare vs stage-0 tables in `docs/specs/V4_OUTLINE.md`;
   log the verdict in `docs/EXPERIMENTS.md`.
4. **Re-finalize — ALSO ON GCP**:
   ```
   TASK_MODE=finalize PROJECT=healys-batch BUCKET=gs://healys-backtester \
     EXTRA_ARGS='--epochs 60 --gbt-estimators 600' bash deploy/gcp/submit.sh 1
   ```
   → `out/finalize-<stamp>/model_final_v4/` + `SHA256SUMS.txt`; pull that down
   and commit it. **Task rc=1 means nothing cleared the eligibility gate** — a
   real result, not a crash; the reports are published either way.
   Training modes default to n2-standard-8, 32 GiB, 12h cap, **STANDARD (not
   SPOT)** — preemption would restart training from zero and there is no
   per-symbol checkpoint to resume from. Override with MACHINE / CPU_MILLI /
   MEMORY_MIB / MAX_RUN / PROVISIONING.
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

1. ~~**zram**~~ — **RETRACTED 2026-08-18, same day it was raised.** The claim
   was that zram "sits directly in the code path that crashed" because it
   appears in both module lists. Reading the Pop!_OS call chain properly kills
   that: `shrink_folio_list > filemap_release_folio > ext4_release_folio >
   jbd2_journal_try_to_free_buffers` is **file-backed page-cache reclaim with
   ext4 journal buffers**. zram serves *anonymous* swap and is not in that path
   at all — it was loaded, not involved. Presence in a module list is not
   presence in a call path; that inference was wrong.
   A 12-minute anonymous-memory->zram thrash (12G working set, peak zram 6.56G
   orig / 2.83G compressed, 11 sweeps, ~132G verified) found **zero** userspace
   corruption and produced **zero** kernel signatures. Real, but it exercised
   the wrong sub-path, so it is weak evidence either way.
2. **The hardware** — same box, same DIMMs. **DEPRIORITISED**, see memtest below.
3. **The NVIDIA proprietary driver** — nvidia_drm/modeset/uvm(OE) then,
   nvidia(O) now; out-of-tree in both, and nvidia_uvm does page-level memory
   management. DMA from a device is invisible to any RAM test.

**memtest86+ already ran overnight on the Pop!_OS install: 20/20 passes, clean**
(user, 2026-08-18; exact date of the run not established — worth pinning down,
since a run well before Aug 17 says less about these crashes). Do NOT re-run it;
that ground is covered. But clean does not mean exonerated, and the reasons are
the useful part:

- memtest cannot see **DMA corruption** — it never loads the NVIDIA driver.
- memtest cannot see a **software lifetime bug** (a page freed while still
  referenced). `mapcount:-131072` and a NULL buffer_head mid
  `try_to_free_buffers` are both exactly that shape, and no RAM test detects it.
- memtest walks patterns at moderate load on a cool CPU. These crashes happen
  under concurrent reclaim + zstd compression + NVMe + GPU traffic. **zstd across
  15.5G of zram is a bandwidth-saturating, highly concurrent access pattern
  memtest never produces**, so a DIMM or memory controller marginal at *that*
  pattern can pass 20 passes.

Corollary worth holding onto: **zram may be the TRIGGER without being the
CULPRIT** — it hammers memory in a way memtest does not, so it could simply be
exposing marginal hardware rather than being buggy itself. The reproduction
test below does not distinguish these two; it only tells us whether the path is
where the damage happens.

Caveat that must not be dropped: kswapd is the kernel's busiest memory-toucher,
so it is the most likely thing to *encounter* corruption whoever caused it.
These traces prove memory got corrupted; they do not name the corrupter.

Revised timeline — worse than the one-off it first looked like:
- 20:45 Pop!_OS oops in kswapd (27h into that boot)
- 22:51 CachyOS installed, first boot
- 23:10 corrupt page struct in kswapd — **15 minutes into a brand-new OS**
- 03:19 silent hard freeze

**WHAT THE WORKLOAD EVIDENCE SAYS.** The CachyOS corruption at 23:10:46 landed
**5m45s after Steam launched at 23:05:01** — downloads, install verification,
heavy disk IO and GPU init. Not an idle box. Combined with the Pop!_OS trace
being *file-cache* reclaim, the profile to reproduce is **page-cache churn from
heavy file IO, with the GPU active** — not anonymous swap thrash.

**NEXT ACTIONS**, in order of cost:
1. **Check BIOS for XMP/DOCP.** "Passes 20 memtest passes, corrupts under mixed
   real load" is a classic above-JEDEC-timings signature, and it costs nothing
   to drop to stock timings. Cheapest remaining test by a wide margin.
2. **Reproduce with the RIGHT profile**: sustained file IO to build and reclaim
   page cache (the ext4/btrfs `release_folio` path), concurrent with GPU load.
   The existing `scripts/zram_reclaim_stress.py` does NOT do this — it drives
   anonymous memory only, and came back clean.
3. `sudo sysctl -w vm.swappiness=60` remains harmless and worth doing, but it
   is no longer justified by the trace evidence.
4. Suspect ordering now: **hardware** (marginal under mixed real load, which
   memtest does not reproduce) and **the NVIDIA out-of-tree module** (DMA, and
   it was busy during the CachyOS event). zram is demoted to bystander.

### SUSPECT RANKING REVERSED (2026-08-18, after the .pyc evidence)

**HARDWARE IS NOW #1 BY A WIDE MARGIN.** The .pyc flip is a single bit in a
buffer the CPU was writing during bytecode compilation — no GPU, no DMA, no
reclaim, no filesystem involved. A rogue DMA clobbers blocks and cachelines, not
single bits. This is the textbook signature of marginal RAM, memory controller,
or CPU cache.

**Why 20 clean memtest passes did not catch it**: single-bit marginal cells are
intermittent and depend on pattern, address, refresh timing and temperature. 20
passes is decent coverage, not proof. Next steps for the hardware, cheapest
first: reseat the DIMMs; test each DIMM individually (a fault may only appear
with both channels populated); run a different tool with different patterns; and
consider that the IMC or CPU cache, not the DIMMs, may be at fault -- in which
case swapping RAM will not help.

The NVIDIA hypothesis below is DEMOTED but not dead -- it could still explain the
kswapd events and the freeze. It cannot explain the .pyc bit flip.

### NVIDIA (demoted 2026-08-18, was leading)

**XMP/DOCP is OFF** — RAM runs JEDEC stock and still passed 20 memtest passes,
so the cheapest hardware explanation is gone.

Hardware: RTX 3060 Ti (GA104), **NVIDIA open kernel module 610.57.04**,
i5-11400, Gigabyte B560 DS3H AC-Y1, BIOS F12c 06/29/2026, kernel 7.1.8-cachyos.

Two published reports put a memory-corruption bug CLASS in this driver family:
- nvidia-open **610.43.03** -> `BUG: Bad page state` freeing a page at the edge
  of a driver-registered "nosave" region, reproduced identically on two kernel
  builds, which isolates it to the driver/GSP rather than the kernel.
  https://forums.developer.nvidia.com/t/hibernate-resume-fails-with-bug-bad-page-state-on-rtx-2070-super-nvidia-open-610-43-03-reproduces-on-two-kernel-versions/377075
- nvidia-open **595.80** -> kernel oops, NULL page fault, **GPU left hard-locked**.
  https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1226

**CAVEAT, do not lose it**: both of those trigger on hibernate/suspend. Ours did
not — there was NO suspend before 23:10:46 (checked), Steam launch at 23:05:01
is the context. So this is NOT the same bug, only the same bug class.

Why the mechanism fits better than anything else: a rogue DMA or stale mapping
writes into whatever kernel pages happen to be there, corrupting an arbitrary
structure — a jbd2 buffer_head on Pop!_OS, a page struct on CachyOS. That
explains the otherwise awkward fact that two DIFFERENT structures broke on the
SAME general path. kswapd walks everything, so kswapd is where damage surfaces;
it is the detector, not the culprit.

The "7.x reclaim regression" idea (Pop 7.0.11 and CachyOS 7.1.8 are both 7.x)
found NO supporting evidence — "Bad page state in kswapd" is a generic
signature spanning 2.4 through 6.9. Not excluded, just unsupported.

**THE DECISIVE TEST, and it is available**: the i5-11400 is a non-F part with
UHD 730, and `lspci` shows only the RTX 3060 Ti, so the iGPU is merely DISABLED
IN BIOS. Enable Internal Graphics, move the monitor to the motherboard output,
blacklist the nvidia modules, run normally for several days. A clean window
confirms NVIDIA. Cost: no discrete GPU while it runs.
Cheaper but less decisive: move to a different nvidia-open branch.

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
