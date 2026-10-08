# nn_meta/v8_event_signals.py — V8 event/attention hypotheses as engine signals.
"""Build entry/exit signal matrices (S tickers x T trading days) for the 16
pre-registered variants (docs/specs/V8_EVENTS_PREREG_20261008.json) on the
daily execution grid of nn_meta.v8_engine.

Conventions: grid days are trading dates (strings); a signal on bar t
executes at bar t+1's 10:30 ET open. Event timing helpers map public times
(UTC) to signal bars exactly as the pre-registration specifies.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TZ = "America/New_York"


# ── timing ───────────────────────────────────────────────────────────────────

def event_signal_bar(tau_utc: pd.Series, days: list[str]) -> np.ndarray:
    """Index of the bar before the first trading day whose 10:00 ET >= tau; -1
    if that day is the first grid day or beyond the grid."""
    ten = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(TZ) + pd.Timedelta(hours=10)
    t = pd.to_datetime(tau_utc, utc=True).dt.tz_convert(TZ)
    x = np.searchsorted(ten.asi8, t.astype("int64").to_numpy(), side="left")
    out = x - 1
    out[(x <= 0) | (x >= len(days))] = -1
    return out


def reaction_bar(tau_utc: pd.Series, days: list[str]) -> np.ndarray:
    """Index of the first trading day whose 16:00 ET close is after tau."""
    close = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(TZ) + pd.Timedelta(hours=16)
    t = pd.to_datetime(tau_utc, utc=True).dt.tz_convert(TZ)
    x = np.searchsorted(close.asi8, t.astype("int64").to_numpy(), side="right")
    x[x >= len(days)] = -1
    return x


def holding_exits(E: np.ndarray, hold: int) -> np.ndarray:
    """Exit when `hold` bars have passed since the most recent entry signal."""
    S, T = E.shape
    X = np.zeros_like(E)
    idx = np.arange(T)
    for s in range(S):
        sig = np.where(E[s], idx, -1)
        last = np.maximum.accumulate(sig)
        X[s] = (last >= 0) & (idx - last == hold)
    return X


def _place(S: int, T: int, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    E = np.zeros((S, T), bool)
    ok = (rows >= 0) & (cols >= 0) & (cols < T)
    E[rows[ok], cols[ok]] = True
    return E


def trailing_tercile_flag(bars: np.ndarray, values: np.ndarray, days: list[str],
                          min_n: int = 30) -> np.ndarray:
    """values[i] is in the top tercile of all values whose bar is in the prior
    365 calendar days (strictly earlier bars), with >= min_n of them."""
    d = pd.to_datetime(np.array(days))[np.clip(bars, 0, None)]
    order = np.argsort(bars, kind="stable")
    flag = np.zeros(len(bars), bool)
    b_sorted, v_sorted, d_sorted = bars[order], values[order], d[order]
    for k, i in enumerate(order):
        if bars[i] < 0 or not np.isfinite(values[i]):
            continue
        lo = np.searchsorted(d_sorted.asi8, (d[i] - pd.Timedelta(days=365)).value, side="left")
        hi = np.searchsorted(b_sorted, bars[i], side="left")      # strictly earlier bars
        hist = v_sorted[lo:hi]
        hist = hist[np.isfinite(hist)]
        if len(hist) >= min_n:
            flag[i] = values[i] >= np.quantile(hist, 2 / 3)
    return flag


# ── hypotheses ───────────────────────────────────────────────────────────────

def abnormal_returns(adj_close: np.ndarray, admitted: np.ndarray) -> np.ndarray:
    """(S, T) abnormal close-to-close return vs the EW admitted universe."""
    r = np.full(adj_close.shape, np.nan)
    r[:, 1:] = adj_close[:, 1:] / adj_close[:, :-1] - 1
    ew = np.nanmean(np.where(admitted, r, np.nan), axis=0)
    return r - ew[None, :]


def h1(ctx: dict) -> dict:
    tickers, days, S, T = ctx["tickers"], ctx["days"], ctx["S"], ctx["T"]
    tix = {t: i for i, t in enumerate(tickers)}
    out = {}
    fl = ctx["filings"]
    e = fl[(fl["form"] == "8-K") & fl["items"].fillna("").str.contains("2.02") & fl["ticker"].isin(tix)]
    e = e.drop_duplicates(["ticker", "available_at_utc"])
    rb = reaction_bar(e["available_at_utc"], days)
    rows = e["ticker"].map(tix).to_numpy()
    ar = np.array([ctx["abn"][r, b] if b >= 0 else np.nan for r, b in zip(rows, rb)])
    flag = trailing_tercile_flag(rb, ar, days)
    E = _place(S, T, np.where(flag, rows, -1), rb)
    for H in (20, 60):
        out[f"H1a_reaction_h{H}"] = (E, holding_exits(E, H))
    # SUE from first-reported quarterly diluted EPS
    f = ctx["facts"]
    f = f[(f["tag"] == "EarningsPerShareDiluted") & (f["unit"] == "USD/shares") & f["start"].notna()
          & f["ticker"].isin(tix)].copy()
    dur = (pd.to_datetime(f["end"]) - pd.to_datetime(f["start"])).dt.days
    f = f[(dur >= 80) & (dur <= 100)]
    f = f.sort_values("available_at_utc").drop_duplicates(["ticker", "end"])   # first report
    recs = []
    for t, g in f.groupby("ticker"):
        g = g.sort_values("end").reset_index(drop=True)
        ends = pd.to_datetime(g["end"])
        yoy = np.full(len(g), np.nan)
        for i in range(len(g)):
            prior = np.nonzero(np.abs((ends[i] - ends[:i]).dt.days - 365) <= 20)[0]
            if prior.size:
                yoy[i] = g["val"].iloc[i] - g["val"].iloc[prior[-1]]
        for i in range(len(g)):
            hist = yoy[max(0, i - 8):i]
            hist = hist[np.isfinite(hist)]
            if np.isfinite(yoy[i]) and len(hist) >= 4 and hist.std(ddof=1) > 0:
                recs.append((t, g["available_at_utc"].iloc[i], yoy[i] / hist.std(ddof=1)))
    sue = pd.DataFrame(recs, columns=["ticker", "tau", "sue"])
    sb = event_signal_bar(sue["tau"], days)
    flag = trailing_tercile_flag(sb, sue["sue"].to_numpy(), days)
    E = _place(S, T, np.where(flag, sue["ticker"].map(tix).to_numpy(), -1), sb)
    for H in (20, 60):
        out[f"H1b_sue_h{H}"] = (E, holding_exits(E, H))
    return out


def h2(ctx: dict) -> dict:
    tickers, days, S, T = ctx["tickers"], ctx["days"], ctx["S"], ctx["T"]
    tix = {t: i for i, t in enumerate(tickers)}
    i = ctx["insider"]
    flag10b5 = i.get("aff10b5one", pd.Series(index=i.index, dtype=object)).astype(str).str.lower()
    p = i[(i["trans_code"] == "P") & (i["trans_acquired_disp_cd"] == "A")
          & ~flag10b5.isin(["1", "true", "y"]) & i["ticker"].isin(tix)].copy()
    p = p.dropna(subset=["trans_date", "available_at_utc"])
    p["avail"] = pd.to_datetime(p["available_at_utc"], utc=True)
    p["tdate"] = pd.to_datetime(p["trans_date"])
    p["owner"] = p["owner_ciks"].fillna("").str.split(",")
    p = p.explode("owner")
    out = {}
    for k in (2, 3):
        ev = []
        for t, g in p.groupby("ticker"):
            g = g.sort_values("avail")
            for tau in g["avail"].unique():
                known = g[g["avail"] <= tau]
                tau_et = pd.Timestamp(tau).tz_convert(TZ).tz_localize(None)
                recent = known[known["tdate"] >= tau_et.normalize() - pd.Timedelta(days=30)]
                if recent["owner"].nunique() >= k:
                    ev.append((t, tau))
        ev = pd.DataFrame(ev, columns=["ticker", "tau"])
        sb = event_signal_bar(ev["tau"], days) if len(ev) else np.array([], int)
        E = _place(S, T, ev["ticker"].map(tix).to_numpy() if len(ev) else np.array([], int), sb)
        for H in (21, 63):
            out[f"H2_cluster_k{k}_h{H}"] = (E, holding_exits(E, H))
    return out


def h3(ctx: dict) -> tuple[dict, dict]:
    tickers, days, S, T = ctx["tickers"], ctx["days"], ctx["S"], ctx["T"]
    sv = ctx["short_ratio"]                                 # (S, T), NaN where missing
    admitted = ctx["admitted"]
    week = pd.to_datetime(np.array(days)).to_period("W")
    last_of_week = np.r_[week[1:] != week[:-1], True]
    out, prio = {}, {}
    for w in (5, 10):
        df = pd.DataFrame(sv.T)
        short = df.rolling(w, min_periods=w).mean()
        base = df.shift(w).rolling(60, min_periods=40)
        z = ((short - base.mean()) / base.std()).to_numpy().T
        for M in (10, 20):
            E = np.zeros((S, T), bool); X = np.zeros((S, T), bool)
            pr = np.full((S, T), -1e9)
            for t in np.nonzero(last_of_week)[0]:
                if t + 1 >= T:
                    continue
                ok = admitted[:, t + 1] & np.isfinite(z[:, t])
                cand = np.nonzero(ok)[0]
                if cand.size == 0:
                    continue
                order = cand[np.argsort(z[cand, t], kind="stable")]
                E[order[:10], t] = True
                keep = set(order[:M].tolist())
                X[[s for s in range(S) if s not in keep], t] = True
                pr[:, t + 1] = -np.nan_to_num(z[:, t], nan=1e9)
            name = f"H3_shortz_w{w}_m{M}"
            out[name] = (E, X & ~E)
            prio[name] = pr
    return out, prio


def h4(ctx: dict) -> dict:
    tickers, days, S, T = ctx["tickers"], ctx["days"], ctx["S"], ctx["T"]
    tix = {t: i for i, t in enumerate(tickers)}
    abn = ctx["abn"]
    sd = pd.DataFrame(abn.T).shift(1).rolling(60, min_periods=40).std().to_numpy().T
    z = abn / sd
    raw = ctx["raw_ret"]
    # news created between the prior close and this close
    n = ctx["news"]
    n = n[n["ticker"].isin(tix)]
    rb = reaction_bar(n["available_at_utc"], days)
    has_news = _place(S, T, n["ticker"].map(tix).to_numpy(), rb)
    out = {}
    for th in (2, 3):
        E = (z >= th) & (raw > 0) & has_news
        out[f"H4a_news_z{th}"] = (E, holding_exits(E, 21))
    v = ctx["views"]                                         # (S, T) views per trading day
    med = pd.DataFrame(v.T).shift(1).rolling(20, min_periods=15).median().to_numpy().T
    for m in (3, 5):
        with np.errstate(divide="ignore", invalid="ignore"):
            E = np.nan_to_num((med >= 100) & (v / med >= m), nan=False).astype(bool)
        out[f"H4b_wiki_m{m}"] = (E, holding_exits(E, 10))
    return out
