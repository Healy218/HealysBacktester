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
  swept families, seam-tested; `NN_META_POOL=v5` plumbs through). The
  300-ticker generation's remaining blocker is POINT-IN-TIME universe
  membership — DESIGNED 2026-08-24 (`docs/specs/PIT_UNIVERSE_SPEC.md`):
  Alpaca rejected by live probe (0 bars for 4 delisted names); backbone =
  the OPRA day_aggs archive we already pay for (option $-volume ranking,
  survivorship-free by construction). Build order in the spec: stage B
  pure module → home-box day_aggs crawler → 2024-08→now backfill +
  delisting-canary gates → --membership wiring.
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
