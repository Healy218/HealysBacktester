# HANDOFF — state for the next session

Written 2026-08-18 ~07:15 CDT (= 12:15 UTC), **UPDATED 2026-08-19 ~12:55 CDT**.
Protocol: `CLAUDE.md`. Previous handoffs: `handoff-history/`.

Reboot DONE 07:14 CDT; crash capture verified live (see below). The cloud
build is unaffected — it runs on GCP Batch, not here.

## !! THE BOX IS PANIC-REBOOTING — MTBF HAS COLLAPSED TO MINUTES !!

Added 2026-08-19 12:55 CDT. **Every boot since 2026-08-18 22:37 has ended in a
kernel panic.** It is not "shutting down": `kernel.panic = 30` turns each panic
into an automatic reboot 30s later, which is exactly what a shutdown loop looks
like from the outside. The crash-capture rig did its job — for the first time
there are records, in `/var/lib/systemd/pstore/<epoch>/`, harvested by
`systemd-pstore.service`.

| Crash | Uptime at death | RIP | Context | Taint already set |
|---|---|---|---|---|
| Aug 18 22:39 | 15h 25m | `__refill_obj_stock` | timer IRQ → RCU slab free on an **idle** cpu (`swapper/10`) | `[B]=BAD_PAGE` |
| Aug 19 07:00 | 8h 20m | `find_lock_entries` | `close()` → `shmem_evict_inode`, `steamwebhelper` | `[B]=BAD_PAGE` |
| Aug 19 09:11 | 2h 10m | panic: killed init | `systemd-shutdown`, after MEI + TPM faults | `[W]=WARN` |
| Aug 19 12:40 | **2m 30s** | `proc_pid_status` | `read()` on `/proc`, by **`ps`** | none |

**THE FINDING: pointers arriving as exact powers of two.** The two page-fault
oopses are one failure wearing two costumes:

    Aug 18:  cmpb $0x0,0x30(%rdi)   RDI = 0x0000000000100000 = 2^20  -> fault @ 0x100030
    Aug 19:  mov  0x34(%r14),%eax   R14 = 0x0000000000040000 = 2^18  -> fault @ 0x40034

Those registers should hold slab and folio pointers (`ffff8e1cbfcb4440`,
`ffffcd5ee1173bc0` shapes). Instead each arrived with every bit cleared but
one, in two unrelated subsystems. Software does not compute those values.
Note also that `[B]=BAD_PAGE` was ALREADY in the taint mask before the fatal
oops in both — each of those boots had corruption detected and survived
earlier, then died to a later hit. The corruption is continuous.

**This promotes HARDWARE further and weakens NVIDIA.** Two arguments the
earlier analysis did not have:

1. **The corruption now lands in paths with no GPU involvement at all** — an
   idle core's timer interrupt doing an RCU batch slab free, a tmpfs inode
   eviction, and `ps` reading `/proc/PID/status`. The rogue-DMA hypothesis now
   has to explain a write into slab freelist metadata on `swapper/10` while
   nothing is rendering.
2. **The MTBF is collapsing on an unchanged kernel.** 15h25m → 8h20m → 2h10m →
   2m30s, all on `7.1.8-1-cachyos`; no kernel change and no relevant package
   change since Aug 18 07:03 (both checked). A 370x degradation in 38 hours
   with no config change is a hardware degradation curve. Software bugs do not
   accelerate like that.

**Loose thread that is NOT memory — do not lose it behind the RAM hypothesis.**
The Aug 19 09:11 record shows `mei_hbm_dispatch` WARN → `mei mei0: unexpected
reset` → `tpm tpm0: A TPM error (257)` / `0x0101` before init died. That is the
Management Engine and the TPM misbehaving: a PCH/firmware signal, not DIMMs. If
that is the root, swapping RAM will not fix it.

**The silver lining: the DIMM bisect is now CHEAP.** The earlier plan was
"memtest86+ overnight". At a 2½-minute MTBF it is a 30-minute experiment —
boot on one DIMM, see whether it survives an hour, swap, repeat. Do that before
buying anything. Consider also that the IMC or CPU cache, not the DIMMs, may be
at fault, in which case a RAM swap changes nothing.

