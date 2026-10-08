# scripts/build_v8_events.py — V8 events backfill: insider, short volume, news.
"""Free point-in-time sources for the V8 pool, 2021-01 → 2025-12 (raw files
kept with retrieval time; parsed tables under nn_meta/validation/v8-events-*):

  --source insider  SEC Form 3/4/5 quarterly bulk data sets (2021q1–2025q4):
                    non-derivative transactions of pool issuers with owner
                    relationship; available_at from the issuer's filing
                    acceptance time (sec/filings.parquet), else filing date
                    + 1 day 06:00 ET.
  --source finra    FINRA consolidated daily short volume (CNMSshvol), pool
                    bar-source symbols per date; available the next trading
                    day 06:00 ET (files post after the close).
  --source news     Alpaca news (free tier) per pool ticker, queried under the
                    bar source symbol of each identity span (FB before
                    META, …); available at created_at.

Network-bound work runs in thread pools under shared rate limiters.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta.v8_parallel import RateLimiter  # noqa: E402

ROOT = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
SIC = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0" / "sic.json"
UA = {"User-Agent": "HealysBacktester research (mrhealy115@gmail.com)"}
TZ = "America/New_York"
START, END = "2021-01-01", "2025-12-31"


def _get(url, *, headers=None, params=None, limiter=None, raw=False):
    for attempt in range(6):
        if limiter:
            limiter.acquire()
        try:
            r = requests.get(url, headers=headers, params=params, timeout=120)
        except requests.RequestException:
            time.sleep(3 * (attempt + 1)); continue
        if r.status_code in (403, 404):
            return None
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * (attempt + 1)); continue
        r.raise_for_status()
        return r.content if raw else r.json()
    raise SystemExit(f"fetch failed: {url} {params}")


def _next_day_6am_utc(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates).dt.tz_localize(TZ)
    return (d + pd.offsets.BDay(1) + pd.Timedelta(hours=6)).dt.tz_convert("UTC")


# ── insider ──────────────────────────────────────────────────────────────────

def insider(threads: int) -> None:
    out = ROOT / "insider"; (out / "raw").mkdir(parents=True, exist_ok=True)
    lim = RateLimiter(8 * 60)
    quarters = [f"{y}q{q}" for y in range(2021, 2026) for q in range(1, 5)]

    def fetch(q):
        p = out / "raw" / f"{q}_form345.zip"
        if not p.exists():
            b = _get(f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip",
                     headers=UA, limiter=lim, raw=True)
            if b is None:
                return q, "missing"
            p.write_bytes(b)
        return q, "ok"
    with ThreadPoolExecutor(threads) as ex:
        print(dict(ex.map(fetch, quarters)), flush=True)
    sic = json.loads(SIC.read_text())
    pool = json.loads(POOL.read_text())
    tech = set().union(*(set(v["tech"]) for v in pool["months"].values()))
    cik2t: dict[int, list[str]] = {}
    for t in tech:
        if sic.get(t, {}).get("cik"):
            cik2t.setdefault(int(sic[t]["cik"]), []).append(t)
    frames = []
    for q in quarters:
        p = out / "raw" / f"{q}_form345.zip"
        if not p.exists():
            continue
        z = zipfile.ZipFile(p)
        read = lambda n: pd.read_csv(z.open(n), sep="\t", dtype=str, low_memory=False)
        sub = read("SUBMISSION.tsv")
        sub = sub[pd.to_numeric(sub["ISSUERCIK"], errors="coerce").isin(cik2t)]
        tr = read("NONDERIV_TRANS.tsv")
        tr = tr[tr["ACCESSION_NUMBER"].isin(sub["ACCESSION_NUMBER"])]
        own = read("REPORTINGOWNER.tsv")
        own = own[own["ACCESSION_NUMBER"].isin(sub["ACCESSION_NUMBER"])]
        own = own.groupby("ACCESSION_NUMBER").agg(
            owners=("RPTOWNERCIK", "nunique"),
            relationship=("RPTOWNER_RELATIONSHIP", lambda s: ",".join(sorted(set(s.dropna())))),
            title=("RPTOWNER_TITLE", lambda s: ",".join(sorted(set(s.dropna()))))).reset_index()
        keep = ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERTRADINGSYMBOL"]
        if "AFF10B5ONE" in sub:
            keep.append("AFF10B5ONE")
        m = tr.merge(sub[keep], on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
        frames.append(m.assign(quarter=q))
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]
    for c in ("trans_shares", "trans_pricepershare", "shrs_ownd_folwng_trans"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["issuercik"] = pd.to_numeric(df["issuercik"], errors="coerce").astype("Int64")
    df["filing_date"] = pd.to_datetime(df["filing_date"], format="%d-%b-%Y").dt.strftime("%Y-%m-%d")
    df["trans_date"] = pd.to_datetime(df["trans_date"], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    fl = pd.read_parquet(ROOT / "sec" / "filings.parquet", columns=["cik", "accession", "available_at_utc"])
    fl = fl.drop_duplicates(["cik", "accession"])
    df = df.merge(fl, left_on=["issuercik", "accession_number"], right_on=["cik", "accession"], how="left")
    miss = df["available_at_utc"].isna()
    df.loc[miss, "available_at_utc"] = _next_day_6am_utc(df.loc[miss, "filing_date"]).to_numpy()
    df["ticker"] = df["issuercik"].map(lambda c: cik2t.get(int(c), [None])[0] if pd.notna(c) else None)
    rows = [df]
    for c, ts in cik2t.items():          # share classes (GOOG/GOOGL)
        for t in ts[1:]:
            rows.append(df[df["issuercik"] == c].assign(ticker=t))
    df = pd.concat(rows, ignore_index=True).drop(columns=["cik", "accession"])
    df.to_parquet(out / "insider.parquet", index=False)
    print(f"insider: {len(df)} transactions, {df['ticker'].nunique()} tickers, "
          f"codes {df['trans_code'].value_counts().head(6).to_dict()}, "
          f"acceptance-timed {(~miss).mean():.1%}", flush=True)


# ── FINRA short volume ───────────────────────────────────────────────────────

def finra(threads: int) -> None:
    out = ROOT / "finra"; (out / "raw").mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "source"])
    d = d[(d["date"] >= START) & (d["date"] <= END)]
    days = sorted(d["date"].unique())
    src_of = {(s, x): t for t, x, s in d.itertuples(index=False)}
    lim = RateLimiter(10 * 60)

    def fetch(day):
        p = out / "raw" / f"CNMSshvol{day.replace('-', '')}.txt.gz"
        if p.exists():
            return day, "done"
        b = _get(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day.replace('-', '')}.txt",
                 limiter=lim, raw=True)
        if b is None:
            return day, "missing"
        with gzip.open(p, "wb") as f:
            f.write(b)
        return day, "ok"
    with ThreadPoolExecutor(threads) as ex:
        res = dict(ex.map(fetch, days))
    print("finra fetch:", pd.Series(res).value_counts().to_dict(), flush=True)
    frames = []
    for day in days:
        p = out / "raw" / f"CNMSshvol{day.replace('-', '')}.txt.gz"
        if not p.exists():
            continue
        x = pd.read_csv(p, sep="|", dtype={"Symbol": str})
        x = x[x["Date"].astype(str).str.fullmatch(r"\d{8}")]
        x["date"] = day
        x["ticker"] = [src_of.get((s, day)) for s in x["Symbol"]]
        frames.append(x[x["ticker"].notna()])
    df = pd.concat(frames, ignore_index=True).rename(columns={
        "Symbol": "source", "ShortVolume": "short_volume", "ShortExemptVolume": "short_exempt_volume",
        "TotalVolume": "total_volume", "Market": "market"}).drop(columns=["Date"])
    df["available_at_utc"] = _next_day_6am_utc(df["date"])
    df.to_parquet(out / "short_volume.parquet", index=False)
    print(f"finra: {len(df)} rows, {df['ticker'].nunique()} tickers, {df['date'].nunique()} days", flush=True)


# ── Alpaca news ──────────────────────────────────────────────────────────────

def news(threads: int) -> None:
    out = ROOT / "news"; (out / "raw").mkdir(parents=True, exist_ok=True)
    env = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    H = {"APCA-API-KEY-ID": env["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": env["ALPACA_API_SECRET"]}
    lim = RateLimiter(190)
    spans = json.loads((BARS / "spans.json").read_text())
    jobs = []
    for s in spans:
        a, b = max(s["first"], START), min(s["last"], END)
        if a <= b:
            jobs.append((s["ticker"], s["source"], a, b))

    def fetch(job):
        ticker, source, a, b = job
        p = out / "raw" / f"{ticker}__{source}__{a}__{b}.jsonl.gz"
        if p.exists():
            return job, "done"
        items, token = [], None
        while True:
            params = {"symbols": source, "start": f"{a}T00:00:00Z", "end": f"{b}T23:59:59Z",
                      "limit": 50, "sort": "asc", "include_content": "false"}
            if token:
                params["page_token"] = token
            j = _get("https://data.alpaca.markets/v1beta1/news", headers=H, params=params, limiter=lim)
            if j is None:
                break
            items += j.get("news", [])
            token = j.get("next_page_token")
            if not token:
                break
        tmp = p.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            f.write(json.dumps({"retrieved_at": datetime.now(timezone.utc).isoformat()}) + "\n")
            for it in items:
                f.write(json.dumps(it) + "\n")
        tmp.replace(p)
        return job, len(items)
    with ThreadPoolExecutor(threads) as ex:
        for i, (job, n) in enumerate(ex.map(fetch, jobs)):
            if (i + 1) % 20 == 0:
                print(f"  news {i + 1}/{len(jobs)} {job[0]}/{job[1]}: {n}", flush=True)
    rows = []
    for p in sorted((out / "raw").glob("*.jsonl.gz")):
        ticker, source, a, b = p.name.removesuffix(".jsonl.gz").split("__")
        with gzip.open(p, "rt") as f:
            next(f)
            for line in f:
                it = json.loads(line)
                if not (a <= it["created_at"][:10] <= b):   # updated later, created outside span
                    continue
                rows.append((ticker, source, it["id"], it["created_at"], it.get("updated_at"),
                             it.get("headline"), it.get("summary"), it.get("source"),
                             ",".join(it.get("symbols", [])), it.get("url")))
    df = pd.DataFrame(rows, columns=["ticker", "source", "id", "created_at", "updated_at", "headline",
                                     "summary", "provider", "symbols", "url"])
    df["available_at_utc"] = pd.to_datetime(df["created_at"], utc=True)
    df.to_parquet(out / "news.parquet", index=False)
    print(f"news: {len(df)} article-ticker rows, {df['id'].nunique()} articles, "
          f"{df['ticker'].nunique()} tickers", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["insider", "finra", "news"], required=True)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    {"insider": insider, "finra": finra, "news": news}[args.source](args.threads)


if __name__ == "__main__":
    main()
