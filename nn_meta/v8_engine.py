# nn_meta/v8_engine.py — V8.1 long-only slot portfolio simulator.
"""Panel construction and a numba simulator for one variant across all
symbols (docs/specs/V8_STAGE1_PREREG_20261008.json).

Per bar t (grid of 1h bars or trading days):
  1. pending exits execute at the execution price P[s, t] (sell cost)
  2. pending entries execute into free slots (10), highest adv20 first;
     each takes min(equity / 10, cash); buy cost reduces the position
  3. held positions mark to M[s, t] (adjusted close of the bar)
  4. forced exits at the close (last bar before a missing/delisted/event day)
  5. bar t's signals queue: entry (if flat) or exit (if held; cancels entry)
A queued entry waits for the next bar where entry is allowed (admitted day;
1h: not the 09:30 bar; 1d: the 10:30 bar exists) unless an exit signal
cancels it. Execution prices: 1h = bar open; 1d = the day's 10:30 bar open.
Costs are bps of notional from nn_meta.v8_fills (half-spread x name factor +
slippage, plus sell fees), scaled by the cost multiplier.
"""
from __future__ import annotations

import json
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

from nn_meta import v8_fills as vf

REPO = Path(__file__).resolve().parent.parent
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
ADMISSION = REPO / "nn_meta" / "validation" / "v8-liquidity-20261008-r0" / "admission.parquet"
SLOTS = 10


def _cost_bps(raw_price, minute, year, tickers_rep, sell: bool) -> np.ndarray:
    ok = np.isfinite(raw_price) & (raw_price > 0)
    out = np.full(raw_price.shape, np.nan)
    if ok.any():
        hs = vf.stock_half_spread_bps(tickers_rep[ok], raw_price[ok], minute[ok], year[ok])
        c = hs + vf.SLIPPAGE_BPS
        if sell:
            c = c + vf.SELL_REG_BPS + vf.TAF_PER_SHARE / raw_price[ok] * 1e4
        out[ok] = c
    return out


