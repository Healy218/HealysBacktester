# scripts/run_v9_oee_j.py — V9 OEE-J: FA score + TA-pool agreement on OTM legs, run once.
"""Implements docs/specs/V9_OEE_J_PREREG_20261008.json (frozen 2026-10-08).

T: the V8 stage-1 signal pool (16 families, 2,840 variants, 1d and 1h). Each
variant's state is +1 after an entry, -1 after an exit; family votes are
variant means per timeframe; daily T is the mean of the 32 family-timeframe
votes; T is daily T averaged over the 5 trading days before the entry day.
F: mean of (2 x trailing percentile - 1) of prior SUE and revenue acceleration.
Variants J1 (agree -> one leg), J2 (tilted strangle), J3 (hybrid) on the 10%
and 20% OTM legs from the OEE-H4 leg table.

Output (<out>/): scores.parquet, trades.parquet, report.json.
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

from nn_meta import v9_oee_eval as ev_  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_v9_oee2", REPO / "scripts" / "run_v9_oee2.py")
r2 = importlib.util.module_from_spec(_spec)
sys.modules["run_v9_oee2"] = r2
_spec.loader.exec_module(r2)

PREREG = REPO / "docs" / "specs" / "V9_OEE_J_PREREG_20261008.json"
SIGNALS = r2.V / "v8-stage1-20261008-r0" / "signals"
FEATURES = r2.V / "v9-oee2-20261008-r0" / "features.parquet"
LEGS = r2.V / "v9-oee-h4-20261008-r0" / "legs.parquet"
DEFAULT_OUT = r2.V / "v9-oee-j-20261008-r0"
WINDOW = 5
VARIANTS = [f"{j}_{p}pct" for p in (10, 20) for j in ("J1_agree_one_leg", "J2_tilted_strangle", "J3_hybrid")]


def variant_states(E: np.ndarray, X: np.ndarray) -> np.ndarray:
    """(variants, bars) booleans -> int8 state: +1 after an entry, -1 after an
    exit, 0 before the first signal or when both fall on the same bar."""
    idx = np.arange(E.shape[1])
    le = np.maximum.accumulate(np.where(E, idx, -1), axis=1)
    lx = np.maximum.accumulate(np.where(X, idx, -1), axis=1)
    return np.sign(le - lx).astype(np.int8)


def family_votes(states: np.ndarray, fam_index: dict[str, np.ndarray]) -> np.ndarray:
    """(families, bars) mean state per family."""
    return np.stack([states[ix].mean(0) for ix in fam_index.values()])


def _ticker_T(job):
    ticker, days_needed = job
    out = {}
    per_tf = []
    for tf in ("1d", "1h"):
        path = SIGNALS / tf / f"{ticker}.npz"
        if not path.exists():
            return ticker, {}
        z = np.load(path)
        n = int(z["T"])
        E = np.unpackbits(z["E"], axis=1, count=n).astype(bool)
        X = np.unpackbits(z["X"], axis=1, count=n).astype(bool)
        meta = json.loads((SIGNALS / tf / "variants.json").read_text())
        grid = json.loads((SIGNALS / tf / "grid.json").read_text())
        fam = {}
        for i, v in enumerate(meta):
            fam.setdefault(v["family"], []).append(i)
        votes = family_votes(variant_states(E, X), {k: np.array(v) for k, v in fam.items()})
        # column of each day's close: the day itself (1d) or its last bar (1h)
        col = {}
        for j, key in enumerate(grid):
            col[key.split("|")[0]] = j
        per_tf.append((votes, col))
    for d in days_needed:
        cols = [c.get(d) for _, c in per_tf]
        if any(c is None for c in cols):
            continue
        out[d] = float(np.mean(np.concatenate([v[:, c] for (v, _), c in zip(per_tf, cols)])))
    return ticker, out


def ta_scores(a: pd.DataFrame, days: list[str], cap: int | None) -> np.ndarray:
    pos = {d: i for i, d in enumerate(days)}
    need: dict[str, set] = {}
    for t, e in zip(a["ticker"], a["entry_day"]):
        i = pos[e]
        need.setdefault(t, set()).update(days[max(i - WINDOW, 0):i])
    workers, why = autosize_workers(per_worker_mb=2500, cap=cap)
    print(f"TA pool: {len(need)} tickers; {why}", flush=True)
    with ProcessPoolExecutor(workers) as ex:
        daily = dict(ex.map(_ticker_T, sorted((t, sorted(s)) for t, s in need.items())))
    T = np.full(len(a), np.nan)
    for j, (t, e) in enumerate(zip(a["ticker"], a["entry_day"])):
        i = pos[e]
        vals = [daily.get(t, {}).get(d) for d in days[max(i - WINDOW, 0):i]]
        if len(vals) == WINDOW and all(v is not None for v in vals):
            T[j] = float(np.mean(vals))
    return T


def leg_ret(sm, e, lg, k) -> float:
    dte_in = e["front_dte"]
    dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
    return ev_.long_return([r2.leg(sm, lg["entry"], lg["cp"], lg["strike"], e["S_entry"], dte_in)],
                           [r2.leg(sm, lg["exit"], lg["cp"], lg["strike"], e["S_reaction"], dte_out)], k)


def strangle_ret(sm, e, c, p, k) -> float:
    dte_in = e["front_dte"]
    dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
    return ev_.long_return(
        [r2.leg(sm, x["entry"], x["cp"], x["strike"], e["S_entry"], dte_in) for x in (c, p)],
        [r2.leg(sm, x["exit"], x["cp"], x["strike"], e["S_reaction"], dte_out) for x in (c, p)], k)


def build_trades(a: pd.DataFrame, sc: pd.DataFrame, legs: pd.DataFrame, sm) -> pd.DataFrame:
    L = {k: g.set_index("leg") for k, g in legs.groupby("key")}
    rows = []
    for k in a.index:
        e, s = a.loc[k], sc.loc[k]
        lg = L.get(k)
        if lg is None or not np.isfinite(s["T"]):
            continue
        for p in (10, 20):
            c = lg.loc[f"p{p}_C"] if f"p{p}_C" in lg.index else None
            q = lg.loc[f"p{p}_P"] if f"p{p}_P" in lg.index else None
            base = {"key": k, "ticker": e["ticker"], "entry_day": e["entry_day"],
                    "reaction_day": e["reaction_day"], "session": e["session"]}
            fire = bool(s["j1_fire"])
            side_leg = (c if s["D_sign"] > 0 else q) if fire else None
            plans = {}
            if fire and side_leg is not None:
                plans[f"J1_agree_one_leg_{p}pct"] = ("one", side_leg)
                plans[f"J3_hybrid_{p}pct"] = ("one", side_leg)
            if c is not None and q is not None:
                plans[f"J2_tilted_strangle_{p}pct"] = ("tilt", None)
                if not fire:
                    plans[f"J3_hybrid_{p}pct"] = ("strangle", None)
            for v, (kind, x) in plans.items():
                rec = {**base, "variant": v, "kind": kind}
                legs_used = [x] if kind == "one" else [c, q]
                if any(not np.isfinite(y["exit"]) for y in legs_used):
                    rows.append({**rec, "dropped": "missing_exit"}); continue
                for k_ in r2.KS:
                    if kind == "one":
                        rec[f"ret_{k_}"] = leg_ret(sm, e, x, k_)
                    elif kind == "strangle":
                        rec[f"ret_{k_}"] = strangle_ret(sm, e, c, q, k_)
                    else:
                        w = 0.5 + 0.5 * s["D"]
                        rec[f"ret_{k_}"] = w * leg_ret(sm, e, c, k_) + (1 - w) * leg_ret(sm, e, q, k_)
                rows.append({**rec, "dropped": ""})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    if (args.out / "report.json").exists():
        raise SystemExit(f"{args.out}/report.json exists: OEE-J runs once")
    args.out.mkdir(parents=True, exist_ok=True)
    assert json.loads(PREREG.read_text())["approved_by"].startswith("user")

    a = ev_.admit(pd.read_parquet(r2.EVENTS)).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
    a.index.name = "key"
    tau = a["tau_utc"].dt.tz_convert("America/New_York")
    h = tau.dt.hour + tau.dt.minute / 60
    a["session"] = np.select([h < 9.5, h < 16], ["pre_market", "intraday"], "after_close")
    feats = pd.read_parquet(FEATURES)
    assert len(feats) == len(a), "OEE-2 features do not align"
    days = sorted(pd.read_parquet(r2.BARS, columns=["date"])["date"].unique())
    # dev and burn-in only: the stage-1 signals end 2025-12-31
    a = a[a["entry_day"] <= r2.DEV[1]]
    feats = feats.loc[a.index]

    sc = pd.DataFrame(index=a.index)
    sc["T"] = ta_scores(a, days, args.workers)
    comps = []
    for c in ("sue", "revenue_accel"):
        p, _ = ev_.trailing_rank(a["entry_day"], feats[c].to_numpy())
        comps.append(2 * p - 1)
    comp = np.column_stack(comps)
    sc["F"] = np.where(np.isfinite(comp).any(1), np.nanmean(np.where(np.isfinite(comp), comp, np.nan), axis=1), 0.0)
    sc["F"] = sc["F"].fillna(0.0)
    sc["D"] = (sc["F"] + sc["T"]) / 2
    sc["D_sign"] = np.sign(sc["D"])
    _, ter_absT = ev_.trailing_rank(a["entry_day"], np.abs(sc["T"].to_numpy()))
    sc["absT_tercile"] = ter_absT
    sc["j1_fire"] = ((np.sign(sc["F"]) == np.sign(sc["T"])) & (np.sign(sc["T"]) != 0)
                     & (sc["F"].abs() >= 1 / 3) & (sc["absT_tercile"] == 1))
    sc.to_parquet(args.out / "scores.parquet")

    legs = pd.read_parquet(LEGS)
    tr = build_trades(a, sc, legs, ev_.SpreadModel(r2.SPREADS))
    tr.to_parquet(args.out / "trades.parquet", index=False)

    ok = tr[tr["dropped"] == ""]
    in_dev = (ok["entry_day"] >= r2.DEV[0]) & (ok["entry_day"] <= r2.DEV[1])
    res, p1 = {}, {}
    for v in VARIANTS:
        t = ok[(ok["variant"] == v) & in_dev]
        res[v] = {f"k{k}": r2.window_stats(t, k, days, folds=True) for k in r2.KS}
        res[v]["kinds"] = t["kind"].value_counts().to_dict()
        p1[v] = res[v]["k1.0"]["p_one_sided"]
    adj_p = ev_.holm(p1)
    for v in VARIANTS:
        s1, s15 = res[v]["k1.0"], res[v]["k1.5"]
        rules = {"edge": bool(s1["mean"] > 0 and s1["t"] >= 2),
                 "multiple_testing": bool(adj_p[v] < 0.05),
                 "folds": bool(s1.get("folds_positive", 0) >= 4),
                 "cost_stress": bool(s15["mean"] > 0 and s15["t"] >= 2)}
        res[v].update(holm_p=adj_p[v], rules=rules, dev_pass=all(rules.values()))
    dv = (a["entry_day"] >= r2.DEV[0])
    up = np.sign(a.loc[dv, "realized_move"])
    acc = {}
    for c in ("T", "F", "D"):
        m = sc.loc[dv, c].notna() & (np.sign(sc.loc[dv, c]) != 0)
        acc[c] = {"n": int(m.sum()), "sign_correct": float((np.sign(sc.loc[dv, c][m]) == up[m]).mean())}
    m = dv & sc["j1_fire"]
    acc["J1_fired"] = {"n": int(m.sum()), "sign_correct": float((sc.loc[m, "D_sign"] == np.sign(a.loc[m, "realized_move"])).mean())}
    report = {"prereg": str(PREREG.relative_to(REPO)), "dev_window": r2.DEV,
              "T_coverage_dev": float(sc.loc[dv, "T"].notna().mean()),
              "sign_accuracy_dev": acc, "variants": res,
              "passed_dev": [v for v in VARIANTS if res[v]["dev_pass"]],
              "confirmation": "requires regenerating the stage-1 signals through 2026-09-14; run only for dev passes"}
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print("sign accuracy (dev):", json.dumps(acc))
    for v in VARIANTS:
        s = res[v]["k1.0"]
        print(f"{v:28s} n={s['n']:4d} mean={s['mean']:+.3f} t={s['t']:+.2f} hit={s.get('hit_rate', float('nan')):.2f} "
              f"holm={adj_p[v]:.3f} folds+={s.get('folds_positive')} k1.5={res[v]['k1.5']['mean']:+.3f} "
              f"pass={res[v]['dev_pass']}")


if __name__ == "__main__":
    main()
