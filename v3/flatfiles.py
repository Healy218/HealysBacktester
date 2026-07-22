# v3/flatfiles.py — bulk OPRA option bars from Massive/Polygon flat files (S3).
"""Quota-free option-bar ingestion for the big run. Two pieces:

1. `populate()` downloads whole-market OPRA minute aggregates from
   files.massive.com and writes ONE universe-filtered 15m parquet per trading
   day: <cache>/flatfiles_15m/<YYYY-MM-DD>.parquet (occ + OHLCV). ~500 files
   for a 2y window, not the millions that per-contract files would be.

2. `FlatFilesProvider` subclasses HybridCachedProvider and overrides ONLY the
   fetch-on-miss: instead of a REST call it slices the requested contract out
   of the day-frames. Everything else (universe/underlying parquets, chain
   selection, per-contract cache write) is inherited, so build_meta_dataset
   runs unchanged and never hits the REST API.

Read entitlement is a rolling ~2y window (data-plan-limits): older days 403,
skipped. Endpoint/creds probed 2026-07-11.

Prebuild:  python -m v3.flatfiles --start 2024-08-01 --end 2026-07-01 \
                                  --cache nn_meta/data_cache_v3 [--smoke]
"""
import argparse
import gzip
import io
import os
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import ClientError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from options.data.hybrid_provider import HybridCachedProvider
from v3.universe import BOOTSTRAP_UNIVERSE

_ENDPOINT = "https://files.massive.com"
_BUCKET = "flatfiles"
_PREFIX = "us_options_opra/minute_aggs_v1"
_OCC_RE = re.compile(r"^O:([A-Z]+)\d{6}[CP]\d+$")
_AGG = {"open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"}
_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _client():
    return boto3.client("s3", endpoint_url=_ENDPOINT,
                        aws_access_key_id=os.environ["MASSIVE_FLAT_FILES_API_KEY"],
                        aws_secret_access_key=os.environ["MASSIVE_FLAT_FILES_API_SECRET"],
                        config=Config(signature_version="s3v4",
                                      retries={"max_attempts": 5}))


def _day_frame_path(cache_dir: Path, day: str) -> Path:
    return cache_dir / "flatfiles_15m" / f"{day}.parquet"


def build_day_frame(c, day: str, cache_dir: Path, universe: set[str]) -> Path | None:
    """Download one whole-market minute file, filter to universe, resample
    1m→15m, write <cache>/flatfiles_15m/<day>.parquet. Idempotent; None if the
    day is outside entitlement (403) or absent (holiday)."""
    out = _day_frame_path(cache_dir, day)
    if out.exists():
        return out
    y, m, _ = day.split("-")
    key = f"{_PREFIX}/{y}/{m}/{day}.csv.gz"
    try:
        raw = c.get_object(Bucket=_BUCKET, Key=key)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("403", "404", "NoSuchKey"):
            return None
        raise
    frame = frame_from_minute_aggs(
        pd.read_csv(io.BytesIO(gzip.decompress(raw))), universe)
    if frame.empty:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    frame.to_parquet(tmp, index=False)
    tmp.replace(out)  # atomic: an interrupted write cannot leave a truncated day-file
    return out


def frame_from_minute_aggs(df: pd.DataFrame, universe: set[str]) -> pd.DataFrame:
    """Pure transform: whole-market 1m aggs → universe-filtered 15m day-frame
    (occ, timestamp[UTC-naive], Open/High/Low/Close/Volume)."""
    root = df["ticker"].str.extract(_OCC_RE, expand=False)
    df = df[root.isin(universe)].copy()
    if df.empty:
        return pd.DataFrame(columns=["occ", "timestamp", *_OHLCV])
    df["occ"] = df["ticker"].str.slice(2)
    ts = pd.to_datetime(df["window_start"], unit="ns", utc=True).dt.tz_localize(None)
    ts.name = "timestamp"
    df = df.set_index(ts)
    frame = (df.groupby("occ").resample("15min").agg(_AGG)
             .dropna(subset=["close"]).reset_index())
    frame = frame.rename(columns={k: k.capitalize() for k in _AGG})
    frame["Volume"] = frame["Volume"].astype("int64")
    return frame


def populate(start: date, end: date, cache_dir: Path, universe, smoke=False) -> int:
    c = _client()
    univ = set(universe)
    built = 0
    d = start
    while d <= end:
        if d.weekday() < 5:                        # skip weekends
            p = build_day_frame(c, d.isoformat(), cache_dir, univ)
            if p:
                n = pd.read_parquet(p, columns=["occ"])["occ"].nunique()
                print(f"  {d}: {n} contracts", flush=True)
                built += 1
                if smoke and built >= 3:
                    break
        d += timedelta(days=1)
    return built


class FlatFilesProvider(HybridCachedProvider):
    """HybridCachedProvider whose option bars come from prebuilt flat-file
    day-frames instead of the REST API."""

    def __init__(self, *args, flatfiles_dir: Path | str, **kwargs):
        super().__init__(*args, **kwargs)
        self._ff_dir = Path(flatfiles_dir)

    @lru_cache(maxsize=40)
    def _day(self, day: str) -> pd.DataFrame | None:
        p = self._ff_dir / f"{day}.parquet"
        return pd.read_parquet(p) if p.exists() else None

    def _fetch_with_retry(self, occ, frm, to, interval):
        """Override: slice `occ` out of the day-frames in [frm, to]."""
        frames = []
        d = frm
        while d <= to:
            if d.weekday() < 5:
                dayf = self._day(d.isoformat())
                if dayf is not None:
                    frames.append(dayf[dayf["occ"] == occ])
            d += timedelta(days=1)
        if not frames:
            return pd.DataFrame(columns=_OHLCV)
        out = pd.concat(frames)
        if out.empty:
            return pd.DataFrame(columns=_OHLCV)
        out = out.set_index("timestamp")[_OHLCV].sort_index()
        if interval in ("1d", "day", "daily"):
            out = out.resample("1D").agg({"Open": "first", "High": "max",
                                          "Low": "min", "Close": "last",
                                          "Volume": "sum"}).dropna(subset=["Close"])
        return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--cache", default="nn_meta/data_cache_v3")
    ap.add_argument("--universe", default=None)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    cache_dir = Path(args.cache)
    universe = args.universe.split(",") if args.universe else BOOTSTRAP_UNIVERSE
    n = populate(date.fromisoformat(args.start), date.fromisoformat(args.end),
                 cache_dir, universe, smoke=args.smoke)
    print(f"\nDONE: built {n} day-frames under {cache_dir}/flatfiles_15m")


if __name__ == "__main__":
    main()
