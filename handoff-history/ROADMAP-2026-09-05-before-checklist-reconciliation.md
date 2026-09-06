# September 5 TradingView scope

Before corrected research rebuilds, include the user's 10 highest-boost scripts
across the supplied general-listing pages and 3 highest-boost Editors' Picks.
The researched selection contains 13 unique open-source indicators. Source,
causality and data-parity checks precede admission; implementation order and
the general listing's 1,000-script scope limit are recorded in
[TRADINGVIEW_EXPANSION](docs/specs/TRADINGVIEW_EXPANSION.md). This extends the
existing Keltner/BBW work; broader panel goals remain below.

# September 5 merge addendum

The user directed merging the review fixes into `main`, continuing in
`/home/healy/Coding/HealysBacktester`, and doing the TradingView work next,
before rebuilding the research artifacts. Integration validation passed: 642 tests and 18 subtests;
the 535-test count in the preserved notes is the pre-merge result. A local
merge does not deploy the server or launch a freeze/build/training campaign.

The September 5 audit repairs use feature/build contract `2026-09-05-causal-v2`.
Pre-audit freezes, partial checkpoints, rows, marks and bundles must be rebuilt
and validated under that contract; preserve existing files as historical
artifacts, and do not relabel them to bypass verification. Historical returns
and gate verdicts below are not corrected performance evidence. Evaluation
with a globally frozen proposal generator is restricted to periods after its
optimization horizon; it is conditional on that generator, not end-to-end
fold-local refreezing.

The roadmap and newer v5/v6/v7 notes below remain preserved. Revalidation is
a prerequisite for relying on old research verdicts or promoting corrected
bundles; it does not discard the panel, real-time parity, FA, SPX0, volatility,
stacking or RL goals. Raw archives and historical work must be retained.

See [audit remediation](docs/reviews/2026-09-05-remediation.md) and the
[original audit](docs/reviews/2026-09-05-adversarial-audit.md) for implemented
repairs and migration requirements.

---

# Roadmap — the one map

Every workstream, one page. This file holds **overall goals**; the tasks for
the phase we are in right now live in `TODO.md` (fed from here); design detail
lives in `docs/specs/`. Reconciled 2026-08-15.

```
DONE ─► v2.2 ROBUST ─► live server + FA collectors ─► v3 ROBUST & LIVE (the scanner today)
                                                            │
                             v3.1-at-scale (ROBUST but outlier-fragile — shelved, not promoted)
                                                            │
                             v4 causal fixes (leak removed, edge confirmed real, Option A candidate)
                                                            │
NOW ──────────────────────────────────────────────────────  ▼
        finish v4 (ledger re-runs) ─► deploy v4 as a SECOND expert on the server
                                                            │
NEXT ─────────────────────────────────────────────────────  ▼
        the expert panel: several models live at once, each a scanner selector that can trigger
        (model tracks 1/3/4 + FA discovery graduate into the panel as they beat their baselines)
```

## ✅ Done

- **v2.2 walk-forward: ROBUST.** 4-strategy pool, 56 symbols, ~2y options.
- **Live alert server** (Hetzner): 15-min scanner → Telegram, hourly FA Stage-0
  collectors archiving append-only parquet, trending digest, heartbeat,
  dead-man switch. Ops notes: `DOCUMENTATION.md`.
- **v3: ROBUST & LIVE (2026-07-11)** — what the scanner runs today.
  7-strategy pool, rank/label_excess/32x16, beats baseline 3/3 folds, ex-top3
  barely moves from headline in every fold (broad-based edge).
- **v3 foundation data**: 289-symbol bootstrap universe, 287M-bar 1m underlying
  crawl 2017→now, TV indicator library.
- **v3.1-at-scale (2026-07-21): shelved.** 118 symbols / 5 pools via
  flat-files. Technically ROBUST (2/3 folds) but outlier-fragile — fold 2's
  +1136% was essentially one 31x TQQQ trade. Not a clear upgrade over live v3;
  nothing promoted. Full chronology: `docs/v31_run_history.md`.
- **v4 causal validation, stage 0 + Option A (2026-07-21).** Removing the
  `prem_spot` leak + purged nested selection: corrected ablation still solidly
  positive (+72.6%), walk-forward winners broadly diversified — the signal is
  real, v3.1's framing of it was not. A deployable candidate
  (`nn_meta/model_final_v4/`, gbt/filter/thr 0.5, 40 seeds) is trained and
  persisted. Design + stage-0 result tables: `docs/specs/V4_OUTLINE.md`.
  Verdicts ledger: `docs/EXPERIMENTS.md`.

