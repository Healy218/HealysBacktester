# scripts/build_v8_admission.py — V8.0-liquidity: daily admission panel.
"""Apply the frozen liquidity rule (docs/specs/V8_LIQUIDITY_20261008.json) to
every (pool symbol, trading day) and write the admission panel.

Vectorized over the whole bar panel; decision-time inputs use only days
before D (prior close, trailing 20-day median dollar volume).

Output: <out>/admission.parquet with ticker, date, member, prev_close,
adv20, adv20_days, status, event_break, admitted, reason (first failing
condition, '' when admitted); <out>/summary.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RULE = REPO / "docs" / "specs" / "V8_LIQUIDITY_20261008.json"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
DEFAULT_OUT = REPO / "nn_meta" / "validation" / "v8-liquidity-20261008-r0"


def admission(daily: pd.DataFrame, coverage: pd.DataFrame, events: list[dict],
              rule: dict) -> pd.DataFrame:
    a = rule["admission"]
    d = daily[["ticker", "date", "close", "volume"]].sort_values(["ticker", "date"]).copy()
    d["dv"] = d["close"] * d["volume"]
    g = d.groupby("ticker", sort=False)
    d["prev_close"] = g["close"].shift(1)
    shifted = g["dv"].shift(1)
    roll = shifted.groupby(d["ticker"], sort=False).rolling(20, min_periods=1)
    d["adv20"] = roll.median().reset_index(level=0, drop=True)
    d["adv20_days"] = roll.count().reset_index(level=0, drop=True)
    p = coverage[["ticker", "date", "needed", "status"]].merge(
        d[["ticker", "date", "prev_close", "adv20", "adv20_days"]],
        on=["ticker", "date"], how="left")
    p = p.rename(columns={"needed": "member"})
    breaks = {(e["ticker"], e["date"]) for e in events}
    p["event_break"] = [(t, x) in breaks for t, x in zip(p["ticker"], p["date"])]
    checks = [
        ("not_member", ~p["member"]),
        ("bar_status", p["status"] != "ok"),
        ("event_break", p["event_break"]),
        ("history", p["adv20_days"].fillna(0) < 10),
        ("price", ~(p["prev_close"] >= a["min_prev_close_usd"])),
        ("adv20", ~(p["adv20"] >= a["min_adv20_usd"])),
    ]
    reason = np.full(len(p), "", dtype=object)
    for name, fail in checks:  # first failing condition wins
        reason = np.where((reason == "") & fail.to_numpy(), name, reason)
    p["reason"] = reason
    p["admitted"] = p["reason"] == ""
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    rule = json.loads(RULE.read_text())
    daily = pd.read_parquet(BARS / "bars_1d.parquet")
    coverage = pd.read_parquet(BARS / "coverage.parquet")
    events = json.loads((BARS / "events.json").read_text())["events"]
    p = admission(daily, coverage, events, rule)
    args.out.mkdir(parents=True, exist_ok=True)
    p.to_parquet(args.out / "admission.parquet", index=False)
    m = p[p["member"]]
    per_day = m[m["admitted"]].groupby("date").size()
    summary = {
        "rule": str(RULE.relative_to(REPO)),
        "member_symbol_days": int(len(m)),
        "admitted_symbol_days": int(m["admitted"].sum()),
        "admitted_share": round(float(m["admitted"].mean()), 4),
        "rejections": m.loc[~m["admitted"], "reason"].value_counts().to_dict(),
        "admitted_per_day": {"min": int(per_day.min()), "median": float(per_day.median()),
                             "max": int(per_day.max())},
        "first_admitted_day": str(per_day.index.min()),
        "last_admitted_day": str(per_day.index.max()),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
