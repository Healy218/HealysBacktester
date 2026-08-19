# TODO — current phase

**Phase: ship v4 as a second expert on the server** (`ROADMAP.md` ▶ NOW).
Set 2026-08-15; target: this weekend.

> **The standing goal (user, 2026-08-16): v4 goes to the server the moment
> it finishes training/building.** Deploy is the *immediate* next action
> once the bundle lands — nothing queued between re-finalize and deploy.
> Corollary: do block 2 (the live scoring path) **while** the dataset builds
> and the model trains, so it is never the bottleneck.

How this file works: it holds the tasks for the *current* ROADMAP phase only.
Work top to bottom, tick boxes here as things land, record mid-task state in
`HANDOFF.md`. When the phase exits, refill this file from ROADMAP's next
phase and log the exit in `docs/EXPERIMENTS.md`.

Everything below runs with `NN_META_POOL=v31` unless said otherwise —
without it the pipeline silently reads/writes the wrong artifact dirs.

## 1 — Finish v4 on the ledger (Option B, `docs/specs/V4_OUTLINE.md` stage 2)

- [~] **Mark-stream build moved to GCP Batch** (compute doctrine, DECISIONS
  2026-08-16) and RUNNING verified as of 08-18 03:28 UTC: job
  `marks-build-54bd73d-202944`, 37/118 symbols published per-symbol to
  `gs://healys-backtester/out/meta_rows/`. Full state + finish chain:
  `HANDOFF.md`. (The local `run_build_parallel.sh` path is retired for this
  build; stale July rows archived in `meta_rows.pre-marks-2026-08-15/`.)
- [x] **Selection-side ledger wiring — DONE 2026-08-17.** `choose_policy`
  scores every candidate AND the baseline through the mark-to-market ledger
  when a stream is supplied (`_ledger_policy_metrics`: shared metric schema,
  ledger-derived return/DD/exposure, ex-top3 re-marked through the ledger);
  no-stream path bit-identical (tested). The decisive regression test
  constructs a policy whose interim marks crater while finals look placid —
  shared sim crowns it, the ledger rejects it. Reports tag 🄻 rows.
- [~] **Re-run through the ledger**: `v4_evaluate --ablation` and
  `--folds 3` (seeds 0-4, epochs 60, gbt 600, embargo 1D). Compare against
  the stage-0 tables in `docs/specs/V4_OUTLINE.md` — numbers are *expected*
  to move; log the new verdict in `docs/EXPERIMENTS.md`.
  **Ran 2026-08-19 and the result is VOID** — it was computed on a dataset
  built from a cache missing 44 flat-file day-frames, which silently dropped
  16,500 low-return trades and so FLATTERED the book. Cause proven and fixed
  (`4f6fa93` + `nn_meta/cache_preflight.py`); the 89 affected symbols are
  rebuilding as `marks-build-d64ca9b-154524`. Full evidence: `HANDOFF.md`.
  Re-run both legs after assemble, then verify with
  `python -m nn_meta.dataset_diff --baseline <stage-0> --candidate <new>`
  (the 13 differing columns must collapse to zero).
- [ ] **Re-finalize**: `v4_finalize` → fresh `model_final_v4/` selected and
  trained under the ledger. Also fixes the current bundle's unverifiable
  manifest (it predates hashed persistence). Persist is atomic + gate-checked
  by construction; the old bundle is additionally in the D: backup.

## 2 — v4 live scoring path — DONE 2026-08-16 (`nn_meta/live/v4_scan.py`)

- [x] **Live v4 scorer**: `nn_meta.live.v4_scan` — every pool strategy
  proposes on the last closed bar, `build_candidate_batch` featurizes (no
  `prem_spot`), the bundle scores all DTE variants, best-of-grid alerts iff
  ≥ threshold. v3 scanner untouched. `--selftest` force-loads all members
  (passes on the real 40-member gbt bundle); real-data dry run clean.
