# scripts/run_v9_oee_h4.py — V9 OEE-H4: out-of-the-money earnings options, run once.
"""Implements docs/specs/V9_OEE_H4_PREREG_20261008.json (frozen 2026-10-08):
13 variants (H4a-d implied-move strangles / directional leg, H4e 5/10/20%
OTM strangles, H4f cheap 10% OTM legs at five cutoffs, H4g 10% strangle cheap
versus the ticker's own past moves) on the OEE-0 events, dev 2023-01-01 →
2025-12-31, 2026 confirmation for dev passes only.

Inputs reused from OEE-2: the admitted events (same order and keys) and its
features.parquet (H1a score tercile, move ratio). Leg prices come from one
chain pass over the admitted events (process pool over entry months).
Output (<out>/): legs.parquet, trades.parquet, report.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v9_oee as oee  # noqa: E402
from nn_meta import v9_oee_eval as ev_  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_v9_oee2", REPO / "scripts" / "run_v9_oee2.py")
r2 = importlib.util.module_from_spec(_spec)
sys.modules["run_v9_oee2"] = r2
_spec.loader.exec_module(r2)

PREREG = REPO / "docs" / "specs" / "V9_OEE_H4_PREREG_20261008.json"
FEATURES = r2.V / "v9-oee2-20261008-r0" / "features.parquet"
DEFAULT_OUT = r2.V / "v9-oee-h4-20261008-r0"
TOL = 0.02
CUTS = [0.10, 0.05, 0.02, 0.01, 0.005]
VARIANTS = (["H4a_strangle_1x", "H4b_strangle_1.5x", "H4c_directional_otm",
             "H4d_strangle_1x_cheap_move", "H4e5_strangle_5pct", "H4e10_strangle_10pct",
             "H4e20_strangle_20pct"]
            + [f"H4f_cheap_leg_10pct_cut{c * 100:g}" for c in CUTS]
            + ["H4g_strangle_10pct_cheap_vs_history"])


def targets(e: dict) -> dict:
    """{name: (cp, target strike)} per event."""
    S, im = e["S_entry"], e["implied_move"]
    out = {}
    for name, x in (("im1", im), ("im15", 1.5 * im), ("p5", 0.05), ("p10", 0.10), ("p20", 0.20)):
        out[f"{name}_C"] = ("C", S * (1 + x))
        out[f"{name}_P"] = ("P", S * (1 - x))
    return out


def pick(on_e: pd.DataFrame, cp: str, S: float, target: float):
    side = 1 if cp == "C" else -1
    c = on_e[(on_e["cp"] == cp) & ((on_e["strike"] - S) * side > 0)]
    if c.empty:
        return None
    row = c.loc[(c["strike"] - target).abs().idxmin()]
    if abs(row["strike"] / target - 1) > TOL:
        return None
    return float(row["strike"]), float(row["close"])


def _legs(job):
    months, evs = job
    tix = sorted({e["ticker"] for e in evs})
    cols = ["date", "ticker", "expiry", "cp", "strike", "close", "volume"]
    ch = pd.concat([pd.read_parquet(r2.CHAINS / f"{m}.parquet", columns=cols,
                                    filters=[("ticker", "in", tix)]) for m in months],
                   ignore_index=True)
    out = []
    for e in evs:
        c = ch[(ch["ticker"] == e["ticker"]) & (ch["expiry"] == e["front_expiry"])]
        on_e = c[(c["date"] == e["entry_day"]) & (c["volume"] > 0) & (c["close"] > 0)]
        expiring = e["front_expiry"] == e["reaction_day"]
        for name, (cp, tgt) in targets(e).items():
            p = pick(on_e, cp, e["S_entry"], tgt)
            if p is None:
                continue
            K, p0 = p
            if expiring:      # prereg: intrinsic from the raw reaction-day close
                S1 = e["S_reaction"]
                p1, how = (max(S1 - K, 0.0) if cp == "C" else max(K - S1, 0.0)), "intrinsic"
            else:
                p1 = oee._close(c, e["reaction_day"], e["front_expiry"], cp, K)
                how = "traded" if np.isfinite(p1) else "missing"
            out.append({"key": e["key"], "leg": name, "cp": cp, "strike": K, "entry": p0,
                        "exit": p1, "exit_how": how})
    return out


def leg_table(a: pd.DataFrame, cap: int | None) -> pd.DataFrame:
    have = {p.stem for p in r2.CHAINS.glob("*.parquet")}
    jobs = []
    for m, g in a.reset_index().groupby(a["entry_day"].str[:7].to_numpy()):
        hi = g["reaction_day"].max()[:7]
        jobs.append((sorted(x for x in have if m <= x <= hi), g.to_dict("records")))
    workers, why = autosize_workers(per_worker_mb=1500, cap=cap)
    print(f"legs: {len(a)} events, {len(jobs)} months; {why}", flush=True)
    with ProcessPoolExecutor(workers) as ex:
        return pd.DataFrame([x for part in ex.map(_legs, jobs) for x in part])


def h4g_cheap(a: pd.DataFrame, legs: pd.DataFrame) -> pd.Series:
    """True when the 10% strangle's entry cost < median intrinsic payoff of the
    same strikes under the ticker's previous 4-8 admitted events' moves."""
    L = legs.set_index(["key", "leg"])
    out = pd.Series(False, index=a.index)
    for _, g in a.sort_values("entry_day").groupby("ticker"):
        for k, row in g.iterrows():
            if (k, "p10_C") not in L.index or (k, "p10_P") not in L.index:
                continue
            prev = g[g["reaction_day"] < row["entry_day"]].tail(8)
            if len(prev) < 4:
                continue
            Kc, Kp = L.loc[(k, "p10_C"), "strike"], L.loc[(k, "p10_P"), "strike"]
            ST = row["S_entry"] * np.exp(prev["realized_move"].to_numpy())
            pay = np.maximum(ST - Kc, 0) + np.maximum(Kp - ST, 0)
            out[k] = L.loc[(k, "p10_C"), "entry"] + L.loc[(k, "p10_P"), "entry"] < np.median(pay)
    return out


def build_trades(a, legs, feats, cheap_g, sm) -> pd.DataFrame:
    L = {k: g.set_index("leg") for k, g in legs.groupby("key")}
    plans = {v: {} for v in VARIANTS}
    for k in a.index:
        lg = L.get(k)
        if lg is None:
            continue
        has = lambda *n: all(x in lg.index for x in n)          # noqa: E731
        if has("im1_C", "im1_P"):
            plans["H4a_strangle_1x"][k] = ["im1_C", "im1_P"]
            if feats.at[k, "move_ratio"] < 0.8:
                plans["H4d_strangle_1x_cheap_move"][k] = ["im1_C", "im1_P"]
        if has("im15_C", "im15_P"):
            plans["H4b_strangle_1.5x"][k] = ["im15_C", "im15_P"]
        t = feats.at[k, "tercile_h1a_score"]
        if t == 1 and has("im1_C"):
            plans["H4c_directional_otm"][k] = ["im1_C"]
        elif t == -1 and has("im1_P"):
            plans["H4c_directional_otm"][k] = ["im1_P"]
        for p in (5, 10, 20):
            if has(f"p{p}_C", f"p{p}_P"):
                plans[f"H4e{p}_strangle_{p}pct"][k] = [f"p{p}_C", f"p{p}_P"]
        S = a.at[k, "S_entry"]
        for c in CUTS:
            q = [n for n in ("p10_C", "p10_P") if n in lg.index and lg.at[n, "entry"] <= c * S]
            if q:
                plans[f"H4f_cheap_leg_10pct_cut{c * 100:g}"][k] = q
        if cheap_g.get(k, False):
            plans["H4g_strangle_10pct_cheap_vs_history"][k] = ["p10_C", "p10_P"]
    rows = []
    for v, pl in plans.items():
        for k, names in pl.items():
            e, lg = a.loc[k], L[k].loc[names]
            rec = {"key": k, "variant": v, "ticker": e["ticker"], "entry_day": e["entry_day"],
                   "reaction_day": e["reaction_day"], "legs": ",".join(names), "session": e["session"]}
            if lg["exit"].isna().any():
                rows.append({**rec, "dropped": "missing_exit"}); continue
            dte_in = e["front_dte"]
            dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
            for k_ in r2.KS:
                rec[f"ret_{k_}"] = ev_.long_return(
                    [r2.leg(sm, x["entry"], x["cp"], x["strike"], e["S_entry"], dte_in) for _, x in lg.iterrows()],
                    [r2.leg(sm, x["exit"], x["cp"], x["strike"], e["S_reaction"], dte_out) for _, x in lg.iterrows()],
                    k_)
            rows.append({**rec, "dropped": ""})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    if (args.out / "report.json").exists():
        raise SystemExit(f"{args.out}/report.json exists: OEE-H4 runs once")
    args.out.mkdir(parents=True, exist_ok=True)
    assert json.loads(PREREG.read_text())["approved_by"].startswith("user")

    a = ev_.admit(pd.read_parquet(r2.EVENTS)).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
    a.index.name = "key"
    tau = a["tau_utc"].dt.tz_convert("America/New_York")
    h = tau.dt.hour + tau.dt.minute / 60
    a["session"] = np.select([h < 9.5, h < 16], ["pre_market", "intraday"], "after_close")
    feats = pd.read_parquet(FEATURES)
    assert len(feats) == len(a) and (feats.index == a.index).all(), "OEE-2 features do not align"
    days = sorted(pd.read_parquet(r2.BARS, columns=["date"])["date"].unique())

    legs = leg_table(a, args.workers)
    legs.to_parquet(args.out / "legs.parquet", index=False)
    cheap_g = h4g_cheap(a, legs)
    tr = build_trades(a, legs, feats, cheap_g, ev_.SpreadModel(r2.SPREADS))
    tr.to_parquet(args.out / "trades.parquet", index=False)

    ok = tr[tr["dropped"] == ""]
    in_dev = (ok["entry_day"] >= r2.DEV[0]) & (ok["entry_day"] <= r2.DEV[1])
    in_conf = (ok["entry_day"] >= r2.CONF[0]) & (ok["entry_day"] <= r2.CONF[1])
    res, p1 = {}, {}
    for v in VARIANTS:
        t = ok[(ok["variant"] == v) & in_dev]
        res[v] = {f"k{k}": r2.window_stats(t, k, days, folds=True) for k in r2.KS}
        res[v]["dropped_dev"] = (tr[(tr["variant"] == v) & (tr["entry_day"] >= r2.DEV[0])
                                    & (tr["entry_day"] <= r2.DEV[1])]["dropped"].value_counts().to_dict())
        p1[v] = res[v]["k1.0"]["p_one_sided"]
    adj_p = ev_.holm(p1)
    for v in VARIANTS:
        s1, s15 = res[v]["k1.0"], res[v]["k1.5"]
        rules = {"edge": bool(s1["mean"] > 0 and s1["t"] >= 2),
                 "multiple_testing": bool(adj_p[v] < 0.05),
                 "folds": bool(s1.get("folds_positive", 0) >= 4),
                 "cost_stress": bool(s15["mean"] > 0 and s15["t"] >= 2)}
        res[v].update(holm_p=adj_p[v], rules=rules, dev_pass=all(rules.values()))
        if res[v]["dev_pass"]:
            c = r2.window_stats(ok[(ok["variant"] == v) & in_conf], 1.0, days, folds=False)
            res[v]["confirmation"] = {**c, "pass": bool(c["mean"] > 0 and c["t"] >= 1)}
    report = {"prereg": str(PREREG.relative_to(REPO)), "events_admitted": len(a),
              "dev_window": r2.DEV, "confirmation_window": r2.CONF,
              "legs_exit_how": legs["exit_how"].value_counts().to_dict(),
              "variants": res,
              "passed_dev": [v for v in VARIANTS if res[v]["dev_pass"]],
              "passed_confirmation": [v for v in VARIANTS if res[v].get("confirmation", {}).get("pass")]}
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    for v in VARIANTS:
        s = res[v]["k1.0"]
        print(f"{v:38s} n={s['n']:4d} mean={s['mean']:+.3f} t={s['t']:+.2f} hit={s.get('hit_rate', float('nan')):.2f} "
              f"holm={adj_p[v]:.3f} folds+={s.get('folds_positive')} k1.5={res[v]['k1.5']['mean']:+.3f} "
              f"pass={res[v]['dev_pass']}" + (f" conf={res[v]['confirmation']['pass']}"
                                               if "confirmation" in res[v] else ""))


if __name__ == "__main__":
    main()
