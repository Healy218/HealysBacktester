# scripts/record_v9_open_interest.py — V9 OVE-0: daily open-interest recorder.
"""Forward-only data: Alpaca's free contracts endpoint reports each option's
open interest (with the date it is as of) and last close, but keeps no
history. Every run saves one snapshot for the V8 pool (tech members frozen at
2026-08 plus the 17 ETFs), expiries up to MAX_DTE calendar days out:

  <root>/<yyyy-mm-dd>/<HHMM>.parquet   symbol, underlying, expiry, cp, strike,
                                       open_interest, open_interest_date,
                                       close_price, close_price_date, fetched_at_utc

Runs twice a trading day (08:00 ET after OCC's overnight update, 18:00 ET);
analysis dedupes on (symbol, open_interest_date). Read-only reference data,
fetched with the retired V6 paper account's keys (ALPACA_PAPER_*) so the
recorder never spends the V8 H1 paper runner's rate budget. Per-day volume
is not recorded: Alpaca serves historical option daily bars on demand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta.v8_parallel import RateLimiter  # noqa: E402

POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
DEFAULT_ROOT = REPO / "nn_meta" / "data_cache_v9" / "open_interest"
URL = "https://paper-api.alpaca.markets/v2/options/contracts"
MAX_DTE = 60
LIMIT = RateLimiter(150)
BATCH = 10


def universe() -> list[str]:
    pool = json.loads(POOL.read_text())
    return sorted(set(pool["months"]["2026-08"]["tech"]) | set(pool["rule"]["etfs_every_month"]))


def fetch(symbols: list[str], headers: dict, today: str) -> list[dict]:
    lte = (datetime.fromisoformat(today) + timedelta(days=MAX_DTE)).date().isoformat()
    params = {"underlying_symbols": ",".join(symbols), "expiration_date_gte": today,
              "expiration_date_lte": lte, "limit": 10000}
    rows, token = [], None
    while True:
        p = dict(params, **({"page_token": token} if token else {}))
        for attempt in range(6):
            LIMIT.acquire()
            try:
                r = requests.get(URL, headers=headers, params=p, timeout=60)
            except requests.RequestException:
                time.sleep(2 * (attempt + 1)); continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1)); continue
            r.raise_for_status()
            break
        else:
            raise SystemExit(f"contracts fetch failed for {symbols[0]}..")
        j = r.json()
        rows += j.get("option_contracts") or []
        token = j.get("next_page_token")
        if not token:
            return rows


def to_frame(rows: list[dict], fetched_at: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    out = pd.DataFrame({
        "symbol": df["symbol"], "underlying": df["underlying_symbol"],
        "expiry": df["expiration_date"], "cp": df["type"].str[0].str.upper(),
        "strike": pd.to_numeric(df["strike_price"]),
        "open_interest": pd.to_numeric(df.get("open_interest"), errors="coerce"),
        "open_interest_date": df.get("open_interest_date"),
        "close_price": pd.to_numeric(df.get("close_price"), errors="coerce"),
        "close_price_date": df.get("close_price_date"),
    })
    out["fetched_at_utc"] = fetched_at
    return out.drop_duplicates("symbol")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--symbols", nargs="*", help="override the universe (smoke test)")
    args = ap.parse_args()
    load_dotenv(REPO / ".env")
    headers = {"APCA-API-KEY-ID": os.environ["ALPACA_PAPER_API_KEY"],
               "APCA-API-SECRET-KEY": os.environ["ALPACA_PAPER_API_SECRET"]}
    now = datetime.now(timezone.utc)
    et = pd.Timestamp(now).tz_convert("America/New_York")
    today = et.date().isoformat()
    syms = args.symbols or universe()
    batches = [syms[i:i + BATCH] for i in range(0, len(syms), BATCH)]
    with ThreadPoolExecutor(4) as ex:
        rows = [r for b in ex.map(lambda b: fetch(b, headers, today), batches) for r in b]
    df = to_frame(rows, now.isoformat())
    out = args.root / today / f"{et:%H%M}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(out)
    got = df["underlying"].nunique() if len(df) else 0
    oi_dates = df["open_interest_date"].value_counts().head(3).to_dict() if len(df) else {}
    print(f"{out.relative_to(REPO) if out.is_relative_to(REPO) else out}: {len(df)} contracts, "
          f"{got}/{len(syms)} underlyings, OI dates {oi_dates}", flush=True)
    if got < 0.9 * len(syms):
        raise SystemExit(f"only {got}/{len(syms)} underlyings returned contracts")


if __name__ == "__main__":
    main()
