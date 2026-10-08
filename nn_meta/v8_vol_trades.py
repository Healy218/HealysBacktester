# nn_meta/v8_vol_trades.py — V8.2 defined-risk option trades (pre-registered).
"""Candidate trade construction and portfolio simulation for stage 2
(docs/specs/V8_STAGE2_PREREG_20261008.json).

build_candidates(chains_day, spot, iv) → one row per (ticker, entry date,
structure) with the trade's return per unit of maximum risk at k = 1.0 and
1.5, its settlement date and legs. Trades must settle by END (the holdout is
never read). simulate() walks the days for one variant.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
SPREAD_MODEL = REPO / "nn_meta" / "validation" / "v8-spreads-option-20261008-r0" / "model.json"
END = "2025-12-31"
FEE = 0.05
MIN_PRICE = 0.50
RISK = 0.02
KS = (1.0, 1.5)
STRUCTURES = {
    # name: list of (cp, side, target) with target in EM units from F (0 = ATM)
    "ib_w1.0": [("C", -1, 0.0), ("P", -1, 0.0), ("C", +1, 1.0), ("P", +1, -1.0)],
    "ib_w1.5": [("C", -1, 0.0), ("P", -1, 0.0), ("C", +1, 1.5), ("P", +1, -1.5)],
    "ic_1.0_1.5": [("C", -1, 1.0), ("P", -1, -1.0), ("C", +1, 1.5), ("P", +1, -1.5)],
    "straddle": [("C", +1, 0.0), ("P", +1, 0.0)],
}
_PRICE = [0, 0.5, 1, 2, 5, 10, 1e9]
_DTE = [0, 1, 3, 8, 31, 91, 10**5]
_OTM = [-10, -0.1, -0.03, 0.03, 0.1, 10]


def spread_table() -> tuple[dict, dict]:
    m = json.loads(SPREAD_MODEL.read_text())
    def lo(s):
        return float(s.strip("[)").split(",")[0])
    cells, by_price = {}, {}
    for c in m["bucket_medians"]:
        pi = _PRICE.index(lo(c["price"])); di = _DTE.index(lo(c["dte"])); oi = _OTM.index(lo(c["otm"]))
        cells[(pi, di, oi)] = c["median_spread_pct"]
        by_price.setdefault(pi, []).append((c["median_spread_pct"], c["n"]))
    fallback = {}
    for pi, xs in by_price.items():
        v = np.array([x for x, _ in xs]); w = np.array([n for _, n in xs], float)
        order = np.argsort(v); cw = np.cumsum(w[order]) / w.sum()
        fallback[pi] = float(v[order][np.searchsorted(cw, 0.5)])
    return cells, fallback


def half_spread(price, dte, otm, table) -> np.ndarray:
    cells, fallback = table
    pi = np.searchsorted(_PRICE, price, side="right") - 1
    di = np.searchsorted(_DTE, dte, side="right") - 1
    oi = np.clip(np.searchsorted(_OTM, otm, side="right") - 1, 0, len(_OTM) - 2)
    pct = np.array([cells.get((a, b, c), fallback.get(a, np.nan)) for a, b, c in zip(pi, di, oi)])
    return price * pct / 200.0


def build_candidates(ch: pd.DataFrame, spot: pd.DataFrame, settle_px: pd.DataFrame,
                     table) -> pd.DataFrame:
    """ch: one month of chains (date, ticker, expiry, cp, strike, close, volume);
    spot: (ticker, date, S, iv30); settle_px: (ticker, date, close) raw daily
    closes through END for settlement lookups."""
    ch = ch[(ch["volume"] >= 1) & (ch["close"] > 0)].merge(spot, on=["ticker", "date"])
    ch = ch[np.isfinite(ch["iv30"])]
    ch["dte"] = (pd.to_datetime(ch["expiry"]) - pd.to_datetime(ch["date"])).dt.days
    ch = ch[(ch["dte"] >= 21) & (ch["dte"] <= 45) & (ch["expiry"] <= END)]
    if ch.empty:
        return pd.DataFrame()
    exp = ch.groupby(["ticker", "date", "expiry"])["dte"].first().reset_index()
    exp["d30"] = (exp["dte"] - 30).abs()
    exp = exp.sort_values(["ticker", "date", "d30", "dte"]).groupby(["ticker", "date"]).head(1)
    ch = ch.merge(exp[["ticker", "date", "expiry"]], on=["ticker", "date", "expiry"])
    # forward from parity, 3 strikes nearest spot
    pv = ch.pivot_table(index=["ticker", "date", "strike", "S"], columns="cp", values="close",
                        aggfunc="last").dropna(subset=["C", "P"]).reset_index()
    pv["fk"] = pv["strike"] + pv["C"] - pv["P"]
    pv["dist"] = (pv["strike"] - pv["S"]).abs()
    pv = pv.sort_values(["ticker", "date", "dist"])
    fwd = pv.groupby(["ticker", "date"]).head(3).groupby(["ticker", "date"])["fk"].median().rename("F")
    settle_idx = settle_px.set_index(["ticker", "date"])["close"]
    days_by_t = {t: g["date"].to_numpy() for t, g in settle_px.groupby("ticker")}
    rows = []
    for (t, d), g in ch.groupby(["ticker", "date"], sort=False):
        if (t, d) not in fwd.index:
            continue
        F = float(fwd.loc[(t, d)])
        S, iv, dte, expiry = float(g["S"].iloc[0]), float(g["iv30"].iloc[0]), int(g["dte"].iloc[0]), g["expiry"].iloc[0]
        em = S * iv * math.sqrt(dte / 365)
        tdays = days_by_t.get(t)
        if tdays is None:
            continue
        j = np.searchsorted(tdays, expiry, side="right") - 1
        if j < 0 or tdays[j] <= d:
            continue
        settle_date = tdays[j]
        ST = float(settle_idx.loc[(t, settle_date)])
        by_cp = {cp: gg.set_index("strike")["close"] for cp, gg in g.groupby("cp")}
        for name, legs in STRUCTURES.items():
            chosen = []
            for cp, side, tgt in legs:
                book = by_cp.get(cp)
                if book is None or book.empty:
                    chosen = None; break
                ks = book.index.to_numpy()
                K = float(ks[np.argmin(np.abs(ks - (F + tgt * em)))])
                chosen.append((cp, side, K, float(book.loc[K])))
            if chosen is None or any(p < MIN_PRICE for *_, p in chosen):
                continue
            if name.startswith("ib") or name.startswith("ic"):
                sc = [K for cp, s, K, _ in chosen if cp == "C" and s < 0][0]
                lc = [K for cp, s, K, _ in chosen if cp == "C" and s > 0][0]
                sp = [K for cp, s, K, _ in chosen if cp == "P" and s < 0][0]
                lp = [K for cp, s, K, _ in chosen if cp == "P" and s > 0][0]
                if not (lc > sc and lp < sp):
                    continue
                width = max(lc - sc, sp - lp)
            prices = np.array([p for *_, p in chosen])
            strikes = np.array([K for _, _, K, _ in chosen])
            sides = np.array([s for _, s, _, _ in chosen])
            cps = np.array([cp for cp, *_ in chosen])
            otm = np.where(cps == "C", np.log(strikes / S), -np.log(strikes / S))
            hs = half_spread(prices, np.full(len(prices), dte), otm, table)
            payoff = np.where(cps == "C", np.maximum(ST - strikes, 0), np.maximum(strikes - ST, 0))
            rec = {"ticker": t, "date": d, "structure": name, "expiry": expiry,
                   "settle_date": settle_date, "dte": dte, "S": S, "F": F, "em": em, "S_T": ST,
                   "strikes": strikes.tolist()}
            fee = FEE * len(legs) / 100.0
            for k in KS:
                fill = prices + sides * k * hs                # buy above, sell below the close
                cash0 = -(sides * fill).sum() - fee           # credit > 0
                pnl = cash0 + (sides * payoff).sum()
                maxloss = (width - cash0) if name != "straddle" else -cash0
                rec[f"R_{k}"] = pnl / maxloss if maxloss > 0 else np.nan
            rows.append(rec)
    return pd.DataFrame(rows)


def simulate(days: np.ndarray, cand: dict, signal: dict, universe: dict) -> tuple[np.ndarray, np.ndarray]:
    """One variant. cand[(ticker, day)] = (R, settle_date); signal[(ticker, day)]
    = True if the PREVIOUS trading day's ratio triggered; universe[day] = set of
    tickers. Returns daily equity and entries per day."""
    equity = 1.0
    open_: dict[str, tuple[str, float, float]] = {}
    eq = np.zeros(len(days)); n_entries = np.zeros(len(days), np.int32)
    for i, d in enumerate(days):
        for t in [t for t, (sd, _, _) in open_.items() if sd <= d]:
            sd, risk, R = open_.pop(t)
            equity += risk * R
        for t in sorted(universe.get(d, ())):
            if t in open_ or not signal.get((t, d), False):
                continue
            c = cand.get((t, d))
            if c is None or not np.isfinite(c[0]):
                continue
            open_[t] = (c[1], RISK * equity, c[0])
            n_entries[i] += 1
        eq[i] = equity
    return eq, n_entries
