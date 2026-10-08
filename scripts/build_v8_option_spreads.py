# scripts/build_v8_option_spreads.py — V8.0-spreads: option NBBO spread table.
"""Option quoted-spread observations from the sealed V7 entry-campaign NBBO
captures (MRHA, read in place), joined to the V8 hourly underlying bars, and
a first spread model.

Sample: capture packs whose sha256 prefix mod 100 < --pct (deterministic,
default 3%). Each 'quotes' capture is a contiguous 5–60 min tick window for
one contract; snapshots are taken every 5 minutes after its start (NBBO =
last record at/before t; 0 < bid < ask). Selection caveat: V7 captured
windows around its own signals, so contracts/times are not a uniform draw of
the chain; the model conditions on contract features, not on that choice.

Outputs under --out: snapshots.parquet, model.json (bucket medians and an
OLS on log quoted spread % of mid), report.json.

Run: systemd-run --user --scope -p MemoryMax=6G ./venv/bin/python \
        scripts/build_v8_option_spreads.py [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta.v8_parallel import autosize_workers  # noqa: E402

STORE = Path("/run/media/healy/MRHA/HealysBacktester/sealed-v7-payloads-20260929")
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
DEFAULT_OUT = REPO / "nn_meta" / "validation" / "v8-spreads-option-20261008-r0"
TZ = "America/New_York"
SNAP_NS = 5 * 60 * 10**9
_OCC = re.compile(r"^(?:O:)?([A-Z.]+\d?)(\d{6})([CP])(\d{8})$")


def parse_occ(contract: str) -> tuple[str, str, str, float] | None:
    m = _OCC.match(contract)
    if m is None:
        return None
    root, ymd, cp, strike = m.groups()
    return root, f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:]}", cp, int(strike) / 1000


def snapshots(records: list[dict], start_ns: int, end_ns: int) -> list[dict]:
    """NBBO at start+5m, start+10m, … ≤ end (records ordered by sip_timestamp),
    vectorized: one searchsorted over the capture's timestamps."""
    if not records:
        return []
    ts = np.fromiter((r["sip_timestamp"] for r in records), np.int64, len(records))
    times = np.arange(start_ns + SNAP_NS, end_ns + 1, SNAP_NS, dtype=np.int64)
    idx = np.searchsorted(ts, times, side="right") - 1
    keep = idx >= 0
    times, idx = times[keep], idx[keep]
    out = []
    for t, i in zip(times.tolist(), idx.tolist()):
        r = records[i]
        bid, ask = r["bid_price"], r["ask_price"]
        if bid is not None and ask is not None and 0 < bid < ask:
            out.append({"t_ns": t, "bid": bid, "ask": ask,
                        "bid_size": r["bid_size"], "ask_size": r["ask_size"],
                        "age_s": (t - r["sip_timestamp"]) / 1e9})
    return out


def process_pack(dest: str) -> list[dict]:
    from nn_meta.v7.packed_quotes_v3 import decode
    rows = []
    con = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        for cid, contract, kind, s, e, rs, sha, blob in con.execute(
                "select capture_id, contract, kind, start_ns, end_ns, raw_size, "
                "sha256, payload from captures where kind = 'quotes'"):
            occ = parse_occ(contract)
            if occ is None:
                continue
            recs, _ = decode(dict(capture_id=cid, contract=contract, kind=kind,
                                  start_ns=s, end_ns=e), blob, rs, sha)
            root, expiry, cp, strike = occ
            for snap in snapshots(recs, s, e):
                rows.append({"contract": contract, "root": root, "expiry": expiry,
                             "cp": cp, "strike": strike, **snap})
    finally:
        con.close()
    return rows


