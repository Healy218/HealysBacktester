# fa/collectors/edgar.py — Stage 0 collector: SEC EDGAR filing index.
"""Pull the daily EDGAR master index for the form types FA cares about and
archive the metadata. Document DOWNLOADS happen lazily in Stage 3 scoring —
this collector only hoards the index.

Fetches today AND the previous business day each run (the daily index fills
in throughout the day; the archive dedupes on accession path). Weekends /
holidays 404 — that's a skip, not an error. EDGAR requires a descriptive
User-Agent and asks for <=10 req/s; we make 2 per run.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd
import requests

from fa import archive

FORMS = {"10-K", "10-Q", "8-K", "4", "S-1"}
_UA = {"User-Agent": "HealysBacktester research (mrhealy115@gmail.com)"}
_TIMEOUT = 30


def _idx_url(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return (f"https://www.sec.gov/Archives/edgar/daily-index/"
            f"{d.year}/QTR{q}/master.{d:%Y%m%d}.idx")


def parse_master_idx(text: str) -> pd.DataFrame:
    """Parse a pipe-delimited EDGAR master .idx into filing-metadata rows."""
    rows = []
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 5 or parts[0].strip().lower() == "cik":
            continue
        cik, company, form, filed, path = (p.strip() for p in parts)
        if form in FORMS:
            rows.append({"cik": cik, "company": company, "form_type": form,
                         "filed": filed, "path": path})
    return pd.DataFrame(rows)


def _prev_business_day(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def collect() -> int:
    ts = pd.Timestamp.now(tz="UTC")
    today = ts.date()
    added = 0
    for d in (_prev_business_day(today), today):
        if d.weekday() >= 5:
            continue
        r = requests.get(_idx_url(d), headers=_UA, timeout=_TIMEOUT)
        time.sleep(0.5)                 # stay well under SEC's rate limit
        if r.status_code in (403, 404):
            # holiday, or the day's index isn't published yet (SEC serves
            # 403 for some missing daily-index files, not 404)
            continue
        r.raise_for_status()
        df = parse_master_idx(r.text)
        if df.empty:
            continue
        df["ts_utc"] = ts
        added += archive.append("edgar", df, key=["path"])
    return added
