# scripts/run_uv1_midday_fade.py — UV1: fade the morning move at 10:30 Central.
"""Implements docs/specs/UV1_MIDDAY_FADE_PREREG_20261011.json (frozen 2026-10-11).

  fetch   Alpaca calendar, SIP 1-minute SPY/QQQ bars (09:30-13:59 ET kept),
          same-day option contracts and the selected contracts' 1-minute bars
          (11:30-13:36 ET). Resumable; raw files under nn_meta/data_cache_uv1/.
  run     The single pre-registered evaluation. Refuses to overwrite its output.

Decision 11:30 ET from the 11:29 bar close; entry 11:30 bar VWAP; exit 13:30
bar VWAP. Filter |m| >= 1% (m = 11:29 close / 09:30 open - 1) skips. Signal A
bets against m; signal B against the 15-minute bar 11:15 open -> 11:29 close.
Options: first strike OTM on the bet's side, same-day expiry, buy mid x 1.05,
sell mid x 0.95, $0.05/contract/side fees (mid = fill-minute trade VWAP).
Stock: 1 bp per side (stress 2 bp). Read-only data keys: ALPACA_PAPER_* (the
retired V6 account, as the OI recorder), so the V8 H1 paper budget is untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy import stats

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta.v8_parallel import RateLimiter  # noqa: E402

SPEC = REPO / "docs" / "specs" / "UV1_MIDDAY_FADE_PREREG_20261011.json"
CACHE = REPO / "nn_meta" / "data_cache_uv1"
OUT = REPO / "nn_meta" / "validation" / "uv1-midday-fade-20261011-r0"
TICKERS = ("SPY", "QQQ")
START, END = "2016-01-01", "2026-10-09"
OPT_FROM = "2024-01-02"          # first session with option bars is found in the data
DEV_END, CONF_START = "2025-12-31", "2026-01-02"
DATA = "https://data.alpaca.markets"
TRADE_API = "https://paper-api.alpaca.markets"
LIMIT = RateLimiter(150)
ET = "America/New_York"
THRESH = 0.01
OPT_COST, OPT_FEE = 0.05, 0.05 / 100      # fraction of mid per side; $ per share-equivalent
STOCK_COST, STOCK_STRESS = 1e-4, 2e-4
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")


# ---------------------------------------------------------------- fetch
def _get(url: str, headers: dict, params: dict) -> dict:
    for attempt in range(8):
        LIMIT.acquire()
        try:
            r = requests.get(url, headers=headers, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * (attempt + 1)); continue
        r.raise_for_status()
        return r.json()
    raise SystemExit(f"GET failed: {url} {params}")


def _pages(url: str, headers: dict, params: dict, key: str) -> list:
    out, token = [], None
    while True:
        j = _get(url, headers, dict(params, **({"page_token": token} if token else {})))
        v = j.get(key) or []
        out.append(v)
        token = j.get("next_page_token")
        if not token:
            return out


def fetch_calendar(h: dict) -> pd.DataFrame:
    p = CACHE / "calendar.parquet"
    if not p.exists():
        cal = pd.DataFrame(_get(f"{TRADE_API}/v2/calendar", h, {"start": START, "end": END}))
        cal[["date", "open", "close"]].to_parquet(p)
    return pd.read_parquet(p)


def fetch_stock_year(h: dict, sym: str, year: int) -> None:
    p = CACHE / "stock" / f"{sym}_{year}.parquet"
    if p.exists():
        return
    end = min(f"{year}-12-31", END)
    pages = _pages(f"{DATA}/v2/stocks/bars", h, {
        "symbols": sym, "timeframe": "1Min", "feed": "sip", "adjustment": "raw",
        "start": f"{year}-01-01T00:00:00Z", "end": f"{end}T23:59:59Z", "limit": 10000}, "bars")
    rows = [b for pg in pages for b in (pg.get(sym) or [])]
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(ET)
    hm = df["t"].dt.strftime("%H:%M")
    df = df[(hm >= "09:30") & (hm <= "13:59")]
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)


def load_stock(sym: str) -> pd.DataFrame:
    df = pd.concat([pd.read_parquet(p) for p in sorted((CACHE / "stock").glob(f"{sym}_*.parquet"))])
    df["date"] = df["t"].dt.strftime("%Y-%m-%d")
    df["hm"] = df["t"].dt.strftime("%H:%M")
    return df


def fetch_contracts_month(h: dict, sym: str, month: str) -> None:
    p = CACHE / "contracts" / f"{sym}_{month}.parquet"
    if p.exists():
        return
    lo = f"{month}-01"
    hi = (pd.Timestamp(lo) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
    hi = min(hi, END)
    rows = []
    for status in ("inactive", "active"):
        for pg in _pages(f"{TRADE_API}/v2/options/contracts", h, {
                "underlying_symbols": sym, "expiration_date_gte": lo, "expiration_date_lte": hi,
                "status": status, "limit": 10000}, "option_contracts"):
            rows += pg
    df = pd.DataFrame([{"symbol": r["symbol"], "expiry": r["expiration_date"],
                        "cp": r["type"][0].upper(), "strike": float(r["strike_price"])} for r in rows])
    p.parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("symbol").to_parquet(p)


def decision_prices(stock: pd.DataFrame) -> pd.DataFrame:
    """Per session: 09:30 open, 11:15 open, 11:29 close, 11:30 and 13:30 VWAP."""
    g = stock.set_index(["date", "hm"])
    def col(hm, f):
        s = g.xs(hm, level="hm")[f]
        return s[~s.index.duplicated()]
    return pd.DataFrame({"open0930": col("09:30", "o"), "open1115": col("11:15", "o"),
                         "close1129": col("11:29", "c"), "vw1130": col("11:30", "vw"),
                         "vw1330": col("13:30", "vw")})


def select_contracts(sessions: list[str]) -> pd.DataFrame:
    rows = []
    for sym in TICKERS:
        px = decision_prices(load_stock(sym))
        ct = pd.concat([pd.read_parquet(p) for p in sorted((CACHE / "contracts").glob(f"{sym}_*.parquet"))])
        by_exp = {e: g for e, g in ct.groupby("expiry")}
        for d in sessions:
            spot = px["close1129"].get(d, np.nan)
            g = by_exp.get(d)
            r = {"date": d, "ticker": sym, "spot": spot, "call": None, "put": None,
                 "has_expiry": g is not None}
            if g is not None and np.isfinite(spot):
                c = g[(g.cp == "C") & (g.strike > spot)].sort_values("strike")
                p = g[(g.cp == "P") & (g.strike < spot)].sort_values("strike")
                r["call"] = c.symbol.iloc[0] if len(c) else None
                r["put"] = p.symbol.iloc[-1] if len(p) else None
            rows.append(r)
    return pd.DataFrame(rows)


def fetch_option_day(h: dict, d: str, syms: list[str]) -> None:
    p = CACHE / "option_bars" / f"{d}.parquet"
    if p.exists() or not syms:
        return
    s = pd.Timestamp(f"{d} 11:30", tz=ET).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    e = pd.Timestamp(f"{d} 13:36", tz=ET).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    pages = _pages(f"{DATA}/v1beta1/options/bars", h, {
        "symbols": ",".join(syms), "timeframe": "1Min", "start": s, "end": e, "limit": 10000}, "bars")
    rows = [dict(b, symbol=k) for pg in pages for k, v in pg.items() for b in v]
    df = pd.DataFrame(rows, columns=["symbol", "t", "o", "h", "l", "c", "v", "n", "vw"])
    if len(df):
        df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(ET)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)


def cmd_fetch() -> None:
    load_dotenv(REPO / ".env")
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_PAPER_API_KEY"],
         "APCA-API-SECRET-KEY": os.environ["ALPACA_PAPER_API_SECRET"]}
    CACHE.mkdir(parents=True, exist_ok=True)
    cal = fetch_calendar(h)
    jobs = [(s, y) for s in TICKERS for y in range(2016, 2027)]
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda j: fetch_stock_year(h, *j), jobs))
    print("stock bars done", flush=True)
    months = pd.period_range(OPT_FROM[:7], END[:7], freq="M").strftime("%Y-%m")
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda j: fetch_contracts_month(h, *j), [(s, m) for s in TICKERS for m in months]))
    print("contracts done", flush=True)
    sessions = cal[(cal.date >= OPT_FROM) & (cal.date <= END) & (cal.close == "16:00")].date.tolist()
    sel = select_contracts(sessions)
    sel.to_parquet(CACHE / "selection.parquet")
    per_day = sel.melt(id_vars="date", value_vars=["call", "put"]).dropna().groupby("date")["value"].apply(list)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda kv: fetch_option_day(h, kv[0], kv[1]), per_day.items()))
    print(f"option bars done: {len(per_day)} sessions", flush=True)


# ---------------------------------------------------------------- run
def option_leg(bars: pd.DataFrame) -> tuple[float, float, str]:
    """Entry/exit mids from one contract's 11:30-13:36 bars per the spec's fallbacks."""
    if bars is None or bars.empty:
        return np.nan, np.nan, "no_entry"
    hm = bars["t"].dt.strftime("%H:%M")
    b = bars[bars["v"] > 0].assign(hm=hm)
    ent = b[(b.hm >= "11:30") & (b.hm <= "11:35")]
    if ent.empty:
        return np.nan, np.nan, "no_entry"
    ex = b[(b.hm >= "13:30") & (b.hm <= "13:35")]
    if len(ex):
        return float(ent.vw.iloc[0]), float(ex.vw.iloc[0]), "vwap"
    late = b[(b.hm >= "13:25") & (b.hm <= "13:35")]
    if len(late):
        return float(ent.vw.iloc[0]), float(late.c.iloc[-1]), "last_trade"
    return float(ent.vw.iloc[0]), 0.0, "zero"


def build_trades(cal: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    full = cal[(cal.date >= "2016-01-04") & (cal.date <= END)]
    early = set(full[full.close != "16:00"].date)
    sessions = full[full.close == "16:00"].date.tolist()
    sel = pd.read_parquet(CACHE / "selection.parquet").set_index(["date", "ticker"])
    obars = {}
    for p in (CACHE / "option_bars").glob("*.parquet"):
        df = pd.read_parquet(p)
        for s, g in df.groupby("symbol"):
            obars[s] = g.sort_values("t")
    opt_first = min(p.stem for p in (CACHE / "option_bars").glob("*.parquet")
                    if len(pd.read_parquet(p)))
    rows, skips = [], {}
    for sym in TICKERS:
        px = decision_prices(load_stock(sym)).reindex(sessions)
        for d, r in px.iterrows():
            base = {"date": d, "ticker": sym, "dow": DAYS[pd.Timestamp(d).dayofweek]}
            if r.isna().any():
                skips[f"{sym}:missing_stock_bar"] = skips.get(f"{sym}:missing_stock_bar", 0) + 1
                continue
            m = r.close1129 / r.open0930 - 1
            b = r.close1129 / r.open1115 - 1
            for sig, x in (("A", m), ("B", b)):
                key = f"{sym}:{sig}"
                if abs(m) >= THRESH:
                    skips[f"{key}:moved_1pct"] = skips.get(f"{key}:moved_1pct", 0) + 1
                    continue
                if x == 0:
                    skips[f"{key}:zero"] = skips.get(f"{key}:zero", 0) + 1
                    continue
                bet = 1 if x < 0 else -1          # fade: down move -> bet up (call / long)
                raw = bet * (r.vw1330 - r.vw1130) / r.vw1130
                rows.append(dict(base, instrument="S", signal=sig, bet=bet, m=m, b=b,
                                 ret=raw - 2 * STOCK_COST, ret_stress=raw - 2 * STOCK_STRESS))
                if d < opt_first:
                    continue
                s = sel.loc[(d, sym)] if (d, sym) in sel.index else None
                if s is None or not s.has_expiry:
                    skips[f"{key}:no_expiry"] = skips.get(f"{key}:no_expiry", 0) + 1
                    continue
                cs = s.call if bet == 1 else s.put
                mid_in, mid_out, how = option_leg(obars.get(cs)) if cs else (np.nan, np.nan, "no_entry")
                if how == "no_entry":
                    skips[f"{key}:no_entry"] = skips.get(f"{key}:no_entry", 0) + 1
                    continue
                debit = mid_in * (1 + OPT_COST) + OPT_FEE
                credit = mid_out * (1 - OPT_COST) - OPT_FEE if mid_out > 0 else 0.0
                rows.append(dict(base, instrument="O", signal=sig, bet=bet, m=m, b=b,
                                 contract=cs, mid_in=mid_in, mid_out=mid_out, exit_how=how,
                                 ret=(credit - debit) / debit, dollars=100 * (credit - debit)))
    skips["early_close_sessions"] = len(early)
    skips["option_first_session"] = opt_first
    return pd.DataFrame(rows), skips


def half(d: pd.Series) -> pd.Series:
    t = pd.to_datetime(d)
    return t.dt.year.astype(str) + np.where(t.dt.month <= 6, "H1", "H2")


def tstat(x: np.ndarray) -> tuple[float, float, float]:
    n = len(x)
    if n < 2 or np.std(x, ddof=1) == 0:
        return float(np.mean(x)) if n else np.nan, np.nan, np.nan
    t = np.mean(x) / (np.std(x, ddof=1) / np.sqrt(n))
    return float(np.mean(x)), float(t), float(stats.t.sf(t, n - 1))


def describe(g: pd.DataFrame) -> dict:
    x = g.ret.to_numpy()
    mean, t, p = tstat(x)
    srt = np.sort(x)[::-1]
    tot = x.sum()
    out = {"n": int(len(x)), "mean": mean, "t": t, "p_one_sided": p,
           "median": float(np.median(x)) if len(x) else None,
           "hit_rate": float((x > 0).mean()) if len(x) else None,
           "mean_without_best": float(srt[1:].mean()) if len(x) > 1 else None,
           "top5_share_of_total": float(srt[:5].sum() / tot) if tot > 0 else None,
           "up_bets": {"n": int((g.bet == 1).sum()), "mean": float(g.ret[g.bet == 1].mean()) if (g.bet == 1).any() else None},
           "down_bets": {"n": int((g.bet == -1).sum()), "mean": float(g.ret[g.bet == -1].mean()) if (g.bet == -1).any() else None}}
    if "dollars" in g and g.dollars.notna().any():
        out["mean_dollars_per_contract"] = float(g.dollars.mean())
        out["exit_how"] = g.exit_how.value_counts().to_dict()
    return out


def cmd_run() -> None:
    spec = json.loads(SPEC.read_text())
    if spec.get("status") != "FROZEN":
        raise SystemExit("spec is not frozen")
    if (OUT / "report.json").exists():
        raise SystemExit(f"{OUT}/report.json exists: the dev run is single-shot")
    cal = pd.read_parquet(CACHE / "calendar.parquet")
    trades, skips = build_trades(cal)
    trades["fold"] = half(trades.date)
    dev = trades[trades.date <= DEV_END]
    conf = trades[trades.date >= CONF_START]
    folds_all = {"S": [f"{y}H{k}" for y in range(2016, 2026) for k in (1, 2)],
                 "O": [f"{y}H{k}" for y in (2024, 2025) for k in (1, 2)]}
    need = {"S": 14, "O": 3}
    res = {}
    for inst in ("O", "S"):
        for sig in ("A", "B"):
            for sym in TICKERS:
                for day in DAYS + ("All",):
                    name = f"{inst}_{sig}_{sym}_{day}"
                    sel = (dev.instrument == inst) & (dev.signal == sig) & (dev.ticker == sym)
                    if day != "All":
                        sel &= dev.dow == day
                    g = dev[sel]
                    v = describe(g)
                    fm = g.groupby("fold").ret.mean()
                    v["folds_positive"] = int(sum(fm.get(f, -1) > 0 for f in folds_all[inst]))
                    v["folds_total"] = len(folds_all[inst])
                    v["fold_means"] = {f: (float(fm[f]) if f in fm else None) for f in folds_all[inst]}
                    if inst == "S":
                        ms, ts, _ = tstat(g.ret_stress.to_numpy())
                        v["stress"] = {"mean": ms, "t": ts}
                    res[name] = v
    names = list(res)
    p = np.array([res[k]["p_one_sided"] if res[k]["p_one_sided"] == res[k]["p_one_sided"] else 1.0 for k in names])
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for i, j in enumerate(order):
        run = max(run, min(1.0, (m - i) * p[j]))
        adj[j] = run
    passes = []
    for k, a in zip(names, adj):
        v = res[k]
        inst = k[0]
        g = {"edge": bool(v["mean"] is not None and v["mean"] > 0 and (v["t"] or 0) >= 2),
             "multiple_testing": bool(a < 0.05),
             "folds": bool(v["folds_positive"] >= need[inst]),
             "cost_stress": bool(inst == "O" or (v["stress"]["mean"] > 0 and (v["stress"]["t"] or 0) >= 2))}
        v["holm_p"] = float(a)
        v["gates"] = g
        v["pass"] = all(g.values())
        if v["pass"]:
            passes.append(k)
    confirmation = {}
    for k in passes:
        inst, sig, sym, day = k.split("_")
        sel = (conf.instrument == inst) & (conf.signal == sig) & (conf.ticker == sym)
        if day != "All":
            sel &= conf.dow == day
        c = describe(conf[sel])
        c["pass"] = bool(c["mean"] is not None and c["mean"] > 0 and (c["t"] or 0) >= 1)
        confirmation[k] = c
    OUT.mkdir(parents=True, exist_ok=True)
    trades.to_parquet(OUT / "trades.parquet")
    report = {"spec": SPEC.name, "run_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
              "skips": skips, "variants": res, "dev_passes": passes, "confirmation": confirmation}
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(f"{'variant':16} {'n':>5} {'mean':>8} {'t':>6} {'holm':>6} {'folds':>6} {'hit':>5}  pass")
    for k in names:
        v = res[k]
        print(f"{k:16} {v['n']:5d} {v['mean']*100:7.3f}% {v['t']:6.2f} {v['holm_p']:6.3f} "
              f"{v['folds_positive']:2d}/{v['folds_total']:<3d} {v['hit_rate']*100:4.0f}%  {'PASS' if v['pass'] else '-'}")
    print("skips:", json.dumps(skips))
    print("dev passes:", passes or "none")
    for k, c in confirmation.items():
        print(f"confirm {k}: n {c['n']} mean {c['mean']*100:.3f}% t {c['t']:.2f} -> {'PASS' if c['pass'] else 'FAIL'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["fetch", "run"])
    a = ap.parse_args()
    cmd_fetch() if a.cmd == "fetch" else cmd_run()


if __name__ == "__main__":
    main()
