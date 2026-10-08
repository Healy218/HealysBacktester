# scripts/build_v8_bars.py — V8.0-data: hourly/daily stock bars for the V8 pool.
"""Regular-session hourly and daily bars for every V8 pool symbol (tech union
plus the fixed ETFs), 2021-01-04 → 2026-09-14, with a per-symbol/day coverage
report.

Identity follows the PIT universe: for each date the bar source is the raw
option root that carried the pool ticker's activity, after the same V8 root
hygiene recorded in the PIT report (aliases, rekeys, test roots) and the
shared TICKER_ALIASES. So META reads FB before 2022-06-09, XYZ reads SQ
before 2025-01-21, FISV reads FI in between its two FISV spells, and the
Roundhill "META" ETF never enters. Dates outside the option record carry the
nearest source.

Vendors:
  v7      1-minute bars from the sealed V7 store on MRHA, read in place
          (stock_1m/raw = unadjusted, stock_1m/all = split+dividend adjusted
          as of capture, 2026-09-15). Never written to.
  alpaca  30-minute SIP bars from the Alpaca free tier for sources the V7
          store lacks (raw and adjustment=all).

Bars: regular session only (09:30–16:00 America/New_York; early closes just
end sooner). Hourly bins are anchored at 09:30 (09:30, 10:30, … 15:30, the
last one half an hour). Each row has raw OHLCV and adjusted OHLC/volume.

Outputs under --out: bars_1h.parquet, bars_1d.parquet, coverage.parquet,
spans.json, coverage_summary.json; per-ticker parts in parts/ (resumable).

Run under a memory cap:
    systemd-run --user --scope -p MemoryMax=6G ./venv/bin/python \
        scripts/build_v8_bars.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import universe_pit as up  # noqa: E402

STORE = Path("/run/media/healy/MRHA/HealysBacktester/sealed-v7-payloads-20260929")
PIT_ROOT = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
DEFAULT_OUT = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
TZ = "America/New_York"
# Dataset preference when the store holds several payloads for one
# (symbol, basis, year): later repairs first.
DATASET_RANK = ["stock-repair-20260915", "base-20260915r4", "base-20260915r3",
                "base-20260915r2", "base-20260915", "historical-stocks-20260915"]
# Bar identity fixes the option record cannot express (verified 2026-10-08 by
# price/volume inspection). Dates before `before` read `source`; None = no
# bars (another security held the ticker).
IDENTITY_OVERRIDES = {
    "COHR": [("2022-09-08", "IIVI")],   # II-VI took COHR on 2022-09-08; old Coherent Inc. before
    "WOLF": [("2021-10-04", "CREE")],   # Cree renamed Wolfspeed 2021-10-04
    "SPCX": [("2026-06-12", None)],     # SpaceX listed 2026-06-12; a SPAC ETF held SPCX before
    "FIG": [("2025-07-31", None)],      # Figma IPO 2025-07-31; another security held FIG before
}
# Corporate events that break the price series: a return across `date` is
# not a holding return. Consumers must not span these.
EVENTS = [
    {"ticker": "WOLF", "date": "2025-09-29",
     "kind": "reorganization: Chapter 11 emergence, old equity cancelled"},
]
REPAIR_MIN_MEDIAN_BARS = 300   # only liquid names: illiquid gaps are real
REPAIR_FRACTION = 0.5

_BAR_RE = re.compile(r"data_v7/([^/]+)/stock_1m/(raw|all)/([^/]+)/(\d{4})/[^/]+/bars\.parquet$")

_spec = importlib.util.spec_from_file_location(
    "build_v8_universe_pit", REPO / "scripts" / "build_v8_universe_pit.py")
_pit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pit)


# ── identity: which source ticker serves each (pool ticker, date) ────────────

def source_by_date(pool: set[str]) -> tuple[list[str], dict[str, dict[str, str]]]:
    """{ticker: {date: source root}} over every trading day in the option
    record, using the hygiene recorded in the PIT report."""
    report = json.loads((PIT_ROOT / "report.json").read_text())
    daily = up.load_daily_rows(PIT_ROOT / "universe_daily")[
        ["root", "date", "opt_dollar_vol"]]
    days = sorted(daily["date"].unique())
    daily["source"] = daily["root"]
    d = _pit.apply_aliases(daily, report["aliases"],
                           [tuple(r) for r in report["rekeys"]])
    d["ticker"] = d["root"].map(up.root_to_ticker)
    d = d[d["ticker"].isin(pool)]
    # rekeyed rows carry the new key as root but their source is the old
    # root (e.g. pre-seam META → METV); they never map to a pool ticker.
    top = (d.sort_values("opt_dollar_vol", ascending=False)
             .drop_duplicates(["ticker", "date"]))
    out: dict[str, dict[str, str]] = {}
    for t, g in top.groupby("ticker"):
        s = pd.Series(dict(zip(g["date"], g["source"]))).reindex(days)
        out[t] = s.ffill().bfill().to_dict()
    return days, out


def spans_of(by_date: dict[str, str]) -> list[dict]:
    spans, cur = [], None
    for day in sorted(by_date):
        src = by_date[day]
        if cur and cur["source"] == src:
            cur["last"] = day
        else:
            cur = {"source": src, "first": day, "last": day}
            spans.append(cur)
    return spans


# ── vendors ──────────────────────────────────────────────────────────────────

def store_index() -> dict[tuple[str, str, str], Path]:
    con = sqlite3.connect(f"file:{STORE / 'files.sqlite3'}?mode=ro", uri=True)
    try:
        rows = con.execute("select source, destination from files "
                           "where source like '%/stock_1m/%bars.parquet'").fetchall()
    finally:
        con.close()
    best: dict[tuple[str, str, str], tuple[int, Path]] = {}
    for src, dest in rows:
        m = _BAR_RE.search(src)
        if m is None:
            continue
        ds, basis, sym, yr = m.groups()
        rank = DATASET_RANK.index(ds) if ds in DATASET_RANK else len(DATASET_RANK)
        key = (sym, basis, yr)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, Path(dest))
    return {k: v[1] for k, v in best.items()}


def _rth(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ)
    mins = ts.dt.hour * 60 + ts.dt.minute
    keep = (mins >= 570) & (mins < 960)
    out = df.loc[keep].copy()
    out["ts"] = ts[keep]
    out["date"] = out["ts"].dt.strftime("%Y-%m-%d")
    out["hour_bin"] = ((mins[keep] - 570) // 60).astype("int8")
    return out


def _merge_bases(raw: pd.DataFrame, adj: pd.DataFrame) -> pd.DataFrame:
    raw = raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                              "Close": "close", "Volume": "volume"})
    adj = adj.rename(columns={"Open": "adj_open", "High": "adj_high",
                              "Low": "adj_low", "Close": "adj_close",
                              "Volume": "adj_volume"})
    m = raw.merge(adj, on="timestamp", how="outer", validate="one_to_one")
    return m


def v7_minutes(index, source: str, years: set[str]) -> pd.DataFrame | None:
    frames = []
    for yr in sorted(years):
        pr, pa = index.get((source, "raw", yr)), index.get((source, "all", yr))
        if pr is None or pa is None:
            continue
        frames.append(_merge_bases(pd.read_parquet(pr), pd.read_parquet(pa)))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _alpaca_headers() -> dict:
    env = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return {"APCA-API-KEY-ID": env["ALPACA_API_KEY"],
            "APCA-API-SECRET-KEY": env["ALPACA_API_SECRET"]}


def _alpaca_bars(headers, sym: str, start: str, end: str, adjustment: str) -> pd.DataFrame:
    rows, token = [], None
    while True:
        params = {"symbols": sym, "timeframe": "30Min", "start": start,
                  "end": end, "adjustment": adjustment, "feed": "sip",
                  "limit": 10000}
        if token:
            params["page_token"] = token
        for attempt in range(5):
            r = requests.get("https://data.alpaca.markets/v2/stocks/bars",
                             headers=headers, params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            raise SystemExit(f"alpaca rate-limited on {sym}")
        j = r.json()
        rows += (j.get("bars") or {}).get(sym, [])
        token = j.get("next_page_token")
        time.sleep(0.35)
        if not token:
            break
    if not rows:
        return pd.DataFrame(columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows).rename(columns={"t": "timestamp", "o": "Open", "h": "High",
                                            "l": "Low", "c": "Close", "v": "Volume"})
    return df[["timestamp", "Open", "High", "Low", "Close", "Volume"]]


def alpaca_minutes(headers, source: str, first: str, last: str) -> pd.DataFrame:
    end = (pd.Timestamp(last) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = _alpaca_bars(headers, source, first, end, "raw")
    adj = _alpaca_bars(headers, source, first, end, "all")
    return _merge_bases(raw, adj)


# ── aggregation ──────────────────────────────────────────────────────────────

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "adj_open": "first", "adj_high": "max",
        "adj_low": "min", "adj_close": "last", "adj_volume": "sum"}


def aggregate(rth: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rth = rth.sort_values("ts")
    g = rth.groupby(keys, sort=True)
    out = g.agg(_AGG)
    out["n_bars"] = g.size()
    out["start"] = g["ts"].min()
    return out.reset_index()


def _alpaca_day(headers, src: str, day: str) -> pd.DataFrame:
    rth = _rth(alpaca_minutes(headers, src, day, day))
    return rth[rth["date"] == day]


def repair_days(span_daily: pd.DataFrame, span_days: list[str]) -> list[str]:
    """V7 days to re-fetch: trading days inside the span's bar range with no
    bars, or with < REPAIR_FRACTION of the trailing 20-day median minute
    count on a liquid name. Checked 2026-10-08: on such days Alpaca shows the
    same bars as V7 (upstream feed gaps), so repairs rarely apply."""
    if span_daily.empty:
        return []
    have = span_daily.set_index("date")
    lo, hi = have.index.min(), have.index.max()
    med = have["n_bars"].rolling(20, min_periods=5).median().shift(1)
    thin = have.index[(have["n_bars"] < REPAIR_FRACTION * med)
                      & (med >= REPAIR_MIN_MEDIAN_BARS)]
    holes = [x for x in span_days if lo <= x <= hi and x not in have.index]
    return sorted(set(thin) | set(holes))


def _neighbor_factors(span_daily: pd.DataFrame, day: str, skip: set) -> tuple[float, float]:
    ok = span_daily[~span_daily["date"].isin(skip)]
    before = ok[ok["date"] < day]
    row = before.iloc[-1] if len(before) else ok.iloc[0]
    return (row["adj_close"] / row["close"],
            row["adj_volume"] / row["volume"] if row["volume"] else 1.0)


def rebase_adjusted(frames: list[pd.DataFrame]) -> None:
    """Make adjusted prices continuous across source seams (renames are not
    corporate actions): scale each earlier span so its last adj/raw ratio
    equals the next span's first. In place, latest span first."""
    for k in range(len(frames) - 2, -1, -1):
        cur, nxt = frames[k], frames[k + 1]
        if cur["daily"].empty or nxt["daily"].empty:
            continue
        a = cur["daily"].iloc[-1]
        b = nxt["daily"].iloc[0]
        f = (b["adj_close"] / b["close"]) / (a["adj_close"] / a["close"])
        if abs(f - 1) < 1e-9:
            continue
        for key in ("daily", "hourly"):
            df = cur[key]
            for c in ("adj_open", "adj_high", "adj_low", "adj_close"):
                df[c] = df[c] * f
            df["adj_volume"] = df["adj_volume"] / f
        cur["rebase"] = f
        for j in range(k):  # earlier spans move with this one
            for key in ("daily", "hourly"):
                df = frames[j][key]
                for c in ("adj_open", "adj_high", "adj_low", "adj_close"):
                    df[c] = df[c] * f
                df["adj_volume"] = df["adj_volume"] / f


