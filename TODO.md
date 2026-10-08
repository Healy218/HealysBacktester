# TODO — V8 stages 0 and 1

**Selected work: [V8 design](docs/specs/V8_DESIGN_20261007.md), stages 0 and 1 only.**
Prove an edge on cheap, liquid instruments under realistic fills before any model
or options. Universe: mostly technology names plus SPDR sector and broad ETFs.
[Decision](docs/DECISIONS.md), [evidence](docs/EXPERIMENTS.md) (October 7 entries).
ETFE is closed (v5 failed; 2026 ETFE test unspent). V6 paper is paused; its
realistic-fill re-evaluation found no edge. **No paid data:** read V7 raw inputs
in place on MRHA (never unpack); Alpaca free tier for anything else. Keep the
local footprint to a few GB and write nothing to MRHA ([data plan](docs/specs/V8_DESIGN_20261007.md#budget-data-and-storage-user-direction-2026-10-07)).
Run large reads under `systemd-run --user --scope -p MemoryMax=…` and stream
per symbol/day; full in-memory loads have crashed this box.

## Stage 0 — tradable universe and cost model

- [x] **V8.0-pool:** first freeze (superseded by V8.0-pit) in [V8_POOL_20261007.json](docs/specs/V8_POOL_20261007.json):
  monthly PIT option-activity members (survivorship-free) with technology SEC SIC
  codes plus 9 declared tech-adjacent platforms; 73–107 tech names per month (124
  total) and all 17 ETFs every month. Membership covers 2024-11 to 2026-07.
- [x] **V8.0-pit:** rebuilt from the V7 option day aggregates with the same
  parameters: 65 monthlies 2021-04 → 2026-08, identical V3 rank/score on the overlap,
  delisting canaries pass, OPRA test roots and renames fixed V8-locally. Pool
  re-frozen in [V8_POOL_PIT2021_20261007.json](docs/specs/V8_POOL_PIT2021_20261007.json)
  (66–109 tech names per month, 162 distinct, plus 17 ETFs); it supersedes the
  first pool. [Evidence](docs/EXPERIMENTS.md).
- [x] **V8.0-data:** hourly/daily regular-session bars (raw + adjusted) for all 179
  pool symbols, 2021 → 2026-09-14: V7 store for 157, Alpaca free tier for 22.
  Identity follows the PIT roots plus verified overrides; coverage 127,125 complete,
  83 partial (upstream feed gaps), 3 missing, 138 post-delisting.
  [Evidence](docs/EXPERIMENTS.md).
- [x] **V8.0-spreads:** stock NBBO spreads measured from a seeded Alpaca free-tier
  sample (207 days × 13 snapshots × all pool symbols; median 7.2 bp, SPY 0.25 bp,
  tech names median 8.9 bp); Abdi–Ranaldo cross-check not informative at this
  liquidity. Option spreads from a 3% sample of V7 NBBO captures (median 7.1% of
  mid; 56% of near-the-money, mid ≥ $1 snapshots ≤ 5%). [Evidence](docs/EXPERIMENTS.md).
- [x] **V8.0-liquidity:** user-approved rule frozen in
  [V8_LIQUIDITY_20261008.json](docs/specs/V8_LIQUIDITY_20261008.json) (prior close
  ≥ $5, 20-day median $ volume ≥ $25M, bar status ok, no entries before 10:00 ET;
  costs carry the spread). Admission panel: 99.3% of member symbol-days, median 93
  symbols/day. Option cutoffs deferred to stage 3. [Decision](docs/DECISIONS.md).
- [x] **V8.0-fills:** `nn_meta/v8_fills.py` + frozen
  [V8_COSTS_20261008.json](docs/specs/V8_COSTS_20261008.json): stock fills at bar price
  ± (measured half-spread × name factor + 1 bp), sell-side regulatory fees; options
  mid ± k × half-spread (k = 1.0 / 0.5) + $0.05/contract. Hand-case tests pass.
- [x] **V8.0-contract:** [V8_CONTRACT_20261008.json](docs/specs/V8_CONTRACT_20261008.json)
  pins 13 artifacts + 10 code files by sha256; `nn_meta.v8_contract.verify()` gates
  stage-1 runs. **Stage 0 complete.**

## Stage 1 — edge on the underlying

- [x] **V8.1-prereg:** pre-register families, horizons (1h/1d), folds, costs and pass
  rules (benchmark-beating out of sample, rank persistence, deflated Sharpe, PBO
  < 0.5, 1.5× cost stress). Development window ends 2025-12-31.
- [x] **V8.1-walkforward:** tuned-variant walk-forward on admitted symbols, expanding
  window, realistic costs. Benchmarks QQQ/XLK (tech) and SPY (book).
- [x] **V8.1-verdict: FAIL** (all five rules; [evidence](docs/EXPERIMENTS.md)). record in EXPERIMENTS. If nothing passes, stage 2
  (volatility) is next, not a meta-model.

## Stage 2 — volatility (approved by the user 2026-10-08)

- [x] **V8.2-data:** daily option chains for the pool from V7 day aggregates.
- [x] **V8.2-iv / -forecast:** IV30 (ATM, parity forward) and PIT 21-day HAR forecast,
  `vol_panel.parquet`. [Evidence](docs/EXPERIMENTS.md).
- [x] **V8.2-prereg:** user-approved, [frozen](docs/specs/V8_STAGE2_PREREG_20261008.json).
- [x] **V8.2-walkforward / -verdict: FAIL** (all variants and always-on structures lose;
  2/6 folds; PBO 0.84). First run invalidated by a split-settlement bug, fixed and rerun.
  [Evidence](docs/EXPERIMENTS.md).

## Events / FA history (user direction 2026-10-08)

- [x] **V8-EV-data:** free PIT backfill 2021–2025 (SEC facts/filings, insider, FINRA
  short volume, news). [Evidence](docs/EXPERIMENTS.md).
- [x] **V8-EV-prereg:** four hypotheses, 16 variants, [frozen](docs/specs/V8_EVENTS_PREREG_20261008.json).
- [x] **V8-EV-walkforward / -verdict: FAIL** for all four; shared gates passed (rank
  0.41, PBO 0.14); H1 earnings drift (SUE, 20-day) is a near-miss: positive in all 6
  folds, OOS Sharpe 1.65, deflated Sharpe 0.92, but beat fully invested benchmarks in
  only 2/6. [Evidence](docs/EXPERIMENTS.md).

- [x] **V8-H1-confirm:** [prereg](docs/specs/V8_H1_CONFIRM_PREREG_20261008.json).
  A (stock, 2026 holdout): **PASS** — +22.2%, Sharpe 1.31 vs QQQ 1.12, alpha +13.8%/yr.
  B (calls at pessimistic 6% spread, 2021–2025): FAIL (t = 1.84, 3/6 folds) — option
  costs unknown, not disproven. [Evidence](docs/EXPERIMENTS.md).
- [x] **V8-H1-short:** short, long-short and puts all FAIL in dev ([prereg](docs/specs/V8_H1_SHORT_PREREG_20261008.json));
  the edge is long-only. [Evidence](docs/EXPERIMENTS.md).
- [ ] **V8-H1-paper (next):** Alpaca paper forward test, stock and ~45 DTE / 0.60 delta call
  side by side on every H1 signal (user decision Oct 8) in a reset paper account (V6 history
  archived, V6 timers disabled). Built: `scripts/run_v8_h1_paper.py` (signals / trade /
  reconcile / status; dry run unless `--live`; idempotent order IDs), `nn_meta/v8_paper.py`,
  units `deploy/systemd/healys-v8-h1-{signals,trade,reconcile}.{service,timer}` (09:45 /
  10:31 / 16:20 ET). **Not enabled until the reset account is verified.**

## Parallel / later (not started)

- FA fundamentals point-in-time backfill for the V8 universe (filing/acceptance
  dated), as candidate features; FA attention remains forward-only (FA-3).
- V6 paper runtime: paused; a 20% premium stop measured on the entry midpoint is
  available as a versioned deployment if the user wants it as a live lab.
