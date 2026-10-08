# scripts/run_v8_h1_paper.py — V8 H1 earnings-drift paper forward test (Alpaca paper).
"""Stock and call side by side on every H1 signal (user decision 2026-10-08).

  signals    refresh SEC filings/EPS facts for the pool, compute SUE events and
             today's top-tercile signals (run before 10:00 ET)
  trade      10:30 ET: exits due today, then entries into each book's free
             slots (stock: shares worth 1/10 of book equity; calls: ~45 DTE /
             0.60 delta, 5% of book equity in premium, marketable limit at the
             ask); quotes at decision time are recorded
  reconcile  after the close: fills, positions, per-book equity marks
  status     print the ledger

Orders are placed only with --live and only in the Alpaca paper account
(paper-api.alpaca.markets); the default is a dry run that prints the plan.
Client order IDs are deterministic, so a rerun cannot double-order.
Universe: the V8 pool's tech members frozen at 2026-08 (the PIT universe
cannot be refreshed without OPRA data). Books start at $50,000 each.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_event_signals as es  # noqa: E402
from nn_meta import v8_paper as vp  # noqa: E402
from nn_meta.v8_parallel import RateLimiter  # noqa: E402

_spec = importlib.util.spec_from_file_location("build_v8_sec", REPO / "scripts" / "build_v8_sec.py")
sec = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(sec)

STATE = REPO / "nn_meta" / "validation" / "v8-paper-h1"
EV = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0" / "sec"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
SIC = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0" / "sic.json"
FROZEN_MONTH = "2026-08"
BOOK_START = {"stock": 50_000.0, "call": 50_000.0}
CALL_PREMIUM_FRACTION = 0.05
TRADE = "https://paper-api.alpaca.markets/v2"
DATA = "https://data.alpaca.markets"
UA = {"User-Agent": "HealysBacktester research (mrhealy115@gmail.com)"}
SEC_LIMIT = RateLimiter(8 * 60)


# ── plumbing ─────────────────────────────────────────────────────────────────

def env() -> dict:
    out = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1); out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def alpaca_headers() -> dict:
    e = env()
    return {"APCA-API-KEY-ID": e["ALPACA_PAPER_API_KEY"], "APCA-API-SECRET-KEY": e["ALPACA_PAPER_API_SECRET"]}


def get(url, params=None, headers=None):
    for attempt in range(5):
        r = requests.get(url, params=params, headers=headers, timeout=60)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(3 * (attempt + 1)); continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def db() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(STATE / "ledger.sqlite3")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS positions (
      book TEXT, ticker TEXT, symbol TEXT, entry_day TEXT, exit_day TEXT, status TEXT,
      qty REAL, entry_fill REAL, exit_fill REAL, entry_order TEXT, exit_order TEXT,
      decision_bid REAL, decision_ask REAL, decision_json TEXT, sue REAL,
      PRIMARY KEY (book, ticker, entry_day));
    CREATE TABLE IF NOT EXISTS marks (day TEXT, book TEXT, cash REAL, positions_value REAL, equity REAL,
      PRIMARY KEY (day, book));
    CREATE TABLE IF NOT EXISTS runs (at TEXT, command TEXT, live INTEGER, summary TEXT);
    """)
    return c


def trading_days(h) -> list[str]:
    today = pd.Timestamp.now(tz=vp.TZ)
    cal = get(f"{TRADE}/calendar", {"start": "2025-01-01",
                                    "end": (today + pd.Timedelta(days=150)).strftime("%Y-%m-%d")}, h)
    return [c["date"] for c in cal]


def pool() -> tuple[list[str], dict[int, list[str]]]:
    p = json.loads(POOL.read_text())
    tech_all = sorted(set().union(*(set(v["tech"]) for v in p["months"].values())))
    frozen = sorted(p["months"][FROZEN_MONTH]["tech"])
    sic = json.loads(SIC.read_text())
    ciks: dict[int, list[str]] = {}
    for t in tech_all:
        if sic.get(t, {}).get("cik"):
            ciks.setdefault(int(sic[t]["cik"]), []).append(t)
    return frozen, ciks


# ── signals ──────────────────────────────────────────────────────────────────