def build_ticker(ticker: str, by_date: dict[str, str], index, headers,
                 log: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    spans_out = []
    for span in spans_of(by_date):
        src, first, last = span["source"], span["first"], span["last"]
        span_days = sorted(x for x in by_date if first <= x <= last)
        years = {str(y) for y in range(int(first[:4]), int(last[:4]) + 1)}
        mins = v7_minutes(index, src, years)
        vendor = "v7"
        if mins is None:
            mins, vendor = alpaca_minutes(headers, src, first, last), "alpaca"
        rth = _rth(mins)
        rth = rth[(rth["date"] >= first) & (rth["date"] <= last)]
        entry = {**span, "ticker": ticker, "vendor": vendor,
                 "rth_rows": int(len(rth)), "repaired": []}
        log.append(entry)
        if rth.empty:
            continue
        rth = rth.assign(vendor=vendor)
        daily = aggregate(rth, ["date"])
        if vendor == "v7":
            todo = repair_days(daily, span_days)
            replaced = []
            for day in todo:
                alt = _alpaca_day(headers, src, day)
                old_v = daily.loc[daily["date"] == day, "volume"].sum()
                if alt.empty or alt["volume"].sum() <= old_v:
                    continue
                pf, vf = _neighbor_factors(daily, day, set(todo))
                for c in ("open", "high", "low", "close"):
                    alt["adj_" + c] = alt[c] * pf
                alt["adj_volume"] = alt["volume"] * vf
                rth = pd.concat([rth[rth["date"] != day], alt.assign(vendor="alpaca")],
                                ignore_index=True)
                replaced.append(day)
            entry["repaired"] = replaced
        parts = {}
        for key, keys in (("hourly", ["date", "hour_bin"]), ("daily", ["date"])):
            a = aggregate(rth, keys + ["vendor"]).sort_values(keys, ignore_index=True)
            a.insert(0, "ticker", ticker)
            a["source"] = src
            parts[key] = a
        spans_out.append({**parts, "entry": entry})
    rebase_adjusted(spans_out)
    for sp in spans_out:
        if "rebase" in sp:
            sp["entry"]["adj_rebase"] = sp["rebase"]
    h = pd.concat([sp["hourly"] for sp in spans_out], ignore_index=True) if spans_out else pd.DataFrame()
    d = pd.concat([sp["daily"] for sp in spans_out], ignore_index=True) if spans_out else pd.DataFrame()
    return h, d


# ── coverage ────────────────────────────────────────────────────────────────

def needed_days(pool_json: dict, days: list[str]) -> dict[str, set[str]]:
    """Days on which each ticker is usable: month M's freeze applies from its
    available_at (first trading day after M) to the next freeze."""
    etfs = set(pool_json["rule"]["etfs_every_month"])
    months = sorted(pool_json["months"].items(), key=lambda kv: kv[1]["available_at"])
    need: dict[str, set[str]] = defaultdict(set)
    for i, (_, m) in enumerate(months):
        lo = m["available_at"]
        hi = months[i + 1][1]["available_at"] if i + 1 < len(months) else "9999"
        span = [d for d in days if lo <= d < hi]
        for t in set(m["tech"]) | etfs:
            need[t].update(span)
    return need


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="comma list of tickers (debug)")
    args = ap.parse_args()
    pool_json = json.loads(POOL.read_text())
    etfs = pool_json["rule"]["etfs_every_month"]
    tech = sorted(set().union(*(set(v["tech"]) for v in pool_json["months"].values())))
    pool = sorted(set(tech) | set(etfs))
    if args.only:
        pool = [t for t in pool if t in set(args.only.split(","))]
    days, sources = source_by_date(set(pool))
    for t in pool:  # ETFs without option activity on some day still need a source
        sources.setdefault(t, {d: t for d in days})
    for t, rules in IDENTITY_OVERRIDES.items():
        if t not in sources:
            continue
        for before, src in rules:
            for day in [x for x in sources[t] if x < before]:
                if src is None:
                    del sources[t][day]
                else:
                    sources[t][day] = src
    index = store_index()
    headers = _alpaca_headers()
    parts = args.out / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    log_path = args.out / "spans.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    done = {e["ticker"] for e in log}
    for t in pool:
        if t in done and (parts / f"{t}.1d.parquet").exists():
            continue
        tl: list = []
        h, d = build_ticker(t, sources[t], index, headers, tl)
        h.to_parquet(parts / f"{t}.1h.parquet", index=False)
        d.to_parquet(parts / f"{t}.1d.parquet", index=False)
        log = [e for e in log if e["ticker"] != t] + tl
        log_path.write_text(json.dumps(log, indent=1) + "\n")
        print(t, [(e["source"], e["first"], e["last"], e["vendor"], e["rth_rows"])
                  for e in tl], flush=True)
    h = pd.concat([pd.read_parquet(p) for p in sorted(parts.glob("*.1h.parquet"))],
                  ignore_index=True)
    d = pd.concat([pd.read_parquet(p) for p in sorted(parts.glob("*.1d.parquet"))],
                  ignore_index=True)
    h.to_parquet(args.out / "bars_1h.parquet", index=False)
    d.to_parquet(args.out / "bars_1d.parquet", index=False)
    need = needed_days(pool_json, days)
    have = d.groupby("ticker")["date"].apply(set).to_dict()
    # Thin liquid-name days that no vendor could fill (both V7 and Alpaca
    # show the same few bars: upstream feed gaps, e.g. 2021-04-19).
    thin = {t: set(repair_days(g[g["vendor"] == "v7"].sort_values("date"), []))
            for t, g in d.groupby("ticker")}
    cov_rows, summary = [], {}
    for t in pool:
        hv = have.get(t, set())
        lo, hi = (min(hv), max(hv)) if hv else ("9999", "0000")
        counts: dict[str, int] = defaultdict(int)
        missing = []
        for x in days:
            needed = x in need.get(t, ())
            status = ("partial" if x in thin.get(t, ()) else
                      "ok" if x in hv else "prelisting" if x < lo
                      else "delisted" if x > hi else "missing")
            if needed:
                counts[status] += 1
                if status == "missing":
                    missing.append(x)
            cov_rows.append({"ticker": t, "date": x, "needed": needed,
                             "status": status})
        summary[t] = {"needed_days": len(need.get(t, ())), **counts,
                      "first_bar": lo if hv else None, "last_bar": hi if hv else None,
                      "missing_days": missing}
    cov = pd.DataFrame(cov_rows).merge(
        d[["ticker", "date", "n_bars", "volume", "vendor", "source"]],
        on=["ticker", "date"], how="left")
    cov.to_parquet(args.out / "coverage.parquet", index=False)
    (args.out / "events.json").write_text(json.dumps(
        {"identity_overrides": IDENTITY_OVERRIDES, "events": EVENTS}, indent=1) + "\n")
    (args.out / "coverage_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n")
    tot = defaultdict(int)
    for v in summary.values():
        for k in ("needed_days", "ok", "partial", "missing", "delisted", "prelisting"):
            tot[k] += v.get(k, 0)
    print(f"{len(pool)} tickers; needed ticker-days: {dict(tot)}")
    for t, v in sorted(summary.items(), key=lambda kv: -len(kv[1]["missing_days"])):
        if v["missing_days"] or v.get("delisted") or v.get("prelisting"):
            print(f"  {t}: missing {len(v['missing_days'])} {v['missing_days'][:4]} "
                  f"partial {v.get('partial', 0)} "
                  f"delisted {v.get('delisted', 0)} prelisting {v.get('prelisting', 0)}")


if __name__ == "__main__":
    main()
