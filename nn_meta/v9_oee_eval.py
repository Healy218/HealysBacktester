# nn_meta/v9_oee_eval.py — V9 OEE-2: features, trades and statistics.
"""Implements docs/specs/V9_OEE1_PREREG_20261008.json (frozen 2026-10-08).

admit(ev)                 the pre-registered event admission
sue_feature / revenue_accel / momentum   PIT direction components
trailing_rank(...)        percentile and tercile against the prior 365 days
half_spread(...)          V8 option spread-model bucket lookup (fraction of price)
long_return / fly_return  net per-trade returns at cost multiple k
clustered_t(...)          mean, day-clustered t and one-sided p
holm(...)                 Holm step-down adjusted p-values
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from scipy import stats

FEE = 0.05 / 100          # $0.05 per contract per side, per share
MIN_TRAILING = 30
MAX_AGE_DAYS = 200
FOLDS = ["2023H1", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2"]
REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]


def admit(ev: pd.DataFrame) -> pd.DataFrame:
    ok = ((ev["status"] == "ok") & ev["straddle_reaction"].notna()
          & ~ev["split_between"].astype(bool) & ~ev["iv_crush_day_before"].astype(bool)
          & (ev["front_days_after_reaction"] <= 7) & (ev["straddle_entry"] >= 0.5)
          & (ev["call_atm_volume"] >= 10) & (ev["put_atm_volume"] >= 10))
    return ev[ok].copy()


def half_year(day: pd.Series) -> pd.Series:
    return day.str[:4] + np.where(day.str[5:7] <= "06", "H1", "H2")


# ── features ─────────────────────────────────────────────────────────────────

def _asof(ev: pd.DataFrame, tbl: pd.DataFrame, col: str) -> pd.Series:
    """Latest tbl[col] per ticker public before the entry close, <= MAX_AGE_DAYS old."""
    cut = pd.to_datetime(ev["entry_day"]).dt.tz_localize("America/New_York") + pd.Timedelta(hours=16)
    left = ev.assign(cut=cut.dt.tz_convert("UTC"), _i=np.arange(len(ev))).sort_values("cut")
    right = tbl.assign(t=pd.to_datetime(tbl["t"], utc=True)).sort_values("t")
    m = pd.merge_asof(left, right[["ticker", "t", col]], left_on="cut", right_on="t",
                      by="ticker", direction="backward", allow_exact_matches=False)
    fresh = (m["cut"] - m["t"]).dt.days <= MAX_AGE_DAYS
    return pd.Series(np.where(fresh, m[col], np.nan), index=m["_i"].to_numpy()).sort_index().to_numpy()


def sue_feature(ev: pd.DataFrame, sue: pd.DataFrame) -> np.ndarray:
    return _asof(ev, sue.rename(columns={"tau": "t"}), "sue")


def revenue_table(facts: pd.DataFrame) -> pd.DataFrame:
    """First-reported quarterly revenue -> YoY growth -> acceleration, per public time."""
    f = facts[facts["tag"].isin(REVENUE_TAGS) & (facts["unit"] == "USD") & facts["start"].notna()].copy()
    dur = (pd.to_datetime(f["end"]) - pd.to_datetime(f["start"])).dt.days
    f = f[(dur >= 80) & (dur <= 100)]
    # one value per (ticker, period end): the earliest report, preferring tag order on ties
    f["tag_rank"] = f["tag"].map({t: i for i, t in enumerate(REVENUE_TAGS)})
    f = f.sort_values(["available_at_utc", "tag_rank"]).drop_duplicates(["ticker", "end"])
    recs = []
    for t, g in f.groupby("ticker"):
        g = g.sort_values("end").reset_index(drop=True)
        ends = pd.to_datetime(g["end"])
        growth = np.full(len(g), np.nan)
        for i in range(len(g)):
            prior = np.nonzero(np.abs((ends[i] - ends[:i]).dt.days - 365) <= 20)[0]
            if prior.size and g["val"].iloc[prior[-1]] > 0:
                growth[i] = g["val"].iloc[i] / g["val"].iloc[prior[-1]] - 1
        for i in range(1, len(g)):
            if np.isfinite(growth[i]) and np.isfinite(growth[i - 1]):
                recs.append((t, g["available_at_utc"].iloc[i], growth[i] - growth[i - 1]))
    return pd.DataFrame(recs, columns=["ticker", "t", "revenue_accel"])


def momentum(ev: pd.DataFrame, adj: pd.DataFrame, days: list[str], lookback: int = 20) -> np.ndarray:
    """adj: wide adj_close (index date, columns tickers incl. QQQ)."""
    pos = {d: i for i, d in enumerate(days)}
    out = np.full(len(ev), np.nan)
    for j, (t, e) in enumerate(zip(ev["ticker"], ev["entry_day"])):
        i = pos.get(e)
        if i is None or i < lookback or t not in adj:
            continue
        a, b = days[i - lookback], e
        try:
            r = math.log(adj.at[b, t] / adj.at[a, t]) - math.log(adj.at[b, "QQQ"] / adj.at[a, "QQQ"])
        except (KeyError, ValueError):
            continue
        out[j] = r
    return out


def trailing_rank(entry_day: pd.Series, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(percentile, tercile) of each x against non-NaN x with entry days in
    [entry - 365 days, entry); tercile +1 top (> 2/3 quantile), -1 bottom
    (< 1/3 quantile), 0 middle, NaN without >= MIN_TRAILING history."""
    d = pd.to_datetime(entry_day).to_numpy()
    order = np.argsort(d, kind="stable")
    d, xs = d[order], np.asarray(x, float)[order]
    pct = np.full(len(d), np.nan)
    ter = np.full(len(d), np.nan)
    lo = np.searchsorted(d, d - np.timedelta64(365, "D"), side="left")
    hi = np.searchsorted(d, d, side="left")
    for i in range(len(d)):
        if not np.isfinite(xs[i]):
            continue
        h = xs[lo[i]:hi[i]]
        h = h[np.isfinite(h)]
        if len(h) < MIN_TRAILING:
            continue
        pct[i] = (h < xs[i]).mean() + 0.5 * (h == xs[i]).mean()
        q1, q2 = np.quantile(h, [1 / 3, 2 / 3])
        ter[i] = 1 if xs[i] > q2 else (-1 if xs[i] < q1 else 0)
    out_p, out_t = np.empty_like(pct), np.empty_like(ter)
    out_p[order], out_t[order] = pct, ter
    return out_p, out_t