def sample_packs(pct: int) -> list[str]:
    con = sqlite3.connect(f"file:{STORE / 'files.sqlite3'}?mode=ro", uri=True)
    try:
        rows = con.execute("select sha, destination from files where source like "
                           "'%entry-campaign-20260927/%captures.sqlite3'").fetchall()
    finally:
        con.close()
    return sorted(d for sha, d in rows if int(sha[:8], 16) % 100 < pct)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["t_ns"], utc=True).dt.tz_convert(TZ)
    df["date"] = ts.dt.strftime("%Y-%m-%d")
    mins = ts.dt.hour * 60 + ts.dt.minute
    df["minute_of_day"] = mins
    df["hour_bin"] = ((mins - 570) // 60).astype("int16")
    df["mid"] = (df["bid"] + df["ask"]) / 2
    df["spread"] = df["ask"] - df["bid"]
    df["spread_pct"] = df["spread"] / df["mid"] * 100
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    # underlying: hourly bar of the bar *source* equal to the option root
    bars = pd.read_parquet(BARS / "bars_1h.parquet",
                           columns=["ticker", "source", "date", "hour_bin", "close"])
    bars = bars.rename(columns={"source": "root", "close": "underlying"})
    df = df.merge(bars, on=["root", "date", "hour_bin"], how="left")
    df["log_moneyness"] = np.log(df["strike"] / df["underlying"])
    # OTM-signed: positive = out of the money for both calls and puts
    df["otm"] = np.where(df["cp"] == "C", df["log_moneyness"], -df["log_moneyness"])
    return df


def fit(df: pd.DataFrame) -> dict:
    d = df[(df["minute_of_day"] >= 570) & (df["minute_of_day"] < 960)
           & df["underlying"].notna() & (df["dte"] >= 0)].copy()
    d["price_b"] = pd.cut(d["mid"], [0, 0.5, 1, 2, 5, 10, 1e9], right=False)
    d["dte_b"] = pd.cut(d["dte"], [0, 1, 3, 8, 31, 91, 10**5], right=False)
    d["otm_b"] = pd.cut(d["otm"], [-10, -0.1, -0.03, 0.03, 0.1, 10], right=False)
    table = (d.groupby(["price_b", "dte_b", "otm_b"], observed=True)["spread_pct"]
               .agg(["median", "count"]).reset_index())
    table = table[table["count"] >= 50]
    # OLS: log(spread %) ~ log(mid) + |otm| + log1p(dte) + minute buckets + year
    y = np.log(d["spread_pct"].clip(lower=1e-3))
    X = pd.DataFrame({"const": 1.0, "log_mid": np.log(d["mid"]),
                      "abs_otm": d["otm"].abs(), "log1p_dte": np.log1p(d["dte"]),
                      "first_30m": (d["minute_of_day"] < 600).astype(float),
                      "last_30m": (d["minute_of_day"] >= 930).astype(float)})
    for yr in sorted(d["date"].str[:4].unique())[1:]:
        X[f"y{yr}"] = (d["date"].str[:4] == yr).astype(float)
    beta, *_ = np.linalg.lstsq(X.to_numpy(), y.to_numpy(), rcond=None)
    pred = X.to_numpy() @ beta
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return {
        "rows": int(len(d)), "roots": int(d["root"].nunique()),
        "dates": [d["date"].min(), d["date"].max()],
        "ols_log_spread_pct": {"coef": dict(zip(X.columns, map(float, beta))),
                               "r2": float(r2)},
        "bucket_medians": [
            {"price": str(r.price_b), "dte": str(r.dte_b), "otm": str(r.otm_b),
             "median_spread_pct": round(float(r["median"]), 3), "n": int(r["count"])}
            for _, r in table.iterrows()],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--pct", type=int, default=3)
    ap.add_argument("--workers", type=int, default=None,
                    help="cap on memory-sized worker count")
    ap.add_argument("--max-packs", type=int, default=0)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    packs = sample_packs(args.pct)
    if args.max_packs:
        packs = packs[:args.max_packs]
    workers, why = autosize_workers(per_worker_mb=1200, cap=args.workers)
    print(f"{len(packs)} packs sampled at {args.pct}%: {why}", flush=True)
    rows: list[dict] = []
    with ProcessPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(process_pack, packs, chunksize=8)):
            rows += r
            if (i + 1) % 1000 == 0:
                print(f"  {i + 1}/{len(packs)} packs, {len(rows)} snapshots", flush=True)
    df = enrich(pd.DataFrame(rows))
    df.to_parquet(args.out / "snapshots.parquet", index=False)
    model = fit(df)
    (args.out / "model.json").write_text(json.dumps(model, indent=1) + "\n")
    report = {"packs": len(packs), "pct": args.pct, "snapshots": int(len(df)),
              "with_underlying": float(df["underlying"].notna().mean()),
              "median_spread_pct": float(df["spread_pct"].median()),
              "spread_pct_quantiles": df["spread_pct"].quantile([.1, .25, .5, .75, .9]).round(3).to_dict()}
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps(report, indent=1, default=str))
    print(json.dumps(model["ols_log_spread_pct"], indent=1))


if __name__ == "__main__":
    main()
