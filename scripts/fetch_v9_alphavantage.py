# scripts/fetch_v9_alphavantage.py — V9 ALT: Alpha Vantage EARNINGS (consensus) history.
"""Free tier: 25 requests/day, about 1 per second. Each run fetches up to
PER_RUN tickers not yet on disk (pool tech names, all months, plus the frozen
2026-08 list), one JSON per ticker with its retrieval time:

  nn_meta/data_cache_v9/alphavantage/<TICKER>.json

quarterlyEarnings rows carry fiscalDateEnding, reportedDate, reportedEPS,
estimatedEPS (consensus), surprise, surprisePercentage, reportTime. Resumable;
a rate-limit reply stops the run without writing. Daily timer until complete.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
OUT = REPO / "nn_meta" / "data_cache_v9" / "alphavantage"
PER_RUN = 24


def key() -> str:
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith("ALPHAVANTAGE_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("ALPHAVANTAGE_KEY missing from .env")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pool = json.loads(POOL.read_text())
    tickers = sorted(set().union(*(set(v["tech"]) for v in pool["months"].values())))
    todo = [t for t in tickers if not (OUT / f"{t}.json").exists()]
    k = key()
    done = 0
    for t in todo[:PER_RUN]:
        r = requests.get("https://www.alphavantage.co/query",
                         params={"function": "EARNINGS", "symbol": t, "apikey": k}, timeout=60)
        j = r.json()
        if "Information" in j or "Note" in j:
            print(f"rate limited after {done}: {str(j)[:120]}")
            break
        j["_retrieved_utc"] = datetime.now(timezone.utc).isoformat()
        tmp = OUT / f"{t}.json.tmp"
        tmp.write_text(json.dumps(j))
        tmp.replace(OUT / f"{t}.json")
        done += 1
        time.sleep(1.5)
    left = len([t for t in tickers if not (OUT / f"{t}.json").exists()])
    print(f"fetched {done}; {len(tickers) - left}/{len(tickers)} on disk; {left} left")
    sys.exit(0)


if __name__ == "__main__":
    main()
