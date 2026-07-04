# Options backtesting subsystem

Self-contained package for backtesting **options** strategies, mirroring the
project's layered hierarchy so it slots into the existing conventions.

```
options/
├── data/         vendor-agnostic interface (provider.py) + adapters:
│                   alpaca_provider.py  (live chain/greeks; no history)
│                   massive_provider.py (deep historical bars — backtest source)
├── selection/    contract selection by DTE + delta / moneyness
├── backtests/    strategy runners  (run_options_single.py — single-leg directional)
└── analysis/     options-specific plotting (payoff, contract price, greeks later)
```

## How it works (single-leg)

vectorBT has **no native options support** (no pricing model, greeks,
expiration, or multi-leg margin) — its engine models a linear-payoff asset.
We reuse it anyway with one insight:

> Trade each option **contract's own historical price series** as if it were the
> asset. The market price already embeds theta / gamma / IV *as realized*, so
> feeding it into `portfolio/simulator.run_backtest` gives correct P&L with **no
> pricing model**.

Flow (`backtests/run_options_single.py`):

1. Signal on the **underlying** (a simple MA crossover to start).
2. At the first entry, **select one contract** (target DTE + delta/moneyness).
3. Pull that **contract's bars**, align the signal onto its timeline, and force a
   settlement exit on its last bar (expiration).
4. Simulate on the contract price via the existing equity engine.

The runner returns the same dict shape as `backtests/run_*.py`
(`{"top5", "error", "portfolio", "price_data"}`), so it can be registered in the
dashboard's `STRATEGIES` map later without engine changes.

## Data availability ⚠️ (verified 2026-07-02)

A live probe of the current **Alpaca** account found:

| Capability | Result |
|---|---|
| Option chain (strikes/expiries) | ✅ 263 SPY calls |
| Greeks + implied vol in snapshot | ✅ present |
| Real-time quote | ✅ |
| **Historical bars** | ❌ **0–4 bars** even for 600-OI contracts over 6 months |

The account is on Alpaca's **free "indicative" feed**: great for live chain +
greeks (so **selection works today**), but it carries **no usable historical
price history**. Real backtests therefore need one of:

- **Alpaca OPRA** options data subscription (history back to ~Feb 2024), or
- **Polygon / Massive** — deeper multi-year options aggregates (planned vendor).

Because of this, `AlpacaOptionsProvider.get_contract_bars` returns an **empty
frame** (not an error) when history is missing, and the runner surfaces a clear
"enable OPRA / use Massive" message.

### Massive (Polygon) — the backtest data source ✅

`MassiveProvider` uses the Polygon-compatible REST API at
`https://api.massive.com` (auth: `apiKey` from `MASSIVE_API_KEY`). Verified on
the **Options Starter** plan:

| Capability | Result |
|---|---|
| Contract listing (`/v3/reference/options/contracts`) | ✅ incl. `as_of` point-in-time + expired contracts |
| **Historical option bars** (`/v2/aggs/.../O:{OCC}/...`) | ✅ full daily history for expired contracts |
| Underlying bars (`/v2/aggs/.../{ticker}/...`) | ✅ (basic stocks tier) |
| Greeks | ⚠️ live snapshot only — historical selection uses **moneyness** |

End-to-end proof (real data): a near-ATM SPY call selected on the 2025-06-16 MA
crossover signal (603C exp 2025-07-18, 33 daily bars) went 10.83 → 24.52 (+126%)
into expiry → **+63%** at 50% sizing. Runs through the unchanged equity engine.

## Swapping data vendors

Everything above the data layer depends only on the abstract
`OptionsDataProvider`. `MassiveProvider` and `AlpacaOptionsProvider` are drop-in;
pass one to the runner: `run(..., provider=MassiveProvider())`. A new vendor is
just a fourth adapter implementing `get_underlying_bars`, `get_chain`
(honoring `as_of` for point-in-time history), and `get_contract_bars`.

## Status & roadmap

- [x] Vendor-agnostic data interface + Alpaca adapter (chain/selection live now)
- [x] Contract selection (DTE + delta/moneyness)
- [x] Single-leg directional runner (reuses the equity engine)
- [x] Payoff + contract-price plots
- [x] **Massive provider — real historical backtest working end-to-end**
- [x] Contract **rolling** (signal overlay rolls into a fresh contract at expiry)
- [x] Dashboard integration — "Asset Type: Options" runs ANY strategy's signals
      as option orders via `backtests/signal_overlay.py` (calls on longs, puts
      on shorts, per-trade selection as-of the entry date, stitched-series
      simulation through the unchanged equity engine)
- [ ] Multi-leg spreads (verticals, condors) + net margin
- [ ] Greeks-managed exits (50% profit / 21 DTE / delta targets)
