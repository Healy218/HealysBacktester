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
change); the box codes, tests, and smokes.

## 1 — spx0 seat, round 3 (wave-2 item 2) — IN FLIGHT

- [~] `spx0-run-48db82e-095520` RUNNING on Batch (launched 2026-08-24
  ~09:55 CDT): credit verticals (wings 1/2/4 steps, loss bounded by
  construction) + 6 intraday-native seats, 3-fold nested walk-forward.
  **Read first:** the walk-forward report's per-fold winners — an eligible
  vertical (dte < 0) or intraday-strategy winner with positive ledger test
  return under the 25% DD cap is the first sign of life this pool has
  shown. Verdict → EXPERIMENTS either way.
- [ ] If a seat shows life: design the promotion path (spx0 has no
  finalize/bundle/live-scan equivalent yet — that's a build) and decide
  levers 4 (1m signals) / 5 (2022 data) with the user.
- [ ] If rejected again: user decision — park the pool or spend lever 5
  (2022 bear-regime data) first.

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

- [ ] Fundamental overlay → composite ranker (code through the score table
  exists: `fa/entities.py`, `fa/scores.py`, `fa/universe_loop.py`).
- [ ] **Freeze the FIRST monthly Top-10 (August 2026)** — calendar-bound:
  every month not frozen is a month of forward tracking lost.
- [ ] Forward tracker + `[fa]` digest; WSB daily trending digest queued
  behind it.

## 4 — Vol-regime track (wave-2 item 3) — first big Batch job

- [ ] Design the realized-vol feature build (v3/data 5.4 GB, 2017→ →
  9y intraday RV) and the HAR-RV/GARCH OOS harness; launch on Batch.
  Product: `available_at`-stamped vol features for every expert; a seat
  only if a sequence model beats the boring baselines per regime.

## 5 — Methodology debt (small, unblocks future verdicts)

- [ ] PBO report wiring — the per-fold candidate matrix it needed now
  exists (`choose_policy` carries `candidate_grid`/`candidate_sharpes`
  since 2026-08-21).
- [ ] DD-brake live enforcement in `v4_scan` sizing (brake is shown, not
  enforced; moot for V118's `dd_brake=None` but a landmine for any braked
  future bundle).

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
