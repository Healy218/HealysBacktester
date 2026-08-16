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

## Next session: start here

1. Open `TODO.md`, phase 1, first box: launch the `--marks` dataset build
   (multi-hour — start it before anything else, `NN_META_POOL=v31`).
2. While it runs: the selection-side ledger wiring in `nn_meta/v4_evaluate.py`
   (spec: `docs/specs/V4_OUTLINE.md` "Option B plan", steps 1–3).

## Gotchas carried forward

- Everything v31/v4: `NN_META_POOL=v31` or you silently touch wrong dirs.
- The marks stream is ~88M rows — the streaming assemble path exists; never
  load-then-concat it (~9 GB peak, box has 15.5 usable).
- `verify_bundle()` on the current `model_final_v4/` fails **by design**
  (pre-hashing manifest); the re-finalize fixes it — don't "debug" it.
- Deploy to Hetzner is `git pull` only, never scp.