def prior_move_ratio(ev: pd.DataFrame) -> np.ndarray:
    """implied move / median |realized move| of the ticker's previous 4-8
    admitted events whose reaction day is before this entry day."""
    out = np.full(len(ev), np.nan)
    idx = {k: i for i, k in enumerate(ev.index)}
    for _, g in ev.sort_values("entry_day").groupby("ticker"):
        for k, row in g.iterrows():
            prev = g[g["reaction_day"] < row["entry_day"]].tail(8)
            if len(prev) >= 4:
                out[idx[k]] = row["implied_move"] / np.median(np.abs(prev["realized_move"]))
    return out


# ── costs ────────────────────────────────────────────────────────────────────

class SpreadModel:
    PRICE = [0, 0.5, 1, 2, 5, 10, 1e9]
    DTE = [1, 3, 8, 31]
    OTM = [-0.1, -0.03, 0.03, 0.1]

    def __init__(self, path):
        m = json.loads(open(path).read())["bucket_medians"]
        self.cell = {}
        for r in m:
            pl = float(r["price"].strip("[)").split(",")[0])
            dl = int(r["dte"].strip("[)").split(",")[0])
            ol = float(r["otm"].strip("[)").split(",")[0])
            self.cell[(self.PRICE.index(pl), self.DTE.index(dl), self.OTM.index(ol))] = r["median_spread_pct"]

    def half_spread(self, price: float, dte: float, otm: float) -> float:
        p = min(max(np.searchsorted(self.PRICE, price, side="right") - 1, 0), 5)
        d = min(max(np.searchsorted(self.DTE, max(dte, 1), side="right") - 1, 0), 2)
        o = min(max(np.searchsorted(self.OTM, otm, side="right") - 1, 0), 2)
        v = self.cell.get((p, d, o))
        if v is None:
            v = max(s for (pp, dd, oo), s in self.cell.items() if dd == d and oo == o)
        return v / 100 / 2


def otm(cp: str, K: float, S: float) -> float:
    x = math.log(K / S)
    return x if cp == "C" else -x


# ── trades ───────────────────────────────────────────────────────────────────

def long_return(legs_in, legs_out, k: float) -> float:
    """legs_*: [(price, half_spread)] per leg. Net return on premium."""
    pay = sum(p * (1 + k * h) + FEE for p, h in legs_in)
    recv = sum(p * (1 - k * h) - FEE for p, h in legs_out)
    return recv / pay - 1


def fly_return(short_in, long_in, short_out, long_out, max_width: float, k: float) -> float:
    """Short iron butterfly; return on maximum loss."""
    credit = (sum(p * (1 - k * h) - FEE for p, h in short_in)
              - sum(p * (1 + k * h) + FEE for p, h in long_in))
    close = (sum(p * (1 + k * h) + FEE for p, h in short_out)
             - sum(p * (1 - k * h) - FEE for p, h in long_out))
    max_loss = max_width - credit
    if max_loss <= 0:
        return float("nan")
    return (credit - close) / max_loss


# ── statistics ───────────────────────────────────────────────────────────────

def clustered_t(r: np.ndarray, cluster: np.ndarray) -> dict:
    r = np.asarray(r, float)
    n = len(r)
    if n < 2:
        return {"n": n, "mean": float(r.mean()) if n else float("nan"), "t": float("nan"),
                "p_one_sided": float("nan"), "clusters": 0}
    m = r.mean()
    s = pd.Series(r - m).groupby(np.asarray(cluster)).sum()
    G = len(s)
    se = math.sqrt((s ** 2).sum() * G / max(G - 1, 1)) / n
    t = m / se if se > 0 else float("nan")
    return {"n": n, "mean": float(m), "t": float(t), "clusters": G,
            "p_one_sided": float(stats.t.sf(t, max(G - 1, 1))) if np.isfinite(t) else float("nan")}


def holm(p: dict) -> dict:
    keys = sorted(p, key=lambda k: (np.nan_to_num(p[k], nan=1.0)))
    m, run, out = len(keys), 0.0, {}
    for i, k in enumerate(keys):
        v = np.nan_to_num(p[k], nan=1.0)
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return out
