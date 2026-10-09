# scripts/run_v9_otm_paper.py — V9 forward paper observation: 20% OTM earnings legs.
"""User decision 2026-10-08: paper-trade the payoff thesis forward (buy the 20%
OTM call and put before every scheduled earnings release of the frozen pool,
half Kelly at 0.25% of equity per leg, 25% daily premium cap). This is an
observation, not a validated edge: the out-of-sample backtest FAILED after
excluding pre-announcements (docs/EXPERIMENTS.md, 2026-10-08). Its value is
real fills on penny options and a forward record of earnings shocks.

  plan       refresh upcoming releases (Finnhub calendar, next 14 days, frozen
             2026-08 pool tech names); timing from the calendar's bmo/amc, else
             the company's usual session from its past 8-K acceptance times
  trade      15:45 ET: exits for positions whose reaction day is today (sell at
             the bid; worthless legs are left to expire), then entries for
             releases whose entry day is today (last close before the release):
             front expiry on/after the reaction day, strikes nearest spot x 1.20
             and x 0.80 (within 2%), limit buy at the ask, qty = floor(0.25% of
             equity / (ask x 100))
  reconcile  after the close: fills and an equity mark
  status     print the ledger

Orders only with --live, only in the dedicated V9 paper account
(ALPACA_V9_PAPER_API_KEY / _SECRET); the runner refuses the V6 and V8 H1
accounts. Client order IDs are deterministic, so reruns cannot double-order.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

STATE = REPO / "nn_meta" / "validation" / "v9-paper-otm"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
FILINGS = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0" / "sec" / "filings.parquet"
TRADE = "https://paper-api.alpaca.markets/v2"
DATA = "https://data.alpaca.markets"
TZ = "America/New_York"
FROZEN_MONTH = "2026-08"
LEG_FRACTION = 0.0025
DAY_CAP = 0.25
OTM = 0.20
TOL = 0.02
REFUSE = {"PA3WD22T4IM7": "V6", "PA3U9D8Q8GQX": "V8 H1 (stonks bot 2)"}


def env() -> dict:
    out = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def req(method, url, headers=None, params=None, body=None):
    for attempt in range(5):
        r = requests.request(method, url, headers=headers, params=params, json=body, timeout=60)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(3 * (attempt + 1)); continue
        if r.status_code >= 400:
            raise SystemExit(f"{method} {url} -> {r.status_code} {r.text[:300]}")
        return r.json()
    raise SystemExit(f"{method} {url} failed after retries")


def alpaca_headers() -> dict:
    e = env()
    if not e.get("ALPACA_V9_PAPER_API_KEY") or not e.get("ALPACA_V9_PAPER_API_SECRET"):
        raise SystemExit("set ALPACA_V9_PAPER_API_KEY / ALPACA_V9_PAPER_API_SECRET in .env "
                         "(a new, empty Alpaca paper account)")
    h = {"APCA-API-KEY-ID": e["ALPACA_V9_PAPER_API_KEY"], "APCA-API-SECRET-KEY": e["ALPACA_V9_PAPER_API_SECRET"]}
    acct = req("GET", f"{TRADE}/account", h)
    if acct.get("account_number") in REFUSE:
        raise SystemExit(f"refusing: these keys belong to the {REFUSE[acct['account_number']]} account")
    return h


def db() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(STATE / "ledger.sqlite3")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS events (ticker TEXT, release_date TEXT, session TEXT, session_source TEXT,
      entry_day TEXT, reaction_day TEXT, updated_at TEXT, PRIMARY KEY (ticker, release_date));
    CREATE TABLE IF NOT EXISTS legs (ticker TEXT, entry_day TEXT, side TEXT, symbol TEXT, expiry TEXT,
      strike REAL, spot REAL, qty INTEGER, decision_bid REAL, decision_ask REAL, entry_order TEXT,
      entry_fill REAL, reaction_day TEXT, exit_order TEXT, exit_fill REAL, status TEXT, note TEXT,
      PRIMARY KEY (ticker, entry_day, side));
    CREATE TABLE IF NOT EXISTS marks (day TEXT PRIMARY KEY, cash REAL, equity REAL);
    CREATE TABLE IF NOT EXISTS runs (at TEXT, command TEXT, live INTEGER, summary TEXT);
    """)
    return c


def pool_tickers() -> list[str]:
    return sorted(json.loads(POOL.read_text())["months"][FROZEN_MONTH]["tech"])


