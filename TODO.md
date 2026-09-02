# TODO — current phase

**Phase: Expert panel, wave 2** (`ROADMAP.md` ▶ NOW; user priorities set
2026-08-16). Entered 2026-08-24 after the v4-ship phase exited the same day
(V118 live, real alerts — see `handoff-history/HANDOFF-2026-08-24-*`).

How this file works: it holds the tasks for the *current* ROADMAP phase only.
Work top to bottom, tick boxes as things land, record mid-task state in
`HANDOFF.md`. When the phase exits, refill this file from ROADMAP's next
phase and log the exit in `docs/EXPERIMENTS.md`.

Everything below runs with `NN_META_POOL=v31` unless said otherwise.
Heavy compute runs on GCP Batch (rebuild + pin `IMAGE_TAG` after every code
change); the box codes, tests, and smokes — **except** the v5 campaign
(block 6), where the box is also a build worker.

**Active focus since 2026-08-26: block 6, the v5 wide-pool campaign.**
Blocks 1–5 are paused behind it unless a live-scanner issue jumps the queue.

## 1 — spx0 seat, round 3 (wave-2 item 2) — IN FLIGHT

- [x] Round 3 DONE 2026-08-24 (EXPERIMENTS): **first signs of life** —
  folds 2/3 positive after costs (+2.7%/+10.2% test), no blowups (the
  vertical −1×margin floor held; worst marked DD 36%). NOT a seat yet:
  fold 1 −50.6%, best deflated Sharpe 0.20, fold-3 marked DD 28.6% > cap.
- [x] **Composition diagnosis DONE 2026-08-24** (EXPERIMENTS): verticals are
  selectable raw material, longs are not; vwap_rev flood adds toll; positive
  cells = ma×verticals and gap_fill_50×longs, consistent across the axis.
  strategy seats actually entered — dataset + reports in
  `out/spx0-20260824T145751Z-41a00/`): cheap, shapes round 4.
- [x] Round 4 (concentrated grid) DONE 2026-08-24 (EXPERIMENTS): fold 2
  jumped to +48.5% (deflated 0.17) but fold 3's validation refused every
  candidate and fold 2's marked DD breaches the cap — regime instability,
  not toll, is now the binding problem. No seat after four rounds.
- [ ] USER DECISION: lever 5 (2022 bear data — blocked on the Massive
  Advanced upgrade the user is evaluating) vs PARK with the machinery kept
  (bounded verticals, seat mapping, package fills are durable either way).

## 2 — Dual-mode cadence, panel-wide (wave-2 item 5; v4 seat DONE)

- [x] v4 seat shipped 2026-08-24: recording in every pass, daily top-10
  `--digest` (20:10 UTC weekdays), underlying-direction hit-rates.
  **Watch Monday:** first populated digest + first real `[v4]` alert
  behavior (threshold ev/0.05 through the EV head).
- [ ] v3/v31 seats: add the same recording hook to the legacy
  `run_live` scorer path + a shared digest (one message for the panel, or
  one per expert — decide when wiring). `watchlist.py` is expert-agnostic
  by design.

## 3 — FA-discovery seat (wave-2 item 4; exit metric: ≥3 frozen monthlies)

- [x] Composite ranker BUILT 2026-08-24 (`fa/ranker.py` for real:
  corroboration ≥2 families, liquidity floor = universe_300, point-in-time,
  write-once freeze; tz-robust scores). Fundamental overlay (filings LLM /
  Form 4 / unusual-options) still a stub — heuristic social+news v1 ships
  first per spec.
- [x] **FIRST monthly Top-10 FROZEN 2026-08-24** (`fa/artifacts/
  top10_2026-08.{json,md}`, EXPERIMENTS row). Exit metric: 1 of ≥3.
- [x] Forward tracker code ready (`fa/tracker.py`: windowed excess vs the
  training-universe basket, never guesses missing bars); first meaningful
  run ~late September.
