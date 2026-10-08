# scripts/run_v8_stage2.py — V8.2 walk-forward under the frozen pre-registration.
"""Build candidate defined-risk trades (process pool over months), simulate
the 15 pre-registered variants and their always-on benchmarks at k = 1.0
and 1.5, and apply the pass rules of docs/specs/V8_STAGE2_PREREG_20261008.json.
Statistics (Sharpe, deflated Sharpe, CSCV PBO) are shared with stage 1.

Outputs under nn_meta/validation/v8-stage2-20261008-r0/: candidates.parquet,
equity_<k>.npz, report.json.
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
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract  # noqa: E402
from nn_meta import v8_vol_trades as vt  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

_s1 = importlib.util.spec_from_file_location("run_v8_stage1", REPO / "scripts" / "run_v8_stage1.py")
s1 = importlib.util.module_from_spec(_s1)
_s1.loader.exec_module(s1)

PREREG = REPO / "docs" / "specs" / "V8_STAGE2_PREREG_20261008.json"
STAGE2 = REPO / "nn_meta" / "validation" / "v8-stage2-20261008-r0"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
PIT = REPO / "nn_meta" / "validation" / "v8-pit-20261007-r0"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
START, END = "2022-03-01", "2025-12-31"
SHORT = ["ib_w1.0", "ib_w1.5", "ic_1.0_1.5"]
THETA_HIGH = [1.1, 1.2, 1.3, 1.5]
THETA_LOW = [0.8, 0.9, 1.0]
MIN_TRADES = 30


def variants() -> list[dict]:
    out = [{"structure": s, "side": "short", "theta": th} for s in SHORT for th in THETA_HIGH]
    out += [{"structure": "straddle", "side": "long", "theta": th} for th in THETA_LOW]
    return out


def monthly_universe(days: list[str]) -> dict:
    pool = json.loads(POOL.read_text())
    etfs = set(pool["rule"]["etfs_every_month"])
    mem = pd.read_parquet(PIT / "membership.parquet", columns=["month", "ticker", "score", "available_at"])
    freezes = mem.drop_duplicates("month")[["month", "available_at"]].sort_values("available_at")
    out = {}
    for d in days:
        usable = freezes[freezes["available_at"] <= d]
        if usable.empty:
            continue
        src = usable["month"].iloc[-1]
        eligible = etfs | set(pool["months"].get(src, {}).get("tech", []))
        m = mem[(mem["month"] == src) & mem["ticker"].isin(eligible)]
        out[d] = set(m.nlargest(12, "score")["ticker"])
    return out


def _cand_month(path: str) -> pd.DataFrame:
    ch = pd.read_parquet(path, columns=["date", "ticker", "expiry", "cp", "strike", "close", "volume"])
    ch = ch[(ch["date"] >= START) & (ch["date"] <= END)]
    if ch.empty:
        return pd.DataFrame()
    vol = pd.read_parquet(STAGE2 / "vol_panel.parquet", columns=["ticker", "date", "iv30"])
    px = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "close", "adj_close"])
    px = px[px["date"] <= END]
    tick = set(_UNIVERSE_TICKERS)
    ch = ch[ch["ticker"].isin(tick)]
    spot = px[["ticker", "date", "close"]].rename(columns={"close": "S"}).merge(vol, on=["ticker", "date"])
    spot = spot[spot["date"].isin(ch["date"].unique())]
    return vt.build_candidates(ch, spot, px[px["ticker"].isin(tick)], vt.spread_table())


_UNIVERSE_TICKERS: list[str] = []


def _init(tickers):
    _UNIVERSE_TICKERS[:] = tickers


def evaluate(days, eq, entries, bench_eq, prereg, names) -> dict:
    days = np.array(days)
    r = np.zeros_like(eq); r[:, 1:] = eq[:, 1:] / eq[:, :-1] - 1
    br = np.zeros_like(bench_eq); br[:, 1:] = bench_eq[:, 1:] / bench_eq[:, :-1] - 1
    folds = []
    for lo, hi in prereg["evaluation"]["folds"]:
        a = int(np.searchsorted(days, lo)); b = int(np.searchsorted(days, hi, side="right"))
        is_sr = s1.sharpe(r[:, :a]); oos_sr = s1.sharpe(r[:, a:b])
        is_n = entries[:, :a].sum(1)
        elig = (is_n >= MIN_TRADES) & np.isfinite(is_sr)
        if not elig.any():
            folds.append({"fold": [lo, hi], "eligible": 0}); continue
        sel = int(np.argmax(np.where(elig, is_sr, -np.inf)))
        oos_ret = float(np.prod(1 + r[sel, a:b]) - 1)
        bidx = names[sel]["bench"]
        b_ret = float(np.prod(1 + br[bidx, a:b]) - 1)
        m = elig & np.isfinite(oos_sr)
        rho = spearmanr(is_sr[m], oos_sr[m]).correlation if m.sum() > 2 else float("nan")
        folds.append({"fold": [lo, hi], "eligible": int(elig.sum()), "selected": names[sel]["v"],
                      "is_sharpe": float(is_sr[sel]), "is_trades": int(is_n[sel]),
                      "oos_return": oos_ret, "oos_sharpe": float(oos_sr[sel]),
                      "oos_trades": int(entries[sel, a:b].sum()),
                      "always_on_return": b_ret, "beats": bool(oos_ret > max(b_ret, 0.0)),
                      "rank_spearman": float(rho),
                      "all_oos_returns": {json.dumps(names[i]["v"]): float(np.prod(1 + r[i, a:b]) - 1)
                                          for i in range(len(names))},
                      "_r": r[sel, a:b]})
    good = [f for f in folds if f.get("eligible")]
    concat = np.concatenate([f.pop("_r") for f in good]) if good else np.array([0.0, 0.0])
    dev = r[:, int(np.searchsorted(days, START)):]
    sr_daily = dev.mean(1) / np.where(dev.std(1, ddof=1) > 0, dev.std(1, ddof=1), np.nan)
    rhos = np.array([f["rank_spearman"] for f in good]) if good else np.array([np.nan])
    return {"folds": folds, "beats": int(sum(f["beats"] for f in good)),
            "rank_positive_folds": int((rhos > 0).sum()), "rank_median": float(np.nanmedian(rhos)),
            "deflated_sharpe": s1.deflated_sharpe(concat, n_trials=len(names),
                                                  sr_var=float(np.nanvar(sr_daily))),
            "pbo": s1.pbo_cscv(dev),
            "total_entries": {json.dumps(names[i]["v"]): int(entries[i].sum()) for i in range(len(names))}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    v8_contract.verify()
    prereg = json.loads(PREREG.read_text())
    px = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date"])
    days = sorted(px.loc[(px["date"] >= START) & (px["date"] <= END), "date"].unique())
    universe = monthly_universe(days)
    tickers = sorted(set().union(*universe.values()))
    cpath = STAGE2 / "candidates.parquet"
    if not cpath.exists():
        months = sorted(str(p) for p in (STAGE2 / "chains").glob("*.parquet")
                        if START[:7] <= p.stem <= END[:7])
        workers, why = autosize_workers(per_worker_mb=4000, cap=args.workers)
        print(f"candidates: {len(months)} months, {len(tickers)} tickers {tickers}, {why}", flush=True)
        with ProcessPoolExecutor(workers, initializer=_init, initargs=(tickers,)) as ex:
            cand = pd.concat(list(ex.map(_cand_month, months)), ignore_index=True)
        cand.to_parquet(cpath, index=False)
    cand = pd.read_parquet(cpath)
    print(f"{len(cand)} candidate trades: {cand['structure'].value_counts().to_dict()}", flush=True)
    vol = pd.read_parquet(STAGE2 / "vol_panel.parquet", columns=["ticker", "date", "iv30", "har_vol"])
    vol = vol[vol["date"] <= END].sort_values(["ticker", "date"])
    vol["ratio"] = vol["iv30"] / vol["har_vol"]
    # the signal for entry day d is the previous trading day's ratio
    vol["entry_day"] = vol.groupby("ticker")["date"].shift(-1)
    sig = vol.dropna(subset=["entry_day", "ratio"])
    report = {"prereg": str(PREREG.relative_to(REPO)), "universe_tickers": tickers,
              "candidates": cand["structure"].value_counts().to_dict()}
    for k in vt.KS:
        cands = {s: {(t, d): (R, sd) for t, d, R, sd in g[["ticker", "date", f"R_{k}", "settle_date"]].itertuples(index=False)}
                 for s, g in cand.groupby("structure")}
        names, eqs, ents = [], [], []
        for v in variants():
            if v["side"] == "short":
                on = sig["ratio"] >= v["theta"]
            else:
                on = sig["ratio"] <= v["theta"]
            signal = dict(zip(zip(sig["ticker"], sig["entry_day"]), on))
            e, n = vt.simulate(np.array(days), cands[v["structure"]], signal, universe)
            names.append({"v": v, "bench": [*SHORT, "straddle"].index(v["structure"])})
            eqs.append(e); ents.append(n)
        bench = []
        for s in [*SHORT, "straddle"]:
            always = {key: True for key in cands[s]}
            e, _ = vt.simulate(np.array(days), cands[s], always, universe)
            bench.append(e)
        eqs, ents, bench = np.array(eqs), np.array(ents), np.array(bench)
        np.savez_compressed(STAGE2 / f"equity_{k}.npz", eq=eqs, entries=ents, bench=bench,
                            days=np.array(days))
        report[f"k{k}"] = evaluate(days, eqs, ents, bench, prereg, names)
        report[f"k{k}"]["always_on_total"] = {s: float(bench[i][-1] - 1) for i, s in enumerate([*SHORT, "straddle"])}
        report[f"k{k}"]["variant_total"] = {json.dumps(names[i]["v"]): float(eqs[i][-1] - 1) for i in range(len(names))}
    a, b = report["k1.0"], report["k1.5"]
    rules = {"beat_benchmarks": a["beats"] >= 4,
             "rank_persistence": a["rank_positive_folds"] >= 4 and a["rank_median"] >= 0.10,
             "deflated_sharpe": a["deflated_sharpe"]["probability"] >= 0.95,
             "pbo": a["pbo"]["pbo"] < 0.5,
             "cost_stress": b["beats"] >= 4}
    report["pass_rules"] = rules
    report["verdict"] = "PASS" if all(rules.values()) else "FAIL"
    (STAGE2 / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({"verdict": report["verdict"], "rules": rules, "beats": [a["beats"], b["beats"]],
                      "rank": [a["rank_positive_folds"], round(a["rank_median"], 3)],
                      "dsr": round(a["deflated_sharpe"]["probability"], 4),
                      "pbo": round(a["pbo"]["pbo"], 3)}, indent=1))


if __name__ == "__main__":
    main()
