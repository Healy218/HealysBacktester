# nn_meta/v8_h1_calls.py — V8 H1 earnings drift expressed with calls (test B).
"""Pre-registered in docs/specs/V8_H1_CONFIRM_PREREG_20261008.json.

pick_call(chain_day, S)  chooses the ~45 DTE, ~0.60 delta call from one
                         (ticker, day) chain of daily aggregates.
exit_price(...)          20 trading days later, with a 5-day no-trade
                         fallback, intrinsic otherwise, OCC split terms.
simulate(trades, ...)    cash-basis book: 5% of equity premium per entry,
                         <= 10 open, one per name, adv20 priority.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from nn_meta import v8_vol

TARGET_DTE, DTE_LO, DTE_HI = 45, 35, 60
TARGET_DELTA = 0.60
MIN_PRICE = 1.00
HOLD = 20
FALLBACK_DAYS = 5
FEE = 0.05
SIZE = 0.05
SLOTS = 10


def pick_call(ch: pd.DataFrame, day: str, S: float, cp: str = "C") -> dict | None:
    """ch: one ticker's chain rows for `day` (expiry, cp, strike, close, volume).
    cp="P" picks the put nearest delta -0.60 the same way."""
    ch = ch[(ch["volume"] >= 1) & (ch["close"] > 0)].copy()
    ch["dte"] = (pd.to_datetime(ch["expiry"]) - pd.Timestamp(day)).dt.days
    ch = ch[(ch["dte"] >= DTE_LO) & (ch["dte"] <= DTE_HI)]
    if ch.empty:
        return None
    exp = ch.groupby("expiry")["dte"].first()
    expiry = (exp - TARGET_DTE).abs().sort_values(kind="stable").index[0]
    e = ch[ch["expiry"] == expiry]
    dte = int(e["dte"].iloc[0])
    pv = e.pivot_table(index="strike", columns="cp", values="close", aggfunc="last").dropna()
    if pv.empty or "C" not in pv or "P" not in pv:
        return None
    near = (pv.index.to_series() - S).abs().sort_values().index[:3]
    F = float(np.median(near + pv.loc[near, "C"] - pv.loc[near, "P"]))
    calls = e[(e["cp"] == cp) & (e["close"] >= MIN_PRICE)]
    if calls.empty:
        return None
    T = dte / 365
    iv = v8_vol.implied_vol(calls["close"], F, calls["strike"], T, cp == "C")
    ok = np.isfinite(iv)
    if not ok.any():
        return None
    calls = calls[ok].assign(iv=iv[ok])
    d1 = (np.log(F / calls["strike"]) + 0.5 * calls["iv"] ** 2 * T) / (calls["iv"] * math.sqrt(T))
    nd1 = 0.5 * (1 + np.vectorize(math.erf)(d1 / math.sqrt(2)))
    calls = calls.assign(delta=nd1 if cp == "C" else nd1 - 1)
    target = TARGET_DELTA if cp == "C" else -TARGET_DELTA
    row = calls.iloc[(calls["delta"] - target).abs().argmin()]
    return {"expiry": expiry, "strike": float(row["strike"]), "price": float(row["close"]),
            "delta": float(row["delta"]), "iv": float(row["iv"]), "dte": dte, "F": F}


def exit_price(prices: dict, days: list[str], i_entry: int, strike: float, expiry: str,
               raw_close: dict, split_factor, cp: str = "C") -> tuple[str, float, str]:
    """prices[(day, strike)] = close if the contract traded; returns
    (exit day, value per original contract share, how)."""
    i = i_entry + HOLD
    if i >= len(days):
        return "", float("nan"), "beyond"
    for k in range(FALLBACK_DAYS + 1):
        if i + k >= len(days) or days[i + k] > expiry:
            break
        d = days[i + k]
        f = split_factor(d)
        p = prices.get((d, round(strike / f, 4)))
        if p is not None:
            return d, p * f, "traded" if k == 0 else f"traded+{k}"
    d = days[i]
    S = raw_close[d] * split_factor(d)                    # in original units
    return d, (max(S - strike, 0.0) if cp == "C" else max(strike - S, 0.0)), "intrinsic"


def simulate(trades: pd.DataFrame, days: list[str], half_spread: float) -> tuple[np.ndarray, pd.DataFrame]:
    """trades: one row per candidate (ticker, entry_day, exit_day, entry_price,
    exit_value, prio). Returns daily cash-basis equity and the taken trades."""
    equity = 1.0
    open_: dict[str, tuple[str, float, float]] = {}
    eq = np.zeros(len(days))
    taken = []
    by_entry = {d: g.sort_values("prio", ascending=False) for d, g in trades.groupby("entry_day")}
    for i, d in enumerate(days):
        for t in [t for t, (xd, _, _) in open_.items() if xd <= d]:
            xd, cost, units = open_.pop(t)
            equity += units - cost
        for _, row in by_entry.get(d, pd.DataFrame()).iterrows():
            if row["ticker"] in open_ or len(open_) >= SLOTS:
                continue
            pay = row["entry_price"] * (1 + half_spread) + FEE / 100
            recv = row["exit_value"] * (1 - half_spread) - FEE / 100
            cost = SIZE * equity
            ret = recv / pay - 1
            open_[row["ticker"]] = (row["exit_day"], cost, cost * (1 + ret))
            taken.append({**row.to_dict(), "ret": ret})
        eq[i] = equity
    return eq, pd.DataFrame(taken)
