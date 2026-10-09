# nn_meta/v9_oee.py — V9 OEE-0: earnings event table (coverage only).
"""Per earnings release (8-K Item 2.02), the option and stock state around it.

Timing. The release time tau is the 8-K acceptance time (EDGAR, true UTC).
Entry day E = last trading day whose 16:00 ET close is before tau; reaction
day R = first trading day whose 16:00 ET close is after tau. A press release
can precede its 8-K, so `iv_crush_day_before` flags events whose front ATM IV
fell more than CRUSH on E (vs E-1) and more than on R (vs E): the release was
probably already public at E's close.

Options (OPRA daily aggregates; prices are last-trade closes, not mids):
  front expiry   nearest expiry on or after R that traded on E
  next expiry    the following expiry (for term structure / event variance)
  forward F      median K + C - P over the 3 strikes nearest spot (parity)
  straddle       C + P at the strike nearest F; post value at R = the same
                 contracts' R closes, intrinsic if they expire on R
  0.5-delta      the call / put whose Black-76 delta is nearest +/-0.5
  implied move   straddle / S at E
  ATM IV         front-expiry ATM IV at E-5..E (fixed expiry; the run-up)
  skew           IV of the OTM put nearest K/F = 0.95 minus the OTM call
                 nearest K/F = 1.05 (each within 0.92-0.98 / 1.02-1.08), and
                 OTM put IV minus ATM IV
Realized move: ln(adj close R / adj close E), and the open gap at R.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from nn_meta import v8_vol

TZ = "America/New_York"
RUNUP = 5
CRUSH = 0.10


def event_days(tau_utc: pd.Series, days: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """(entry index, reaction index) on the trading-day grid; -1 off grid."""
    close = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(TZ) + pd.Timedelta(hours=16)
    t = pd.to_datetime(tau_utc, utc=True).dt.tz_convert(TZ)
    r = np.searchsorted(close.asi8, t.astype("int64").to_numpy(), side="right")
    e = r - 1
    bad = (r >= len(days)) | (e < 0)
    return np.where(bad, -1, e), np.where(bad, -1, r)


def forward(day: pd.DataFrame, S: float) -> float:
    pv = day.pivot_table(index="strike", columns="cp", values="close", aggfunc="last")
    if "C" not in pv or "P" not in pv:
        return float("nan")
    pv = pv.dropna()
    if pv.empty:
        return float("nan")
    near = (pv.index.to_series() - S).abs().sort_values(kind="stable").index[:3]
    return float(np.median(near + pv.loc[near, "C"] - pv.loc[near, "P"]))


def _iv(rows: pd.DataFrame, F: float, T: float) -> np.ndarray:
    return v8_vol.implied_vol(rows["close"].to_numpy(), F, rows["strike"].to_numpy(), T,
                              (rows["cp"] == "C").to_numpy())


def atm_iv(day: pd.DataFrame, S: float, T: float) -> tuple[float, float]:
    """(F, ATM IV) for one expiry's chain on one day: OTM options within 5% of
    F, linear in log-moneyness between the nearest strike either side."""
    F = forward(day, S)
    if not np.isfinite(F) or T <= 0:
        return F, float("nan")
    d = day.assign(lm=np.log(day["strike"] / F))
    otm = ((d["cp"] == "C") & (d["lm"] >= 0)) | ((d["cp"] == "P") & (d["lm"] < 0))
    d = d[otm & (d["lm"].abs() <= 0.05) & (d["close"] >= 0.05)]
    if d.empty:
        return F, float("nan")
    d = d.assign(iv=_iv(d, F, T)).dropna(subset=["iv"])
    b, a = d[d["lm"] < 0], d[d["lm"] >= 0]
    if len(b) and len(a):
        b, a = b.loc[b["lm"].idxmax()], a.loc[a["lm"].idxmin()]
        w = -b["lm"] / (a["lm"] - b["lm"]) if a["lm"] != b["lm"] else 0.0
        return F, float(b["iv"] + w * (a["iv"] - b["iv"]))
    if len(b) or len(a):
        x = b if len(b) else a
        return F, float(x.loc[x["lm"].abs().idxmin(), "iv"])
    return F, float("nan")


def _otm_iv(day: pd.DataFrame, F: float, T: float, cp: str, target: float,
            lo: float, hi: float) -> float:
    d = day[(day["cp"] == cp) & (day["close"] >= 0.05)]
    m = d["strike"] / F
    d = d[(m >= lo) & (m <= hi)]
    if d.empty:
        return float("nan")
    r = d.loc[[(d["strike"] / F - target).abs().idxmin()]]
    return float(_iv(r, F, T)[0])


def _delta_pick(day: pd.DataFrame, F: float, T: float, cp: str) -> pd.Series | None:
    d = day[(day["cp"] == cp) & (day["close"] > 0)]
    if d.empty:
        return None
    iv = _iv(d, F, T)
    ok = np.isfinite(iv)
    if not ok.any():
        return None
    d = d[ok].assign(iv=iv[ok])
    d1 = (np.log(F / d["strike"]) + 0.5 * d["iv"] ** 2 * T) / (d["iv"] * math.sqrt(T))
    nd1 = 0.5 * (1 + np.vectorize(math.erf)(d1 / math.sqrt(2)))
    d = d.assign(delta=nd1 if cp == "C" else nd1 - 1)
    target = 0.5 if cp == "C" else -0.5
    return d.loc[(d["delta"] - target).abs().idxmin()]


def _close(ch: pd.DataFrame, day: str, expiry: str, cp: str, K: float) -> float:
    x = ch[(ch["date"] == day) & (ch["expiry"] == expiry) & (ch["cp"] == cp)
           & (ch["strike"] == K) & (ch["volume"] > 0)]
    return float(x["close"].iloc[-1]) if len(x) else float("nan")


def _post(ch, R, expiry, cp, K, S_R) -> tuple[float, str]:
    p = _close(ch, R, expiry, cp, K)
    if np.isfinite(p):
        return p, "traded"
    if expiry == R and np.isfinite(S_R):
        return (max(S_R - K, 0.0) if cp == "C" else max(K - S_R, 0.0)), "intrinsic"
    return float("nan"), "missing"


def _years(day: str, expiry: str) -> float:
    # expiry at its 16:00 close; one trading-day floor so same-day expiries price
    return max((pd.Timestamp(expiry) - pd.Timestamp(day)).days, 0.5) / 365


def event_row(ev: dict, ch: pd.DataFrame, days: list[str], px: pd.DataFrame) -> dict:
    """ev: ticker, accession, tau_utc, e, r (grid indices). ch: the ticker's
    chain rows for days[e-RUNUP .. r]. px: the ticker's daily bars indexed by date."""
    E, R = days[ev["e"]], days[ev["r"]]
    out = {"entry_day": E, "reaction_day": R, "status": "ok"}
    if E not in px.index or R not in px.index:
        out["status"] = "no_bars"
        return out
    S, S_R = float(px.at[E, "close"]), float(px.at[R, "close"])
    adj_ret = math.log(px.at[R, "adj_close"] / px.at[E, "adj_close"])
    out.update(S_entry=S, S_reaction=S_R, realized_move=adj_ret,
               reaction_gap=math.log(px.at[R, "adj_open"] / px.at[E, "adj_close"]),
               split_between=abs(math.log(S_R / S) - adj_ret) > 0.01)
    on_e = ch[(ch["date"] == E) & (ch["volume"] > 0) & (ch["close"] > 0)]
    exps = sorted(x for x in on_e["expiry"].unique() if x >= R)
    if not exps:
        out["status"] = "no_front_expiry"
        return out
    front = exps[0]
    nxt = exps[1] if len(exps) > 1 else None
    T = _years(E, front)
    out.update(front_expiry=front, front_dte=(pd.Timestamp(front) - pd.Timestamp(E)).days,
               front_days_after_reaction=(pd.Timestamp(front) - pd.Timestamp(R)).days,
               next_expiry=nxt)
    fe = on_e[on_e["expiry"] == front]
    F, iv0 = atm_iv(fe, S, T)
    out.update(F_entry=F, atm_iv_front=iv0)
    if not np.isfinite(F):
        out["status"] = "no_forward"
        return out
    # straddle at the strike nearest F with both legs traded on E
    pv = fe.pivot_table(index="strike", columns="cp", values="close", aggfunc="last")
    pv = pv.dropna() if {"C", "P"} <= set(pv.columns) else pv.iloc[0:0]
    if pv.empty:
        out["status"] = "no_straddle"
        return out
    K = float((pv.index.to_series() - F).abs().idxmin())
    c0, p0 = float(pv.at[K, "C"]), float(pv.at[K, "P"])
    vol = fe[fe["strike"] == K].groupby("cp")["volume"].sum()
    out.update(straddle_strike=K, call_atm_entry=c0, put_atm_entry=p0,
               straddle_entry=c0 + p0, implied_move=(c0 + p0) / S,
               call_atm_volume=int(vol.get("C", 0)), put_atm_volume=int(vol.get("P", 0)))
    c1, hc = _post(ch, R, front, "C", K, S_R)
    p1, hp = _post(ch, R, front, "P", K, S_R)
    out.update(call_atm_reaction=c1, put_atm_reaction=p1, straddle_reaction=c1 + p1,
               straddle_exit_how="+".join(sorted({hc, hp})))
    for cp, name in (("C", "call50"), ("P", "put50")):
        row = _delta_pick(fe, F, T, cp)
        if row is None:
            continue
        x1, how = _post(ch, R, front, cp, float(row["strike"]), S_R)
        out.update({f"{name}_strike": float(row["strike"]), f"{name}_delta": float(row["delta"]),
                    f"{name}_iv": float(row["iv"]), f"{name}_entry": float(row["close"]),
                    f"{name}_reaction": x1, f"{name}_exit_how": how})
    put95 = _otm_iv(fe, F, T, "P", 0.95, 0.92, 0.98)
    call105 = _otm_iv(fe, F, T, "C", 1.05, 1.02, 1.08)
    out.update(iv_put95=put95, iv_call105=call105, skew_put_call=put95 - call105,
               skew_put_atm=put95 - iv0)
    if nxt is not None:
        ne = on_e[on_e["expiry"] == nxt]
        out.update(next_dte=(pd.Timestamp(nxt) - pd.Timestamp(E)).days,
                   atm_iv_next=atm_iv(ne, S, _years(E, nxt))[1])
    # fixed-expiry ATM IV run-up over E-RUNUP .. E, and the crush on R
    ivs = {}
    for k in range(-RUNUP, 2):
        i = ev["e"] + k
        if i < 0 or i >= len(days) or days[i] not in px.index:
            continue
        d = days[i]
        dd = ch[(ch["date"] == d) & (ch["expiry"] == front) & (ch["volume"] > 0) & (ch["close"] > 0)]
        if d > front or dd.empty:
            continue
        ivs[k] = atm_iv(dd, float(px.at[d, "close"]), _years(d, front))[1]
    for k in range(-RUNUP, 2):
        out[f"atm_iv_front_e{k:+d}"] = ivs.get(k, float("nan"))
    iv_m1, iv_e, iv_r = (ivs.get(k, float("nan")) for k in (-1, 0, 1))
    out["iv_runup"] = iv_e / ivs.get(-RUNUP, float("nan")) - 1
    d_e, d_r = iv_e / iv_m1 - 1, iv_r / iv_e - 1
    out["iv_crush_day_before"] = bool(np.isfinite(d_e) and np.isfinite(d_r)
                                      and d_e < -CRUSH and d_e < d_r)
    return out


def preannouncement_flags(ev: pd.DataFrame, filings: pd.DataFrame, days: int = 30) -> np.ndarray:
    """True for an Item 2.02 8-K followed by another Item 2.02 8-K from the same
    ticker within `days` calendar days: an unscheduled pre-announcement (or a
    non-earnings 2.02 such as quarterly deliveries), whose date nobody knew in
    advance. Uses filing dates only, never prices."""
    f = filings[(filings["form"] == "8-K")
                & filings["items"].fillna("").str.contains("2.02", regex=False)]
    t = pd.to_datetime(f["acceptance_utc"], utc=True)
    by = {k: pd.DatetimeIndex(g.sort_values()) for k, g in t.groupby(f["ticker"])}
    out = np.zeros(len(ev), bool)
    for j, (tk, tau) in enumerate(zip(ev["ticker"], pd.to_datetime(ev["tau_utc"], utc=True))):
        later = by.get(tk, pd.DatetimeIndex([], tz="UTC"))
        later = later[later > tau]
        out[j] = len(later) > 0 and (later[0] - tau) <= pd.Timedelta(days=days)
    return out