## ✅ Shipped v4 as a second expert — EXIT ACHIEVED 2026-08-24

The full Option B arc landed: selection routed through the mark-to-market
ledger, the EV head + DD brake joined the grid, the gate's baseline bar
moved to ex-top3 (the raw bar was one 1526× ticket), and the **first
gate-eligible bundle (V118: gbt×40, ev/0.05, val +605%, maxDD 21.9%)
deployed to the server — `[v4]` alerts are REAL as of 2026-08-24** (paper
2026-08-16 → real 2026-08-24; the scan self-enforces verified+eligible).
Parity green, v3 untouched, prem_spot leak question closed (leaks in both
families under purged selection). Wave-2 item 1 (EV-sized seat)
effectively shipped inside V118 — the ev mode IS the deployed policy, so
no separate `[v4ev]` seat is needed.

## ▶ NOW — Expert panel, wave 2 (user priorities set 2026-08-16)

The panel's first three seats went live 2026-08-16 (v3 real; [v4], [v31]
paper). Wave 2, in dependency order — each seat deploys ALONGSIDE, tracked
by its own ledger, promoted only by forward results:

1. **EV-sized v4 seat — DONE 2026-08-24, folded into V118**: the EV head
   won the grid outright (ev/0.05 through the ledger, all folds), so the
   deployed `[v4]` IS the EV seat; no separate `[v4ev]` label.
2. **SPX/NDX daily-options trader** (user priority #5, ranked ahead of
   vol-regime): a NEW pool (`spx0`) through the same v4 causal contract —
   SPX + NDX daily-expiry options, calls and puts, ~2y RAW 1-MINUTE bars (stage-0 decision 2026-08-17; extracting to data_cache_spx0/),
   multiple trades/day, signal-driven entries AND exits, **25% max-DD
   gate**, no upside cap.
   **Stage-0 data audit DONE 2026-08-19** (`scripts/spx0_stage0_audit.py`;
   findings in `HANDOFF.md`): ① options ARE in the flat files and the archive
   is CLEAN — 500 day-files 2024-08-16..2026-08-14, the only weekday gaps are
   the 21 market holidays; all four roots present daily; 0DTE depth healthy at
   a median 566 same-day contracts/day. ② index underlying is 403-gated, so
   SPY/QQQ-proxy signals with ratio-mapped strikes stands.
   The one blocker found — a truncated 10,000-bar proxy stub covering 1 of 500
   option sessions — was **CLEARED the same day**:
   `scripts/build_spx0_underlying.py` builds SPY/QQQ from the 9y crawl,
   RTH-filtered, now **500/500 sessions (100%)**, and fails closed under 99%.
   **The data layer for this seat is READY**; what remains is design, not data.
   Cost modeling matters most here (index fees + spreads on small premiums) —
   stage-2 accounting is non-negotiable, and the audit backs that up: **median
   volume per 1m bar is 3 contracts** (p90 ~48), so most bars are untradeable
   and the pool must concentrate on liquid strikes/times.
   **Design history (EXPERIMENTS/DECISIONS 2026-08-21..24):** round 1 (long
   ATM 0DTE) — no edge after costs; round 2 (naked sell-premium, stop-based
   margin) — passed val, blew up on test (−1863%, equity through zero):
   stops cannot bound a naked short's tail. Round 3 (credit verticals with
   loss bounded BY CONSTRUCTION + intraday-native signal seats) is the
   current shot — in flight on Batch as of 2026-08-24.
3. **Vol-regime track (track 1)** — the first big GCP Batch job after the
   pilot passes: v3/data (5.4 GB, 2017→) → 9y intraday realized-vol →
   HAR-RV/GARCH full OOS → one small sequence model that beats them per
   regime or is dropped. Product: `available_at`-stamped vol features for
   every expert; a seat only if the features prove out.
4. **FA-discovery seat** — composite ranker → FIRST frozen monthly Top-10 →
   forward tracker → `[fa]` digest + the WSB daily trending digest.
   Exit metric unchanged: ≥3 frozen monthlies tracking.
