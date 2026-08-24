"""Magnitude-aware labels and EV-based slot sizing (v4 backlog item).

The meta-classifier predicts P(win), not win size, which produces the v3.1
top-decile inversion (see `nn_meta/diagnostics.py`).  This module supplies the
two codeable halves of the fix, both pure so they can be tested before v31
data lands:

* A magnitude signal without a second NN head: bucket realized returns into
  size-carrying classes and turn predicted bucket probabilities into an
  expected value.  (A regression head is the alternative; its target is just
  the raw return.)
* EV-based slot sizing: a portfolio that ranks *and sizes* by predicted EV,
  capped per name at the uniform fraction so it can only de-risk low-EV names,
  never over-concentrate.  It reduces to uniform sizing when EVs are equal, so
  it is a strict, fold-selectable alternative to the rank policy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Size-carrying return buckets: deep loss / loss / win / big win.  The midpoints
# convert predicted bucket probabilities into an expected return.
DEFAULT_BUCKET_EDGES = (-np.inf, -0.5, 0.0, 0.5, np.inf)
DEFAULT_BUCKET_MIDPOINTS = (-0.75, -0.25, 0.25, 1.0)


def magnitude_target(net_return) -> np.ndarray:
    """Regression target for a magnitude head: the signed realized return."""
    return np.asarray(net_return, dtype=float)


def return_bucket_labels(net_return, edges=DEFAULT_BUCKET_EDGES) -> np.ndarray:
    """Integer size-carrying class per trade (0..len(edges)-2)."""
    r = np.asarray(net_return, dtype=float)
    # np.digitize with the interior edges yields 0..n_buckets-1.
    return np.clip(np.digitize(r, np.asarray(edges[1:-1], dtype=float)),
                   0, len(edges) - 2)


def bucket_expected_value(bucket_probs, midpoints=DEFAULT_BUCKET_MIDPOINTS) -> np.ndarray:
    """Expected return from predicted bucket probabilities (rows sum to 1)."""
    probs = np.asarray(bucket_probs, dtype=float)
    mids = np.asarray(midpoints, dtype=float)
    if probs.shape[-1] != len(mids):
        raise ValueError("bucket_probs columns must match midpoints")
    return probs @ mids


def predicted_ev(p_win, magnitude) -> np.ndarray:
    """EV from a probability head and a magnitude head: P(win) * E[win size]."""
    return np.asarray(p_win, dtype=float) * np.asarray(magnitude, dtype=float)


def gross_scale(drawdown: float, dd_brake: float | None, floor: float) -> float:
    """Drawdown-aware gross multiplier in ``[floor, 1]``.

    ``1 - drawdown/dd_brake`` floored at ``floor``: untouched at the equity
    peak, fully braked (``floor``) once the drawdown reaches ``dd_brake``.
    ``dd_brake=None`` disables the brake (always 1.0). Depends only on the
    drawdown already realized, so it is causal by construction.
    """
    if dd_brake is None:
        return 1.0
    if not 0 < dd_brake <= 1 or not 0 < floor <= 1:
        raise ValueError("dd_brake and floor must lie in (0, 1]")
    return float(max(floor, min(1.0, 1.0 - float(drawdown) / float(dd_brake))))


def ev_weighted_portfolio(cands: pd.DataFrame, k: int, f: float, *,
                          ev_col: str = "pred_ev", dd_brake: float | None = None,
                          dd_floor: float = 1.0):
    """Slot portfolio that ranks and sizes by predicted EV.

    At each entry bar the top positive-EV candidates (one per symbol) fill the
    free slots, each sized proportional to its EV share of that set, scaled to
    the ``k*f`` gross budget and capped at ``f`` of equity per name.  P&L
    realizes at each exit.  Returns ``(total_return, max_drawdown, entered)``
    where ``entered`` is a list of ``(row_index, net_return, amount,
    size_fraction)`` — ``size_fraction`` is the fraction of equity-at-entry
    the trade received (``<= f``), which the mark-to-market ledger consumes.

    With ``dd_brake`` every new position is further multiplied by
    :func:`gross_scale` of the portfolio's own realized drawdown at that entry
    (floored at ``dd_floor``), so gross shrinks into a losing streak and
    recovers with equity. ``dd_brake=None`` is bit-identical to no brake.
    """
    open_pos: list = []          # (exit_ts, amount, net_return, symbol)
    open_syms: set = set()
    equity, peak, max_dd = 1.0, 1.0, 0.0
    entered: list = []
    budget = k * f

    def _close_due(now):
        nonlocal equity, peak, max_dd
        for p in sorted([p for p in open_pos if p[0] <= now], key=lambda x: x[0]):
            open_pos.remove(p)
            open_syms.discard(p[3])
            equity += p[1] * p[2]
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak)

    for ts, grp in cands.groupby("entry_ts", sort=True):
        _close_due(ts)
        if equity <= 0:
            # Busted book (possible when per-margin returns run below −1, e.g.
            # spx0 short variants gapping past their stop): there is nothing
            # left to size with, and frac × negative equity would flip losses
            # into gains. Stop entering; open positions still realize below.
            continue
        free = k - len(open_pos)
        if free <= 0:
            continue
        picks = []
        for r in grp.sort_values(ev_col, ascending=False).itertuples():
            if len(picks) >= free:
                break
            if r.symbol in open_syms or float(getattr(r, ev_col)) <= 0:
                continue
            picks.append(r)
            open_syms.add(r.symbol)
        if not picks:
            continue
        evs = np.array([float(getattr(r, ev_col)) for r in picks])
        weights = evs / evs.sum()
        # Brake on the drawdown realized BEFORE this entry (peak/equity are
        # only updated at closes, all of which precede ``ts``).
        scale = gross_scale((peak - equity) / peak, dd_brake, dd_floor)
        for r, w in zip(picks, weights):
            frac = min(w * budget, f) * scale             # per-name cap = uniform f
            amount = frac * equity
            open_pos.append((pd.Timestamp(r.exit_ts), amount, float(r.net_return),
                             r.symbol))
            entered.append((r.Index, float(r.net_return), amount, frac))
    _close_due(pd.Timestamp.max)
    return equity - 1.0, max_dd, entered


def ev_selected_rows(cands: pd.DataFrame, k: int, f: float, *,
                     ev_col: str = "pred_ev", dd_brake: float | None = None,
                     dd_floor: float = 1.0) -> pd.DataFrame:
    """Rows the EV portfolio actually enters, with a ``size_fraction`` column
    (fraction of equity at entry, ``<= f``). This is the EV analogue of
    ``v4_evaluate._selected_rows`` and feeds the mark-to-market ledger so EV
    sizing is scored on exactly the same accounting as filter/rank."""
    cands = cands.dropna(subset=["entry_ts", "exit_ts", "net_return", ev_col])
    if cands.empty:
        return cands.assign(size_fraction=pd.Series(dtype=float))
    _, _, entered = ev_weighted_portfolio(cands, k, f, ev_col=ev_col,
                                          dd_brake=dd_brake, dd_floor=dd_floor)
    if not entered:
        return cands.iloc[0:0].assign(size_fraction=pd.Series(dtype=float))
    out = cands.loc[[e[0] for e in entered]].copy()
    out["size_fraction"] = [e[3] for e in entered]
    return out


def ev_candidate_rows(rows: pd.DataFrame, pred_ev, threshold: float) -> pd.DataFrame:
    """Thresholded, DTE-deduped (best EV per proposal) EV candidate pool."""
    cands = rows.assign(pred_ev=np.asarray(pred_ev, dtype=float))
    cands = cands[cands["pred_ev"] >= threshold]
    return cands.sort_values("pred_ev", ascending=False) \
        .drop_duplicates(["symbol", "strategy", "trade_idx"])


def portfolio_metrics_ev(cands: pd.DataFrame, k: int, f: float, *,
                         ev_col: str = "pred_ev", n_proposals: int | None = None,
                         dd_brake: float | None = None, dd_floor: float = 1.0) -> dict:
    """EV-sized portfolio metrics, matching select_meta.portfolio_metrics keys."""
    cands = cands.dropna(subset=["entry_ts", "exit_ts", "net_return", ev_col])
    empty = {"n": 0, "n_kept": 0, "n_proposals": n_proposals or len(cands),
             "total_return": None, "max_drawdown": None, "win_rate": None,
             "mean_return": None, "per_trade_sharpe": None, "total_ex_top3": None}
    if cands.empty:
        return empty
    kw = dict(ev_col=ev_col, dd_brake=dd_brake, dd_floor=dd_floor)
    total, max_dd, entered = ev_weighted_portfolio(cands, k, f, **kw)
    if not entered:
        return empty
    rets = np.array([e[1] for e in entered])
    if len(entered) > 3:
        top_idx = [e[0] for e in sorted(entered, key=lambda x: -x[1])[:3]]
        ex_total, _, _ = ev_weighted_portfolio(cands.drop(index=top_idx), k, f, **kw)
    else:
        ex_total = 0.0
    return {
        "n": len(entered), "n_kept": len(entered),
        "n_proposals": n_proposals if n_proposals is not None else len(cands),
        "total_return": total, "max_drawdown": max_dd,
        "win_rate": float((rets > 0).mean()), "mean_return": float(rets.mean()),
        "per_trade_sharpe": float(rets.mean() / rets.std(ddof=1))
        if len(rets) > 1 and rets.std(ddof=1) > 0 else None,
        "total_ex_top3": ex_total,
    }


def evaluate_ev(rows: pd.DataFrame, pred_ev: np.ndarray, threshold: float = 0.0, *,
                k: int, f: float, dd_brake: float | None = None,
                dd_floor: float = 1.0) -> dict:
    """Fold-selectable EV policy: keep pred_ev >= threshold, size by EV.

    Mirrors the rank evaluator's signature so it can join the policy grid once
    a magnitude/EV prediction column exists (second head or bucket classifier).
    """
    return portfolio_metrics_ev(ev_candidate_rows(rows, pred_ev, threshold), k, f,
                                n_proposals=len(rows), dd_brake=dd_brake,
                                dd_floor=dd_floor)