def refresh_sec(ciks: dict[int, list[str]]) -> pd.DataFrame:
    """Backfill facts + live updates for issuers with new 10-Q/10-K filings."""
    base = pd.read_parquet(EV / "facts.parquet")
    base_f = pd.read_parquet(EV / "filings.parquet", columns=["cik", "accession"])
    live_p = STATE / "live_facts.parquet"
    live = pd.read_parquet(live_p) if live_p.exists() else base.iloc[0:0]
    known = set(base_f["accession"]) | set(live.get("accession", pd.Series(dtype=str)))
    new_rows = []
    for cik, tickers in ciks.items():
        SEC_LIMIT.acquire()
        subs = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=UA)
        rec = subs["filings"]["recent"]
        fresh = {rec["accessionNumber"][i]: (rec["acceptanceDateTime"][i], rec["filingDate"][i])
                 for i in range(len(rec["form"]))
                 if rec["form"][i] in ("10-Q", "10-K") and rec["accessionNumber"][i] not in known}
        if not fresh:
            continue
        SEC_LIMIT.acquire()
        facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", headers=UA)
        body = facts.get("facts", {}).get("us-gaap", {}).get("EarningsPerShareDiluted", {})
        for x in body.get("units", {}).get("USD/shares", []):
            if x["accn"] in fresh:
                acc, fd = fresh[x["accn"]]
                avail = sec.available_at(pd.Series([acc]), pd.Series([fd])).iloc[0]
                for t in tickers:
                    new_rows.append({"cik": cik, "ticker": t, "taxonomy": "us-gaap",
                                     "tag": "EarningsPerShareDiluted", "unit": "USD/shares",
                                     "start": x.get("start"), "end": x["end"], "val": x["val"],
                                     "fy": x.get("fy"), "fp": x.get("fp"), "form": x.get("form"),
                                     "filed": x["filed"], "accession": x["accn"], "frame": x.get("frame"),
                                     "available_at_utc": avail})
    if new_rows:
        live = pd.concat([live, pd.DataFrame(new_rows)], ignore_index=True)
        live.to_parquet(live_p, index=False)
    print(f"SEC: {len(new_rows)} new EPS facts", flush=True)
    return pd.concat([base, live], ignore_index=True)


def compute_signals(h) -> pd.DataFrame:
    frozen, ciks = pool()
    facts = refresh_sec(ciks)
    tickers = sorted({t for ts in ciks.values() for t in ts})
    sue = es.sue_table({"facts": facts, "tickers": tickers})
    days = trading_days(h)
    sig = vp.tercile_signals(sue, days)
    sig["tradeable"] = sig["ticker"].isin(frozen)
    sig.to_parquet(STATE / "signals.parquet", index=False)
    return sig


# ── market data ──────────────────────────────────────────────────────────────

