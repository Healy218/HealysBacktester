# scripts/build_v8_sec.py — V8 events backfill: SEC XBRL facts and filings.
"""For every V8 pool tech name (CIKs resolved in V8.0-pit, delisted issuers
included), capture SEC company facts and the full filing history (recent +
paged older files) as raw gzipped JSON with retrieval time, then parse:

  filings.parquet  cik, ticker, accession, form, filing_date, report_date,
                   acceptance_utc, items, available_at_utc
  facts.parquet    cik, ticker, taxonomy, tag, unit, start, end, val, fy, fp,
                   form, filed, accession, frame, available_at_utc (joined from
                   the filing's acceptance time; filed date at 06:00 ET+1 day
                   when the filing is not in the history)

PIT availability: EDGAR accepts filings until 22:00 ET, and those accepted
after 17:30 ET receive the next business day's filing date; we treat any
filing as public at its acceptance time if accepted 06:00–17:30 ET on a
business day, otherwise at 06:00 ET on the next business day.

Threads share one SEC rate limiter (8 requests/s; SEC asks <= 10).
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta.v8_parallel import RateLimiter  # noqa: E402

POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
SIC = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0" / "sic.json"
OUT = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0" / "sec"
UA = {"User-Agent": "HealysBacktester research (mrhealy115@gmail.com)"}
LIMIT = RateLimiter(8 * 60)
TZ = "America/New_York"


def _get(url: str) -> dict | None:
    for attempt in range(6):
        LIMIT.acquire()
        try:
            r = requests.get(url, headers=UA, timeout=60)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code == 404:
            return None
        if r.status_code in (429, 503) or r.status_code >= 500:
            time.sleep(5 * (attempt + 1)); continue
        r.raise_for_status()
        return r.json()
    raise SystemExit(f"SEC fetch failed: {url}")


def _save(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump({"retrieved_at": datetime.now(timezone.utc).isoformat(), "data": obj}, f)
    tmp.replace(path)


def capture(cik: int) -> str:
    raw = OUT / "raw"
    facts_p, subs_p = raw / f"facts-{cik:010d}.json.gz", raw / f"subs-{cik:010d}.json.gz"
    if not facts_p.exists():
        _save(facts_p, _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"))
    if not subs_p.exists():
        subs = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        pages = []
        for f in (subs or {}).get("filings", {}).get("files", []):
            pages.append(_get(f"https://data.sec.gov/submissions/{f['name']}"))
        _save(subs_p, {"main": subs, "pages": pages})
    return f"{cik}"


def available_at(acceptance_utc: pd.Series, filing_date: pd.Series) -> pd.Series:
    """Public time per the docstring rule (UTC)."""
    acc = pd.to_datetime(acceptance_utc, utc=True, errors="coerce")
    fallback = pd.to_datetime(filing_date) .dt.tz_localize(TZ) + pd.Timedelta(days=1, hours=6)
    et = acc.dt.tz_convert(TZ)
    mins = et.dt.hour * 60 + et.dt.minute
    business = et.dt.dayofweek < 5
    in_window = business & (mins >= 360) & (mins <= 1050)
    next_bd = (et.dt.normalize() + pd.offsets.BDay(1)) + pd.Timedelta(hours=6)
    early = business & (mins < 360)
    same_day_6 = et.dt.normalize() + pd.Timedelta(hours=6)
    out = acc.where(in_window, (same_day_6.where(early, next_bd)).dt.tz_convert("UTC"))
    return out.fillna(fallback.dt.tz_convert("UTC"))


def parse(ciks: dict[int, list[str]]) -> None:
    """ciks: {cik: [tickers]} (share classes such as GOOG/GOOGL share a CIK)."""
    filings, facts = [], []
    for cik, tickers in ciks.items():
        ticker = tickers[0]
        sp = OUT / "raw" / f"subs-{cik:010d}.json.gz"
        fp = OUT / "raw" / f"facts-{cik:010d}.json.gz"
        subs = json.load(gzip.open(sp, "rt"))["data"]
        blocks = [subs["main"]["filings"]["recent"]] if subs["main"] else []
        blocks += [p for p in subs["pages"] if p]
        for b in blocks:
            df = pd.DataFrame({k: b[k] for k in ("accessionNumber", "form", "filingDate",
                                                   "reportDate", "acceptanceDateTime", "items")})
            df.insert(0, "cik", cik); df.insert(1, "ticker", ticker)
            filings.append(df)
        fj = json.load(gzip.open(fp, "rt"))["data"]
        for tax, tags in (fj or {}).get("facts", {}).items():
            for tag, body in tags.items():
                for unit, rows in body.get("units", {}).items():
                    for x in rows:
                        if x.get("filed", "") < "2019-01-01":
                            continue
                        facts.append((cik, ticker, tax, tag, unit, x.get("start"), x["end"], x["val"],
                                      x.get("fy"), x.get("fp"), x.get("form"), x["filed"],
                                      x["accn"], x.get("frame")))
    fl = pd.concat(filings, ignore_index=True)
    fa_rows = facts
    # replicate per extra share-class ticker
    extra = {c: ts[1:] for c, ts in ciks.items() if len(ts) > 1}
    if extra:
        add = [fl[fl["cik"] == c].assign(ticker=t) for c, ts in extra.items() for t in ts]
        fl = pd.concat([fl, *add], ignore_index=True)
        facts = fa_rows + [(r[0], t, *r[2:]) for r in fa_rows if r[0] in extra for t in extra[r[0]]]
    fl = fl.rename(columns={
        "accessionNumber": "accession", "filingDate": "filing_date", "reportDate": "report_date",
        "acceptanceDateTime": "acceptance_utc"}).drop_duplicates(["cik", "ticker", "accession"])
    fl["available_at_utc"] = available_at(fl["acceptance_utc"], fl["filing_date"])
    fl.to_parquet(OUT / "filings.parquet", index=False)
    fa = pd.DataFrame(facts, columns=["cik", "ticker", "taxonomy", "tag", "unit", "start", "end", "val",
                                      "fy", "fp", "form", "filed", "accession", "frame"])
    fa = fa.merge(fl[["cik", "accession", "available_at_utc"]].drop_duplicates(["cik", "accession"]),
                  on=["cik", "accession"], how="left")
    miss = fa["available_at_utc"].isna()
    if miss.any():
        idx = fa.index[miss]
        fa.loc[idx, "available_at_utc"] = available_at(
            pd.Series([None] * len(idx), index=idx, dtype="object"), fa.loc[idx, "filed"])
    fa["val"] = pd.to_numeric(fa["val"], errors="coerce")
    fa.to_parquet(OUT / "facts.parquet", index=False)
    print(f"filings {len(fl)} ({fl['form'].isin(['8-K']).sum()} 8-K), facts {len(fa)} "
          f"({miss.mean():.1%} with date-only availability)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    pool = json.loads(POOL.read_text())
    tech = set().union(*(set(v["tech"]) for v in pool["months"].values()))
    sic = json.loads(SIC.read_text())
    ciks: dict[int, list[str]] = {}
    for t in sorted(tech):
        if sic.get(t, {}).get("cik"):
            ciks.setdefault(int(sic[t]["cik"]), []).append(t)
    missing = sorted(t for t in tech if not sic.get(t, {}).get("cik"))
    print(f"{len(ciks)} CIKs for {sum(map(len, ciks.values()))} of {len(tech)} tech names; "
          f"missing {missing}", flush=True)
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.threads) as ex:
        for i, c in enumerate(ex.map(capture, sorted(ciks))):
            if (i + 1) % 25 == 0:
                print(f"  captured {i + 1}/{len(ciks)}", flush=True)
    parse(ciks)


if __name__ == "__main__":
    main()
