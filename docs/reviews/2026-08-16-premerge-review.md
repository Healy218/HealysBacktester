# Pre-merge review — `codex/v4-causal-validation` → `main` (2026-08-16)

**Scope**: the branch-only diff `main...HEAD` — 6 commits, 13 files,
+1007/−101 (GCP Batch scaffolding, bars_daily compaction, renamed-listings
crawl, three-expert heartbeat, docs). This is the review gate from TODO's
"/ultrareview window open" item: `main` is held behind the branch until this
passes.

**Provenance**: the cloud `/ultrareview` service timed out (3 attempts, twice),
so this ran locally: three parallel Fable 5 review forks, one per functional
slice, plus a whole-diff pass. Every finding below was verified against the
actual code by its reviewing fork; the P0 and the sharpest P1s were
independently re-verified by the orchestrating session. Targeted suites run
by the forks: `tests/test_heartbeat.py` 13/13, `tests/test_download_universe.py`
15/15. No working-tree changes were made; the real bar caches were confirmed
intact afterward (13 parts / 181 MB, no `.old`/`.compacting` litter).

**Status**: v1 — the whole-diff pass (docs files + second opinion) was still
running at publish time; any deltas will be appended below.

**Bottom line**: 1 P0, 7 P1, 8 P2. Production is NOT currently exposed — all
findings are branch-only and the server runs `main`. The P0 blocks the merge;
the heartbeat P1s should land with it (same deploy); the GCP P1s block the
first paid Batch run, not the merge.

---

## P0 — must fix before merge

### P0-1 · `nn_meta/download_universe.py:363` — compaction crash-recovery is dead code on every real entry path; the rerun *deletes the only copy of the bars cache*

CONFIRMED (fork repro in an isolated dir + independent code read).

Mechanism: the crash-safe swap is `bars_daily` → `.old`, `.compacting` →
`bars_daily`, delete `.old` (`:397-399`). The recovery guard (`:363`) requires
`.old` present **and** `bars_daily` missing. But `main()` calls
`config.ensure_dirs()` (`:433`) before dispatching to `compact_bars_daily()`,
and `ensure_dirs` (`nn_meta/config.py:277-279`) recreates `BARS_DAILY_DIR`
empty with `exist_ok=True`. After a crash between the two renames, the rerun
therefore sees a present-but-empty `bars_daily`, skips recovery, classifies
the state as "crashed after the swap" (`:368-369`), and `rmtree`s `.old` —
the full cache. Standalone `--compact` then prints "no bar parts — nothing to
do"; the weekly `--bars-and-surface-only` cron path is worse: it first refills
the empty dir with last-10-days parts, so the destroyed cache *looks* alive.
Bars older than Massive's rolling 2-year window exist only in this cache
(v31 window starts 2024-07), so part of the loss is unrecoverable from the API.

Why the tests miss it: `test_main_compact_flag_is_standalone_and_offline`
stubs `ensure_dirs` to a no-op, and
`test_compact_bars_daily_recovers_from_crashed_swap` calls
`compact_bars_daily()` directly, bypassing `main()`.

Fix direction (either suffices; both are small):
- Run the recovery check before / independent of `ensure_dirs()`, **or**
  make the crashed-state test content-based: "`bars_daily` has no
  `bars_part_*` ∧ `.old` has parts ⇒ restore `.old`".
- Add a `main()`-path recovery test with the real `ensure_dirs` (no stub).

---

## P1 — should fix before this deploys

### Heartbeat (`nn_meta/live/heartbeat.py`, commit 3618d78)

All three share one theme: the digest can go silent or under-report in
exactly the false-"all-healthy" direction the module exists to prevent.
All CONFIRMED (fork + independent read).

