# nn_meta/v8_paper.py — V8 H1 paper forward test: pure decision logic.
"""Live counterparts of the backtested H1 rules (H1b_sue_h20,
docs/specs/V8_H1_CONFIRM_PREREG_20261008.json), kept free of I/O so they can
be unit-tested. The runner (scripts/run_v8_h1_paper.py) supplies data.

Execution day of an event public at tau: the first trading day whose 10:00
ET is at or after tau (orders at 10:30 ET). Exit: 20 trading days after the
latest execution day for that name (a newer signal extends the hold).
"""
from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd

from nn_meta import v8_vol

TZ = "America/New_York"
HOLD = 20
SLOTS = 10
MIN_PREV_CLOSE = 5.0
MIN_ADV20 = 25e6
CALL_DTE, CALL_DTE_LO, CALL_DTE_HI = 45, 35, 60
CALL_DELTA = 0.60
CALL_MIN_ASK = 1.00


def execution_day(tau_utc, trading_days: list[str]) -> str | None:
    t = pd.Timestamp(tau_utc).tz_convert(TZ)
    for d in trading_days:
        if pd.Timestamp(f"{d} 10:00", tz=TZ) >= t:
            return d
    return None


def exit_day(entry_day: str, trading_days: list[str]) -> str | None:
    i = trading_days.index(entry_day) + HOLD
    return trading_days[i] if i < len(trading_days) else None


def tercile_signals(events: pd.DataFrame, trading_days: list[str], min_n: int = 30) -> pd.DataFrame:
    """events: ticker, tau (UTC), sue. Adds exec_day and top-tercile flag vs
    events whose exec day is earlier and within the prior 365 calendar days."""
    e = events.copy()
    e["exec_day"] = [execution_day(t, trading_days) for t in e["tau"]]
    e = e.dropna(subset=["exec_day"]).sort_values("exec_day").reset_index(drop=True)
    days = pd.to_datetime(e["exec_day"])
    flags = []
    for i in range(len(e)):
        prior = e[(e["exec_day"] < e.at[i, "exec_day"]) & (days > days[i] - pd.Timedelta(days=365))]["sue"]
        prior = prior[np.isfinite(prior)]
        flags.append(len(prior) >= min_n and e.at[i, "sue"] >= np.quantile(prior, 2 / 3))
    e["signal"] = flags
    return e


def admitted(prev_close: float, adv20: float, n_days: int) -> bool:
    return n_days >= 10 and prev_close >= MIN_PREV_CLOSE and adv20 >= MIN_ADV20


def plan_entries(candidates: pd.DataFrame, held: set[str], slots: int = SLOTS) -> list[str]:
    """candidates: ticker, adv20 (admitted, signalled today). Highest adv20
    first, ticker as tie-break, into free slots, skipping names already held."""
    c = candidates[~candidates["ticker"].isin(held)]
    c = c.sort_values(["adv20", "ticker"], ascending=[False, True])
    free = max(0, slots - len(held))
    return c["ticker"].head(free).tolist()


def pick_call_from_quotes(chain: pd.DataFrame, today: str, S: float) -> dict | None:
    """chain: symbol, expiry, cp, strike, bid, ask (live quotes). Expiry nearest
    45 DTE within 35-60; forward from put-call parity on mids at the 3
    strikes nearest spot; call nearest delta 0.60 (Black-76 on mids) with
    ask >= $1."""
    q = chain[(chain["bid"] > 0) & (chain["ask"] >= chain["bid"])].copy()
    q["mid"] = (q["bid"] + q["ask"]) / 2
    q["dte"] = (pd.to_datetime(q["expiry"]) - pd.Timestamp(today)).dt.days
    q = q[(q["dte"] >= CALL_DTE_LO) & (q["dte"] <= CALL_DTE_HI)]
    if q.empty:
        return None
    exp = q.groupby("expiry")["dte"].first()
    expiry = (exp - CALL_DTE).abs().sort_values(kind="stable").index[0]
    e = q[q["expiry"] == expiry]
    dte = int(e["dte"].iloc[0])
    pv = e.pivot_table(index="strike", columns="cp", values="mid", aggfunc="last").dropna()
    if pv.empty or "C" not in pv or "P" not in pv:
        return None
    near = (pv.index.to_series() - S).abs().sort_values().index[:3]
    F = float(np.median(near + pv.loc[near, "C"] - pv.loc[near, "P"]))
    calls = e[(e["cp"] == "C") & (e["ask"] >= CALL_MIN_ASK)].copy()
    T = dte / 365
    iv = v8_vol.implied_vol(calls["mid"], F, calls["strike"], T, True)
    calls = calls[np.isfinite(iv)].assign(iv=iv[np.isfinite(iv)])
    if calls.empty:
        return None
    d1 = (np.log(F / calls["strike"]) + 0.5 * calls["iv"] ** 2 * T) / (calls["iv"] * math.sqrt(T))
    calls["delta"] = 0.5 * (1 + np.vectorize(math.erf)(d1 / math.sqrt(2)))
    r = calls.iloc[(calls["delta"] - CALL_DELTA).abs().argmin()]
    return {"symbol": r["symbol"], "expiry": expiry, "strike": float(r["strike"]), "bid": float(r["bid"]),
            "ask": float(r["ask"]), "mid": float(r["mid"]), "delta": float(r["delta"]), "iv": float(r["iv"]),
            "dte": dte, "F": F}


def client_order_id(book: str, ticker: str, day: str, side: str) -> str:
    """Deterministic: a rerun of the same decision can never double-order."""
    return f"v8h1-{book}-{ticker}-{day}-{side}"


def now_et() -> datetime:
    return pd.Timestamp.now(tz=TZ).to_pydatetime()
