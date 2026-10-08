# TODO — V8 stages 0 and 1

**Selected work: [V8 design](docs/specs/V8_DESIGN_20261007.md), stages 0 and 1 only.**
Prove an edge on cheap, liquid instruments under realistic fills before any model
or options. Universe: mostly technology names plus SPDR sector and broad ETFs.
[Decision](docs/DECISIONS.md), [evidence](docs/EXPERIMENTS.md) (October 7 entries).
ETFE is closed (v5 failed; 2026 ETFE test unspent). V6 paper is paused; its
realistic-fill re-evaluation found no edge.

## Stage 0 — tradable universe and cost model

- [x] **V8.0-pool:** frozen in [V8_POOL_20261007.json](docs/specs/V8_POOL_20261007.json):
  monthly PIT option-activity members (survivorship-free) with technology SEC SIC
  codes plus 9 declared tech-adjacent platforms; 73–107 tech names per month (124
  total) and all 17 ETFs every month. Membership covers 2024-11 to 2026-07.
- [ ] **V8.0-data:** stock bars for the pool (Alpaca); option quotes from Massive
  flat files for spreads; coverage report per symbol and day.
- [ ] **V8.0-liquidity:** decision-time liquidity rule (stock spread/volume; option
  spread ≤ 3–5% of mid, open interest, volume, price floor). Choose the cutoff
  from data and freeze it before any stage-1 result.
- [ ] **V8.0-fills:** fill model (stock touch + slippage; options mid ± k × half-spread,
  k = 1.0 primary, 0.5 sensitivity; Robinhood fees). Unit tests on hand cases.
- [ ] **V8.0-contract:** freeze the universe/cost contract and coverage report.

## Stage 1 — edge on the underlying

- [ ] **V8.1-prereg:** pre-register families, horizons (1h/1d), folds, costs and pass
  rules (benchmark-beating out of sample, rank persistence, deflated Sharpe, PBO
  < 0.5, 1.5× cost stress). Development window ends 2025-12-31.
- [ ] **V8.1-walkforward:** tuned-variant walk-forward on admitted symbols, expanding
  window, realistic costs. Benchmarks QQQ/XLK (tech) and SPY (book).
- [ ] **V8.1-verdict:** record in EXPERIMENTS. If nothing passes, stage 2
  (volatility) is next, not a meta-model.

## Parallel / later (not started)

- FA fundamentals point-in-time backfill for the V8 universe (filing/acceptance
  dated), as candidate features; FA attention remains forward-only (FA-3).
- V6 paper runtime: paused; a 20% premium stop measured on the entry midpoint is
  available as a versioned deployment if the user wants it as a live lab.
