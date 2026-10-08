# scripts/run_v8_h1_confirm.py — H1 confirmation: stock holdout (A) and calls (B).
"""Single pre-registered run of docs/specs/V8_H1_CONFIRM_PREREG_20261008.json.

A: H1b_sue_h20 on the daily engine through 2026-09-14; score 2026 only.
B: the same signals as ~45 DTE / 0.60 delta calls at pessimistic fixed
   spreads; dev 2021-05..2025-12, and 2026 only if dev passes.
Output: nn_meta/validation/v8-events-20261008-r0/h1_confirm/report.json.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract  # noqa: E402
from nn_meta import v8_engine as en  # noqa: E402
from nn_meta import v8_event_signals as es  # noqa: E402
from nn_meta import v8_h1_calls as hc  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


s1 = _load("run_v8_stage1", REPO / "scripts" / "run_v8_stage1.py")
ev = _load("run_v8_events", REPO / "scripts" / "run_v8_events.py")
PREREG = REPO / "docs" / "specs" / "V8_H1_CONFIRM_PREREG_20261008.json"
OUT = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0" / "h1_confirm"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
CHAINS = REPO / "nn_meta" / "validation" / "v8-stage2-20261008-r0" / "chains"
DATA_END = "2026-09-14"
DEV_START, DEV_END, HOLD_START = "2021-05-03", "2025-12-31", "2026-01-01"
FOLDS = [["2023-01-01", "2023-06-30"], ["2023-07-01", "2023-12-31"], ["2024-01-01", "2024-06-30"],
         ["2024-07-01", "2024-12-31"], ["2025-01-01", "2025-06-30"], ["2025-07-01", "2025-12-31"]]


def window_stats(r: np.ndarray, bench: pd.DataFrame, a: int, b: int) -> dict:
    x = r[a:b]; q = bench["QQQ"].to_numpy()[a:b]; e = bench["EW_universe"].to_numpy()[a:b]
    sh = lambda y: float(y.mean() / y.std(ddof=1) * math.sqrt(252))
    X = np.column_stack([np.ones(len(e)), e])
    coef, *_ = np.linalg.lstsq(X, x, rcond=None)
    return {"return": float(np.prod(1 + x) - 1), "sharpe": sh(x), "qqq_return": float(np.prod(1 + q) - 1),
            "qqq_sharpe": sh(q), "ew_return": float(np.prod(1 + e) - 1),
            "alpha_annual": float(coef[0] * 252), "beta_ew": float(coef[1]), "days": int(b - a)}


def _chain_month(job):
    path, pairs = job
    ch = pd.read_parquet(path, columns=["date", "ticker", "expiry", "cp", "strike", "close", "volume"])
    key = ch["ticker"] + "|" + ch["date"]
    return ch[key.isin(pairs)]


def main() -> None:
    v8_contract.verify()
    OUT.mkdir(parents=True, exist_ok=True)
    px = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "close", "adj_close"])
    px = px[px["date"] <= DATA_END]
    grid = sorted(px["date"].unique())
    tickers = sorted(px["ticker"].unique())
    panel = en.build_panel("1d", tickers, grid)
    days = panel["days"]
    ev.END = DATA_END                                   # events usable through the data end
    ctx = ev.build_context(tickers, days)
    E, X = es.h1(ctx)["H1b_sue_h20"]
    bench = s1.benchmarks(days)
    dd = np.array(days)
    report = {"prereg": str(PREREG.relative_to(REPO)), "entry_signals": int(E.sum()),
              "entry_signals_2026": int(E[:, dd >= HOLD_START].sum())}
    # ── A: stock holdout ──
    Eb, Xb = np.packbits(E[:, None, :], axis=2), np.packbits(X[:, None, :], axis=2)
    a = int(np.searchsorted(dd, "2026-01-02")); b = len(days)
    A = {}
    for mult in (1.0, 1.5):
        eq, tr, _ = en.run_variant(panel, Eb, Xb, 0, mult)
        r = np.zeros_like(eq); r[1:] = eq[1:] / eq[:-1] - 1
        st = window_stats(r, bench, a, b)
        st["round_trips_2026"] = int(tr[a:].sum())
        st["dev_check_2023_2025"] = window_stats(r, bench, int(np.searchsorted(dd, "2023-01-01")),
                                                  int(np.searchsorted(dd, DEV_END, side="right")))
        A[f"x{mult}"] = st
    rules_a = {k: (A["x1.0"]["return"] > 0, A["x1.0"]["sharpe"] > A["x1.0"]["qqq_sharpe"],
                   A["x1.0"]["alpha_annual"] > 0)[i] for i, k in enumerate(["positive", "sharpe_vs_qqq", "alpha"])}
    rules_a["cost_stress"] = (A["x1.5"]["return"] > 0 and A["x1.5"]["sharpe"] > A["x1.5"]["qqq_sharpe"]
                              and A["x1.5"]["alpha_annual"] > 0)
    report["A_stock_holdout"] = {"stats": A, "rules": rules_a,
                                 "verdict": "PASS" if all(rules_a.values()) else "FAIL"}
    # ── B: calls ──
    s_idx, t_idx = np.nonzero(E)
    cand = pd.DataFrame({"s": s_idx, "t": t_idx})
    cand = cand[cand["t"] + 1 < len(days)]
    cand["ticker"] = [tickers[s] for s in cand["s"]]
    cand["entry_i"] = cand["t"] + 1
    cand["entry_day"] = [days[i] for i in cand["entry_i"]]
    cand["prio"] = [panel["prio"][s, i] for s, i in zip(cand["s"], cand["entry_i"])]
    need = set()
    for t, i in zip(cand["ticker"], cand["entry_i"]):
        for k in [0] + list(range(hc.HOLD, hc.HOLD + hc.FALLBACK_DAYS + 1)):
            if i + k < len(days):
                need.add(f"{t}|{days[i + k]}")
    months = sorted({p.split("|")[1][:7] for p in need})
    workers, why = autosize_workers(per_worker_mb=3000)
    print(f"calls: {len(cand)} candidate entries, {len(need)} chain-days, {why}", flush=True)
    with ProcessPoolExecutor(workers) as exe:
        chains = pd.concat(list(exe.map(_chain_month, [(str(CHAINS / f"{m}.parquet"), need) for m in months])),
                           ignore_index=True)
    by_td = {k: g for k, g in chains.groupby(["ticker", "date"])}
    rawc = px.pivot(index="date", columns="ticker", values="close")
    ratio = (px["close"] / px["adj_close"]).set_axis(pd.MultiIndex.from_frame(px[["ticker", "date"]]))
    rows = []
    for _, c in cand.iterrows():
        t, i, d = c["ticker"], int(c["entry_i"]), c["entry_day"]
        g = by_td.get((t, d))
        S = rawc.at[d, t] if d in rawc.index else np.nan
        if g is None or not np.isfinite(S):
            continue
        pick = hc.pick_call(g, d, float(S))
        if pick is None:
            continue
        r0 = ratio.get((t, d), np.nan)
        def split_factor(day, t=t, r0=r0):
            r1 = ratio.get((t, day), np.nan)
            f = r1 / r0 if np.isfinite(r1) and np.isfinite(r0) else 1.0
            return 1.0 / f if abs(math.log(f)) > 0.1 else 1.0
        prices = {}
        for k in range(hc.HOLD, hc.HOLD + hc.FALLBACK_DAYS + 1):
            if i + k < len(days):
                gg = by_td.get((t, days[i + k]))
                if gg is not None:
                    q = gg[(gg["cp"] == "C") & (gg["expiry"] == pick["expiry"]) & (gg["volume"] >= 1)]
                    prices.update({(days[i + k], round(float(kk), 4)): float(v) for kk, v in zip(q["strike"], q["close"])})
        rc = {days[j]: rawc.at[days[j], t] for j in range(i, min(i + hc.HOLD + 1, len(days)))}
        xd, xv, how = hc.exit_price(prices, days, i, pick["strike"], pick["expiry"], rc, split_factor)
        if not xd or not np.isfinite(xv):
            continue
        rows.append({"ticker": t, "entry_day": d, "exit_day": xd, "entry_price": pick["price"],
                     "exit_value": xv, "exit_how": how, "prio": c["prio"], **{f"call_{k}": v for k, v in pick.items()}})
    trades = pd.DataFrame(rows)
    trades.to_parquet(OUT / "call_candidates.parquet", index=False)
    print(f"calls: {len(trades)} priced candidates; exits {trades['exit_how'].value_counts().to_dict()}", flush=True)

    def book(tr, lo, hi, hs):
        sel = tr[(tr["entry_day"] >= lo) & (tr["exit_day"] <= hi)]
        dsub = [x for x in days if lo <= x <= hi]
        eq, taken = hc.simulate(sel, dsub, hs)
        rets = taken["ret"].to_numpy() if len(taken) else np.array([])
        t_stat = float(rets.mean() / (rets.std(ddof=1) / math.sqrt(len(rets)))) if len(rets) > 1 else float("nan")
        folds = []
        dsa = np.array(dsub)
        for flo, fhi in FOLDS:
            fa = int(np.searchsorted(dsa, flo)); fb = int(np.searchsorted(dsa, fhi, side="right")) - 1
            if fa < len(dsa) and fb >= fa:
                prev = eq[fa - 1] if fa > 0 else 1.0
                folds.append(float(eq[fb] / prev - 1))
        return {"total_return": float(eq[-1] - 1), "trades": int(len(rets)),
                "mean_trade_return": float(rets.mean()) if len(rets) else float("nan"),
                "median_trade_return": float(np.median(rets)) if len(rets) else float("nan"),
                "win_rate": float((rets > 0).mean()) if len(rets) else float("nan"),
                "t_stat": t_stat, "fold_returns": folds}
    dev = {f"hs{hs}": book(trades, DEV_START, DEV_END, hs) for hs in (0.03, 0.045)}
    d0, d1 = dev["hs0.03"], dev["hs0.045"]
    rules_b = {"positive_total": d0["total_return"] > 0,
               "folds_positive": sum(x > 0 for x in d0["fold_returns"]) >= 4,
               "trade_edge": d0["mean_trade_return"] > 0 and d0["t_stat"] >= 2,
               "cost_stress": d1["total_return"] > 0 and d1["mean_trade_return"] > 0 and d1["t_stat"] >= 2}
    B = {"dev": dev, "dev_rules": rules_b, "dev_verdict": "PASS" if all(rules_b.values()) else "FAIL"}
    if B["dev_verdict"] == "PASS":
        h = book(trades, HOLD_START, DATA_END, 0.03)
        B["holdout"] = h
        B["holdout_verdict"] = "PASS" if (h["total_return"] > 0 and h["mean_trade_return"] > 0
                                          and h["t_stat"] >= 1) else "FAIL"
    else:
        B["holdout"] = "not run (dev failed, as pre-registered)"
    report["B_calls"] = B
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({"A": report["A_stock_holdout"]["verdict"], "A_rules": {k: bool(v) for k, v in rules_a.items()},
                      "A_2026": {k: round(v, 3) for k, v in A["x1.0"].items() if isinstance(v, float)},
                      "B_dev": B["dev_verdict"], "B_rules": {k: bool(v) for k, v in rules_b.items()},
                      "B_dev_stats": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d0.items()},
                      "B_holdout": B.get("holdout_verdict", "not run")}, indent=1, default=str))


if __name__ == "__main__":
    main()
