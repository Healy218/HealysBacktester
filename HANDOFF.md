# Handoff — October 7, 2026 — V8 selected after the realistic-execution review

## Focus and result

- **ETFE closed:** v5 failed (its validation pass came from intrinsic-value
  expiry credit). Signal-edge and tuned-variant walk-forward diagnostics found no
  edge on SPY/QQQ intraday. The 2026 ETFE test is unspent.
- **Server experts:** read-only copies of the server alert database and ledgers
  showed neither paper ledger ever recorded exits. V118 (v4) sent 1 alert from
  Sep 8. V5's 415 scorable alerts averaged −6.4% from Alpaca option bars.
- **V6:** all 13 paper round trips lost (−$14,839); about 85% of the loss was
  spread. Realistic-fill re-evaluation (`nn_meta/validation/v6-fillcost-20261007-r0/`,
  reproduction matched exactly) found no profitable configuration; the backtest
  edge was midpoint pricing of illiquid contracts.
- **Overnight V6 incubator:** never deployed a model (no accepted candidate). Its
  gate scores prediction error, not tradable P&L.
- **User decision:** start [V8](docs/specs/V8_DESIGN_20261007.md). Edge first on
  the underlying, realistic fills, and a mostly-tech plus sector-ETF universe.
  FA is a forward-only overlay plus backfilled candidate features. Stages 0–1
  authorized. All evidence is in [EXPERIMENTS](docs/EXPERIMENTS.md) (October 7).

## Status at session end

No research jobs running. V6 paper services remain paused by user choice: the
scanner fails each run on stale daily data (expected while
`healys-v6-data.timer` is disabled). One V6 paper position (TMUS) is open. The
server is reachable by the user's own `ssh mrhea@62.238.20.66`; the agent is
blocked from production reads unless a permission rule is added.

## Next actions

1. Work [TODO](TODO.md) stage 0: freeze the pool without hindsight, gather data,
   derive and freeze the liquidity cutoff and fill model.
2. Then stage 1 pre-registration and the tuned-variant walk-forward.
3. Commit hygiene: stage only your own hunks (`git apply --cached`); other dirty
   V6/V7 work in the tree is not yours.

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-v8.md).