**`kernel.nmi_watchdog` was found at 0 on the live box.** `ffb7c24` added
`kernel.nmi_watchdog = 1` to `scripts/crash_capture_setup.sh`, but the script
was never re-run here, so `/etc/sysctl.d/99-crash-capture.conf` lacked the line
and `hardlockup_panic=1` had been inert the entire time. Set live and persisted
to the conf 2026-08-19 by the user. Verify with `sysctl kernel.nmi_watchdog`.

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

## !! THE ASSEMBLED DATASET IS STALE — REBUILD BEFORE ANY TRAINING RUN !!

Added 2026-08-19 12:55 CDT. `4f6fa93` found the cause of the confounded stage-0
comparison (44 of 486 flat-file day-frames missing from the bucket; see the
commit message and `nn_meta/cache_preflight.py`). **The 44 frames WERE then
uploaded — but after the dataset had already been built, and the box panicked
before anything was re-run.** Verified live against the bucket 2026-08-19 12:50:

| Object | Timestamp (UTC) | Built from |
|---|---|---|
| `out/meta_rows/*.parquet` (118) | 28 on 08-17, 90 on 08-18 | **incomplete cache** |
| `out/meta_marks/*.parquet` (118) | 28 on 08-17, 90 on 08-18 | **incomplete cache** |
| `out/meta_dataset.parquet` | 08-19 **04:03:37Z** | **incomplete cache** |
| the 44 missing `flatfiles_15m/*.parquet` | 08-19 **11:31–11:32Z** | — |

The frames landed **7.5 hours after** the dataset was assembled. Commit
`4f6fa93` was made 06:39 CDT (11:39Z), ~7 min after the upload finished, and the
box panicked at 07:00 CDT — which is why none of this reached the handoff.

**Consequences, in order:**

1. Every number in the 2026-08-19 `docs/EXPERIMENTS.md` entry was computed on
   the flattered dataset. Treat the whole row as void, not merely confounded.
2. **Re-running `TASK_MODE=evaluate` alone would reproduce the same wrong
   numbers**, because evaluate reads `out/meta_dataset.parquet` and never
   touches the option-bar cache. The `cache_preflight` guard added in `4f6fa93`
   runs only on the `build`/`assemble` path (see the `case` in
   `deploy/gcp/task.sh`) — it CANNOT catch this.
3. **TRAP — a naive re-submit of the build does nothing.** `task.sh` resumes by
   rsyncing `out/meta_rows` and `out/meta_marks` down and skipping symbols that
   already have checkpoints. All 118 are present and stale, so the build would
   skip every one and assemble the same dataset. **`out/meta_rows/` and
   `out/meta_marks/` must be moved aside first** (archive to a dated prefix —
   do not delete; they are the evidence for the comparison).
4. A new image is required: the current images (`7845325`, `58c2e5b`) predate
   `4f6fa93` and do not contain `cache_preflight`. See the image-bakes-the-repo
   trap below.

**The correct restart is the full chain from `build`, not from `evaluate`:**
archive `meta_rows`/`meta_marks` → new image at `4f6fa93` → build 118 symbols
(~6 sym/hr on 8 VMs ≈ 20h) → assemble → both evaluate runs. Prefer
`e2-standard-8`; `n2` hit `CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED`.

### CONFIRMED 2026-08-19 by a full stage-0 diff — and the rebuild list is 90, not 118

The stage-0 vs new-dataset diff reproduces the recorded numbers **exactly**
(13 of 66 shared columns; contract 3.40%, entry_premium 4.98%, label 4.31%,
net_return 6.89%). Method note that matters: align on the SIGNAL keys
(`symbol, strategy, entry_ts, direction, right`) — **not** on contract/strike/
expiration, because those are the columns that moved, so sorting by them
mis-pairs rows and inflates the diff. A naive alignment also invents ~845 fake
`dte` differences on AAPL out of duplicate keys; restrict to keys unique on
both sides, or align on signal keys only.