1. **`heartbeat.py:176`** — the baseline is persisted inside
   `build_message()` *before* `main()` sends, and `TelegramNotifier.send`'s
   `False` return (`notifier.py:83-88`) is ignored (`:186-187`). A failed
   send permanently consumes that digest's new-crash deltas: 3 overnight
   crashes + one failed POST ⇒ next digest says "0 new crashes", forever
   unreported. Fix: persist the baseline only after a successful send (or
   check the return and retain the old baseline on failure).
2. **`heartbeat.py:137-174`** — no per-expert exception isolation. One
   unreadable log (`PermissionError`/`OSError` from `read_text` at `:82` or
   `stat` at `:163`; `errors="ignore"` only covers decode) aborts the whole
   digest for all three experts — daily, silently, indefinitely. Fix:
   per-expert try/except that surfaces the failure as a ⚠️ line and keeps
   the other experts' sections.
3. **`heartbeat.py:142`** — `max(0, cur − base)` clamps a truncated/rotated
   log to zero: baseline tracebacks=40, log truncated, 5 real crashes ⇒
   delta 0 ⇒ healthy digest (window bounded to one cycle). Same clamp also
   fires a *false* "0 scan passes — may be DOWN" during RTH on a healthy
   expert. Fix: `cur < base` ⇒ reset baseline + append a "log
   rotated/truncated — counters reset" note.

### GCP Batch (`deploy/gcp/`, commit 449b545) — gate the first paid run

4. **`deploy/gcp/README.md:76`** — step 4's
   `cp deploy/gcp/Dockerfile ./Dockerfile.gcp` is dead: `gcloud builds
   submit --tag` only reads a context-root file named exactly `Dockerfile`.
   On this box it silently built from the untracked root `Dockerfile`
   workaround; if that copy drifts, images get tagged with a SHA they
   weren't built from. Fix: `cp` to `./Dockerfile`, build, `rm` — or a
   `cloudbuild.yaml`.
