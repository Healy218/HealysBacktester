# Point-in-time universe module — design (2026-08-24)

> **STATUS: BUILT + FROZEN 2026-08-24, same day.** All four build-order
> steps landed (`nn_meta/universe_pit.py`, `scripts/build_universe_daily
> .py`, 21 frozen monthlies 2024-11→2026-07 in `v3/artifacts/universe_pit/`,
> `--membership` in the v5 entry points). Deviations from this design:
> entitlement actually starts **2024-08-26** (not 2024-08-01), so the first
> full-window month is 2024-11; canaries are X/SWTX/WBA (obvious picks
> like MRO/JNPR/HES died in-window but never ranked top-270); put/call
> split: recorded. Open-question defaults all held. Verdict: EXPERIMENTS
> 2026-08-24; decisions: DECISIONS 2026-08-24 (late).

The last blocker before the v5 generation (120 → ~300 names, wide strategy
pool). Purpose: survivorship-free, monthly universe membership so a
backtest can only ever train on names it could have known about AT THE
TIME. ROADMAP's parked item, promoted; consumers are the v5 sweep/dataset
build and the FA graduation rule (graduates enter at their ranking date).

## Source decision — settled by experiment, 2026-08-24

**Alpaca is REJECTED as the backbone**: probed live — TWTR, SIVB, ATVI,
FRC (all delisted 2022–23) return **0 daily bars each**. A source that
cannot show dead tickers is survivorship-biased at the source; ranking on
it would quietly rebuild the exact bias this module exists to kill.

**The backbone is the Massive OPRA flat-file archive we already pay for**
($29 options Starter): the provider's per-date, whole-market files include
every name that traded options THAT DAY, dead or alive — survivorship-free
by construction. Use the `day_aggs_v1` family (per-contract DAILY bars,
~tens of MB/day), not the minute files `populate()` uses: the ranking
needs daily aggregates only. Note the LOCAL `flatfiles_15m/` cache is
universe-FILTERED and cannot seed this module — stage A re-pulls raw day
aggregates.

Ranking metric: **daily option dollar volume per underlying**
(Σ close × volume × 100 across the underlying's contracts). For an
options-trading system this is truer than stock $-volume — it IS the
tradability we need — and it costs $0 beyond the current plan. A second
adapter (Massive stocks grouped-daily, stock $-volume, 5–10y) can be added
if/when the stocks plan lands; the module is source-agnostic below stage A.

Window: the current entitlement's ~2y matches the options training window
exactly — membership 2024-08→now is what v5 trains against. Deeper
backfill rides the same code when deeper entitlement exists.

## Architecture

```
stage A (HOME BOX — crawls never leave home; keys stay in .env)
  per trading day: download day_aggs_v1 → parse OCC → group by underlying
  → one small row set (underlying, date, opt_dollar_vol, n_contracts,
  n_trades) → append v3/data/universe_daily/<yyyy-mm>.parquet; raw file
  discarded. ~500 days × ~20 MB download; resumable per day.

stage B (deterministic, local, tested)
  monthly reconstitution at each month-end M, using rows ≤ M ONLY:
  - liquidity score: trailing 63-trading-day MEDIAN opt_dollar_vol
  - eligibility: ≥ 50 active days in the window; score > 0
  - rank; membership with HYSTERESIS: enter at rank ≤ 270, stay until
    rank > 330 (target N = 300; the band caps churn like index rules do)
  - underlying mapping: OCC root → ticker (TICKER_ALIASES for renames;
    adjusted roots like 'AAPL1' dropped; index roots SPXW/NDXP excluded —
    they are the spx0 pool's business, not the equity universe's)
  → frozen artifact per month: v3/artifacts/universe_pit/<yyyy-mm>.json
    (write-once, committed — same provenance discipline as FA monthlies)
  → consolidated universe_membership.parquet (month, ticker, rank, score,
    entered, exited)
  available_at = the first trading day AFTER month-end M.

stage C (consumption)
  - v5 sweep + dataset build take --membership: a (symbol, month) is
    swept/built only if the symbol was a member as-of that month.
  - FA graduation (fa/universe_loop.eligible_graduates) adds names at
    their ranking date, on top of the $-volume core.
```

## Validation gates (fail-closed, like everything else)

1. **No lookahead**: unit test — a spike in month M+1 must not move
   membership at M.
2. **Delisting canary**: the module REFUSES to freeze a backfill in which
   no ticker ever exits the universe across ≥ 12 months — a churn-free
   history is the signature of a survivorship-biased source, not a stable
   market. Canary names (delistings inside the window) are asserted to
   appear while alive and drop after death.
3. **Churn report**: per-month entries/exits printed into the artifact;
   hysteresis is tuned from this, documented, then frozen.
4. Coverage: a day file that fails to parse fails the month loudly
   (the 2026-08-19 silent-drop lesson).

## Build order

1. `nn_meta/universe_pit.py`: stage B on a supplied daily-aggregate frame
   (pure, tested first — synthetic daily rows).
2. `scripts/build_universe_daily.py`: stage A crawler (home box, resumable,
   reuses flatfiles.py's auth/download plumbing against day_aggs_v1).
3. Backfill 2024-08→now, freeze the monthlies, run the gates.
4. Wire `--membership` into the v5 sweep/build entry points (stage C).

## Open questions (decide during build, defaults stated)

- N=300 with 270/330 bands (defaults; churn report may retune once).
- ETFs in or out: IN (SPY/QQQ/IWM are tradable and already in every pool).
- Whether stage A also records per-underlying PUT/CALL split (cheap to
  add now, possibly useful to FA's unusual-options overlay — leaning yes).