- [ ] Monthly freeze automation — must run on the HOME box, not the server:
  frozen artifacts are git-tracked, and a server-side write would dirty the
  server repo and wedge pulls (the scp lesson). Shape: systemd timer
  (Persistent=true, like healys-stocktwits) on the 1st → rsync-pull
  `fa/archive` from the server → `fa.ranker --prior-month --freeze` →
  commit+push. Until then: manual, ~1 min on the 1st.
- [ ] `[fa]` digest to Telegram + WSB daily trending digest; fundamental
  overlay legs (filings deltas, Form 4, unusual options).

## 4 — Vol-regime track (wave-2 item 3) — first big Batch job

- [ ] Design the realized-vol feature build (v3/data 5.4 GB, 2017→ →
  9y intraday RV) and the HAR-RV/GARCH OOS harness; launch on Batch.
  Product: `available_at`-stamped vol features for every expert; a seat
  only if a sequence model beats the boring baselines per regime.

## 5 — Methodology debt (small, unblocks future verdicts)

- [x] PBO report wiring DONE 2026-08-24: CSCV over the whole policy grid
  (equal-weight daily candidate P&L on validation), reported per run
  beside deflated Sharpe; never guesses on thin windows.
- [x] v5 wide pool DEFINED 2026-08-24 (`PROPOSAL_STRATEGIES_V5`: all 10
  swept families, seam-tested; `NN_META_POOL=v5` plumbs through).
- [x] **PIT universe BUILT + FROZEN 2026-08-24** (all 4 spec steps,
  EXPERIMENTS row): `nn_meta/universe_pit.py` + crawler + 496-day
  backfill → 21 frozen monthlies 2024-11→2026-07 (~300 members, canaries
  X/SWTX/WBA pass, renames FI→FISV & BITF→DRAM aliased); `--membership`
  wired into build_meta_dataset + walkforward_meta (default ON for v5).
  **v5 is unblocked.** Ongoing: monthly crawl+freeze must ride the same
  home-box automation as the FA monthly (block 3) — the entitlement
  window rolls, so crawl promptly each month.
- [ ] DD-brake live enforcement in `v4_scan` sizing (brake is shown, not
  enforced; moot for V118's `dd_brake=None` but a landmine for any braked
  future bundle).

## 6 — v5 wide-pool campaign (IN FLIGHT since 2026-08-26)

The generation the PIT universe unblocked: 10 families × 441 PIT members,
all stages on GCP Batch + the home box. Live detail (job ids, relaunch
commands, infra traps) lives in `HANDOFF.md` — this is the checklist.

- [x] **Freeze DONE 2026-08-29**: 453/453 tasks, zero failures, ~75h,
  ~$40. Merged spec published to `artifacts_v5_in/baseline_spec.json`:
  441 symbols frozen, 12 skipped-thin, every family is somebody's
  best_strategy (rsi 182 · stoch 49 · bbands 46 · volume 42 · squeeze 40
  · supertrend 39 · ma 28 · elliott 11 · macd 3 · tv_rating 1).
- [x] Per-family build checkpoints (`--partial-dir`) + bucket partial
  sync — spot preemption costs ~40min, not ~8h. Kill/resume validated.
- [x] Home box as a third build worker (`run_build_v5_local.sh`, walks
  the spec backwards; bucket skip-check is the only coordination).
- [x] `submit.sh` fails closed when the image tag has no manifest.
- [ ] **Dataset build: 144/441 rows** (two cloud fleets + the box).
- [ ] Reconcile stragglers when the fleets drain (one task died
  permanently to exhausted retries in an earlier fleet).
- [ ] **Audit marks coverage** for symbols finished after 2026-09-01
  00:33Z (the incomplete-checkpoint window — see HANDOFF); rebuild any
  whose rows lack mark-stream entries. Bounded to ~8 symbols + in-flight.
