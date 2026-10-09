# scripts/run_v9_otm_oos.py — V9: out-of-sample test of 20% OTM earnings legs, run once.
"""Implements docs/specs/V9_OTM_OOS_PREREG_20261008.json (frozen 2026-10-08).

Each available 20% OTM leg (both sides of every admitted earnings event) is
one bet. Windows: 2021-04 → 2022-02 (new OEE-0 table) and 2026-01 → 2026-09-14.
Reports the pass rules, Kelly fractions and robustness; 10% legs reported.
Output (<out>/): legs.parquet, report.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v9_oee as oee  # noqa: E402
from nn_meta import v9_oee_eval as ev_  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_v9_oee_h4", REPO / "scripts" / "run_v9_oee_h4.py")
h4 = importlib.util.module_from_spec(_spec)
sys.modules["run_v9_oee_h4"] = h4
_spec.loader.exec_module(h4)
r2 = h4.r2

PREREG = REPO / "docs" / "specs" / "V9_OTM_OOS_PREREG_20261008.json"
EARLY = r2.V / "v9-oee0-early-20261008-r0" / "events.parquet"
DEV_LEGS = r2.V / "v9-oee-h4-20261008-r0" / "legs.parquet"
DEFAULT_OUT = r2.V / "v9-otm-oos-20261008-r0"
FILINGS = r2.V / "v8-events-20261008-r0" / "sec" / "filings.parquet"
WINDOWS = {"oos_early": ("2021-04-01", "2022-02-28"), "oos_2026": ("2026-01-02", "2026-09-14"),
           "dev_2023_2025": ("2023-01-01", "2025-12-31")}
PENNY = 0.01


def admitted(path: Path) -> pd.DataFrame:
    """Admitted events in the OEE key order (keys match the H4 leg table)."""
    a = ev_.admit(pd.read_parquet(path)).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
    a.index.name = "key"
    return a


def scheduled(a: pd.DataFrame) -> pd.DataFrame:
    """Amendment 2026-10-08: drop unscheduled pre-announcements."""
    pre = oee.preannouncement_flags(a, pd.read_parquet(FILINGS))
    return a[~pre]


def leg_returns(legs: pd.DataFrame, a: pd.DataFrame, sm, penny: float = 0.0) -> pd.DataFrame:
    x = legs.merge(a[["ticker", "entry_day", "reaction_day", "front_expiry", "front_dte",
                      "S_entry", "S_reaction"]], left_on="key", right_index=True)
    x = x[x["exit"].notna()].copy()
    dte_out = (pd.to_datetime(x["front_expiry"]) - pd.to_datetime(x["reaction_day"])).dt.days
    for k in r2.KS:
        x[f"ret_{k}"] = [
            ev_.long_return([r2.leg(sm, e + penny, cp, K, S0, d0)],
                            [r2.leg(sm, max(z - penny, 0.0), cp, K, S1, d1)], k)
            for e, z, cp, K, S0, S1, d0, d1 in zip(x["entry"], x["exit"], x["cp"], x["strike"],
                                                   x["S_entry"], x["S_reaction"], x["front_dte"], dte_out)]
    return x


def kelly(r: np.ndarray) -> dict:
    fs = np.linspace(0, 0.2, 4001)[1:]
    g = np.array([np.mean(np.log1p(f * r)) for f in fs])
    i = int(g.argmax())
    if g[i] <= 0:
        return {"full": 0.0, "half": 0.0, "growth_per_bet_full": 0.0, "growth_per_bet_half": 0.0}
    gh = float(np.mean(np.log1p(fs[i] / 2 * r)))
    return {"full": float(fs[i]), "half": float(fs[i] / 2), "growth_per_bet_full": float(g[i]),
            "growth_per_bet_half": gh}


def summarize(x: pd.DataFrame, rng) -> dict:
    if x.empty:
        return {"n": 0}
    r = x["ret_1.0"].to_numpy()
    ev_sum = x.groupby("key")["ret_1.0"].sum().sort_values(ascending=False)
    top_event = ev_sum.index[0]
    no_top = x[x["key"] != top_event]["ret_1.0"]
    top = x.sort_values("ret_1.0", ascending=False).head(5)
    return {
        "n": len(r), "events": int(x["key"].nunique()), "win_rate": float((r > 0).mean()),
        "mean_k1.0": float(r.mean()), "mean_k1.5": float(x["ret_1.5"].mean()),
        "median": float(np.median(r)),
        "mean_without_top_event": float(no_top.mean()),
        "top_event": {"ticker": x.loc[x["key"] == top_event, "ticker"].iloc[0],
                      "entry_day": x.loc[x["key"] == top_event, "entry_day"].iloc[0],
                      "summed_return": float(ev_sum.iloc[0])},
        "top5": top[["ticker", "entry_day", "leg", "entry", "exit", "ret_1.0"]].to_dict("records"),
        "top5_share_of_sum": float(top["ret_1.0"].sum() / r.sum()) if r.sum() != 0 else None,
        "quantiles": {q: float(np.quantile(r, q)) for q in (0.05, 0.5, 0.9, 0.99)},
        "kelly": kelly(r),
        "bootstrap_p_mean_gt_0": float(np.mean([rng.choice(r, len(r)).mean() > 0 for _ in range(4000)])),
        "clustered": ev_.clustered_t(r, x["reaction_day"].to_numpy()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    if (args.out / "report.json").exists():
        raise SystemExit(f"{args.out}/report.json exists: runs once")
    args.out.mkdir(parents=True, exist_ok=True)
    assert json.loads(PREREG.read_text())["approved_by"].startswith("user")
    sm = ev_.SpreadModel(r2.SPREADS)
    rng = np.random.default_rng(20261008)

    early = scheduled(admitted(EARLY))
    main_a = scheduled(admitted(r2.EVENTS))
    legs_early = h4.leg_table(early, args.workers)
    legs_main = pd.read_parquet(DEV_LEGS)
    legs_main = legs_main[legs_main["key"].isin(main_a.index)]
    frames = []
    for name, a, legs in (("early", early, legs_early), ("main", main_a, legs_main)):
        for penny in (0.0, PENNY):
            x = leg_returns(legs[legs["leg"].isin(["p20_C", "p20_P", "p10_C", "p10_P"])], a, sm, penny)
            x["table"], x["penny"] = name, penny
            x["key"] = name + ":" + x["key"].astype(str)
            frames.append(x)
    allx = pd.concat(frames, ignore_index=True)
    allx.to_parquet(args.out / "legs.parquet", index=False)

    def window(x, w):
        lo, hi = WINDOWS[w]
        return x[(x["entry_day"] >= lo) & (x["entry_day"] <= hi)]

    rep = {"prereg": str(PREREG.relative_to(REPO)), "windows": WINDOWS, "results": {}}
    for pct in (20, 10):
        base = allx[allx["leg"].str.startswith(f"p{pct}") & (allx["penny"] == 0.0)]
        pen = allx[allx["leg"].str.startswith(f"p{pct}") & (allx["penny"] == PENNY)]
        oos = pd.concat([window(base, "oos_early"), window(base, "oos_2026")])
        res = {w: summarize(window(base, w), rng) for w in WINDOWS}
        res["oos_pooled"] = summarize(oos, rng)
        res["all_2021_2026"] = summarize(base, rng)
        oos_pen = pd.concat([window(pen, "oos_early"), window(pen, "oos_2026")])
        res["oos_pooled_penny"] = {"mean_k1.0": float(oos_pen["ret_1.0"].mean()) if len(oos_pen) else None}
        rep["results"][f"{pct}pct"] = res
    p = rep["results"]["20pct"]["oos_pooled"]
    rules = {"positive": p["mean_k1.0"] > 0, "cost_stress": p["mean_k1.5"] > 0,
             "not_one_shock": p["mean_without_top_event"] > 0}
    rep["rules"], rep["pass"] = rules, all(rules.values())
    (args.out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    for pct in ("20pct", "10pct"):
        for w, s in rep["results"][pct].items():
            if "n" not in s or not s["n"]:
                print(pct, w, s); continue
            k = s["kelly"]
            print(f"{pct} {w:15s} n={s['n']:5d} win={s['win_rate']:.1%} mean={s['mean_k1.0']:+.1%} "
                  f"k1.5={s['mean_k1.5']:+.1%} w/o top event={s['mean_without_top_event']:+.1%} "
                  f"top={s['top_event']['ticker']} {s['top_event']['entry_day']} half-Kelly={k['half']:.2%} "
                  f"boot P>0={s['bootstrap_p_mean_gt_0']:.0%}")
    print("rules:", rules, "PASS" if rep["pass"] else "FAIL")


if __name__ == "__main__":
    main()