**One mechanism explains all of it.** 16,617 rows (3.40%) had a DIFFERENT
option contract selected; `contract`, `strike`, `expiration`, `executed` and
`moneyness` differ on exactly those rows, and everything else (premium, fills,
returns, labels) is downstream. **All 16,500 `executed` 1→0 flips have a
changed contract; ZERO flips without one.** 14,430 of 16,617 (86.8%) have
their ENTRY DAY on one of the 44 missing day-frames, and the month profile
tracks the missing-day histogram (2026-02: 9 missing days → 20.0% of that
month's rows changed; months with no missing days → ~0.0%).

Direction of the error: stage-0 executed 0.6440 → new 0.6106. The incomplete
cache DROPS trades, and per `4f6fa93` the dropped ones average +0.017 net
return against +0.114 for survivors — so **the current dataset reads better
than the truth**. Do not train or deploy on it.

**ONLY 90 SYMBOLS NEED REBUILDING.** Bucket timestamps split the build cleanly:
28 `meta_rows` were written 08-17 and 90 on 08-18, and the 44 day-frames went
missing between those two batches. The 29 symbols with ZERO contract changes
are exactly the 08-17 set plus SQ (built 08-18 but coincidentally unchanged).
Rebuild the **90 dated 08-18** — the criterion is which cache the symbol was
built against, not which happened to differ. Saves ~25% of the ~20h.
Per-symbol dates captured at `scratchpad/builddates.txt`; regenerate with
`gcloud storage ls -l gs://healys-backtester/out/meta_rows/`.

**TRAP — do not pilot on AAPL.** The README's canonical pilot pair is
`AAPL,SPY`, and **AAPL has zero changed rows**: it was built 08-17 against a
complete cache, so rebuilding it is byte-identical no matter what and proves
nothing. A pilot on AAPL alone reads as "the missing-frames theory is refuted",
which is wrong. Pick a symbol confirmed to be affected — MARA (380), NKE (341),
RGTI (335), INTC (307), MRNA (300) — or SPY (230).

### Harness trap seen all through this session

`Bash` calls that run LONG in the foreground fail with `Cannot convert a symbol
to a string` before executing — a 35 MB `gcloud storage cp`, `pytest tests`
over the whole suite, multi-file loops. Fast equivalents of the same commands
succeed, and the same long command succeeds with `run_in_background`. Workaround:
background it, or split it (the 35 MB download went through as 5 × 8 MB
`gsutil cat -r` range reads). Not a permission rule — there are no deny rules.

## Where everything stands

- **MARKS BUILD COMPLETE 2026-08-19: 118/118, job SUCCEEDED.** Assemble also
  SUCCEEDED (`marks-assemble-7845325-225241`). Dataset verified before spending
  a training job on it: `meta_dataset.parquet` **489,255 rows x 69 cols, 118/118
  symbols none missing**, entry_ts 2024-08-01..2026-07-02, both `label` and
  `label_excess` present; `meta_dataset.marks.parquet` **6,200,510 rows**;
  `option_b_blockers` returns NONE, so the ledger can run.
- **BOTH LEDGER RE-RUNS FINISHED 2026-08-19 (GCP, image `58c2e5b`, e2-standard-8).**
  Full tables + verdict: `docs/EXPERIMENTS.md` (2026-08-19 entry). Headline: all
  gates passed and the fully-corrected ablation row is +231.3% / 24.7% maxDD with
  the best deflated Sharpe (0.920) — but **DO NOT FINALIZE YET**, three things
  are open:
  1. The stage-0 comparison is CONFOUNDED — the dataset changed. Stage-0 hash
     `353d090c` vs new `2ba866dc`; same rows/symbols/span but 13 of 66 shared
     columns differ (contract 3.40%, entry_premium 4.98%, label 4.31%,
     net_return 6.89%; `executed` mean 0.6440->0.6106). Cache refreshes are the
     likely cause. The 3x improvement cannot be credited to the ledger.
  2. The ablation's leakage finding INVERTED — dropping `prem_spot` now raises
     return instead of halving it. Partly because `nn` wins both legacy rows and
     `gbt` wins both v4 rows, so it is not one family across schemas.
  3. Fold 3 degraded — maxDD 25.0%->53.4% plus a top-decile return inversion.
  **Capacity note**: n2-standard-8 hit CODE_GCE_ZONE_RESOURCE_POOL_EXHAUSTED and
  re-queued after 1080s; e2-standard-8 (same 8vCPU/32GiB) ran fine. Prefer e2 for
  training jobs. `submit.sh` still defaults to n2 — change it if e2 keeps working.
- *(superseded)* BOTH LEDGER RE-RUNS SUBMITTED on GCP (image `58c2e5b`, n2-standard-8,
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
