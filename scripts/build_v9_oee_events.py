# scripts/build_v9_oee_events.py — V9 OEE-0: earnings event table (coverage only).
"""Every 8-K with Item 2.02 by a V8 pool tech name, released 2022-03-01 →
2026-09-14 (end of bars and chains), with the option and stock state around
it (nn_meta/v9_oee.py). No signal-to-return analysis: the report counts
coverage and data quality only.

Universe: the event's ticker is a tech member of the pool month of its entry
day (2026-09 uses 2026-08, the last frozen month). Repeated Item 2.02 filings
by one ticker within 5 trading days keep the first (amendments, re-filings).

Output (<out>/): events.parquet, report.json. Process pool over entry
months; each worker reads only the chain months it needs.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v9_oee  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

V = REPO / "nn_meta" / "validation"
FILINGS = V / "v8-events-20261008-r0" / "sec" / "filings.parquet"
CHAINS = V / "v8-stage2-20261008-r0" / "chains"
BARS = V / "v8-data-20261008-r0" / "bars_1d.parquet"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
DEFAULT_OUT = V / "v9-oee0-20261008-r0"
START, END = "2022-03-01", "2026-09-14"
DEDUP_DAYS = 5


def load_events(days: list[str]) -> pd.DataFrame:
    fl = pd.read_parquet(FILINGS)
    e = fl[(fl["form"] == "8-K") & fl["items"].fillna("").str.contains("2.02", regex=False)].copy()
    e["tau_utc"] = pd.to_datetime(e["acceptance_utc"], utc=True)
    e = e.dropna(subset=["tau_utc"])
    e["e"], e["r"] = v9_oee.event_days(e["tau_utc"], days)
    e = e[e["r"] >= 0]
    e["entry_day"] = [days[i] for i in e["e"]]
    e = e[(e["entry_day"] >= START) & (e["entry_day"] <= END)]
    pool = json.loads(POOL.read_text())["months"]
    months = sorted(pool)

    def member(row):
        m = max((x for x in months if x <= row["entry_day"][:7]), default=None)
        return m is not None and row["ticker"] in pool[m]["tech"]
    e = e[e.apply(member, axis=1)].sort_values(["ticker", "tau_utc"])
    keep, last = [], {}
    for idx, t, r in zip(e.index, e["ticker"], e["r"]):
        if t in last and r - last[t] <= DEDUP_DAYS:
            continue
        last[t] = r
        keep.append(idx)
    n_dup = len(e) - len(keep)
    e = e.loc[keep]
    return e[["ticker", "cik", "accession", "filing_date", "items", "tau_utc", "e", "r"]], n_dup


def _work(job):
    month, evs, days, chain_months, bars_path = job
    tix = sorted({ev["ticker"] for ev in evs})
    lo = days[max(min(ev["e"] for ev in evs) - v9_oee.RUNUP, 0)]
    hi = days[max(ev["r"] for ev in evs)]
    cols = ["date", "ticker", "expiry", "cp", "strike", "close", "volume"]
    ch = pd.concat([pd.read_parquet(CHAINS / f"{m}.parquet", columns=cols,
                                    filters=[("ticker", "in", tix)]) for m in chain_months],
                   ignore_index=True)
    ch = ch[(ch["date"] >= lo) & (ch["date"] <= hi)]
    bars = pd.read_parquet(bars_path, columns=["ticker", "date", "open", "close", "adj_open", "adj_close"],
                           filters=[("ticker", "in", tix)])
    bars = bars[(bars["date"] >= lo) & (bars["date"] <= hi)]
    chs = {t: g for t, g in ch.groupby("ticker")}
    pxs = {t: g.set_index("date") for t, g in bars.groupby("ticker")}
    rows = []
    for ev in evs:
        c = chs.get(ev["ticker"])
        px = pxs.get(ev["ticker"], pd.DataFrame(columns=["close"]))
        if c is None:
            row = {"entry_day": days[ev["e"]], "reaction_day": days[ev["r"]], "status": "no_chain"}
        else:
            row = v9_oee.event_row(ev, c, days, px)
        rows.append({**{k: ev[k] for k in ("ticker", "accession", "tau_utc")}, **row})
    return month, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--limit-tickers", nargs="*", help="smoke test on these tickers")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    days = sorted(pd.read_parquet(BARS, columns=["date"])["date"].unique())
    ev, n_dup = load_events(days)
    if args.limit_tickers:
        ev = ev[ev["ticker"].isin(args.limit_tickers)]
    have = {p.stem for p in CHAINS.glob("*.parquet")}
    jobs = []
    for m, g in ev.groupby(ev["e"].map(lambda i: days[i][:7])):
        recs = g.to_dict("records")
        lo = days[max(g["e"].min() - v9_oee.RUNUP, 0)][:7]
        hi = days[g["r"].max()][:7]
        cm = sorted(x for x in have if lo <= x <= hi)
        jobs.append((m, recs, days, cm, str(BARS)))
    workers, why = autosize_workers(per_worker_mb=2000, cap=args.workers)
    print(f"{len(ev)} events ({n_dup} repeats dropped), {ev['ticker'].nunique()} tickers, "
          f"{len(jobs)} months; {why}", flush=True)
    rows = []
    with ProcessPoolExecutor(workers) as ex:
        for m, r in ex.map(_work, jobs):
            rows += r
            print(f"  {m}: {len(r)} events", flush=True)
    df = pd.DataFrame(rows).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
    df["tau_utc"] = pd.to_datetime(df["tau_utc"], utc=True)
    df.to_parquet(args.out / "events.parquet", index=False)
    (args.out / "report.json").write_text(json.dumps(report(df, n_dup), indent=1, default=str))
    print(json.dumps(report(df, n_dup)["coverage"], indent=1))


def report(df: pd.DataFrame, n_dup: int) -> dict:
    """Coverage and data quality only — no outcome statistics."""
    ok = df[df["status"] == "ok"]
    tau = df["tau_utc"].dt.tz_convert("America/New_York")
    hour = tau.dt.hour + tau.dt.minute / 60
    session = np.select([hour < 9.5, hour < 16], ["pre_market", "intraday"], "after_close")
    usable = ok[ok["straddle_reaction"].notna() & ~ok["split_between"].astype(bool)
                & ~ok["iv_crush_day_before"].astype(bool)]
    weekly = ok["front_days_after_reaction"] <= 7
    by_year = df.assign(y=df["entry_day"].str[:4]).groupby("y").agg(
        events=("status", "size"), ok=("status", lambda s: int((s == "ok").sum())))
    return {
        "scope": {"start": START, "end": END, "source": str(FILINGS.relative_to(REPO)),
                  "repeats_dropped": n_dup, "dedup_trading_days": DEDUP_DAYS},
        "coverage": {
            "events": len(df), "tickers": int(df["ticker"].nunique()),
            "status": dict(Counter(df["status"])),
            "release_session": dict(Counter(session)),
            "ok_with_straddle_exit": int(ok["straddle_reaction"].notna().sum()),
            "straddle_exit_how": dict(Counter(ok["straddle_exit_how"].dropna())),
            "front_expiry_within_7d_of_reaction": int(weekly.sum()),
            "iv_crush_day_before_flag": int(ok["iv_crush_day_before"].astype(bool).sum()),
            "split_between": int(ok["split_between"].astype(bool).sum()),
            "iv_runup_available": int(ok["iv_runup"].notna().sum()),
            "skew_available": int(ok["skew_put_call"].notna().sum()),
            "call50_put50_available": int((ok["call50_entry"].notna() & ok["put50_entry"].notna()).sum()),
            "usable_core": len(usable),
            "usable_core_weekly": int((usable["front_days_after_reaction"] <= 7).sum()),
            "by_year": by_year.to_dict("index"),
        },
        "quality": {
            "front_dte_median": float(ok["front_dte"].median()),
            "atm_volume_median_call_put": [float(ok["call_atm_volume"].median()),
                                           float(ok["put_atm_volume"].median())],
            "tickers_without_events": "foreign filers (6-K) and names with no Item 2.02 8-K",
        },
        "note": "Coverage only. Implied and realized moves are stored per event "
                "but not compared here; OEE-1 pre-registers before any such analysis.",
    }


if __name__ == "__main__":
    main()