def build_panel(tf: str, tickers: list[str], grid: list[str]) -> dict:
    """Dense (S, T) arrays aligned to the signal grid."""
    S, T = len(tickers), len(grid)
    tix = {t: i for i, t in enumerate(tickers)}
    gix = {k: i for i, k in enumerate(grid)}
    days = sorted({k.split("|")[0] for k in grid})
    dix = {d: i for i, d in enumerate(days)}
    end = days[-1]
    h = pd.read_parquet(BARS / "bars_1h.parquet",
                        columns=["ticker", "date", "hour_bin", "open", "close", "adj_open", "adj_close"])
    h = h[(h["date"] <= end) & h["ticker"].isin(tix)]
    P = np.full((S, T), np.nan); M = np.full((S, T), np.nan)
    raw_exec = np.full((S, T), np.nan); raw_close = np.full((S, T), np.nan)
    exec_minute = np.zeros((S, T)); entry_slot = np.zeros((S, T), bool)
    if tf == "1h":
        si = h["ticker"].map(tix).to_numpy()
        ti = (h["date"] + "|" + h["hour_bin"].astype(int).astype(str)).map(gix).to_numpy()
        P[si, ti] = h["adj_open"]; M[si, ti] = h["adj_close"]
        raw_exec[si, ti] = h["open"]; raw_close[si, ti] = h["close"]
        exec_minute[si, ti] = 570 + 60 * h["hour_bin"].to_numpy()
        entry_slot[si, ti] = h["hour_bin"].to_numpy() >= 1
        bar_day = np.array([dix[k.split("|")[0]] for k in grid])
    else:
        d = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "close", "adj_close"])
        d = d[(d["date"] <= end) & d["ticker"].isin(tix)]
        si = d["ticker"].map(tix).to_numpy(); ti = d["date"].map(gix).to_numpy()
        M[si, ti] = d["adj_close"]; raw_close[si, ti] = d["close"]
        b1 = h[h["hour_bin"] == 1]
        si = b1["ticker"].map(tix).to_numpy(); ti = b1["date"].map(gix).to_numpy()
        P[si, ti] = b1["adj_open"]; raw_exec[si, ti] = b1["open"]
        exec_minute[:] = 630
        entry_slot[si, ti] = True
        bar_day = np.arange(T)
    year = np.broadcast_to(np.array([int(days[bd][:4]) for bd in bar_day]), (S, T))
    trep = np.broadcast_to(np.array(tickers, object)[:, None], (S, T))
    cost_buy = _cost_bps(raw_exec, exec_minute, year, trep, sell=False)
    cost_sell = _cost_bps(raw_exec, exec_minute, year, trep, sell=True)
    cost_close = _cost_bps(raw_close, np.full((S, T), 955.0), year, trep, sell=True)
    # admission, adv20 priority and day status
    adm = pd.read_parquet(ADMISSION, columns=["ticker", "date", "status", "admitted", "adv20"])
    adm = adm[(adm["date"] <= end) & adm["ticker"].isin(tix) & adm["date"].isin(dix)]
    A = np.zeros((S, len(days)), bool); V = np.full((S, len(days)), -1.0)
    bad_day = np.zeros((S, len(days)), bool)
    si = adm["ticker"].map(tix).to_numpy(); di = adm["date"].map(dix).to_numpy()
    A[si, di] = adm["admitted"].to_numpy()
    V[si, di] = adm["adv20"].fillna(-1).to_numpy()
    bad_day[si, di] = adm["status"].isin(["missing", "delisted", "prelisting"]).to_numpy()
    events = json.loads((BARS / "events.json").read_text())["events"]
    for e in events:
        if e["ticker"] in tix and e["date"] in dix:
            bad_day[tix[e["ticker"]], dix[e["date"]]] = True
    has_exec = np.isfinite(P) & np.isfinite(cost_buy)
    has_mark = np.isfinite(M)
    entry_ok = has_exec & entry_slot & A[:, bar_day]
    prio = V[:, bar_day]
    # forced exit at the close of a symbol's last bar of day d when day d+1 is bad
    last_of_day = np.zeros((S, T), bool)
    for s in range(S):
        idx = np.nonzero(has_mark[s])[0]
        if idx.size:
            dd = bar_day[idx]
            last = np.r_[dd[1:] != dd[:-1], True]
            last_of_day[s, idx[last]] = True
    next_bad = np.zeros((S, len(days)), bool)
    next_bad[:, :-1] = bad_day[:, 1:]
    force = last_of_day & next_bad[:, bar_day] & np.isfinite(cost_close)
    day_last_bar = np.array([np.nonzero(bar_day == i)[0].max() for i in range(len(days))])
    return {"tf": tf, "tickers": tickers, "grid": grid, "days": days,
            "P": np.nan_to_num(P), "M": np.nan_to_num(M),
            "has_exec": has_exec, "has_mark": has_mark, "entry_ok": entry_ok,
            "cost_buy": np.nan_to_num(cost_buy), "cost_sell": np.nan_to_num(cost_sell),
            "cost_close": np.nan_to_num(cost_close), "force": force,
            "prio": np.nan_to_num(prio, nan=-1.0), "bar_day": bar_day,
            "day_last_bar": day_last_bar}


@nb.njit(nogil=True, cache=True)
def _bit(bits, s, v, t):
    return (bits[s, v, t >> 3] >> (7 - (t & 7))) & 1


