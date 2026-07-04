# nn_options_signal/download_contracts.py
"""Crawl the full SPY option contract listing from Massive -> contracts.parquet.

Pages through /v3/reference/options/contracts for every contract whose
expiration falls in [EXPIRY_MIN, EXPIRY_MAX], querying expired=true and
expired=false separately (the API partitions them), deduping on ticker.

Run:  python -m nn_options_signal.download_contracts [--smoke]
"""
import argparse
import os
import sys
import time

import pandas as pd
import requests
from dotenv import load_dotenv

from nn_options_signal import config


def _get_with_retry(session: requests.Session, url: str, params: dict) -> dict:
    for attempt in range(config.MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()
    raise RuntimeError(f"exhausted retries for {url}")


def crawl(expired: bool, key: str, expiry_min: str, expiry_max: str,
          underlying: str) -> list[dict]:
    session = requests.Session()
    rows: list[dict] = []
    params = {
        "underlying_ticker": underlying,
        "expiration_date.gte": expiry_min,
        "expiration_date.lte": expiry_max,
        "expired": "true" if expired else "false",
        "limit": 1000,
        "apiKey": key,
    }
    url = config.MASSIVE_BASE_URL + "/v3/reference/options/contracts"
    page = 0
    while True:
        body = _get_with_retry(session, url, params)
        for c in body.get("results", []):
            rows.append({
                "ticker": c["ticker"],
                "underlying": underlying,
                "strike": float(c["strike_price"]),
                "expiration": c["expiration_date"],
                "type": c["contract_type"],           # 'call' / 'put'
            })
        page += 1
        if page % 20 == 0:
            print(f"  {underlying} expired={expired}: page {page}, {len(rows)} contracts", flush=True)
        next_url = body.get("next_url")
        if not next_url:
            break
        # next_url is a full URL carrying the cursor; re-attach only the key
        url, params = next_url, {"apiKey": key}
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="tiny expiry slice for pipeline validation")
    args = ap.parse_args()

    load_dotenv(config.ROOT.parent / ".env")
    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        sys.exit("MASSIVE_API_KEY not set")

    expiry_min = config.SMOKE_EXPIRY_MIN if args.smoke else config.EXPIRY_MIN
    expiry_max = config.SMOKE_EXPIRY_MAX if args.smoke else config.EXPIRY_MAX
    config.ensure_dirs()

    t0 = time.time()
    rows: list[dict] = []
    for sym in config.UNDERLYINGS:
        n0 = len(rows)
        rows += crawl(True, key, expiry_min, expiry_max, sym)
        rows += crawl(False, key, expiry_min, expiry_max, sym)
        print(f"  {sym}: {len(rows) - n0} contracts", flush=True)
    df = pd.DataFrame(rows).drop_duplicates("ticker").reset_index(drop=True)
    df["expiration"] = pd.to_datetime(df["expiration"])
    df.to_parquet(config.CONTRACTS_PARQUET, index=False)

    print(f"contracts: {len(df)} unique across {df['underlying'].nunique()} underlyings | "
          f"expiries {df['expiration'].min().date()} → {df['expiration'].max().date()} "
          f"| {time.time() - t0:.0f}s")
    print(f"wrote {config.CONTRACTS_PARQUET}")


if __name__ == "__main__":
    main()
