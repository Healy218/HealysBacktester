# scripts/sample_v8_stock_spreads.py — V8.0-liquidity input: measured stock spreads.
"""Sample quoted NBBO spreads for the V8 pool from the Alpaca free tier and
cross-check them against a bar-based estimator.

Sample design (deterministic, seed 8): 3 trading days per calendar month,
2021-01 → 2026-09; 13 snapshots per day at 09:45, 10:15, … 15:45 ET (none
at/after an early close). At each snapshot every symbol with a daily bar
that day is queried under its bar *source* ticker (FB in 2021, not META):

  window  quotes in [t − 10 s, t]; symbols without one fall back to
          [t − 5 min, t]
  valid   0 < bid < ask, ask/bid < 1.5 (drops stub and crossed quotes)
  record  last valid quote at/before t (bid, ask, spread_bps vs mid, age_s)
          and the mean spread_bps over the window's valid quotes

Outputs under --out: samples/<date>.parquet (resumable per day),
quotes.parquet (all samples), crosscheck.json.

Cross-check (--crosscheck): Abdi–Ranaldo (2017) effective-spread estimate
from daily high/low/close over each symbol-month, versus the month's median
measured quoted spread. AR estimates the effective spread, so agreement is
judged by rank correlation, not equality.

Run:  ./venv/bin/python scripts/sample_v8_stock_spreads.py [--crosscheck]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta.v8_parallel import RateLimiter  # noqa: E402

BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
DEFAULT_OUT = REPO / "nn_meta" / "validation" / "v8-spreads-stock-20261008-r0"
TZ = "America/New_York"
DAYS_PER_MONTH = 3
SEED = 8
SNAP_MINUTES = [9 * 60 + 45 + 30 * k for k in range(13)]  # 09:45 … 15:45
WINDOW_S, FALLBACK_S = 10, 300
URL = "https://data.alpaca.markets/v2/stocks/quotes"
RATE_PER_MIN = 190  # free tier allows 200 requests/minute per account
LIMITER = RateLimiter(RATE_PER_MIN)  # shared by all day-threads


def _headers() -> dict:
    env = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return {"APCA-API-KEY-ID": env["ALPACA_API_KEY"],
            "APCA-API-SECRET-KEY": env["ALPACA_API_SECRET"]}


def sample_days(days: list[str]) -> list[str]:
    rng = random.Random(SEED)
    by_month: dict[str, list[str]] = {}
    for d in days:
        by_month.setdefault(d[:7], []).append(d)
    out = []
    for m in sorted(by_month):
        ds = by_month[m]
        out += sorted(rng.sample(ds, min(DAYS_PER_MONTH, len(ds))))
    return out


def fetch_quotes(headers, symbols: list[str], start: pd.Timestamp,
                 end: pd.Timestamp) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    token = None
    while True:
        params = {"symbols": ",".join(symbols),
                  "start": start.tz_convert("UTC").isoformat().replace("+00:00", "Z"),
                  "end": end.tz_convert("UTC").isoformat().replace("+00:00", "Z"),
                  "feed": "sip", "limit": 10000}
        if token:
            params["page_token"] = token
        for attempt in range(6):
            LIMITER.acquire()
            try:
                r = requests.get(URL, headers=headers, params=params, timeout=60)
            except requests.RequestException:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            raise SystemExit(f"alpaca quotes failed at {start}")
        j = r.json()
        for sym, qs in (j.get("quotes") or {}).items():
            out.setdefault(sym, []).extend(qs)
        token = j.get("next_page_token")
        if not token:
            return out


def summarize(sym: str, qs: list[dict], t: pd.Timestamp, window_s: int) -> dict | None:
    valid = [q for q in qs if 0 < q["bp"] < q["ap"] and q["ap"] / q["bp"] < 1.5]
    if not valid:
        return None
    last = valid[-1]
    mid = (last["ap"] + last["bp"]) / 2
    sp = [(q["ap"] - q["bp"]) / ((q["ap"] + q["bp"]) / 2) * 1e4 for q in valid]
    return {"bid": last["bp"], "ask": last["ap"], "bid_size": last["bs"],
            "ask_size": last["as"],
            "spread_bps": (last["ap"] - last["bp"]) / mid * 1e4,
            "spread_abs": last["ap"] - last["bp"],
            "mean_spread_bps": float(np.mean(sp)), "n_quotes": len(valid),
            "age_s": (t - pd.Timestamp(last["t"])).total_seconds(),
            "window_s": window_s}


def sample_day(headers, day: str, active: pd.DataFrame) -> pd.DataFrame:
    rows = []
    src_to_ticker = dict(zip(active["source"], active["ticker"]))
    close_min = active["close_minute"].max()
    for m in SNAP_MINUTES:
        if m >= close_min:
            continue
        t = pd.Timestamp(day, tz=TZ) + pd.Timedelta(minutes=m)
        srcs = sorted(src_to_ticker)
        got = fetch_quotes(headers, srcs, t - pd.Timedelta(seconds=WINDOW_S), t)
        res = {s: summarize(s, got.get(s, []), t, WINDOW_S) for s in srcs}
        miss = [s for s, v in res.items() if v is None]
        if miss:
            got2 = fetch_quotes(headers, miss, t - pd.Timedelta(seconds=FALLBACK_S), t)
            for s in miss:
                res[s] = summarize(s, got2.get(s, []), t, FALLBACK_S)
        for s, v in res.items():
            rows.append({"date": day, "snap": f"{m // 60:02d}:{m % 60:02d}",
                         "ticker": src_to_ticker[s], "source": s,
                         **(v or {"n_quotes": 0, "window_s": FALLBACK_S})})
    return pd.DataFrame(rows)


def abdi_ranaldo(daily: pd.DataFrame) -> pd.DataFrame:
    """Monthly AR (2017) spread estimate in bps per ticker from daily raw
    high/low/close: s^2 = 4 E[(c_t - eta_t)(c_t - eta_{t+1})] over the month;
    a negative monthly mean is floored at zero (flooring daily terms instead
    inflates the estimate ~25x on liquid names)."""
    d = daily.sort_values(["ticker", "date"]).copy()
    d["c"] = np.log(d["close"])
    d["eta"] = (np.log(d["high"]) + np.log(d["low"])) / 2
    d["eta_next"] = d.groupby("ticker")["eta"].shift(-1)
    d["term"] = 4 * (d["c"] - d["eta"]) * (d["c"] - d["eta_next"])
    d["month"] = d["date"].str[:7]
    m = d.groupby(["ticker", "month"])["term"].mean().clip(lower=0)
    return (np.sqrt(m) * 1e4).rename("ar_bps").reset_index()


def crosscheck(out: Path) -> dict:
    q = pd.read_parquet(out / "quotes.parquet")
    q = q[q["spread_bps"].notna()]
    q["month"] = q["date"].str[:7]
    meas = q.groupby(["ticker", "month"])["mean_spread_bps"].median().rename("quoted_bps")
    daily = pd.read_parquet(BARS / "bars_1d.parquet",
                            columns=["ticker", "date", "high", "low", "close"])
    ar = abdi_ranaldo(daily).set_index(["ticker", "month"])["ar_bps"]
    j = pd.concat([meas, ar], axis=1, join="inner").dropna()
    by_ticker = j.groupby(level=0).median()
    res = {
        "symbol_months": int(len(j)),
        "spearman_symbol_month": float(j["quoted_bps"].corr(j["ar_bps"], method="spearman")),
        "spearman_symbol_level": float(by_ticker["quoted_bps"].corr(by_ticker["ar_bps"], method="spearman")),
        "median_quoted_bps": float(j["quoted_bps"].median()),
        "median_ar_bps": float(j["ar_bps"].median()),
        "ar_over_quoted_median": float((j["ar_bps"] / j["quoted_bps"]).median()),
        "by_quoted_decile": (j.assign(dec=pd.qcut(j["quoted_bps"], 10, labels=False))
                              .groupby("dec")[["quoted_bps", "ar_bps"]].median()
                              .round(2).to_dict(orient="index")),
    }
    (out / "crosscheck.json").write_text(json.dumps(res, indent=1) + "\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-days", type=int, default=0, help="debug cap")
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--threads", type=int, default=6,
                    help="concurrent days; network-bound, so not memory-sized")
    args = ap.parse_args()
    if args.crosscheck:
        print(json.dumps(crosscheck(args.out), indent=1))
        return
    daily = pd.read_parquet(BARS / "bars_1d.parquet",
                            columns=["ticker", "date", "source"])
    hourly = pd.read_parquet(BARS / "bars_1h.parquet",
                             columns=["ticker", "date", "hour_bin"])
    days = sorted(daily["date"].unique())
    picks = sample_days(days)
    if args.max_days:
        picks = picks[:args.max_days]
    # session end per day (early closes): last hour bin across the pool
    last_bin = hourly.groupby("date")["hour_bin"].max()
    headers = _headers()
    (args.out / "samples").mkdir(parents=True, exist_ok=True)
    todo = [d for d in picks if not (args.out / "samples" / f"{d}.parquet").exists()]
    print(f"{len(todo)} of {len(picks)} days to sample with {args.threads} threads "
          f"sharing {RATE_PER_MIN} requests/min", flush=True)

    def run(day: str) -> str:
        active = daily[daily["date"] == day][["ticker", "source"]].copy()
        # full session ends in hour bin 6 (15:30-16:00); early closes at 13:00
        active["close_minute"] = 960 if int(last_bin[day]) == 6 else 780
        t0 = time.time()
        df = sample_day(headers, day, active)
        tmp = args.out / "samples" / f"{day}.tmp"
        df.to_parquet(tmp, index=False)
        tmp.replace(args.out / "samples" / f"{day}.parquet")
        ok = df["spread_bps"].notna().mean() if "spread_bps" in df else 0
        return f"{day}: {len(df)} samples, {ok:.1%} quoted, {time.time() - t0:.0f}s"

    with ThreadPoolExecutor(args.threads) as ex:
        futs = [ex.submit(run, d) for d in todo]
        for i, f in enumerate(as_completed(futs)):
            print(f"[{i + 1}/{len(todo)}] {f.result()}", flush=True)
    parts = sorted((args.out / "samples").glob("*.parquet"))
    pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True).to_parquet(
        args.out / "quotes.parquet", index=False)
    print(f"wrote {args.out / 'quotes.parquet'} from {len(parts)} days")


if __name__ == "__main__":
    main()
