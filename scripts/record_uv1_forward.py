# scripts/record_uv1_forward.py — UV1 forward log (observation only, no orders).
"""Each trading afternoon, record what the UV1 rule (docs/specs/UV1_MIDDAY_FADE_PREREG_20261011.json)
would have done that day, for fresh out-of-sample evidence (user request 2026-10-11):

  10:30 CT decision: m = 11:29 ET close / 09:30 open - 1 for SPY and QQQ.
  0 < m < 1%  -> rule buys the first-OTM same-day PUT;  -1% < m < 0 -> the first-OTM CALL.
  Both the call and the put are recorded every day (so the opposite side can be read too),
  bought at the 11:30 ET minute VWAP and sold at the 13:30 ET minute VWAP (UV1 fallbacks),
  net of mid x 1.05 / x 0.95 and $0.05/contract/side.

Appends one row per ticker per full session to nn_meta/data_cache_uv1/forward/uv1_forward.csv,
catching up any missed sessions since START. Runs from healys-uv1-forward.timer at 14:05 ET
(Alpaca's free tier serves SIP bars 15 minutes after the fact). Read-only ALPACA_PAPER_* keys.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import run_uv1_midday_fade as uv1  # noqa: E402

START = "2026-10-12"
LOG = uv1.CACHE / "forward" / "uv1_forward.csv"


def utc(d: str, hm: str) -> str:
    return pd.Timestamp(f"{d} {hm}", tz=uv1.ET).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def stock_bars(h: dict, sym: str, d: str) -> pd.DataFrame:
    pages = uv1._pages(f"{uv1.DATA}/v2/stocks/bars", h, {
        "symbols": sym, "timeframe": "1Min", "feed": "sip", "adjustment": "raw",
        "start": utc(d, "09:30"), "end": utc(d, "13:59"), "limit": 10000}, "bars")
    df = pd.DataFrame([b for pg in pages for b in (pg.get(sym) or [])])
    if df.empty:
        return df
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(uv1.ET)
    df["date"], df["hm"] = df["t"].dt.strftime("%Y-%m-%d"), df["t"].dt.strftime("%H:%M")
    return df


def same_day_contracts(h: dict, sym: str, d: str) -> pd.DataFrame:
    rows = []
    for status in ("active", "inactive"):
        for pg in uv1._pages(f"{uv1.TRADE_API}/v2/options/contracts", h, {
                "underlying_symbols": sym, "expiration_date": d, "status": status, "limit": 10000},
                "option_contracts"):
            rows += pg
    return pd.DataFrame([{"symbol": r["symbol"], "cp": r["type"][0].upper(),
                          "strike": float(r["strike_price"])} for r in rows]).drop_duplicates("symbol")


def option_bars(h: dict, syms: list[str], d: str) -> dict[str, pd.DataFrame]:
    pages = uv1._pages(f"{uv1.DATA}/v1beta1/options/bars", h, {
        "symbols": ",".join(syms), "timeframe": "1Min", "start": utc(d, "11:30"),
        "end": utc(d, "13:36"), "limit": 10000}, "bars")
    df = pd.DataFrame([dict(b, symbol=k) for pg in pages for k, v in pg.items() for b in v],
                      columns=["symbol", "t", "o", "h", "l", "c", "v", "n", "vw"])
    if df.empty:
        return {}
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(uv1.ET)
    return {s: g.sort_values("t") for s, g in df.groupby("symbol")}


def net(mid_in: float, mid_out: float) -> float:
    debit = mid_in * (1 + uv1.OPT_COST) + uv1.OPT_FEE
    credit = mid_out * (1 - uv1.OPT_COST) - uv1.OPT_FEE if mid_out > 0 else 0.0
    return (credit - debit) / debit


def record_day(h: dict, d: str) -> list[dict]:
    out = []
    for sym in uv1.TICKERS:
        st = stock_bars(h, sym, d)
        row = {"date": d, "day": pd.Timestamp(d).strftime("%a"), "ticker": sym,
               "recorded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}
        px = uv1.decision_prices(st).reindex([d]).iloc[0] if not st.empty else None
        if px is None or px.isna().any():
            out.append(dict(row, note="missing stock bar")); continue
        m = px.close1129 / px.open0930 - 1
        side = "skip" if (m == 0 or abs(m) >= uv1.THRESH) else ("put" if m > 0 else "call")
        row.update(open_0930=px.open0930, spot_1129=px.close1129, morning_move_pct=round(m * 100, 3),
                   rule_buys=side, stock_move_1130_1330_pct=round((px.vw1330 / px.vw1130 - 1) * 100, 3))
        ct = same_day_contracts(h, sym, d)
        if ct.empty:
            out.append(dict(row, note="no same-day expiry")); continue
        spot = px.close1129
        c = ct[(ct.cp == "C") & (ct.strike > spot)].sort_values("strike")
        p = ct[(ct.cp == "P") & (ct.strike < spot)].sort_values("strike")
        legs = {"call": c.symbol.iloc[0] if len(c) else None, "put": p.symbol.iloc[-1] if len(p) else None}
        bars = option_bars(h, [s for s in legs.values() if s], d)
        for name, s in legs.items():
            mid_in, mid_out, how = uv1.option_leg(bars.get(s)) if s else (np.nan, np.nan, "no_entry")
            row.update({f"{name}_symbol": s, f"{name}_mid_in": mid_in, f"{name}_mid_out": mid_out,
                        f"{name}_exit": how,
                        f"{name}_net_pct": round(net(mid_in, mid_out) * 100, 2) if how != "no_entry" else np.nan})
        row["rule_net_pct"] = row.get(f"{side}_net_pct", np.nan) if side != "skip" else np.nan
        out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="record this session only (YYYY-MM-DD)")
    args = ap.parse_args()
    load_dotenv(REPO / ".env")
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_PAPER_API_KEY"],
         "APCA-API-SECRET-KEY": os.environ["ALPACA_PAPER_API_SECRET"]}
    now = pd.Timestamp.now(tz=uv1.ET)
    today = now.strftime("%Y-%m-%d")
    cal = pd.DataFrame(uv1._get(f"{uv1.TRADE_API}/v2/calendar", h, {"start": args.date or START, "end": today}))
    full = cal[cal.close == "16:00"].date.tolist() if len(cal) else []
    if today in full and now.strftime("%H:%M") < "13:55":
        full.remove(today)                     # bars not yet available
    done = set(pd.read_csv(LOG).date) if LOG.exists() else set()
    todo = [args.date] if args.date else [d for d in full if d not in done]
    rows = [r for d in todo for r in record_day(h, d)]
    if not rows:
        print("nothing to record"); return
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    df = pd.concat([pd.read_csv(LOG), new], ignore_index=True) if LOG.exists() else new
    df.drop_duplicates(["date", "ticker"], keep="last").sort_values(["date", "ticker"]).to_csv(LOG, index=False)
    cols = ["date", "ticker", "morning_move_pct", "rule_buys", "stock_move_1130_1330_pct", "call_net_pct", "put_net_pct", "rule_net_pct"]
    print(new[[c for c in cols if c in new]].to_string(index=False))


if __name__ == "__main__":
    main()
