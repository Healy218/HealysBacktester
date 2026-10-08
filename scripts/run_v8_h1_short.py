# scripts/run_v8_h1_short.py — H1 short side, long-short and puts (pre-registered).
"""Single run of docs/specs/V8_H1_SHORT_PREREG_20261008.json. Dev 2021-05..2025-12
first; the 2026 holdout runs only for the strategies whose dev rules pass.
Output: nn_meta/validation/v8-events-20261008-r0/h1_short/report.json.
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
cf = _load("run_v8_h1_confirm", REPO / "scripts" / "run_v8_h1_confirm.py")
PREREG = REPO / "docs" / "specs" / "V8_H1_SHORT_PREREG_20261008.json"
EVR = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0"
OUT = EVR / "h1_short"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
DATA_END, DEV_START, DEV_END = "2026-09-14", "2021-05-03", "2025-12-31"
FOLDS = cf.FOLDS
N_TRIALS = 18


def borrow_matrix(px: pd.DataFrame, tickers, days, adv20: np.ndarray) -> np.ndarray:
    raw = px.pivot(index="ticker", columns="date", values="close").reindex(index=tickers, columns=days).to_numpy()
    prev = np.full(raw.shape, np.nan); prev[:, 1:] = raw[:, :-1]
    easy = (prev >= 20) & (adv20 >= 250e6)
    return np.where(easy, 0.01, 0.05)


def daily_r(eq):
    r = np.zeros_like(eq); r[1:] = eq[1:] / eq[:-1] - 1
    return r


def dev_stats(r, bench, dd):
    out = {"folds": []}
    for lo, hi in FOLDS:
        a = int(np.searchsorted(dd, lo)); b = int(np.searchsorted(dd, hi, side="right"))
        out["folds"].append(float(np.prod(1 + r[a:b]) - 1))
    s = int(np.searchsorted(dd, DEV_START)); e = int(np.searchsorted(dd, DEV_END, side="right"))
    out["total"] = float(np.prod(1 + r[s:e]) - 1)
    a23 = int(np.searchsorted(dd, "2023-01-01"))
    out["w2023_2025"] = cf.window_stats(r, bench, a23, e)
    return out


def main() -> None:
    v8_contract.verify()
    OUT.mkdir(parents=True, exist_ok=True)
    px = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "close", "adj_close"])
    px = px[px["date"] <= DATA_END]
    days = sorted(px["date"].unique()); tickers = sorted(px["ticker"].unique())
    panel = en.build_panel("1d", tickers, days)
    days = panel["days"]; dd = np.array(days)
    ev.END = DATA_END
    ctx = ev.build_context(tickers, days)
    EL, XL = es.h1(ctx)["H1b_sue_h20"]
    ES, XS = es.h1_short(ctx)
    borrow = borrow_matrix(px, tickers, days, panel["prio"])
    bench = s1.benchmarks(days)
    pk = lambda m: np.packbits(m[:, None, :], axis=2)
    report = {"prereg": str(PREREG.relative_to(REPO)), "short_signals": int(ES.sum()),
              "short_signals_2026": int(ES[:, dd >= "2026-01-01"].sum()),
              "borrow_5pct_share_of_signals": float((borrow[ES] > 0.02).mean()) if ES.any() else None}
    books = {}
    for mult in (1.0, 1.5):
        eqL, trL, _ = en.run_variant(panel, pk(EL), pk(XL), 0, mult)
        eqS, trS, wS = en.run_variant_short(panel, pk(ES), pk(XS), 0, mult, borrow)
        rL, rS = daily_r(eqL), daily_r(eqS)
        books[mult] = {"short": rS, "long_short": 0.5 * (rL + rS), "short_trades": trS, "short_wins": wS}
    # DSR variance from the 16 event variants plus these two books (dev, 2021-05..2025)
    z = np.load(EVR / "equity_1.0.npz")
    evr = np.zeros_like(z["eq"]); evr[:, 1:] = z["eq"][:, 1:] / z["eq"][:, :-1] - 1
    ezd = np.array(z["days"]); es0 = int(np.searchsorted(ezd, DEV_START))
    s = int(np.searchsorted(dd, DEV_START)); e = int(np.searchsorted(dd, DEV_END, side="right"))
    srs = [x[es0:].mean() / x[es0:].std(ddof=1) for x in evr if x[es0:].std() > 0]
    srs += [books[1.0][k][s:e].mean() / books[1.0][k][s:e].std(ddof=1) for k in ("short", "long_short")]
    sr_var = float(np.var(srs))
    a23 = int(np.searchsorted(dd, "2023-01-01"))
    dev = {}
    for k in ("short", "long_short"):
        dev[k] = {f"x{m}": dev_stats(books[m][k], bench, dd) for m in (1.0, 1.5)}
        dev[k]["dsr"] = s1.deflated_sharpe(books[1.0][k][a23:e], n_trials=N_TRIALS, sr_var=sr_var)
    dev["short"]["round_trips_dev"] = int(books[1.0]["short_trades"][s:e].sum())
    dev["short"]["win_rate_dev"] = float(books[1.0]["short_wins"][s:e].sum() / max(books[1.0]["short_trades"][s:e].sum(), 1))
    d, d5 = dev["short"]["x1.0"], dev["short"]["x1.5"]
    rules_s = {"positive": d["total"] > 0, "folds_positive": sum(x > 0 for x in d["folds"]) >= 4,
               "alpha": d["w2023_2025"]["alpha_annual"] > 0,
               "deflated_sharpe": dev["short"]["dsr"]["probability"] >= 0.95,
               "cost_stress": d5["total"] > 0 and sum(x > 0 for x in d5["folds"]) >= 4}
    c, c5 = dev["long_short"]["x1.0"], dev["long_short"]["x1.5"]
    w, w5 = c["w2023_2025"], c5["w2023_2025"]
    rules_ls = {"sharpe_vs_qqq": w["sharpe"] > w["qqq_sharpe"], "alpha": w["alpha_annual"] > 0,
                "folds_positive": sum(x > 0 for x in c["folds"]) >= 4,
                "deflated_sharpe": dev["long_short"]["dsr"]["probability"] >= 0.95,
                "cost_stress": w5["sharpe"] > w5["qqq_sharpe"] and w5["alpha_annual"] > 0}
    report["dev"] = dev
    report["dev_rules"] = {"H1_short": rules_s, "H1_long_short": rules_ls}
    hold = {}
    h0 = int(np.searchsorted(dd, "2026-01-02"))
    if all(rules_s.values()):
        st = {f"x{m}": cf.window_stats(books[m]["short"], bench, h0, len(dd)) for m in (1.0, 1.5)}
        hold["H1_short"] = {"stats": st, "verdict": "PASS" if all(st[x]["return"] > 0 and st[x]["alpha_annual"] > 0 for x in st) else "FAIL"}
    else:
        hold["H1_short"] = "not run (dev failed)"
    if all(rules_ls.values()):
        st = {f"x{m}": cf.window_stats(books[m]["long_short"], bench, h0, len(dd)) for m in (1.0, 1.5)}
        hold["H1_long_short"] = {"stats": st, "verdict": "PASS" if all(st[x]["sharpe"] > st[x]["qqq_sharpe"] and st[x]["alpha_annual"] > 0 for x in st) else "FAIL"}
    else:
        hold["H1_long_short"] = "not run (dev failed)"
    # ── puts ──
    s_idx, t_idx = np.nonzero(ES)
    cand = pd.DataFrame({"s": s_idx, "t": t_idx})
    cand = cand[cand["t"] + 1 < len(days)]
    cand["ticker"] = [tickers[x] for x in cand["s"]]
    cand["entry_i"] = cand["t"] + 1
    cand["entry_day"] = [days[i] for i in cand["entry_i"]]
    cand["prio"] = [panel["prio"][x, i] for x, i in zip(cand["s"], cand["entry_i"])]
    need = {f"{t}|{days[i + k]}" for t, i in zip(cand["ticker"], cand["entry_i"])
            for k in [0] + list(range(hc.HOLD, hc.HOLD + hc.FALLBACK_DAYS + 1)) if i + k < len(days)}
    months = sorted({p.split("|")[1][:7] for p in need})
    workers, _ = autosize_workers(per_worker_mb=3000)
    with ProcessPoolExecutor(workers) as exe:
        chains = pd.concat(list(exe.map(cf._chain_month, [(str(cf.CHAINS / f"{m}.parquet"), need) for m in months])),
                           ignore_index=True)
    by_td = {k: g for k, g in chains.groupby(["ticker", "date"])}
    rawc = px.pivot(index="date", columns="ticker", values="close")
    ratio = (px["close"] / px["adj_close"]).set_axis(pd.MultiIndex.from_frame(px[["ticker", "date"]]))
    rows = []
    for _, cnd in cand.iterrows():
        t, i, dday = cnd["ticker"], int(cnd["entry_i"]), cnd["entry_day"]
        g = by_td.get((t, dday)); S = rawc.at[dday, t] if dday in rawc.index else np.nan
        if g is None or not np.isfinite(S):
            continue
        pick = hc.pick_call(g, dday, float(S), cp="P")
        if pick is None:
            continue
        r0 = ratio.get((t, dday), np.nan)
        def split_factor(day, t=t, r0=r0):
            r1 = ratio.get((t, day), np.nan)
            f = r1 / r0 if np.isfinite(r1) and np.isfinite(r0) else 1.0
            return 1.0 / f if abs(math.log(f)) > 0.1 else 1.0
        prices = {}
        for k in range(hc.HOLD, hc.HOLD + hc.FALLBACK_DAYS + 1):
            if i + k < len(days):
                gg = by_td.get((t, days[i + k]))
                if gg is not None:
                    q = gg[(gg["cp"] == "P") & (gg["expiry"] == pick["expiry"]) & (gg["volume"] >= 1)]
                    prices.update({(days[i + k], round(float(kk), 4)): float(v) for kk, v in zip(q["strike"], q["close"])})
        rc = {days[j]: rawc.at[days[j], t] for j in range(i, min(i + hc.HOLD + 1, len(days)))}
        xd, xv, how = hc.exit_price(prices, days, i, pick["strike"], pick["expiry"], rc, split_factor, cp="P")
        if not xd or not np.isfinite(xv):
            continue
        rows.append({"ticker": t, "entry_day": dday, "exit_day": xd, "entry_price": pick["price"],
                     "exit_value": xv, "exit_how": how, "prio": cnd["prio"],
                     **{f"put_{k}": v for k, v in pick.items()}})
    trades = pd.DataFrame(rows)
    trades.to_parquet(OUT / "put_candidates.parquet", index=False)

    def book(tr, lo, hi, hs):
        sel = tr[(tr["entry_day"] >= lo) & (tr["exit_day"] <= hi)]
        dsub = [x for x in days if lo <= x <= hi]
        eq, taken = hc.simulate(sel, dsub, hs)
        rets = taken["ret"].to_numpy() if len(taken) else np.array([])
        tstat = float(rets.mean() / (rets.std(ddof=1) / math.sqrt(len(rets)))) if len(rets) > 1 else float("nan")
        dsa = np.array(dsub); folds = []
        for flo, fhi in FOLDS:
            fa = int(np.searchsorted(dsa, flo)); fb = int(np.searchsorted(dsa, fhi, side="right")) - 1
            if fa < len(dsa) and fb >= fa:
                folds.append(float(eq[fb] / (eq[fa - 1] if fa > 0 else 1.0) - 1))
        return {"total_return": float(eq[-1] - 1), "trades": int(len(rets)),
                "mean_trade_return": float(rets.mean()) if len(rets) else float("nan"),
                "median_trade_return": float(np.median(rets)) if len(rets) else float("nan"),
                "win_rate": float((rets > 0).mean()) if len(rets) else float("nan"),
                "t_stat": tstat, "fold_returns": folds}
    pdev = {f"hs{h}": book(trades, DEV_START, DEV_END, h) for h in (0.03, 0.045)}
    p0, p1 = pdev["hs0.03"], pdev["hs0.045"]
    rules_p = {"positive_total": p0["total_return"] > 0,
               "folds_positive": sum(x > 0 for x in p0["fold_returns"]) >= 4,
               "trade_edge": p0["mean_trade_return"] > 0 and p0["t_stat"] >= 2,
               "cost_stress": p1["total_return"] > 0 and p1["mean_trade_return"] > 0 and p1["t_stat"] >= 2}
    report["puts"] = {"candidates": int(len(trades)), "dev": pdev, "dev_rules": rules_p}
    if all(rules_p.values()):
        h = book(trades, "2026-01-01", DATA_END, 0.03)
        hold["H1_puts"] = {"stats": h, "verdict": "PASS" if (h["total_return"] > 0 and h["mean_trade_return"] > 0 and h["t_stat"] >= 1) else "FAIL"}
    else:
        hold["H1_puts"] = "not run (dev failed)"
    report["holdout_2026"] = hold
    report["dev_verdicts"] = {"H1_short": "PASS" if all(rules_s.values()) else "FAIL",
                              "H1_long_short": "PASS" if all(rules_ls.values()) else "FAIL",
                              "H1_puts": "PASS" if all(rules_p.values()) else "FAIL"}
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({"dev_verdicts": report["dev_verdicts"],
                      "rules": {k: {r: bool(v) for r, v in x.items()} for k, x in report["dev_rules"].items()},
                      "put_rules": {r: bool(v) for r, v in rules_p.items()},
                      "holdout": {k: (v if isinstance(v, str) else v["verdict"]) for k, v in hold.items()}}, indent=1))


if __name__ == "__main__":
    main()