def usual_session(ticker: str, filings: pd.DataFrame) -> str | None:
    f = filings[(filings["ticker"] == ticker) & (filings["form"] == "8-K")
                & filings["items"].fillna("").str.contains("2.02", regex=False)]
    if len(f) < 3:
        return None
    t = pd.to_datetime(f["acceptance_utc"], utc=True).dt.tz_convert(TZ).tail(8)
    h = t.dt.hour + t.dt.minute / 60
    s = pd.Series(["bmo" if x < 9.5 else ("amc" if x >= 16 else "dmh") for x in h]).value_counts()
    return s.index[0] if s.iloc[0] >= 0.75 * len(h) else None


def trading_days(h) -> list[str]:
    today = pd.Timestamp.now(tz=TZ)
    cal = req("GET", f"{TRADE}/calendar", h, {"start": (today - pd.Timedelta(days=30)).strftime("%Y-%m-%d"),
                                               "end": (today + pd.Timedelta(days=60)).strftime("%Y-%m-%d")})
    return [c["date"] for c in cal]


def entry_reaction(release: str, session: str, days: list[str]) -> tuple[str, str] | None:
    """amc on D: enter D's close, react D+1; bmo on D: enter D-1's close, react D."""
    if release not in days:
        return None
    i = days.index(release)
    if session == "amc":
        return (days[i], days[i + 1]) if i + 1 < len(days) else None
    if session == "bmo":
        return (days[i - 1], days[i]) if i >= 1 else None
    return None


def cmd_plan(c, h) -> str:
    e = env()
    today = pd.Timestamp.now(tz=TZ).normalize()
    cal = req("GET", "https://finnhub.io/api/v1/calendar/earnings", None,
              {"from": today.strftime("%Y-%m-%d"), "to": (today + pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
               "token": e["FINNHUB_API_KEY"]})["earningsCalendar"]
    tick = set(pool_tickers())
    filings = pd.read_parquet(FILINGS)
    days = trading_days(h)
    n = skipped = 0
    for x in cal:
        if x["symbol"] not in tick:
            continue
        session, src = (x["hour"], "finnhub") if x["hour"] in ("bmo", "amc") else (usual_session(x["symbol"], filings), "history")
        er = entry_reaction(x["date"], session or "", days)
        if er is None:
            skipped += 1
        c.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?)",
                  (x["symbol"], x["date"], session or "unknown", src, er[0] if er else None,
                   er[1] if er else None, pd.Timestamp.now(tz="UTC").isoformat()))
        n += 1
    c.commit()
    return f"{n} pool releases in the next 14 days ({skipped} with unknown timing are not traded)"


def latest_spot(ticker, h) -> float:
    j = req("GET", f"{DATA}/v2/stocks/{ticker}/trades/latest", h, {"feed": "iex"})
    return float(j["trade"]["p"])