@nb.njit(nogil=True, cache=True)
def simulate(Ebits, Xbits, v, P, M, has_exec, has_mark, entry_ok, cost_buy,
             cost_sell, cost_close, force, prio, day_last_bar, n_days, mult, slots):
    S, T = P.shape
    cash = 1.0
    held = np.zeros(S, np.bool_)
    val = np.zeros(S)
    lastm = np.zeros(S)
    basis = np.zeros(S)
    pend_e = np.zeros(S, np.bool_)
    pend_x = np.zeros(S, np.bool_)
    n_open = 0
    eq_bar = np.zeros(T)
    trades_bar = np.zeros(T, np.int32)
    wins_bar = np.zeros(T, np.int32)
    cand = np.empty(S, np.int64)
    for t in range(T):
        # 1. exits
        for s in range(S):
            if held[s] and pend_x[s] and has_exec[s, t]:
                val[s] *= P[s, t] / lastm[s]
                proceeds = val[s] * (1.0 - mult * cost_sell[s, t] / 1e4)
                cash += proceeds
                trades_bar[t] += 1
                if proceeds > basis[s]:
                    wins_bar[t] += 1
                held[s] = False; pend_x[s] = False; val[s] = 0.0; n_open -= 1
        # 2. entries
        free = slots - n_open
        if free > 0:
            nc = 0
            for s in range(S):
                if pend_e[s] and (not held[s]) and entry_ok[s, t]:
                    cand[nc] = s; nc += 1
            if nc > 0:
                equity = cash
                for s in range(S):
                    if held[s]:
                        equity += val[s]
                for k in range(min(free, nc)):
                    best = -1; bp = -np.inf
                    for j in range(nc):
                        s = cand[j]
                        if s >= 0 and prio[s, t] > bp:
                            bp = prio[s, t]; best = j
                    s = cand[best]; cand[best] = -1
                    alloc = min(equity / slots, cash)
                    if alloc <= 1e-12:
                        break
                    cash -= alloc
                    basis[s] = alloc
                    val[s] = alloc / (1.0 + mult * cost_buy[s, t] / 1e4)
                    lastm[s] = P[s, t]
                    held[s] = True; pend_e[s] = False; n_open += 1
        # 3. mark
        for s in range(S):
            if held[s] and has_mark[s, t]:
                val[s] *= M[s, t] / lastm[s]
                lastm[s] = M[s, t]
        # 4. forced exits at the close
        for s in range(S):
            if held[s] and force[s, t]:
                proceeds = val[s] * (1.0 - mult * cost_close[s, t] / 1e4)
                cash += proceeds
                trades_bar[t] += 1
                if proceeds > basis[s]:
                    wins_bar[t] += 1
                held[s] = False; pend_x[s] = False; val[s] = 0.0; n_open -= 1
        # 5. signals of bar t
        for s in range(S):
            if has_mark[s, t]:
                if _bit(Xbits, s, v, t):
                    pend_e[s] = False
                    if held[s]:
                        pend_x[s] = True
                elif _bit(Ebits, s, v, t) and not held[s]:
                    pend_e[s] = True
        e = cash
        for s in range(S):
            if held[s]:
                e += val[s]
        eq_bar[t] = e
    eq_day = np.zeros(n_days)
    tr_day = np.zeros(n_days, np.int32)
    win_day = np.zeros(n_days, np.int32)
    prev = -1
    for d in range(n_days):
        last = day_last_bar[d]
        eq_day[d] = eq_bar[last]
        for t in range(prev + 1, last + 1):
            tr_day[d] += trades_bar[t]
            win_day[d] += wins_bar[t]
        prev = last
    return eq_day, tr_day, win_day


def load_bits(sig_dir: Path, tickers: list[str]) -> tuple[np.ndarray, np.ndarray]:
    first = np.load(sig_dir / f"{tickers[0]}.npz")
    V, nb_ = first["E"].shape
    E = np.zeros((len(tickers), V, nb_), np.uint8)
    X = np.zeros_like(E)
    for i, t in enumerate(tickers):
        z = np.load(sig_dir / f"{t}.npz")
        E[i], X[i] = z["E"], z["X"]
    return E, X


def run_variant(panel: dict, E, X, v: int, mult: float):
    p = panel
    return simulate(E, X, v, p["P"], p["M"], p["has_exec"], p["has_mark"],
                    p["entry_ok"], p["cost_buy"], p["cost_sell"], p["cost_close"],
                    p["force"], p["prio"], p["day_last_bar"], len(p["days"]),
                    float(mult), SLOTS)


