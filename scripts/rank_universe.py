# scripts/rank_universe.py — rank the WHOLE MARKET by option dollar volume.
"""Build the expanded universe list from the flat-files *day_aggs* product.

The local minute-agg day parquets are PRE-FILTERED to the incumbent universe
(discovered 2026-08-16 — they contain only its ~119 roots), so ranking needs
the whole-market source: `us_options_opra/day_aggs_v1/` on the flat-files S3
(a few MB per day, every OPRA contract). Notional per underlying =
Σ close × volume × 100 over the trailing N trading days. Incumbents are
force-included (spec/model continuity); renamed listings fold to their spec
symbol via config.TICKER_ALIASES.

Run:  NN_META_POOL=v31 ./venv/bin/python scripts/rank_universe.py \
          --top 200 --days 30 --out v3/artifacts/universe_200.json
"""
import argparse
import gzip
import io
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import boto3
import pandas as pd
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from nn_meta import config  # noqa: E402

_ROOT_RE = re.compile(r"^(?:O:)?([A-Z]+[A-Z0-9]*?)\d{6}[CP]\d{8}$")


def _s3():
    return boto3.client(
        "s3", endpoint_url="https://files.massive.com",
        aws_access_key_id=os.environ["MASSIVE_FLAT_FILES_API_KEY"],
        aws_secret_access_key=os.environ["MASSIVE_FLAT_FILES_API_SECRET"],
        config=Config(signature_version="s3v4"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--days", type=int, default=30, help="trading days to sum")
    ap.add_argument("--out", type=str, default="v3/artifacts/universe_200.json")
    args = ap.parse_args()

    s3 = _s3()
    totals: dict[str, float] = {}
    got, day = 0, date.today()
    while got < args.days and (date.today() - day).days < args.days * 2 + 20:
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        key = (f"us_options_opra/day_aggs_v1/{day.year}/{day.month:02d}/"
               f"{day.isoformat()}.csv.gz")
        try:
            body = s3.get_object(Bucket="flatfiles", Key=key)["Body"].read()
        except Exception:
            continue                              # holiday / not yet published
        d = pd.read_csv(io.BytesIO(gzip.decompress(body)),
                        usecols=["ticker", "volume", "close"])
        roots = d["ticker"].str.extract(_ROOT_RE.pattern, expand=True)[0]
        g = (d["close"] * d["volume"]).groupby(roots).sum() * 100
        for root, notional in g.items():
            totals[root] = totals.get(root, 0.0) + float(notional)
        got += 1
        if got % 10 == 0:
            print(f"  {got}/{args.days} trading days (whole market: "
                  f"{len(totals)} roots)", flush=True)

    # Index-option roots are excluded from the EQUITY universe: no stock
    # underlying, cash-settled, different pipeline — they belong to the
    # dedicated index pool (spx0). Their whole-market rank (SPX/NDX at #1-4
    # by notional, 2026-08-16) is recorded evidence for that pool's stage-0.
    INDEX_ROOTS = {"SPX", "SPXW", "NDX", "NDXP", "RUT", "RUTW", "VIX", "VIXW", "XSP"}
    totals = {r: n for r, n in totals.items() if r not in INDEX_ROOTS}
    fold = {v: k for k, v in config.TICKER_ALIASES.items()}
    folded: dict[str, float] = {}
    for root, notional in totals.items():
        folded[fold.get(root, root)] = folded.get(fold.get(root, root), 0.0) \
            + notional

    ranked = sorted(folded, key=folded.get, reverse=True)
    incumbents = list(config.UNDERLYINGS)
    out = list(incumbents)
    for sym in ranked:
        if len(out) >= args.top:
            break
        if sym not in out:
            out.append(sym)

    added = [s for s in out if s not in incumbents]
    Path(args.out).write_text(json.dumps(sorted(out), indent=0) + "\n")
    print(f"\nuniverse: {len(out)} symbols → {args.out}")
    print(f"incumbents kept: {len(incumbents)} | added: {len(added)}")
    print("additions by rank: " + ", ".join(
        [s for s in ranked if s in added][:len(added)]))


if __name__ == "__main__":
    main()