def pick_legs(ticker, spot, reaction_day, h) -> dict:
    lte = (pd.Timestamp(reaction_day) + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    cons = req("GET", f"{TRADE}/options/contracts", h, {"underlying_symbols": ticker, "expiration_date_gte": reaction_day,
                                                        "expiration_date_lte": lte, "limit": 10000})["option_contracts"]
    if not cons:
        return {}
    front = min(x["expiration_date"] for x in cons)
    out = {}
    for side, cp, target in (("call", "call", spot * (1 + OTM)), ("put", "put", spot * (1 - OTM))):
        cand = [x for x in cons if x["expiration_date"] == front and x["type"] == cp]
        if not cand:
            continue
        best = min(cand, key=lambda x: abs(float(x["strike_price"]) - target))
        if abs(float(best["strike_price"]) / target - 1) <= TOL:
            out[side] = {"symbol": best["symbol"], "strike": float(best["strike_price"]), "expiry": front}
    if out:
        snaps = req("GET", f"{DATA}/v1beta1/options/snapshots", h,
                    {"symbols": ",".join(v["symbol"] for v in out.values()), "feed": "indicative"})["snapshots"]
        for v in out.values():
            q = (snaps.get(v["symbol"]) or {}).get("latestQuote") or {}
            v["bid"], v["ask"] = float(q.get("bp") or 0), float(q.get("ap") or 0)
    return out


def order(h, symbol, qty, side, limit, cid, live) -> str | None:
    if not live:
        return None
    body = {"symbol": symbol, "qty": str(qty), "side": side, "type": "limit", "time_in_force": "day",
            "limit_price": f"{limit:.2f}", "client_order_id": cid}
    return req("POST", f"{TRADE}/orders", h, body=body)["id"]


def cmd_trade(c, h, live) -> str:
    today = pd.Timestamp.now(tz=TZ).strftime("%Y-%m-%d")
    acct = req("GET", f"{TRADE}/account", h)
    equity = float(acct["equity"])
    msgs = []
    # exits first
    for tk, ed, side, sym, qty in c.execute(
            "SELECT ticker, entry_day, side, symbol, qty FROM legs WHERE reaction_day=? AND status='open'", (today,)).fetchall():
        snap = req("GET", f"{DATA}/v1beta1/options/snapshots", h, {"symbols": sym, "feed": "indicative"})["snapshots"]
        bid = float(((snap.get(sym) or {}).get("latestQuote") or {}).get("bp") or 0)
        if bid >= 0.01:
            oid = order(h, sym, qty, "sell", bid, f"v9otm-x-{sym}-{today}", live)
            c.execute("UPDATE legs SET exit_order=?, status=? WHERE ticker=? AND entry_day=? AND side=?",
                      (oid, "exiting" if live else "exit_dry", tk, ed, side))
            msgs.append(f"exit {sym} x{qty} @ {bid}")
        else:
            c.execute("UPDATE legs SET status='expire_worthless', note='no bid at exit' WHERE ticker=? AND entry_day=? AND side=?",
                      (tk, ed, side))
            msgs.append(f"leave {sym} (no bid)")
    # entries
    budget = DAY_CAP * equity
    for tk, rd in c.execute("SELECT ticker, reaction_day FROM events WHERE entry_day=?", (today,)).fetchall():
        spot = latest_spot(tk, h)
        legs = pick_legs(tk, spot, rd, h)
        for side in ("call", "put"):
            v = legs.get(side)
            if v is None:
                msgs.append(f"{tk} {side}: no strike within 2% of target"); continue
            if v["ask"] <= 0:
                msgs.append(f"{tk} {side}: no ask"); continue
            qty = math.floor(LEG_FRACTION * equity / (v["ask"] * 100))
            cost = qty * v["ask"] * 100
            if qty < 1 or cost > budget:
                msgs.append(f"{tk} {side}: qty {qty} (ask {v['ask']}) skipped"); continue
            budget -= cost
            oid = order(h, v["symbol"], qty, "buy", v["ask"], f"v9otm-e-{v['symbol']}-{today}", live)
            c.execute("INSERT OR REPLACE INTO legs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (tk, today, side, v["symbol"], v["expiry"], v["strike"], spot, qty, v["bid"], v["ask"],
                       oid, None, rd, None, None, "open" if live else "dry", None))
            msgs.append(f"buy {v['symbol']} x{qty} @ {v['ask']} (bid {v['bid']})")
    c.commit()
    return "; ".join(msgs) or "nothing due"


def cmd_reconcile(c, h) -> str:
    n = 0
    for col, st in (("entry_order", "entry_fill"), ("exit_order", "exit_fill")):
        for oid, tk, ed, side in c.execute(
                f"SELECT {col}, ticker, entry_day, side FROM legs WHERE {col} IS NOT NULL AND {st} IS NULL").fetchall():
            o = req("GET", f"{TRADE}/orders/{oid}", h)
            if o.get("filled_avg_price"):
                c.execute(f"UPDATE legs SET {st}=? WHERE ticker=? AND entry_day=? AND side=?",
                          (float(o["filled_avg_price"]), tk, ed, side)); n += 1
            elif o.get("status") in ("canceled", "expired", "rejected"):
                c.execute("UPDATE legs SET status=?, note=? WHERE ticker=? AND entry_day=? AND side=?",
                          (f"{col}_{o['status']}", o.get("status"), tk, ed, side))
    acct = req("GET", f"{TRADE}/account", h)
    c.execute("INSERT OR REPLACE INTO marks VALUES (?,?,?)",
              (pd.Timestamp.now(tz=TZ).strftime("%Y-%m-%d"), float(acct["cash"]), float(acct["equity"])))
    c.commit()
    return f"{n} fills recorded; equity {acct['equity']}"


def cmd_status(c) -> str:
    out = []
    for name in ("events", "legs", "marks"):
        df = pd.read_sql(f"SELECT * FROM {name}", c)
        out.append(f"== {name} ({len(df)})\n{df.tail(30).to_string(index=False) if len(df) else '(empty)'}")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "trade", "reconcile", "status"])
    ap.add_argument("--live", action="store_true", help="place orders (default: dry run)")
    args = ap.parse_args()
    c = db()
    if args.command == "status":
        print(cmd_status(c)); return
    h = alpaca_headers()
    summary = {"plan": lambda: cmd_plan(c, h), "trade": lambda: cmd_trade(c, h, args.live),
               "reconcile": lambda: cmd_reconcile(c, h)}[args.command]()
    c.execute("INSERT INTO runs VALUES (?,?,?,?)", (pd.Timestamp.now(tz="UTC").isoformat(), args.command,
                                                     int(args.live), summary))
    c.commit()
    print(summary)


if __name__ == "__main__":
    main()