@nb.njit(nogil=True, cache=True)
def simulate_short(Ebits, Xbits, v, P, M, has_exec, has_mark, entry_ok, cost_buy,
                   cost_sell, cost_close, force, prio, day_last_bar, n_days, mult, slots,
                   borrow_daily):
    """Short-side twin of simulate(): an entry sells short shares worth
    min(equity / slots, cash) as collateral, paying the sell cost; positions
    mark additively (gain when price falls); each bar accrues borrow on the
    short's current value (borrow_daily = annual rate / 252 per bar); exits
    and forced exits buy to cover. Same signal, slot and priority rules."""
    S, T = P.shape
    cash = 1.0
    held = np.zeros(S, np.bool_)
    val = np.zeros(S)
    qty = np.zeros(S)
    lastm = np.zeros(S)
    basis = np.zeros(S)
    pend_e = np.zeros(S, np.bool_)
    pend_x = np.zeros(S, np.bool_)
    n_open = 0
    eq_bar = np.zeros(T)
    trades_bar = np.zeros(T, np.int32)
    wins_bar = np.zeros(T, np.int32)
    cand = np.empty(S, np.int64)
    for t in range(T):
        for s in range(S):                                   # 1. cover pending exits
            if held[s] and pend_x[s] and has_exec[s, t]:
                val[s] += qty[s] * (lastm[s] - P[s, t])
                proceeds = val[s] - qty[s] * P[s, t] * mult * cost_buy[s, t] / 1e4
                cash += proceeds
                trades_bar[t] += 1
                if proceeds > basis[s]:
                    wins_bar[t] += 1
                held[s] = False; pend_x[s] = False; val[s] = 0.0; qty[s] = 0.0; n_open -= 1
        free = slots - n_open                                # 2. new shorts
        if free > 0:
            nc = 0
            for s in range(S):
                if pend_e[s] and (not held[s]) and entry_ok[s, t]:
                    cand[nc] = s; nc += 1
            if nc > 0:
                equity = cash
                for s in range(S):
                    if held[s]:
                        equity += val[s]
                for k in range(min(free, nc)):
                    best = -1; bp = -np.inf
                    for j in range(nc):
                        s = cand[j]
                        if s >= 0 and prio[s, t] > bp:
                            bp = prio[s, t]; best = j
                    if best < 0:
                        break
                    s = cand[best]; cand[best] = -1
                    alloc = min(equity / slots, cash)
                    if alloc <= 1e-12:
                        break
                    cash -= alloc
                    basis[s] = alloc
                    qty[s] = alloc / P[s, t]
                    val[s] = alloc - alloc * mult * cost_sell[s, t] / 1e4
                    lastm[s] = P[s, t]
                    held[s] = True; pend_e[s] = False; n_open += 1
        for s in range(S):                                   # 3. mark + borrow
            if held[s] and has_mark[s, t]:
                val[s] += qty[s] * (lastm[s] - M[s, t])
                lastm[s] = M[s, t]
                val[s] -= qty[s] * M[s, t] * borrow_daily[s, t]
        for s in range(S):                                   # 4. forced covers at the close
            if held[s] and force[s, t]:
                proceeds = val[s] - qty[s] * lastm[s] * mult * cost_close[s, t] / 1e4
                cash += proceeds
                trades_bar[t] += 1
                if proceeds > basis[s]:
                    wins_bar[t] += 1
                held[s] = False; pend_x[s] = False; val[s] = 0.0; qty[s] = 0.0; n_open -= 1
        for s in range(S):                                   # 5. signals
            if has_mark[s, t]:
                if _bit(Xbits, s, v, t):
                    pend_e[s] = False
                    if held[s]:
                        pend_x[s] = True
                elif _bit(Ebits, s, v, t) and not held[s]:
                    pend_e[s] = True
        e = cash
        for s in range(S):
            if held[s]:
                e += val[s]
        eq_bar[t] = e
    eq_day = np.zeros(n_days)
    tr_day = np.zeros(n_days, np.int32)
    win_day = np.zeros(n_days, np.int32)
    prev = -1
    for d in range(n_days):
        last = day_last_bar[d]
        eq_day[d] = eq_bar[last]
        for t in range(prev + 1, last + 1):
            tr_day[d] += trades_bar[t]
            win_day[d] += wins_bar[t]
        prev = last
    return eq_day, tr_day, win_day


def run_variant_short(panel: dict, E, X, v: int, mult: float, borrow_annual: np.ndarray):
    p = panel
    return simulate_short(E, X, v, p["P"], p["M"], p["has_exec"], p["has_mark"],
                          p["entry_ok"], p["cost_buy"], p["cost_sell"], p["cost_close"],
                          p["force"], p["prio"], p["day_last_bar"], len(p["days"]),
                          float(mult), SLOTS, borrow_annual / 252.0)
