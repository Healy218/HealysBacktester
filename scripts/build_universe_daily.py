# scripts/build_universe_daily.py — stage A of the PIT universe crawl.
"""Per-trading-day OPRA day_aggs_v1 → per-root daily rows (HOME BOX ONLY;
keys stay in .env). docs/specs/PIT_UNIVERSE_SPEC.md.

Downloads one whole-market per-contract DAILY file per trading day
(~tens of MB), reduces it to one small row per OCC root via
nn_meta.universe_pit.daily_rows_from_day_aggs, appends it to
v3/data/universe_daily/<yyyy-mm>.parquet, and discards the raw file.
Roots stay RAW here — mapping/exclusion is stage B's business, so aliases
can change without a recrawl.

Resumable per day: a day already present in its month parquet is skipped.
403/404 days are entitlement holes or holidays and are skipped quietly
(counted); a day that DOWNLOADS but fails to parse raises — the
2026-08-19 silent-drop lesson.

Run:  ./venv/bin/python scripts/build_universe_daily.py \
          [--start 2024-08-01] [--end YYYY-MM-DD] [--smoke]
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

from nn_meta.universe_pit import (UNIVERSE_DAILY_DIR,          # noqa: E402
                                  daily_rows_from_day_aggs)
from v3.flatfiles import _BUCKET, _client                      # noqa: E402

_PREFIX = "us_options_opra/day_aggs_v1"


def _month_path(day: str) -> Path:
    return UNIVERSE_DAILY_DIR / f"{day[:7]}.parquet"


def _done_days(month_path: Path) -> set[str]:
    if not month_path.exists():
        return set()
    return set(pd.read_parquet(month_path, columns=["date"])["date"].unique())


def build_day(c, day: str) -> str:
    """'built' | 'done' | 'absent'. Raises on a downloaded-but-unparseable
    day (fail the month loudly, never drop it silently)."""
    out = _month_path(day)
    if day in _done_days(out):
        return "done"
    y, m, _ = day.split("-")
    key = f"{_PREFIX}/{y}/{m}/{day}.csv.gz"
    try:
        raw = c.get_object(Bucket=_BUCKET, Key=key)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("403", "404", "NoSuchKey"):
            return "absent"
        raise
    rows = daily_rows_from_day_aggs(
        pd.read_csv(io.BytesIO(gzip.decompress(raw))), day)
    if out.exists():
        rows = pd.concat([pd.read_parquet(out), rows], ignore_index=True)
        rows = rows.sort_values(["date", "root"], ignore_index=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    rows.to_parquet(tmp, index=False)
    tmp.replace(out)  # atomic: no truncated month file on interrupt
    return "built"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--smoke", action="store_true",
                    help="stop after 3 built days")
    args = ap.parse_args()
    c = _client()
    built = skipped = absent = 0
    d = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    while d <= end:
        if d.weekday() < 5:
            day = d.isoformat()
            state = build_day(c, day)
            if state == "built":
                built += 1
                n = pd.read_parquet(_month_path(day))
                n = (n[n["date"] == day])["root"].nunique()
                print(f"  {day}: {n} roots", flush=True)
                if args.smoke and built >= 3:
                    break
            elif state == "done":
                skipped += 1
            else:
                absent += 1
                print(f"  {day}: absent (403/404 — holiday or entitlement)",
                      flush=True)
        d += timedelta(days=1)
    print(f"\nDONE: {built} built, {skipped} already present, {absent} absent "
          f"under {UNIVERSE_DAILY_DIR}")
    if built == 0 and skipped == 0:
        sys.exit("nothing built and nothing cached — check window/entitlement")


if __name__ == "__main__":
    main()