def daily_bars(h, tickers: list[str], end: str) -> pd.DataFrame:
    start = (pd.Timestamp(end) - pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    j = get(f"{DATA}/v2/stocks/bars", {"symbols": ",".join(tickers), "timeframe": "1Day", "start": start,
                                      "end": end, "adjustment": "raw", "feed": "sip", "limit": 10000}, h)
    rows = [(s, b["t"][:10], b["c"], b["v"]) for s, bs in (j.get("bars") or {}).items() for b in bs]
    return pd.DataFrame(rows, columns=["ticker", "date", "close", "volume"])


def stock_quote(h, t):
    q = get(f"{DATA}/v2/stocks/{t}/quotes/latest", {"feed": "iex"}, h)["quote"]
    return float(q["bp"]), float(q["ap"])


def option_chain(h, t, today):
    lo = (pd.Timestamp(today) + pd.Timedelta(days=vp.CALL_DTE_LO)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(today) + pd.Timedelta(days=vp.CALL_DTE_HI)).strftime("%Y-%m-%d")
    rows, token = [], None
    while True:
        p = {"feed": "indicative", "expiration_date_gte": lo, "expiration_date_lte": hi, "limit": 1000}
        if token:
            p["page_token"] = token
        j = get(f"{DATA}/v1beta1/options/snapshots/{t}", p, h)
        for sym, v in (j.get("snapshots") or {}).items():
            q = v.get("latestQuote") or {}
            tail = sym[-15:]
            rows.append((sym, f"20{tail[:2]}-{tail[2:4]}-{tail[4:6]}", tail[6], int(tail[7:]) / 1000,
                         float(q.get("bp") or 0), float(q.get("ap") or 0)))
        token = j.get("next_page_token")
        if not token:
            break
    return pd.DataFrame(rows, columns=["symbol", "expiry", "cp", "strike", "bid", "ask"])


def submit(h, order: dict, live: bool) -> dict:
    if not live:
        return {"dry_run": True, **order}
    r = requests.post(f"{TRADE}/orders", json=order, headers=h, timeout=60)
    if r.status_code == 422 and "client_order_id" in r.text:      # already placed: idempotent
        return get(f"{TRADE}/orders:by_client_order_id", {"client_order_id": order["client_order_id"]}, h)
    r.raise_for_status()
    return r.json()


# ── books ────────────────────────────────────────────────────────────────────

def book_equity(c, book: str) -> float:
    m = c.execute("SELECT equity FROM marks WHERE book=? ORDER BY day DESC LIMIT 1", (book,)).fetchone()
    return float(m[0]) if m else BOOK_START[book]


def book_cash(c, book: str) -> float:
    spent = c.execute("SELECT COALESCE(SUM(qty*entry_fill*CASE WHEN ?='call' THEN 100 ELSE 1 END),0) "
                      "FROM positions WHERE book=? AND entry_fill IS NOT NULL", (book, book)).fetchone()[0]
    back = c.execute("SELECT COALESCE(SUM(qty*exit_fill*CASE WHEN ?='call' THEN 100 ELSE 1 END),0) "
                     "FROM positions WHERE book=? AND exit_fill IS NOT NULL", (book, book)).fetchone()[0]
    return BOOK_START[book] - spent + back


def trade(live: bool, force: bool) -> None:
    h = alpaca_headers()
    days = trading_days(h)
    today = pd.Timestamp.now(tz=vp.TZ).strftime("%Y-%m-%d")
    now = pd.Timestamp.now(tz=vp.TZ)
    if today not in days and not force:
        print(f"{today}: market closed"); return
    if now < pd.Timestamp(f"{today} 10:30", tz=vp.TZ) and not force:
        print("before 10:30 ET; refusing (use --force for a dry rehearsal)"); return
    c = db()
    plan = []
    # exits due
    due = c.execute("SELECT book, ticker, symbol, entry_day, qty FROM positions "
                    "WHERE status='open' AND exit_day<=?", (today,)).fetchall()
    for book, t, sym, ed, qty in due:
        if book == "stock":
            bid, ask = stock_quote(h, t)
            o = {"symbol": t, "qty": str(qty), "side": "sell", "type": "market", "time_in_force": "day",
                 "client_order_id": vp.client_order_id(book, t, ed, "sell")}
        else:
            ch = option_chain(h, t, today)
            q = ch[ch["symbol"] == sym]
            bid = float(q["bid"].iloc[0]) if len(q) else 0.0; ask = float(q["ask"].iloc[0]) if len(q) else 0.0
            o = {"symbol": sym, "qty": str(int(qty)), "side": "sell", "type": "limit", "time_in_force": "day",
                 "limit_price": f"{max(bid, 0.01):.2f}", "client_order_id": vp.client_order_id(book, t, ed, "sell")}
        res = submit(h, o, live)
        plan.append({"action": "exit", "book": book, "ticker": t, "bid": bid, "ask": ask, "order": o})
        if live:
            c.execute("UPDATE positions SET status='exiting', exit_order=? WHERE book=? AND ticker=? AND entry_day=?",
                      (res.get("id"), book, t, ed))
    # entries
    sig_p = STATE / "signals.parquet"
    if not sig_p.exists():
        print("no signals.parquet; run `signals` first"); return
    sig = pd.read_parquet(sig_p)
    todays = sig[(sig["exec_day"] == today) & sig["signal"] & sig["tradeable"]]
    if len(todays):
        prev = days[days.index(today) - 1]          # free SIP data stops 15 min ago
        bars = daily_bars(h, sorted(todays["ticker"].unique()), prev)
        bars = bars[bars["date"] < today]
        cand = []
        for t, g in bars.groupby("ticker"):
            g = g.sort_values("date").tail(20)
            adv20 = float((g["close"] * g["volume"]).median())
            if vp.admitted(float(g["close"].iloc[-1]), adv20, len(g)):
                cand.append((t, adv20, float(todays[todays["ticker"] == t]["sue"].iloc[-1])))
        cand = pd.DataFrame(cand, columns=["ticker", "adv20", "sue"])
        for book in ("stock", "call"):
            held = {r[0] for r in c.execute("SELECT ticker FROM positions WHERE book=? AND status IN ('open','pending')", (book,))}
            # a new signal on a held name extends its hold
            for t in set(cand["ticker"]) & held:
                c.execute("UPDATE positions SET exit_day=? WHERE book=? AND ticker=? AND status IN ('open','pending')",
                          (vp.exit_day(today, days), book, t))
            eq, cash = book_equity(c, book), book_cash(c, book)
            for t in vp.plan_entries(cand, held):
                row = cand[cand["ticker"] == t].iloc[0]
                if book == "stock":
                    bid, ask = stock_quote(h, t)
                    dollars = min(eq / vp.SLOTS, cash)
                    qty = math.floor(dollars / ask) if ask > 0 else 0
                    if qty <= 0:
                        continue
                    o = {"symbol": t, "qty": str(qty), "side": "buy", "type": "market", "time_in_force": "day",
                         "client_order_id": vp.client_order_id(book, t, today, "buy")}
                    sym, dec = t, {}
                else:
                    S = float(bars[bars["ticker"] == t].sort_values("date")["close"].iloc[-1])
                    pick = vp.pick_call_from_quotes(option_chain(h, t, today), today, S)
                    if pick is None:
                        plan.append({"action": "skip", "book": book, "ticker": t, "reason": "no qualifying call"}); continue
                    budget = min(CALL_PREMIUM_FRACTION * eq, cash)
                    qty = math.floor(budget / (pick["ask"] * 100))
                    if qty <= 0:
                        plan.append({"action": "skip", "book": book, "ticker": t, "reason": "premium above budget"}); continue
                    bid, ask = pick["bid"], pick["ask"]
                    o = {"symbol": pick["symbol"], "qty": str(qty), "side": "buy", "type": "limit",
                         "time_in_force": "day", "limit_price": f"{ask:.2f}",
                         "client_order_id": vp.client_order_id(book, t, today, "buy")}
                    sym, dec = pick["symbol"], pick
                cash -= qty * ask * (100 if book == "call" else 1)
                res = submit(h, o, live)
                plan.append({"action": "entry", "book": book, "ticker": t, "bid": bid, "ask": ask, "order": o})
                if live:
                    c.execute("INSERT OR IGNORE INTO positions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (book, t, sym, today, vp.exit_day(today, days), "pending", qty, None, None,
                               res.get("id"), None, bid, ask, json.dumps(dec, default=str), float(row["sue"])))
    c.execute("INSERT INTO runs VALUES (?,?,?,?)", (now.isoformat(), "trade", int(live), json.dumps(plan, default=str)))
    c.commit()
    print(json.dumps(plan, indent=1, default=str))


