# HANDOFF — state for the next session

Written 2026-08-15 (docs-reorganization session). Protocol: `CLAUDE.md` →
"Session protocol". This file is rewritten fresh every session; the previous
one moves to `handoff-history/`.

## What this session did

- Full sweep of every .md + verification against the live machine, then the
  docs reorg: single `ROADMAP.md`, `TODO.md` (current phase),
  `DOCUMENTATION.md` (notes/traps/ops), this file + `handoff-history/`,
  `docs/DECISIONS.md` + `docs/EXPERIMENTS.md` ledgers, specs moved to
  `docs/specs/`, old v2.2 handoff archived.
- Crash investigation closed as a **non-issue** (user decision) and scrubbed
  from the docs; checkpoint/recovery infra kept as ordinary good practice.
- Weekend goal set (see `TODO.md`): finish v4 (Option B) and deploy it as a
  second labeled expert on the server, alongside v3. Longer arc: the expert
  panel (`ROADMAP.md` ⏭ NEXT).

## Verified state of the world (checked today, not assumed)

- Branch `codex/v4-causal-validation`, clean, fully pushed. **345 tests
  green** (25 s).
- Production healthy: home StockTwits collector ran 18:01 and pushed to
  Hetzner successfully; server cron untouched since 07-17 fixes.
- v4: Option A bundle on disk (`model_final_v4/`, gitignored, also on D:).
  **Option B compute has NOT started** — no `.marks.parquet` sidecar exists
  anywhere; raw bars ARE local (`nn_meta/data_cache_v3/`, 3.4 GB).
  First-implementation gate 4/5 (live parity open).
- Home box leftovers, harmless: `turbo-cap.service` still installed
  system-side (diagnostic, now moot — disable at leisure);
  `healys-boot-restart.service` committed but not installed; stale run logs
  at repo root (`v4_v31.log`, `v31_notify.log`, empty `wf_prewarm_*.log`)
  are gitignored litter from an aborted 07-27 session, safe to delete.

## THE STANDING GOAL (user, 2026-08-16)

**v4 goes to the server the moment it finishes training/building.** When the
dataset build completes: re-run evaluate through the ledger → re-finalize →
deploy immediately. The live scoring path (TODO block 2) gets built *while*
compute runs so deploy is never waiting on code.

## Running job (2026-08-16 02:42): the --marks dataset build

- `scripts/run_build_parallel.sh` (now emits marks + jobstate marker),
  logs `v31_marks_build.log` + `v31_build_0.log` at repo root; done when
  `scripts/.jobstate/v31_marks_build.exit` contains `0` and the log prints
  `PARALLEL-BUILD-DONE`. Output: rebuilt `meta_dataset.parquet` (now with
  fill provenance columns — it will show as a *modified tracked file*,
  expected, don't commit until verified) + `meta_dataset.marks.parquet`.
- **Widened to 3 shards 2026-08-16 10:27** after killing background Steam +
  Discord (~1.4 GB freed; user closed the rest). 8 symbols were already
  checkpointed and skip on resume. Observed per-worker RSS with `--marks`
  peaks ~4.0 GB (launcher budget bumped 2800→3600 MB accordingly). ETA at
  3 shards: ~30–36 h from relaunch → dataset lands late Sun / Mon morning.
- Beware self-matching pkill: quoting `nn_meta.build_meta_dataset` inside a
  compound Bash call kills your own shell mid-batch (`pkill -f` matches the
  wrapper's cmdline). Use a `[_]` bracket in the pattern.
- July checkpoints archived at `artifacts_v31/meta_rows.pre-marks-2026-08-15/`
  (delete once the new dataset assembles clean).

## Done 2026-08-16 midday: TODO block 2 — the [v4] expert is code-complete

`nn_meta/live/v4_scan.py` (committed + pushed): second scanner pass under
`NN_META_POOL=v31`, causal candidates, model-picked DTE, `[v4]`-labeled
alerts, own outbox/ledger/health state, `--paper` trust policy for the
Option A bundle, `--selftest` deploy check (passes on the real bundle),
real-data dry run clean, suite 356 green. Build widened to 3 shards after
killing background Steam/Discord.

## Done 2026-08-16 evening: [v31] expert live + the universe-horizon outage fix

- **Outage averted**: live chain ended at WINDOW_END+DTE_MAX (= 2026-08-16;
  had already thinned to Aug 7). `download_universe --live-horizon` rebuilt
  both pools' chains through 2026-11-30 on the server; weekly Sunday crons
  keep chain + underlying-daily + IV surface current (server crontab now 10
  lines; bar caches seeded, incremental `--bars-and-surface-only` mode).
- **[v31] expert live**: legacy scorer under `NN_META_POOL=v31` (hybrid
  provider via `get_provider(live=True)`), own dedupe file, `[v31]` alert
  labels, `model_final_v31/` committed, 40/40 selftest + dry-run green on
  the server. Three experts total: v3 (real), [v4] paper, [v31] paper.
- Verify when convenient: surface backfill completion
  (`logs/surface_refresh_*.log` on the server → `surface:` + NaN-rate lines,
  surface max date ≈ last trading day), and Monday's first RTH cycle across
  all three logs (`live_cron.log`, `v4_cron.log`, `v31_cron.log`) — watch
  for Alpaca rate-limit errors from three simultaneous scanners; stagger
  crons if they appear.

## Next session: start here

1. Check the build (log tails + marker above). If done: `--assemble` output
   sanity (row counts vs the July dataset ±, marks row count ~88M), then
   TODO block 1 items 2–4 (ledger selection wiring → re-runs → re-finalize),
   then swap the server bundle in place and drop `--paper` from the cron.
2. If the server deploy (TODO block 3) hasn't happened yet, that's the next
   action — the plan is fully specified there; user go/no-go was pending at
   the time of writing.

## Gotchas carried forward

- Everything v31/v4: `NN_META_POOL=v31` or you silently touch wrong dirs.
- The marks stream is ~88M rows — the streaming assemble path exists; never
  load-then-concat it (~9 GB peak, box has 15.5 usable).
- `verify_bundle()` on the current `model_final_v4/` fails **by design**
  (pre-hashing manifest); the re-finalize fixes it — don't "debug" it.
- Deploy to Hetzner is `git pull` only, never scp.