- [x] **Parity**: candidate builder is parity-by-construction and covered by
  `tests/test_v4_candidates.py` + 11 new `tests/test_v4_scan.py` tests
  (suite 356 green). Re-validate against whichever bundle survives the
  Option B re-finalize (spec'd as Option B step 4) before dropping `--paper`.
- [x] **Expert-labeled alerts + own state**: `[v4]`-titled Telegram alerts
  with paper tag, own AlertState/Outbox (at-least-once, crash replay),
  PaperLedger, health snapshot — all under `nn_meta/live/.v4_*.json`.

## 3 — Deploy to Hetzner (alongside v3, never replacing it)

**DONE 2026-08-16 ~16:05 UTC — the [v4] expert is live on the server in
paper mode.** (User approved same day.)

- [x] Verified v3-safety, fast-forward merged the branch → `main` (46
  commits; only v3-critical deltas were a docstring + default-off kwarg).
- [x] `model_final_v4/` force-added (9.7 MB / 42 files); `docs/DECISIONS.md`
  updated.
- [x] Server pulled main; `pip` top-up installed lightgbm 4.7.0 + scipy.
- [x] rsync'd `surface_daily` + `underlying_daily` parquets into the
  server's `nn_meta/data_cache_v3/`.
- [x] Server selftest: 40/40 gbt members, score median matches local
  (0.433) — deterministic. Real-data dry run: 3 symbols, 0 errors.
- [x] Cron installed (v3 line untouched; crontab backed up to
  `~/crontab.bak.2026-08-16`): `*/15 * * * * … NN_META_POOL=v31 …
  nn_meta.live.v4_scan --once --paper >> logs/v4_cron.log`.
- [x] Rollback documented in `DOCUMENTATION.md` (delete the one cron line).

**Data-feed audit (2026-08-16, user-requested) — verified + findings:**
Universe membership is correct by construction: v3 scans its 55 trained
symbols (all healthy), v4 scans its 118 (117 healthy). Findings:
- [x] **SQ → XYZ rename**: SQ returned zero bars (dark seat). Fixed with
  `TICKER_ALIASES` in `v4_scan` — bars fetch under XYZ, model/state keys
  stay "SQ", alerts show "XYZ (fka SQ)".
- [x] **Context caches now self-updating (2026-08-16 evening).** All three
  layers: ① chain/universe + ② underlying-daily (beta) refreshed on the
  server via `--live-horizon` and kept fresh by Sunday 10:00/10:30 UTC
  crons; ③ IV surface: bar caches seeded to the server (420 MB), the
  incremental `--bars-and-surface-only --refresh-recent-days` mode +
  `build_surface` backfill ran, and Sunday 11:00/12:00 crons keep it
  current. Server is fully self-sufficient — no home-box dependency.
  (Edge contracts whose life predates the 2y entitlement 403 harmlessly.)
- [x] **PRODUCTION OUTAGE AVERTED (found 2026-08-16 during the v31-deploy
  prep)**: the live chain's universe ends at `WINDOW_END + DTE_MAX` =
  2026-08-16 — the universe filter clips contract eligibility to the frozen
  research window, so from Monday every v3 signal would have failed
  contract selection and been *silently filtered* (and the chain had
  already thinned: max cached expiry was 2026-08-07). Fixed:
  `download_universe --live-horizon 120` rebuilds listings/universe through
  today+120d and underlying daily through today (beta un-staled as a
  bonus); ran on the server for both pools; **weekly Sunday refresh cron**
  installed so it never recurs. Research constants untouched.
- [x] **Latent trap CLOSED — verified 2026-08-19**: `.alert_state.json` is no
  longer tracked (`git ls-files` clean) and is gitignored via
  `nn_meta/live/.alert_state*.json`. Original note kept for context:
  v3's `nn_meta/live/.alert_state.json` was *tracked in git* while the server mutates it live — any
  future commit touching/deleting it will conflict with the server's dirty
  copy on pull. Untrack it deliberately some quiet weekend (backup server
  copy → `git rm --cached` + gitignore → pull → restore). The new v4 state
  files are gitignored from the start (learned the hard way, 2026-08-16).

**Remaining for this phase** (after the Option B chain in block 1):
- [ ] Re-finalize → push new `model_final_v4/` → server `git pull` →
  selftest → drop `--paper` from the cron line (bundle then must verify +
  be gate-eligible, enforced by the scan itself).
- [ ] Re-validate candidate parity against the surviving bundle (Option B
  step 4) and close the last first-implementation gate item.

## Fallback if the weekend runs short

Deploy the **existing Option A bundle** as the `[v4]` expert in
paper/alert-only mode (labeled unvalidated-by-ledger), and let the Option B
re-finalize replace the bundle in place next week. Deploying alongside —
never swapping v3 — is what makes this safe either way.

## From the 2026-08-16 adversarial review (`docs/reviews/`)

P0s + quick P1s were fixed and deployed same-day (commit `9b8b473`:
atomic bar cache, shared ticker aliases, lazy TF import, universe shrink
guard, atomic dataset write). Remaining queue, ordered:

- [x] `bars_daily` compaction (newest-wins by NUMERIC part index — mixed
  padded/unpadded names would invert lexically; crash-safe dir swap;
  auto-runs after the weekly refresh) + `TICKER_ALIASES` in the daily crawl.
  Agent-built, verified + cherry-picked; suite green.
- [x] Heartbeat covers all three experts: per-expert passes/RTH-scans/
  alerts/new-crash deltas with per-log baselines, RTH-down warnings on
  missing/stale logs, old-schema migration without false crash explosions.
  Agent-built, verified + cherry-picked; suite green.
- [x] Paper-ledger crash-consistency reorder in `v4_scan.scan_pass`
  (enqueue → ledger → mark; duplicate trade_id no-op)
- [x] State-file landmines defused: `.alert_state.json` +
  `.claude/settings.local.json` untracked + gitignored; server choreography
  done (live dedupe state preserved through the pull)
- [x] Monday watch: Alpaca 429s — RESOLVED 2026-08-18, zero genuine hits (the
  first count was timestamp milliseconds; `scripts/server_health.sh` re-checks)
- [ ] **/ultrareview window open**: `main` is deliberately held behind the
  branch; once the two agents' commits land, run `/ultrareview` from the
  DESKTOP session (not Remote Control) to multi-agent-review the branch-only
  diff, then merge to main and deploy.

## Parked (not this phase)

- PBO report wiring (needs the per-fold candidate matrix).
- Magnitude/EV head training on v31 data (`nn_meta/ev_sizing.py` is
  code-ready; joins the policy grid once trained).
- Fold-3 regime miss (noise vs real weakness): carried into the expert-panel
  phase, where per-expert forward tracking answers it empirically.