- [ ] **FIRST THING next campaign — the universe read path** (user decision
  2026-09-02). All measured on the live v5 universe, not estimated. Three
  changes at three layers; together they attack BOTH constraints the v5
  build hit (RAM ceiling and per-call scan cost).

  *The problem.* `universe.parquet` is 5,214,222 contracts / 44 MB on disk.
  A symbol build only ever needs its OWN underlying — 21,009 rows, **0.4%**
  (verified: `Execution.select`, `options/execution.py:89`, always passes
  `self.symbol`). But today every worker loads the whole thing and every
  lookup scans the whole thing:
  - `HybridProvider._get_universe` (`options/data/hybrid_provider.py:96`)
    reads the parquet per PROCESS → **0.96 GB resident per worker**, then
    `u = self._universe.copy()` to normalize 3 columns → peak RSS
    2.53 → 3.17 GB (~0.64 GB transient spike).
  - `get_chain` (`hybrid_provider.py:120`) builds boolean masks over all
    5.2M rows on EVERY call: **216 ms/call vs 0.70 ms on a per-symbol
    pre-filter — 310x**. `Execution._chain_cache` memoizes on
    `(as_of, right, target_dte)`, so misses are per trade-date and per
    roll: order 10^3 scans/symbol ≈ **15–40 min of the ~126 min/symbol**.

  *The fix, in dependency order:*
  1. **Derive sorted/partitioned** — `v3/derive_contracts.py:109` writes
     `uni.to_parquet(...)` straight from a dict iteration, so underlyings
     are scattered and every row group is mixed → pyarrow can skip NOTHING
     and predicate pushdown is useless. Add `uni.sort_values("underlying")`
     before the write (row-group stats become meaningful) or
     `partition_cols=["underlying"]` (one small file per symbol).
     **This one is a prerequisite — steps 2–3 underdeliver without it.**
  2. **Read only what the worker needs** — load with
     `filters=[("underlying","==",sym)]`. 0.96 GB → a few MB per worker;
     the `.copy()` spike becomes irrelevant. Per-worker RSS ~5.4 → ~4.4 GB
     → 4 workers becomes 5–6.
  3. **Keep `get_chain`'s API, fix its target** — mask the per-underlying
     slice, not the full frame. Callers and tests unchanged.

  *Not a data-acquisition problem.* universe.parquet is derived offline
  from flat-files already on disk — no REST, no quota. Flat-files are
  already the documented optimal bulk path. No Massive plan or endpoint
  change helps here (checked 2026-09-02).

  *And not a C++ problem.* The masks already run in numpy/Arrow C++,
  vectorbt sims are Numba-JIT, training is TF/LightGBM. A rewrite buys
  maybe 2–5x on genuine Python overhead, costs months, and re-risks
  diff-gate-validated code — against 310x for ~20 lines of Python.

  Deliberately NOT done mid-campaign: touching the data path with symbols
  in flight is the pattern that cost three fleet rebuilds in the v5 build
  stage. Note step 1 means re-deriving (or one-shot re-sorting) the
  universe, which workers currently hold open.
- [ ] Before the NEXT generation: move `WINDOW_START`/`TRAIN_START` to
  2024-12 (~20% of the current train span is built then dropped by the
  membership filter), and key family partials by window (or clear
  `out/v5/meta_partial/` on any window change — stale partials would
  silently mix windows within one symbol).
- [ ] Settle the membership-vs-`assign_split` ordering mismatch
  (`assemble` filters before, `run_fold` after) before trusting the
  evaluate ladder's fold splits.
- [ ] Assemble (`--membership` ON for v5) → `out/v5/meta_dataset.parquet`.
- [ ] Evaluate/finalize ladder with PBO + deflated Sharpe; verdict row in
  `docs/EXPERIMENTS.md`: does the wide pool beat v31?
- [ ] Post-campaign: delete stale Artifact Registry tags.

## Forward-tracking duties (standing, this phase)

- Scoreboard reads: `[v4]` real-alert hit-rate vs its paper history; the
  watchlist digest's 7-day rates once they populate; v31's
  outlier-fragility question answers itself here.
- Fold-3 regime miss (noise vs real weakness) — answered empirically by
  per-expert forward tracking, not by another backtest.

## Parked (unchanged)

- Point-in-time universe selection (survivorship fix) — first candidate
  for the next research generation on Batch.
- Deeper options history (2017→) — provider entitlement, not code.
- Stacked blend (track 4) behind wave-2 outputs; RL sizing (track 3) last.