5. **`deploy/gcp/submit.sh:38`** — the job JSON hardcodes
   `"TASK_MODE": "build"`, so the documented `TASK_MODE=assemble`
   submission (README step 6b and submit.sh's own final echo) does nothing
   without hand-editing the script. Fix: `"TASK_MODE": "${TASK_MODE:-build}"`.
6. **`deploy/gcp/task.sh:30-32`** — the assemble branch's only output upload
   is `gsutil … cp … || true; exit 0`. A transient GCS failure ⇒ Batch
   reports SUCCEEDED while the VM holding the only copy of the assembled
   dataset self-deletes. Fix: drop `|| true` on publish steps (the
   resume-pull `|| true`s above are correct; build-mode publishes at
   `:52-53` already lack it).
7. **`deploy/gcp/teardown.sh:18`** — teardown deletes the entire `healys`
   Artifact Registry *repository* (one-time setup, README step 3), which the
   per-run flow never recreates — the next run's image push fails until the
   operator rediscovers step 3. Fix: delete images inside the repo
   (`gcloud artifacts docker images delete`), or move repo creation into
   the per-run flow.

---

## P2 — nits and hardening

- **`nn_meta/live/heartbeat.py:83`** — `text.count("Traceback")` counts a
  chained exception ("During handling…") as 2+ crashes. Errs noisy, never
  masks.
- **`nn_meta/download_universe.py:44`** — module-level
  `from nn_meta.live.scanner import TICKER_ALIASES` executes the scanner's
  import-time `setup_logging`, which mkdirs `logs/` relative to CWD as a
  side effect of every crawler run (crashes pre-argparse from a read-only
  CWD). Benign on the current server cron and in the GCP container
  (`task.sh` runs at the repo root on a writable FS), but it newly couples
  the offline crawler to the live scanner. Fix: move `TICKER_ALIASES` to a
  constants-only home (`nn_meta/config.py`).
- **`nn_meta/download_universe.py:397-398`** — one instant with no
  `bars_daily` during the swap; an overrunning 11:00 refresh could collide
  with the 12:00 surface cron's glob-then-open. Self-heals next run; add a
  runbook line about cron overlap. (Also the crash window that triggers
  P0-1.)
- **Root `Dockerfile` (untracked)** — byte-identical to
  `deploy/gcp/Dockerfile`; it's the manual workaround for P1-4. Delete it
  once P1-4 is fixed (or gitignore `/Dockerfile` as a transient build
  artifact).
- **No `.dockerignore`** — the gcloud path is safe (`.gcloudignore`
  auto-derives from `.gitignore`, which covers `.env` and `venv/` —
  verified), but the root Dockerfile invites a plain local
  `docker build .`, which would bake `.env` secrets and ~7 GB of venv/cache
  into layers. Commit a `.dockerignore` (`.env*`, `venv/`, `.git`, caches).
- **`deploy/gcp/teardown.sh`** — `gcloud builds submit` auto-creates the
  `gs://healys-batch_cloudbuild` staging bucket (one source tarball per
  build); it's absent from teardown and the README's residual-billing
  table. Cents/month, but contradicts the leave-nothing promise. PLAUSIBLE.
- **`deploy/gcp/submit.sh:34`** — on Spot, preemptions count against
  `maxRetryCount: 3`; a churny pool can FAIL a shard that checkpoint-resume
  would finish on resubmit. Acceptable by design — worth one README
  sentence. PLAUSIBLE.
- **`deploy/gcp/Dockerfile:9`** — "comparable byte-for-byte" overstates:
  the base image is undigested and apt packages float. The Python stack
  *is* exact — `constraints-linux.txt` matches `./venv/bin/pip freeze`
  byte-for-byte (verified).

---

## Verified good — do not relitigate

- **Heartbeat**: parse patterns match all three scanners' real prints
  (`run_live.py:65/89/95`, `v4_scan.py:344/360`; v31 shares the run_live
  path). Legacy single-log schema migration genuinely preserves the v3
  traceback baseline (pinned by test). `is_rth` is zoneinfo/DST-safe; the
  17:00 UTC digest lands inside RTH year-round, so a Friday-night cron
  death produces a Monday stale-mtime warning. Expert counters are isolated
  per name/path; the state file is gitignored and written atomically. Test
  coverage is well beyond happy-path (migration, corrupt state, first-run
  grace, missing/stale log, FA-error exclusion) — the gaps are exactly the
  three P1 paths.
- **Bars compaction**: numeric newest-wins ordering is correct and the
  mixed padded/unpadded lexical inversion is regression-pinned; an
  unparseable part name demotes to oldest (never crashes or mis-wins);
  refresh numbering can't collide with the dense renumber; all other
  partial states (crash during tmp write, crash after swap, stale
  `.compacting`) recover correctly once P0-1 is fixed; the manifest is
  correctly untouched.
- **Alias crawl**: bars fetch under XYZ, store/key under `underlying="SQ"`,
  consistent with `v4_scan` and the surface build; no old/new double-count
  is possible (`UNDERLYINGS` holds only "SQ").
- **GCP mechanics**: shard math (`[k::n]` over `BATCH_TASK_INDEX` 0..N−1)
  is disjoint and complete; `--symbols/--marks/--assemble` all exist
  (`nn_meta/build_meta_dataset.py:459-463`); repo-root derivation follows
  the house convention; `NN_META_POOL=v31` is baked into the image;
  `SHARDS=30` is cloud job width, not a local autosize violation; the
  resume-rsync design is idempotent; `bash -n` clean on all scripts.

## Suggested landing order

1. P0-1 + its `main()`-path test (blocks merge).
2. Heartbeat P1s 1–3 (same file, one commit; they ship to the server with
   this merge).
3. GCP P1s 4–7 + root-Dockerfile/`.dockerignore` P2s (block the first paid
   Batch run, not the merge).
4. Remaining P2s at leisure; README/runbook lines with their subsystems.

---

*Appendix reserved: whole-diff pass deltas (pending at v1).*