def reconcile() -> None:
    h = alpaca_headers()
    c = db()
    today = pd.Timestamp.now(tz=vp.TZ).strftime("%Y-%m-%d")
    for book, t, ed, eo, xo, status in c.execute(
            "SELECT book, ticker, entry_day, entry_order, exit_order, status FROM positions "
            "WHERE status IN ('pending','exiting')").fetchall():
        if status == "pending" and eo:
            o = get(f"{TRADE}/orders/{eo}", headers=h)
            if o["status"] == "filled":
                c.execute("UPDATE positions SET status='open', entry_fill=?, qty=? WHERE book=? AND ticker=? AND entry_day=?",
                          (float(o["filled_avg_price"]), float(o["filled_qty"]), book, t, ed))
            elif o["status"] in ("canceled", "expired", "rejected"):
                c.execute("UPDATE positions SET status='unfilled' WHERE book=? AND ticker=? AND entry_day=?", (book, t, ed))
        if status == "exiting" and xo:
            o = get(f"{TRADE}/orders/{xo}", headers=h)
            if o["status"] == "filled":
                c.execute("UPDATE positions SET status='closed', exit_fill=? WHERE book=? AND ticker=? AND entry_day=?",
                          (float(o["filled_avg_price"]), book, t, ed))
            elif o["status"] in ("canceled", "expired", "rejected"):
                c.execute("UPDATE positions SET status='open', exit_order=NULL WHERE book=? AND ticker=? AND entry_day=?",
                          (book, t, ed))
    pos = {p["symbol"]: float(p["market_value"]) for p in get(f"{TRADE}/positions", headers=h)}
    for book in ("stock", "call"):
        held = c.execute("SELECT symbol FROM positions WHERE book=? AND status IN ('open','exiting')", (book,)).fetchall()
        value = sum(pos.get(s, 0.0) for (s,) in held)
        cash = book_cash(c, book)
        c.execute("INSERT OR REPLACE INTO marks VALUES (?,?,?,?,?)", (today, book, cash, value, cash + value))
    c.commit()
    status()


def status() -> None:
    c = db()
    print(pd.read_sql("SELECT * FROM marks ORDER BY day DESC, book LIMIT 6", c).to_string(index=False))
    print(pd.read_sql("SELECT book, ticker, symbol, entry_day, exit_day, status, qty, entry_fill, exit_fill "
                      "FROM positions ORDER BY entry_day DESC LIMIT 30", c).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["signals", "trade", "reconcile", "status"])
    ap.add_argument("--live", action="store_true", help="place paper orders (default: dry run)")
    ap.add_argument("--force", action="store_true", help="ignore market-hours checks (dry rehearsal)")
    a = ap.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    if a.command == "signals":
        s = compute_signals(alpaca_headers())
        recent = s[s["signal"]].sort_values("exec_day").tail(10)
        print(recent[["ticker", "tau", "exec_day", "sue", "tradeable"]].to_string(index=False))
    elif a.command == "trade":
        trade(a.live, a.force)
    elif a.command == "reconcile":
        reconcile()
    else:
        status()


if __name__ == "__main__":
    main()
