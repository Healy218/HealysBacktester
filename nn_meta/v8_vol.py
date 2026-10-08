# nn_meta/v8_vol.py — V8.2 volatility inputs: implied and forecast realized vol.
"""Vectorized building blocks for stage 2.

Implied vol (from OPRA daily aggregates, last-trade closes):
  forward   F per (ticker, date, expiry) = median over the 3 strikes nearest
            spot of K + C - P (put-call parity; discounting ignored, ~0.4%
            price error at 30 days)
  ATM IV    Black-76 IVs of out-of-the-money options with |log(K/F)| <= 5%,
            volume > 0 and close >= $0.05; linear interpolation in log(K/F)
            between the nearest strike below and above F (one side → that side)
  IV30      total variance linear in T between the expiries bracketing 30
            calendar days (5–120 DTE considered); no bracket → nearest expiry
            within 20–45 DTE, flagged

Realized variance (adjusted hourly bars): RV_d = overnight^2 + sum of squared
intraday hourly log returns (first bar measured from its open).

HAR forecast (direct 21-trading-day horizon): target mean(RV_{t+1..t+21}),
features [1, RV_t, mean RV_{t-4..t}, mean RV_{t-21..t}], OLS on the ticker's
own history whose targets are fully realized before the fit date; refit on
the first trading day of each month. Forecast vol = sqrt(252 * prediction).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import ndtr

H = 21


def black76(F, K, T, sigma, is_call):
    F, K, T, sigma = (np.asarray(x, float) for x in (F, K, T, sigma))
    sd = sigma * np.sqrt(T)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(F / K) + 0.5 * sd ** 2) / sd
    d2 = d1 - sd
    call = F * ndtr(d1) - K * ndtr(d2)
    return np.where(is_call, call, call - F + K)


def implied_vol(price, F, K, T, is_call, lo=1e-3, hi=5.0, iters=60) -> np.ndarray:
    """Bisection on Black-76; NaN when the price is outside no-arbitrage bounds."""
    price, F, K, T = (np.asarray(x, float) for x in (price, F, K, T))
    intrinsic = np.where(is_call, np.maximum(F - K, 0), np.maximum(K - F, 0))
    upper = np.where(is_call, F, K)
    ok = (price > intrinsic + 1e-6) & (price < upper) & (T > 0)
    a = np.full(price.shape, lo); b = np.full(price.shape, hi)
    for _ in range(iters):
        m = 0.5 * (a + b)
        too_high = black76(F, K, T, m, is_call) > price
        b = np.where(too_high, m, b); a = np.where(too_high, a, m)
    return np.where(ok, 0.5 * (a + b), np.nan)


def atm_iv_by_expiry(ch: pd.DataFrame, spot: pd.DataFrame) -> pd.DataFrame:
    """ch: date, ticker, expiry, cp, strike, close, volume; spot: date, ticker, S.
    Returns per (ticker, date, expiry): dte, F, iv_atm, sides (1 or 2)."""
    d = ch.merge(spot, on=["date", "ticker"])
    d["dte"] = (pd.to_datetime(d["expiry"]) - pd.to_datetime(d["date"])).dt.days
    d = d[(d["dte"] >= 5) & (d["dte"] <= 120) & (d["volume"] > 0) & (d["close"] > 0)
          & ((d["strike"] / d["S"] - 1).abs() <= 0.10)]
    key = ["ticker", "date", "expiry"]
    pv = d.pivot_table(index=key + ["strike", "S", "dte"], columns="cp", values="close",
                       aggfunc="last").dropna(subset=["C", "P"]).reset_index()
    pv["fk"] = pv["strike"] + pv["C"] - pv["P"]
    pv["dist"] = (pv["strike"] - pv["S"]).abs()
    pv = pv.sort_values(key + ["dist"])
    pv["r"] = pv.groupby(key).cumcount()
    fwd = pv[pv["r"] < 3].groupby(key).agg(F=("fk", "median"), dte=("dte", "first")).reset_index()
    o = d.merge(fwd[key + ["F"]], on=key)
    o["lm"] = np.log(o["strike"] / o["F"])
    otm = ((o["cp"] == "C") & (o["lm"] >= 0)) | ((o["cp"] == "P") & (o["lm"] < 0))
    o = o[otm & (o["lm"].abs() <= 0.05) & (o["close"] >= 0.05)].copy()
    o["iv"] = implied_vol(o["close"], o["F"], o["strike"], o["dte"] / 365, o["cp"] == "C")
    o = o.dropna(subset=["iv"])
    below = o[o["lm"] < 0].sort_values(key + ["lm"]).groupby(key).tail(1)
    above = o[o["lm"] >= 0].sort_values(key + ["lm"]).groupby(key).head(1)
    m = fwd.merge(below[key + ["lm", "iv"]].rename(columns={"lm": "lb", "iv": "ivb"}), on=key, how="left")
    m = m.merge(above[key + ["lm", "iv"]].rename(columns={"lm": "la", "iv": "iva"}), on=key, how="left")
    both = m["ivb"].notna() & m["iva"].notna()
    w = np.where(both, -m["lb"] / (m["la"] - m["lb"]).replace(0, np.nan), 0.0)
    m["iv_atm"] = np.where(both, m["ivb"] + w * (m["iva"] - m["ivb"]),
                           m["ivb"].fillna(m["iva"]))
    m["sides"] = both.astype(int) + 1
    return m.dropna(subset=["iv_atm"])[key + ["dte", "F", "iv_atm", "sides"]]


def iv30(by_exp: pd.DataFrame) -> pd.DataFrame:
    """Constant-maturity 30-calendar-day ATM IV per (ticker, date)."""
    rows = []
    for (t, d), g in by_exp.groupby(["ticker", "date"], sort=False):
        g = g.sort_values("dte")
        lo, hi = g[g["dte"] <= 30], g[g["dte"] >= 30]
        if len(lo) and len(hi):
            a, b = lo.iloc[-1], hi.iloc[0]
            if a["dte"] == b["dte"]:
                iv, flag = a["iv_atm"], "exact"
            else:
                wa, wb = a["iv_atm"] ** 2 * a["dte"], b["iv_atm"] ** 2 * b["dte"]
                w30 = wa + (wb - wa) * (30 - a["dte"]) / (b["dte"] - a["dte"])
                iv, flag = np.sqrt(max(w30, 0) / 30), "bracket"
        else:
            near = g[(g["dte"] >= 20) & (g["dte"] <= 45)]
            if near.empty:
                continue
            r = near.iloc[(near["dte"] - 30).abs().argmin()]
            iv, flag = r["iv_atm"], "nearest"
        rows.append((t, d, float(iv), flag, int(g["sides"].min())))
    return pd.DataFrame(rows, columns=["ticker", "date", "iv30", "iv30_method", "min_sides"])


def realized_variance(hourly: pd.DataFrame) -> pd.DataFrame:
    """Per (ticker, date) RV from adjusted hourly bars (sorted by date, hour_bin)."""
    h = hourly.sort_values(["ticker", "date", "hour_bin"])
    intr = np.log(h["adj_close"] / h["adj_open"].where(h["hour_bin"] == 0,
                                                      h.groupby(["ticker", "date"])["adj_close"].shift(1)))
    h = h.assign(r2=intr ** 2)
    day = h.groupby(["ticker", "date"]).agg(rv_intra=("r2", "sum"), open=("adj_open", "first"),
                                            close=("adj_close", "last")).reset_index()
    day["prev_close"] = day.groupby("ticker")["close"].shift(1)
    day["rv"] = day["rv_intra"] + np.log(day["open"] / day["prev_close"]).fillna(0) ** 2
    return day[["ticker", "date", "rv", "close"]]


def har_direct(rv: pd.DataFrame) -> pd.DataFrame:
    """PIT 21-day HAR forecast and the realized forward vol per (ticker, date)."""
    out = []
    for t, g in rv.groupby("ticker", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        x = g["rv"].to_numpy()
        n = len(x)
        d = x
        w = pd.Series(x).rolling(5).mean().to_numpy()
        m = pd.Series(x).rolling(22).mean().to_numpy()
        fwd = pd.Series(x[::-1]).rolling(H).mean().to_numpy()[::-1]
        y = np.r_[fwd[1:], np.nan]                       # mean RV_{t+1..t+21}
        y[n - H:] = np.nan
        X = np.column_stack([np.ones(n), d, w, m])
        pred = np.full(n, np.nan)
        months = g["date"].str[:7].to_numpy()
        first_of_month = np.r_[True, months[1:] != months[:-1]]
        coef = None
        for i in range(n):
            if first_of_month[i]:
                usable = np.arange(n) <= i - 1 - H          # targets realized by day i-1
                ok = usable & np.isfinite(y) & np.isfinite(X).all(1)
                if ok.sum() >= 250:
                    coef, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            if coef is not None and np.isfinite(X[i]).all():
                pred[i] = X[i] @ coef
        out.append(pd.DataFrame({"ticker": t, "date": g["date"],
                                 "har_vol": np.sqrt(252 * np.clip(pred, 1e-10, None)),
                                 "rv_fwd_vol": np.sqrt(252 * y)}))
    return pd.concat(out, ignore_index=True)
