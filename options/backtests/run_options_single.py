# options/backtests/run_options_single.py
"""
Single-leg directional options backtest runner.

Model
-----
1. Generate a directional signal on the UNDERLYING (a simple MA crossover here).
2. At the first entry, select ONE option contract from the chain (target DTE +
   delta / moneyness, call for bullish).
3. Trade that contract's OWN historical price series — which already embeds
   theta / gamma / IV as realized — and force a settlement exit on its last bar
   (expiration).
4. Compute P&L by reusing the existing equity engine, ``portfolio.simulator``.

Because we trade the contract's realized price, NO options-pricing model is
needed. The only requirement is real historical contract bars (see the data
caveats in options/README.md — Alpaca's free feed does not provide them).

Returns the same dict contract as ``backtests/run_*.py``
(``{"top5", "error", "portfolio", "price_data"}``) so it can slot into the
dashboard once a history-capable data source is wired.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from utils.logging_utils import setup_logging
from utils import freq_utils, runner_utils, param_utils
from data import data_cleaner
from portfolio import simulator
from options.data.provider import OptionsDataProvider
from options.selection import contract_selector

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "OPT-SINGLE"


def _default_provider() -> OptionsDataProvider:
    """Pick the best available historical options data source.

    Prefers Massive (real multi-year history) when ``MASSIVE_API_KEY`` is set,
    otherwise falls back to Alpaca (live chain only — no usable history).
    """
    import os
    if os.environ.get("MASSIVE_API_KEY"):
        from options.data.massive_provider import MassiveProvider
        return MassiveProvider()
    from options.data.alpaca_provider import AlpacaOptionsProvider
    return AlpacaOptionsProvider()


def _underlying_signal(close: pd.Series, fast: int, slow: int):
    """Long MA-crossover signal on the underlying → (entries, exits) bool Series."""
    fast_ma = close.rolling(fast, min_periods=1).mean()
    slow_ma = close.rolling(slow, min_periods=1).mean()
    bullish = fast_ma > slow_ma
    prev = bullish.shift(1, fill_value=False)
    entries = (bullish & ~prev).fillna(False).astype(bool)   # cross up
    exits = (~bullish & prev).fillna(False).astype(bool)     # cross down
    return entries, exits


def _options_sim_kwargs(backtest_config: dict, strategy_config: dict) -> dict:
    """Build simulation kwargs suited to a single long option position.

    Deliberately does NOT inherit the equity ``BACKTEST_CONFIG``'s trend filter,
    ATR sizing, 5% stop, or 90% allocation — those are wrong for an option
    premium series (premia routinely swing >5%/day, and a ~30-bar contract has no
    50-bar trend). Capital/fees come from the shared config; position sizing and
    any optional premium stop/target come from the options strategy config.
    """
    return dict(
        initial_capital=backtest_config.get("INITIAL_CAPITAL", 100_000.0),
        fees=backtest_config.get("FEES_PERCENT", 0.001),
        slippage=backtest_config.get("SLIPPAGE_PERCENT", 0.0005),
        size=float(strategy_config.get("ALLOCATION", 0.10)),
        size_type="percent",
        sl_stop=strategy_config.get("STOP_LOSS_PERCENT"),   # None = no premium stop
        tp_stop=strategy_config.get("TAKE_PROFIT_PERCENT"),  # None = no premium target
    )


def run(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    backtest_config: dict,
    strategy_config: dict,
    progress_callback=None,
    provider: Optional[OptionsDataProvider] = None,
) -> dict:
    """Run a single-leg long-option backtest. See the module docstring for the model.

    ``strategy_config`` keys (all optional, with defaults):
      RIGHT         "C" | "P" | "auto"  — auto → call (bullish crossover)
      TARGET_DTE    int   days to expiration to target      (default 30)
      TARGET_DELTA  float absolute delta to target          (default 0.50)
      MONEYNESS     float fallback strike offset vs spot     (default 0.0 = ATM)
      MA_FAST       int   fast MA window for the signal      (default 10)
      MA_SLOW       int   slow MA window for the signal      (default 30)

    A ``provider`` can be injected (e.g. a synthetic provider in tests); when
    omitted it defaults to :class:`AlpacaOptionsProvider`.
    """
    try:
        if provider is None:
            provider = _default_provider()

        right_cfg = str(strategy_config.get("RIGHT", "auto")).lower()
        target_dte = int(strategy_config.get("TARGET_DTE", 30))
        target_delta = float(strategy_config.get("TARGET_DELTA", 0.50))
        moneyness = float(strategy_config.get("MONEYNESS", 0.0))
        fast = int(strategy_config.get("MA_FAST", 10))
        slow = int(strategy_config.get("MA_SLOW", 30))
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)

        if progress_callback:
            progress_callback(0, 4)

        # 1) Underlying data + signal
        raw = provider.get_underlying_bars(symbol, start_date, end_date, interval)
        if raw is None or raw.empty:
            return runner_utils.err(f"No underlying data for '{symbol}'.", _TAG, logger)
        underlying = data_cleaner.clean_ohlcv_data(raw)
        if underlying is None or underlying.empty:
            return runner_utils.err("Underlying data cleaning failed.", _TAG, logger)

        entries_u, exits_u = _underlying_signal(underlying["Close"], fast, slow)
        if not bool(entries_u.any()):
            return runner_utils.err(
                "No entry signals on the underlying for this window.", _TAG, logger)

        if progress_callback:
            progress_callback(1, 4)

        # 2) Select a contract as of the first entry
        first_entry = entries_u[entries_u].index[0]
        as_of = first_entry.date() if hasattr(first_entry, "date") else date.today()
        the_right = "P" if right_cfg in ("p", "put") else "C"  # auto / call → C
        spot = float(underlying["Close"].loc[:first_entry].iloc[-1])

        # Bound BOTH the expiration window (around the target DTE) and the strike
        # band so the reference query returns complete strike coverage for the
        # relevant expiries — an unbounded query hits the 1000-row cap and biases
        # selection toward a truncated (deep-ITM) subset.
        exp_lo = as_of + timedelta(days=max(1, target_dte - 10))
        exp_hi = as_of + timedelta(days=target_dte + 20)
        chain = provider.get_chain(
            symbol, right=the_right,
            expiration_gte=exp_lo, expiration_lte=exp_hi,
            strike_gte=spot * 0.85, strike_lte=spot * 1.15,
            as_of=as_of,
        )
        if not chain:
            return runner_utils.err(f"No option chain returned for {symbol}.", _TAG, logger)

        contract = contract_selector.select_contract(
            chain, right=the_right, spot=spot, target_dte=target_dte,
            target_delta=target_delta, moneyness=moneyness, as_of=as_of,
        )
        if contract is None:
            return runner_utils.err("Could not select a contract from the chain.", _TAG, logger)
        logger.info(
            f"[{_TAG}] {symbol} @ {as_of}: selected {contract.symbol} "
            f"(strike {contract.strike:g}, exp {contract.expiration}, delta={contract.delta})"
        )

        if progress_callback:
            progress_callback(2, 4)

        # 3) Contract price series
        opt = provider.get_contract_bars(contract.symbol, start_date, end_date, interval)
        if opt is None or opt.empty or "Close" not in opt.columns:
            return runner_utils.err(
                f"No historical price bars for {contract.symbol}. On Alpaca's free "
                f"feed this is expected — enable OPRA data or switch to Polygon/"
                f"Massive for historical backtests (see options/README.md).",
                _TAG, logger,
            )

        # Enter once at the first contract bar on/after the signal, then hold until
        # an underlying exit signal fires or the final bar (settlement at expiry).
        label = f"{contract.strike:g}{contract.right} {contract.expiration:%Y-%m-%d}"
        entries = pd.Series(False, index=opt.index)
        pos = int(opt.index.searchsorted(pd.Timestamp(first_entry)))
        if pos >= len(opt.index):
            return runner_utils.err(
                f"{contract.symbol} has no bars on/after the entry signal ({as_of}).",
                _TAG, logger)
        entries.iloc[pos] = True
        exits = exits_u.reindex(opt.index, fill_value=False).astype(bool)
        if len(exits):
            exits.iloc[-1] = True
        # Shape signals as single-column DataFrames so the resulting portfolio is
        # column-indexable exactly like the multi-parameter runners — this keeps
        # the shared row builder and the dashboard graph path working.
        entries = entries.astype(bool).to_frame(name=label)
        exits = exits.to_frame(name=label)

        if progress_callback:
            progress_callback(3, 4)

        # 4) Simulate on the option price series (reuse the equity engine)
        sim_kwargs = _options_sim_kwargs(backtest_config, strategy_config)
        portfolio = simulator.run_backtest(
            price_df=opt,
            entries_series=entries,
            exits_series=exits,
            frequency=freq,
            **sim_kwargs,
        )
        if portfolio is None:
            return runner_utils.err("Option simulation returned no portfolio.", _TAG, logger)

        # Reuse the shared single-column row builder (no min-trade filter, so a
        # one-shot option trade still produces a row) then relabel with contract info.
        row = param_utils._make_row_from_index(portfolio, 0, "Single-leg")
        row["param_label"] = (
            f"{contract.right} {contract.strike:g} exp {contract.expiration:%Y-%m-%d}"
            + (f" Δ{contract.delta:.2f}" if contract.delta is not None else "")
        )

        if progress_callback:
            progress_callback(4, 4)
        return {"top5": [row], "error": None, "portfolio": portfolio, "price_data": opt}

    except Exception as e:
        logger.exception(f"[{_TAG}] Unexpected error: {e}")
        return runner_utils.err(str(e), _TAG, logger)
