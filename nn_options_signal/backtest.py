# nn_options_signal/backtest.py
"""Standalone daily backtest simulator — long, short, and long-short modes.

Causal loop over decision days. While flat:
  long      : buy the highest-scored contract if score > threshold
  short     : sell the LOWEST-scored contract if score < threshold
              (naked single-leg short, margin-based sizing)
  longshort : buy the top AND short the bottom if their score spread exceeds
              the pair threshold (two single-leg tickets, same horizon)

Entries fill at the NEXT day's open, exits at the close H trading days later
(earlier if forced by DTE). One decision at a time; explicit costs. Rows whose
forward window is unknowable (contract never traded again -> no fill) are
skipped, mirroring an unfilled order.

Short margin uses the standard naked-equity-option formula
premium + max(20%*spot - OTM, 10%*basis), computed off the decision-day spot.
Assignment risk before expiry is not modeled (disclosed in the report).
"""
import numpy as np
import pandas as pd

from nn_options_signal import config


def naked_margin_per_contract(premium: float, spot: float, strike: float,
                              is_call: bool) -> float:
    otm = max(strike - spot, 0.0) if is_call else max(spot - strike, 0.0)
    basis = spot if is_call else strike
    core = max(config.MARGIN_BASE_PCT * spot - otm, config.MARGIN_MIN_PCT * basis)
    return (premium + core) * config.CONTRACT_MULTIPLIER


def _long_leg(row, equity, c, comm, exit_close_col):
    entry, exit_px = float(row["entry_open"]), float(row[exit_close_col])
    mult = config.CONTRACT_MULTIPLIER
    n = int(equity * config.POSITION_FRACTION // (entry * (1 + c) * mult + comm))
    if n < 1:
        return None
    pnl = n * mult * (exit_px * (1 - c) - entry * (1 + c)) - 2 * comm * n
    basis = n * mult * entry * (1 + c) + 2 * comm * n
    return {"side": "long", "contracts": n, "entry": entry, "exit": exit_px,
            "pnl": pnl, "ret_net": pnl / basis}


def _short_leg(row, equity, c, comm, exit_close_col):
    entry, exit_px = float(row["entry_open"]), float(row[exit_close_col])
    mult = config.CONTRACT_MULTIPLIER
    margin = naked_margin_per_contract(entry, float(row["spot"]),
                                       float(row["strike"]), row["type"] == "call")
    n = int(equity * config.SHORT_POSITION_FRACTION // (margin + comm))
    if n < 1:
        return None
    pnl = n * mult * (entry * (1 - c) - exit_px * (1 + c)) - 2 * comm * n
    basis = n * margin + 2 * comm * n
    return {"side": "short", "contracts": n, "entry": entry, "exit": exit_px,
            "pnl": pnl, "ret_net": pnl / basis}


def run_backtest(panel: pd.DataFrame, pred_col: str, horizon: int,
                 mode: str = "long", threshold: float | None = None,
                 cost_mult: float = 1.0) -> dict:
    exit_close_col = f"exit_close_h{horizon}"
    exit_date_col = f"exit_date_h{horizon}"
    c = config.COST_PER_SIDE_PCT * cost_mult
    comm = config.COMMISSION_PER_CONTRACT * cost_mult
    if threshold is None:
        threshold = {"long": config.PRED_THRESHOLD,
                     "short": config.SHORT_PRED_THRESHOLD,
                     "longshort": config.PRED_SPREAD_THRESHOLD}[mode]

    df = panel.dropna(subset=[pred_col, "entry_open", exit_close_col, exit_date_col])
    df = df.sort_values(["date", pred_col], ascending=[True, False])

    equity = config.INITIAL_CAPITAL
    busy_until = pd.Timestamp.min
    trades, curve = [], []
    n_decisions = 0

    def record(leg: dict, row, date) -> None:
        trades.append({**leg, "decision_date": date, "exit_date": row[exit_date_col],
                       "ticker": row["ticker"], "underlying": row.get("underlying", "SPY"),
                       "type": row["type"], "strike": row["strike"], "dte": row["dte"],
                       "pred": float(row[pred_col])})

    for date, day in df.groupby("date", sort=True):
        if date <= busy_until:
            continue
        top, bottom = day.iloc[0], day.iloc[-1]
        legs = []

        if mode == "long" and top[pred_col] > threshold:
            leg = _long_leg(top, equity, c, comm, exit_close_col)
            if leg:
                legs.append((leg, top))
        elif mode == "short" and bottom[pred_col] < threshold:
            leg = _short_leg(bottom, equity, c, comm, exit_close_col)
            if leg:
                legs.append((leg, bottom))
        elif mode == "longshort" and top["ticker"] != bottom["ticker"] \
                and (top[pred_col] - bottom[pred_col]) > threshold:
            l1 = _long_leg(top, equity, c, comm, exit_close_col)
            l2 = _short_leg(bottom, equity, c, comm, exit_close_col)
            if l1:
                legs.append((l1, top))
            if l2:
                legs.append((l2, bottom))

        if not legs:
            curve.append((date, equity))
            continue

        n_decisions += 1
        exit_dates = []
        for leg, row in legs:
            equity += leg["pnl"]
            exit_dates.append(pd.Timestamp(row[exit_date_col]))
            record(leg, row, date)
        busy_until = max(exit_dates)
        curve.append((date, equity))

    trades_df = pd.DataFrame(trades)
    curve_df = pd.DataFrame(curve, columns=["date", "equity"])

    total_return = equity / config.INITIAL_CAPITAL - 1
    if not curve_df.empty:
        peak = curve_df["equity"].cummax()
        max_dd = float(((peak - curve_df["equity"]) / peak).max())
    else:
        max_dd = 0.0
    if not trades_df.empty:
        wins = trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()
        losses = -trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum()
        profit_factor = float(wins / losses) if losses > 0 else float("inf")
        win_rate = float((trades_df["pnl"] > 0).mean())
        avg_win = float(trades_df.loc[trades_df["pnl"] > 0, "ret_net"].mean()) if wins else 0.0
        avg_loss = float(trades_df.loc[trades_df["pnl"] < 0, "ret_net"].mean()) if losses else 0.0
    else:
        profit_factor, win_rate, avg_win, avg_loss = 0.0, 0.0, 0.0, 0.0

    return {
        "total_return": float(total_return), "max_drawdown": max_dd,
        "n_trades": n_decisions, "n_legs": len(trades_df),
        "win_rate": win_rate, "profit_factor": profit_factor,
        "avg_win": avg_win, "avg_loss": avg_loss, "final_equity": float(equity),
        "trades": trades_df, "equity_curve": curve_df,
    }


def mechanical_atm_score(panel: pd.DataFrame, right: str = "call") -> pd.Series:
    """Benchmark scorer: the `right`-type contract nearest ATM with DTE closest
    to 30 gets the highest score (in (1, 2]); everything else -inf."""
    score = pd.Series(-np.inf, index=panel.index)
    m = panel["type"] == right
    score[m] = 1.0 / (1.0 + panel.loc[m, "moneyness"].abs() * 100
                      + (panel.loc[m, "dte"] - 30).abs() / 30) + 1.0
    return score
