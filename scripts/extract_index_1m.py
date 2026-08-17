# scripts/extract_index_1m.py — raw 1-minute index-option bars for spx0.
"""Extract UNRESAMPLED 1m bars for the index roots from the whole-market
flat files → <cache>/flatfiles_1m/<day>.parquet.

The spx0 stage-0 design wants true 1-minute granularity (user decision
2026-08-17); the main extraction resamples everything to the house 15m. This
runs independently of those workers (no shared state, same S3 source, same
atomic day-file pattern), sharded by date:

    ./venv/bin/python scripts/extract_index_1m.py --start 2024-08-16 \
        --end 2026-08-15 --shard 0 --of 2
"""
import argparse
import gzip
import io
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from v3.flatfiles import _BUCKET, _client, _OCC_RE, _PREFIX  # noqa: E402

INDEX_ROOTS = {"SPX", "SPXW", "NDX", "NDXP"}
OUT_COLS = ["occ", "timestamp", "Open", "High", "Low", "Close", "Volume"]
CACHE = Path("nn_meta/data_cache_spx0/flatfiles_1m")


def one_day(c, day: str) -> int | None:
    out = CACHE / f"{day}.parquet"
    if out.exists():
        return -1
    y, m, _ = day.split("-")
    try:
        raw = c.get_object(Bucket=_BUCKET,
                           Key=f"{_PREFIX}/{y}/{m}/{day}.csv.gz")["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("403", "404", "NoSuchKey"):
            return None
        raise
    df = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    root = df["ticker"].str.extract(_OCC_RE, expand=False)
    df = df[root.isin(INDEX_ROOTS)].copy()
    if df.empty:
        return None
    df["occ"] = df["ticker"].str.slice(2)
    df["timestamp"] = pd.to_datetime(df["window_start"], unit="ns",
                                     utc=True).dt.tz_localize(None)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    df["Volume"] = df["Volume"].astype("int64")
    frame = df[OUT_COLS].sort_values(["occ", "timestamp"])
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    frame.to_parquet(tmp, index=False)
    tmp.replace(out)
    return len(frame)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--of", type=int, default=1)
    args = ap.parse_args()
    c = _client()
    d, i, built = date.fromisoformat(args.start), 0, 0
    while d <= date.fromisoformat(args.end):
        if d.weekday() < 5:
            if i % args.of == args.shard:
                n = one_day(c, d.isoformat())
                if n and n > 0:
                    built += 1
                    print(f"  {d}: {n:,} index 1m rows", flush=True)
            i += 1
        d += timedelta(days=1)
    print(f"shard {args.shard}/{args.of}: built {built} day files")


if __name__ == "__main__":
    main()
