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
  --source wiki     English Wikipedia daily page views (agent=user) per pool
                    tech name: article from Wikidata by SEC CIK (P5531),
                    summed over the article and every article-namespace
                    redirect to it (page views do not follow redirects, e.g.
                    "Facebook, Inc." before Meta Platforms); a UTC day's
                    views are available at 06:00 ET the next business day.

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


# ── Wikipedia page views ─────────────────────────────────────────────────────

# Titles for names Wikidata cannot map, each verified 2026-10-08 to exist, not
# be a disambiguation page and describe the company (or its eponymous product).
MANUAL_TITLES = {"CRSR": "Corsair Gaming", "CRWV": "CoreWeave", "DBX": "Dropbox", "DUOL": "Duolingo",
                 "FIG": "Figma", "PDD": "Pinduoduo", "PENG": "Penguin Solutions",
                 "PINS": "Pinterest", "PYPL": "PayPal", "RDDT": "Reddit", "SST": "System1",
                 "U": "Unity Technologies"}
# Symbol matches rejected on review: TE matched TECO Energy (NYSE: TE before
# 2016); in the V8 window TE is T1 Energy.
REJECT_SYMBOL = {"TE"}
# Lumentum (LITE) has page views only from late 2025: excluded. "Netflix, Inc."
# was split from "Netflix", which held the company's traffic before (111
# zero-view days in 2021): both titles are summed for NFLX.
EXTRA_TITLES = {"NFLX": ["Netflix"]}

def wiki(threads: int) -> None:
    out = ROOT / "wiki"; (out / "raw").mkdir(parents=True, exist_ok=True)
    pool = json.loads(POOL.read_text())
    tech = set().union(*(set(v["tech"]) for v in pool["months"].values()))
    sic = json.loads(SIC.read_text())
    cik2t: dict[str, list[str]] = {}
    for t in sorted(tech):
        if sic.get(t, {}).get("cik"):
            cik2t.setdefault(f"{int(sic[t]['cik']):010d}", []).append(t)
    lim = RateLimiter(40 * 60)
    q = ("SELECT ?cik ?article WHERE { VALUES ?cik {" + " ".join(f'"{c}"' for c in cik2t)
         + "} ?item wdt:P5531 ?cik . ?article schema:about ?item ; "
           "schema:isPartOf <https://en.wikipedia.org/> . }")
    j = _get("https://query.wikidata.org/sparql", headers=UA, params={"query": q, "format": "json"}, limiter=lim)
    articles: dict[str, str] = {}
    for b in j["results"]["bindings"]:
        title = requests.utils.unquote(b["article"]["value"].rsplit("/wiki/", 1)[1]).replace("_", " ")
        articles.setdefault(b["cik"]["value"], title)
    # fallback: ticker symbol qualifier (P249) on a NASDAQ/NYSE listing (P414)
    todo = {ts[0]: c for c, ts in cik2t.items() if c not in articles}
    exch = "wd:Q82059 wd:Q13677"            # NASDAQ, New York Stock Exchange
    q2 = ("SELECT ?sym ?article WHERE { VALUES ?sym {" + " ".join(f'"{t}"' for t in todo)
          + "} VALUES ?ex {" + exch + "} ?item p:P414 ?st . ?st ps:P414 ?ex ; pq:P249 ?sym . "
            "?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }")
    j2 = _get("https://query.wikidata.org/sparql", headers=UA, params={"query": q2, "format": "json"}, limiter=lim)
    by_symbol: dict[str, set] = {}
    for b in j2["results"]["bindings"]:
        title = requests.utils.unquote(b["article"]["value"].rsplit("/wiki/", 1)[1]).replace("_", " ")
        by_symbol.setdefault(b["sym"]["value"], set()).add(title)
    via_symbol = {}
    for t, c in todo.items():
        if t in REJECT_SYMBOL:
            continue
        if len(by_symbol.get(t, ())) == 1:          # ambiguous symbols are left unmapped
            articles[c] = next(iter(by_symbol[t])); via_symbol[t] = articles[c]
    manual = {}
    for t, title in MANUAL_TITLES.items():
        c = next((c for c, ts in cik2t.items() if t in ts), None)
        if c and c not in articles:
            articles[c] = title; manual[t] = title
    (out / "mapping.json").write_text(json.dumps(
        {"via_cik": {cik2t[c][0]: a for c, a in articles.items()
                     if cik2t[c][0] not in via_symbol and cik2t[c][0] not in manual},
         "via_symbol": via_symbol, "manual": manual, "rejected_symbol": sorted(REJECT_SYMBOL)},
        indent=1, sort_keys=True) + "\n")
    unmapped = sorted(t for c, ts in cik2t.items() if c not in articles for t in ts)
    print(f"wiki: {len(articles)} of {len(cik2t)} CIKs mapped ({len(via_symbol)} via ticker symbol); "
          f"unmapped {unmapped}", flush=True)

    def titles_for(title):
        out_t, cont = [title], {}
        while True:
            r = _get("https://en.wikipedia.org/w/api.php", headers=UA, limiter=lim,
                     params={"action": "query", "titles": title, "prop": "redirects", "rdlimit": "max",
                             "rdnamespace": 0, "format": "json", **cont})
            for pg in r["query"]["pages"].values():
                out_t += [x["title"] for x in pg.get("redirects", [])]
            if "continue" not in r:
                return out_t
            cont = r["continue"]

    def views(title):
        u = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
             + requests.utils.quote(title.replace(" ", "_"), safe="") + "/daily/20210101/20251231")
        j = _get(u, headers=UA, limiter=lim)
        return [(it["timestamp"][:8], it["views"]) for it in (j or {}).get("items", [])]

    def per_cik(cik):
        p = out / "raw" / f"{cik}.json.gz"
        if p.exists():
            return cik, "done"
        ts = titles_for(articles[cik])
        for t in cik2t[cik]:
            for extra in EXTRA_TITLES.get(t, []):
                ts += [x for x in titles_for(extra) if x not in ts]
        series = {t: views(t) for t in ts}
        with gzip.open(p, "wt") as f:
            json.dump({"retrieved_at": datetime.now(timezone.utc).isoformat(), "article": articles[cik],
                       "titles": ts, "views": series}, f)
        return cik, len(ts)
    with ThreadPoolExecutor(threads) as ex:
        for i, (c, n) in enumerate(ex.map(per_cik, sorted(articles))):
            if (i + 1) % 25 == 0:
                print(f"  wiki {i + 1}/{len(articles)}", flush=True)
    rows = []
    for c in sorted(articles):
        d = json.load(gzip.open(out / "raw" / f"{c}.json.gz", "rt"))
        tot: dict[str, int] = {}
        main: dict[str, int] = dict(d["views"].get(d["article"], []))
        for series in d["views"].values():
            for day, v in series:
                tot[day] = tot.get(day, 0) + v
        for t in cik2t[c]:
            for day, v in tot.items():
                rows.append((t, d["article"], f"{day[:4]}-{day[4:6]}-{day[6:]}", v, main.get(day, 0)))
    df = pd.DataFrame(rows, columns=["ticker", "article", "date", "views", "views_main_title"])
    df["available_at_utc"] = _next_day_6am_utc(df["date"])
    df.to_parquet(out / "pageviews.parquet", index=False)
    print(f"wiki: {len(df)} rows, {df['ticker'].nunique()} tickers", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["insider", "finra", "news", "wiki"], required=True)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    {"insider": insider, "finra": finra, "news": news, "wiki": wiki}[args.source](args.threads)


if __name__ == "__main__":
    main()
