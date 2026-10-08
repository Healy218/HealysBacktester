# scripts/run_v8_stage1.py — V8.1 walk-forward under the frozen pre-registration.
"""Run every stage-1 variant (1h and 1d, long only, 10 slots) at cost
multipliers 1.0 and 1.5, then evaluate exactly as pre-registered in
docs/specs/V8_STAGE1_PREREG_20261008.json:

  folds          six half-years 2023H1..2025H2, expanding in-sample from 2021-05-03
  selection      top in-sample annualized Sharpe, >= 30 in-sample round trips,
                 pooled over both timeframes (top-1 primary; top-10, per family)
  benchmarks     QQQ, XLK, SPY, equal-weight admitted universe
  pass rules     beat every benchmark in >= 4/6 folds (1.0x); rank persistence
                 (Spearman IS vs OOS Sharpe > 0 in >= 4/6, median >= 0.10);
                 deflated Sharpe >= 0.95; CSCV PBO < 0.5 (16 blocks);
                 beat-benchmarks again at 1.5x

Outputs under --out: returns_<mult>.npz (daily equity, trades, wins per
variant), report.json. Engine threads share memory (numba nogil).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr, skew, kurtosis

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract  # noqa: E402
from nn_meta import v8_engine as en  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

PREREG = REPO / "docs" / "specs" / "V8_STAGE1_PREREG_20261008.json"
STAGE = REPO / "nn_meta" / "validation" / "v8-stage1-20261008-r0"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
START = "2021-05-03"
MIN_TRADES = 30
ANN = math.sqrt(252)


def simulate_all(mult: float, threads: int) -> dict:
    out = {"eq": [], "tr": [], "win": [], "variants": []}
    days_ref = None
    for tf in ("1h", "1d"):
        sig = STAGE / "signals" / tf
        grid = json.loads((sig / "grid.json").read_text())
        variants = json.loads((sig / "variants.json").read_text())
        tickers = sorted(p.stem for p in sig.glob("*.npz"))
        panel = en.build_panel(tf, tickers, grid)
        if days_ref is None:
            days_ref = panel["days"]
        elif panel["days"] != days_ref:
            raise SystemExit("1h and 1d day grids differ")
        E, X = en.load_bits(sig, tickers)
        t0 = time.time()
        with ThreadPoolExecutor(threads) as ex:
            res = list(ex.map(lambda v: en.run_variant(panel, E, X, v, mult), range(len(variants))))
        print(f"  {tf} x{mult}: {len(variants)} variants in {time.time() - t0:.1f}s", flush=True)
        out["eq"] += [r[0] for r in res]; out["tr"] += [r[1] for r in res]
        out["win"] += [r[2] for r in res]; out["variants"] += variants
        del E, X
    return {"days": days_ref, "eq": np.array(out["eq"]), "tr": np.array(out["tr"]),
            "win": np.array(out["win"]), "variants": out["variants"]}


def benchmarks(days: list[str]) -> pd.DataFrame:
    d = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "adj_close"])
    d = d[d["date"].isin(days)]
    px = d.pivot(index="date", columns="ticker", values="adj_close").reindex(days)
    ret = px / px.shift(1) - 1
    adm = pd.read_parquet(REPO / "nn_meta/validation/v8-liquidity-20261008-r0/admission.parquet",
                          columns=["ticker", "date", "admitted"])
    adm = adm[adm["date"].isin(days)].pivot(index="date", columns="ticker",
                                             values="admitted").reindex(days).fillna(False)
    adm = adm.reindex(columns=ret.columns, fill_value=False).astype(bool)
    ew = ret.where(adm).mean(axis=1)
    return pd.DataFrame({"QQQ": ret["QQQ"], "XLK": ret["XLK"], "SPY": ret["SPY"],
                         "EW_universe": ew}).fillna(0.0)


def sharpe(r: np.ndarray, axis=-1) -> np.ndarray:
    m = r.mean(axis=axis); s = r.std(axis=axis, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(s > 0, m / s * ANN, np.nan)


def deflated_sharpe(r: np.ndarray, n_trials: int, sr_var: float) -> dict:
    """Bailey & Lopez de Prado (2014), per-period (daily) Sharpe."""
    T = len(r)
    sr = r.mean() / r.std(ddof=1)
    g = 0.5772156649
    sr0 = math.sqrt(sr_var) * ((1 - g) * norm.ppf(1 - 1 / n_trials)
                               + g * norm.ppf(1 - 1 / (n_trials * math.e)))
    sk, ku = skew(r), kurtosis(r, fisher=False)
    denom = math.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-12))
    z = (sr - sr0) * math.sqrt(T - 1) / denom
    return {"daily_sharpe": float(sr), "annual_sharpe": float(sr * ANN),
            "sr0_daily": float(sr0), "probability": float(norm.cdf(z)), "T": T}


def pbo_cscv(R: np.ndarray, blocks: int = 16) -> dict:
    """CSCV PBO over a (variants, days) return matrix."""
    n, T = R.shape
    edges = np.linspace(0, T, blocks + 1).astype(int)
    s1 = np.stack([R[:, a:b].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    s2 = np.stack([(R[:, a:b] ** 2).sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    cnt = np.diff(edges)
    logits = []
    all_b = set(range(blocks))
    for combo in combinations(range(blocks), blocks // 2):
        ins = list(combo); oos = sorted(all_b - set(combo))
        def sr(cols):
            c = cnt[cols].sum(); m = s1[:, cols].sum(1) / c
            v = (s2[:, cols].sum(1) - c * m ** 2) / (c - 1)
            return np.where(v > 0, m / np.sqrt(np.maximum(v, 1e-30)), -np.inf)
        si, so = sr(ins), sr(oos)
        best = int(np.argmax(si))
        rank = (so < so[best]).sum() + 1           # 1 = worst
        w = rank / (n + 1)
        logits.append(math.log(w / (1 - w)))
    logits = np.array(logits)
    return {"pbo": float((logits <= 0).mean()), "combinations": len(logits),
            "median_logit": float(np.median(logits))}


def evaluate(sim: dict, bench: pd.DataFrame, prereg: dict) -> dict:
    days = np.array(sim["days"])
    eq = sim["eq"]
    r = np.zeros_like(eq)
    r[:, 1:] = eq[:, 1:] / eq[:, :-1] - 1
    start = int(np.searchsorted(days, START))
    fams = np.array([v["family"] + "/" + v["timeframe"] for v in sim["variants"]])
    folds = []
    for lo, hi in prereg["evaluation"]["folds"]:
        a = int(np.searchsorted(days, lo)); b = int(np.searchsorted(days, hi, side="right"))
        is_r, oos_r = r[:, start:a], r[:, a:b]
        is_tr = sim["tr"][:, start:a].sum(1)
        is_sr, oos_sr = sharpe(is_r), sharpe(oos_r)
        elig = (is_tr >= MIN_TRADES) & np.isfinite(is_sr)
        order = np.argsort(np.where(elig, is_sr, -np.inf))[::-1]
        top1, top10 = int(order[0]), order[:10]
        oos_ret = np.prod(1 + oos_r, axis=1) - 1
        b_ret = (1 + bench.iloc[a:b]).prod() - 1
        per_family = {}
        for f in np.unique(fams[elig]):
            idx = np.nonzero(elig & (fams == f))[0]
            j = idx[np.argmax(is_sr[idx])]
            per_family[f] = {"variant": sim["variants"][j]["params"], "is_sharpe": float(is_sr[j]),
                             "oos_return": float(oos_ret[j]), "oos_sharpe": float(oos_sr[j])}
        m = elig & np.isfinite(oos_sr)
        rho = spearmanr(is_sr[m], oos_sr[m]).correlation if m.sum() > 2 else float("nan")
        folds.append({
            "fold": [lo, hi], "eligible": int(elig.sum()),
            "top1": {"variant": sim["variants"][top1], "is_sharpe": float(is_sr[top1]),
                     "is_trades": int(is_tr[top1]), "oos_return": float(oos_ret[top1]),
                     "oos_sharpe": float(oos_sr[top1])},
            "top10_oos_return": float(np.prod(1 + oos_r[top10].mean(0)) - 1),
            "benchmarks": {k: float(v) for k, v in b_ret.items()},
            "top1_beats_all": bool(oos_ret[top1] > b_ret.max()),
            "top10_beats_all": bool(np.prod(1 + oos_r[top10].mean(0)) - 1 > b_ret.max()),
            "rank_spearman": float(rho),
            "best_per_family": per_family,
            "_top1_oos_returns": oos_r[top1],
        })
    beats = sum(f["top1_beats_all"] for f in folds)
    rhos = np.array([f["rank_spearman"] for f in folds])
    concat = np.concatenate([f.pop("_top1_oos_returns") for f in folds])
    dev = r[:, start:int(np.searchsorted(days, "2025-12-31", side="right"))]
    active = sim["tr"][:, start:].sum(1) > 0
    sr_daily = dev[active].mean(1) / dev[active].std(1, ddof=1)
    dsr = deflated_sharpe(concat, n_trials=len(sim["variants"]), sr_var=float(np.nanvar(sr_daily)))
    pbo = pbo_cscv(dev[active])
    return {"folds": folds, "top1_folds_beating_all": int(beats),
            "rank_positive_folds": int((rhos > 0).sum()),
            "rank_median": float(np.nanmedian(rhos)),
            "deflated_sharpe": dsr, "pbo": pbo,
            "variants": len(sim["variants"]), "active_variants": int(active.sum())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=STAGE)
    ap.add_argument("--threads", type=int, default=None)
    args = ap.parse_args()
    v8_contract.verify()
    prereg = json.loads(PREREG.read_text())
    threads, why = autosize_workers(per_worker_mb=200, cap=args.threads)
    print(f"engine: {why}", flush=True)
    report = {"prereg": str(PREREG.relative_to(REPO))}
    for mult in (1.0, 1.5):
        sim = simulate_all(mult, threads)
        np.savez_compressed(args.out / f"returns_{mult}.npz", eq=sim["eq"], tr=sim["tr"],
                            win=sim["win"], days=np.array(sim["days"]))
        bench = benchmarks(sim["days"])
        report[f"x{mult}"] = evaluate(sim, bench, prereg)
    a, b = report["x1.0"], report["x1.5"]
    rules = {
        "beat_benchmarks": a["top1_folds_beating_all"] >= 4,
        "rank_persistence": a["rank_positive_folds"] >= 4 and a["rank_median"] >= 0.10,
        "deflated_sharpe": a["deflated_sharpe"]["probability"] >= 0.95,
        "pbo": a["pbo"]["pbo"] < 0.5,
        "cost_stress": b["top1_folds_beating_all"] >= 4,
    }
    report["pass_rules"] = rules
    report["verdict"] = "PASS" if all(rules.values()) else "FAIL"
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({"verdict": report["verdict"], "rules": rules,
                      "top1_beats": [a["top1_folds_beating_all"], b["top1_folds_beating_all"]],
                      "rank": [a["rank_positive_folds"], round(a["rank_median"], 3)],
                      "dsr": round(a["deflated_sharpe"]["probability"], 4),
                      "pbo": round(a["pbo"]["pbo"], 3)}, indent=1))


if __name__ == "__main__":
    main()