5. **Dual-mode cadence, panel-wide** (user decision): every expert gains a
   daily **top-N watchlist digest** (best-scored candidates regardless of
   threshold — flow to browse) alongside the existing threshold-gated
   conviction pings; the scoreboard tracks watchlist hit-rates so the dial
   becomes data-driven. **v4 seat SHIPPED 2026-08-24** (`v4_scan --digest`,
   20:10 UTC weekdays, underlying-direction hit-rates); v3/v31 seats
   remain (the legacy scorer path needs its own recording hook).

Standing pieces of the panel design (unchanged): expert registry (bundle +
schema + policy + label), per-expert paper ledgers, scoreboard-driven
promotion/demotion (`docs/EXPERIMENTS.md`). Stacked blend stays queued
behind wave 2's outputs; RL sizing stays last. Compute venue: heavy runs on
GCP Batch contingent on the pilot's byte-identity verdict; crawls and keys
never leave home.

**2026-09-05 addenda:** [v5] (wide pool, PIT universe, risk-aware gate) is
the fourth seat (paper); the panel now runs on streamed SIP bars with
one-minute-after-close passes (the pre-09-08 paper record was intraday-blind
— EXPERIMENTS); Massive Options Advanced + Alpaca Algo Trader Plus unlock
deep option history, quotes, trades and NBBO fills (plans in TODO; v7
real-time contract in `docs/specs/REALTIME_SPEC.md`); generation v6
(additive: keltner, bbw_squeeze, weekly expiries) is mid-freeze.

**Exit:** the wave-2 seats live with tracked ledgers; the SPX/NDX stage-0
audit written; watchlists flowing daily.

## ⏭ Model tracks — the pipeline that feeds the panel

From `docs/specs/V4_OUTLINE.md` (full detail there). Each track graduates
into the expert panel only by beating its boring baseline through the v4
evaluation contract (purged nested selection, costed portfolio-level OOS,
calibration, deflated Sharpe):

1. **Track 2 — classification** (today's v3/v4): calibration + deflated
   Sharpe shipped; PBO report wiring and the magnitude/EV head remain.
2. **Track 1 — volatility forecasting**: HAR-RV/GARCH baselines shipped; a
   sequence model must beat them OOS or its features don't ship.
3. **Track 4 — stacked blend** (+ FinBERT-class sentiment on the FA archive).
4. **Track 3 — RL sizing/exit** on the stage-2 ledger, last.

## ⏭ FA — ticker discovery (`docs/specs/FA_SPEC.md`)

Stage-0 collectors live since July — history only accumulates forward, which
is why they deployed early. Code through the score table is done
(`fa/entities.py`, `fa/scores.py`, `fa/universe_loop.py`). Remaining:
fundamental overlay → composite ranker → frozen monthly Top-10 → forward
tracker → point-in-time graduation into the training universe (and, once the
panel exists, an FA-discovery expert). Queued: daily WSB-trending digest,
exit/roll alerts on the live scanner.

**Exit:** ≥3 monthly top-10 artifacts frozen and tracking forward returns.

## ⏸ Parked

- **Cloud batch compute (Google Cloud Batch)** — assessed 2026-08-16,
  **highly feasible**: every heavy stage is an embarrassingly-parallel,
  checkpointed CPU job; a full research generation ≈ $10–20 spot and ~1–2 h
  wall vs ~a week local. Pilot spec + architecture:
  `docs/GCP_BATCH_FEASIBILITY.md`. First real customer: the next full
  retrain after Option B.
- **Deeper options history (2017→)**: blocked on a paid Massive/Polygon
  entitlement — proven limit, not a code gap (`DOCUMENTATION.md` → data
  limits). Underlying-only deep history is already crawled. (Cloud compute
  does not change this — it's a provider limit.)
- **Point-in-time universe selection** (survivorship-bias fix) — promoted
  in importance by the cloud doctrine: universe expansion (120 → ~300 by
  $volume) and a wider strategy-candidate pool are now compute-trivial
  (~$25/build; the flat-files day archive is already whole-market), so the
  binding constraints are THIS item plus the liquidity floor and
  multiple-testing discipline — not build cost.
- PBO report wiring; magnitude/EV head training (join the grid when trained).

---
**Standing rules across phases**
- Point-in-time everything; frozen artifacts; no retroactive edits.
- Checkpoint every long stage (spot-safe by construction).
- Evaluate portfolio-level, out-of-fold, with costs, ex-outliers.
- New complexity must beat the boring baseline (GBT, buy-and-hold basket)
  before it ships.
- Experts are **added alongside** the live scanner, never swapped in until
  their gates pass; `main` stays the operational line.
