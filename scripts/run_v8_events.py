# scripts/run_v8_events.py — V8 event/attention hypotheses, pre-registered run.
"""Build the 16 variants of docs/specs/V8_EVENTS_PREREG_20261008.json,
simulate them on the daily V8 engine at cost 1.0x and 1.5x, and apply the
per-hypothesis rules and shared gates. Statistics come from the stage-1
runner. Output: nn_meta/validation/v8-events-20261008-r0/report.json and
equity_<mult>.npz.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract  # noqa: E402
from nn_meta import v8_engine as en  # noqa: E402
from nn_meta import v8_event_signals as es  # noqa: E402

_s1 = importlib.util.spec_from_file_location("run_v8_stage1", REPO / "scripts" / "run_v8_stage1.py")
s1 = importlib.util.module_from_spec(_s1)
_s1.loader.exec_module(s1)

PREREG = REPO / "docs" / "specs" / "V8_EVENTS_PREREG_20261008.json"
EV = REPO / "nn_meta" / "validation" / "v8-events-20261008-r0"
SIG1D = REPO / "nn_meta" / "validation" / "v8-stage1-20261008-r0" / "signals" / "1d"
BARS = REPO / "nn_meta" / "validation" / "v8-data-20261008-r0"
ADM = REPO / "nn_meta" / "validation" / "v8-liquidity-20261008-r0" / "admission.parquet"
START, END = "2021-05-03", "2025-12-31"
MIN_TRADES = 30


def matrix(df: pd.DataFrame, col: str, tickers, days) -> np.ndarray:
    p = df.pivot_table(index="ticker", columns="date", values=col, aggfunc="last")
    return p.reindex(index=tickers, columns=days).to_numpy(float)


def build_context(tickers, days) -> dict:
    d = pd.read_parquet(BARS / "bars_1d.parquet", columns=["ticker", "date", "adj_close"])
    d = d[d["date"] <= END]
    adj = matrix(d, "adj_close", tickers, days)
    adm = pd.read_parquet(ADM, columns=["ticker", "date", "admitted"])
    admitted = np.nan_to_num(matrix(adm[adm["date"] <= END].assign(
        admitted=lambda x: x["admitted"].astype(float)), "admitted", tickers, days)).astype(bool)
    raw_ret = np.full(adj.shape, np.nan); raw_ret[:, 1:] = adj[:, 1:] / adj[:, :-1] - 1
    sv = pd.read_parquet(EV / "finra" / "short_volume.parquet")
    sv = sv.groupby(["ticker", "date"], as_index=False)[["short_volume", "total_volume"]].sum()
    sv["ratio"] = sv["short_volume"] / sv["total_volume"]
    wiki = pd.read_parquet(EV / "wiki" / "pageviews.parquet", columns=["ticker", "date", "views"])
    cut = lambda x, c="available_at_utc": x[pd.to_datetime(x[c], utc=True) <= pd.Timestamp(END + " 23:59", tz="America/New_York")]
    return {
        "tickers": tickers, "days": days, "S": len(tickers), "T": len(days),
        "admitted": admitted, "raw_ret": raw_ret, "abn": es.abnormal_returns(adj, admitted),
        "filings": cut(pd.read_parquet(EV / "sec" / "filings.parquet")),
        "facts": cut(pd.read_parquet(EV / "sec" / "facts.parquet")),
        "insider": cut(pd.read_parquet(EV / "insider" / "insider.parquet")),
        "news": cut(pd.read_parquet(EV / "news" / "news.parquet", columns=["ticker", "available_at_utc"])),
        "short_ratio": matrix(sv, "ratio", tickers, days),
        "views": matrix(wiki, "views", tickers, days),
    }


def main() -> None:
    v8_contract.verify()
    prereg = json.loads(PREREG.read_text())
    grid = json.loads((SIG1D / "grid.json").read_text())
    tickers = sorted(p.stem for p in SIG1D.glob("*.npz"))
    panel = en.build_panel("1d", tickers, grid)
    days = panel["days"]
    ctx = build_context(tickers, days)
    variants: dict = {}
    variants.update(es.h1(ctx)); variants.update(es.h2(ctx))
    h3v, h3prio = es.h3(ctx); variants.update(h3v); variants.update(es.h4(ctx))
    names = sorted(variants)
    assert len(names) == 16, names
    hyp = {n: n.split("_")[0][:2] for n in names}               # H1..H4
    E = np.stack([variants[n][0] for n in names], 1)            # (S, V, T)
    X = np.stack([variants[n][1] for n in names], 1)
    Eb, Xb = np.packbits(E, axis=2), np.packbits(X, axis=2)
    signal_counts = {n: int(variants[n][0].sum()) for n in names}
    print("entry signals:", signal_counts, flush=True)
    bench = s1.benchmarks(days)
    report = {"prereg": str(PREREG.relative_to(REPO)), "signal_counts": signal_counts}
    for mult in (1.0, 1.5):
        eq, tr = [], []
        for v, n in enumerate(names):
            p = dict(panel)
            if n in h3prio:
                p["prio"] = h3prio[n]
            e, t, _ = en.run_variant(p, Eb, Xb, v, mult)
            eq.append(e); tr.append(t)
        eq, tr = np.array(eq), np.array(tr)
        np.savez_compressed(EV / f"equity_{mult}.npz", eq=eq, tr=tr, days=np.array(days), names=np.array(names))
        r = np.zeros_like(eq); r[:, 1:] = eq[:, 1:] / eq[:, :-1] - 1
        dd = np.array(days); start = int(np.searchsorted(dd, START))
        res = {"folds": [], "per_hypothesis": {}}
        concat = {h: [] for h in sorted(set(hyp.values()))}
        beats = {h: 0 for h in concat}
        rhos = []
        for lo, hi in prereg["evaluation"]["folds"]:
            a = int(np.searchsorted(dd, lo)); b = int(np.searchsorted(dd, hi, side="right"))
            is_sr, oos_sr = s1.sharpe(r[:, start:a]), s1.sharpe(r[:, a:b])
            is_tr = tr[:, start:a].sum(1)
            elig = (is_tr >= MIN_TRADES) & np.isfinite(is_sr)
            bret = (1 + bench.iloc[a:b]).prod() - 1
            m = elig & np.isfinite(oos_sr)
            rho = spearmanr(is_sr[m], oos_sr[m]).correlation if m.sum() > 2 else np.nan
            rhos.append(rho)
            fold = {"fold": [lo, hi], "benchmarks": {k: float(x) for k, x in bret.items()},
                    "rank_spearman": float(rho), "hypotheses": {}}
            for h in concat:
                idx = [i for i, n in enumerate(names) if hyp[n] == h and elig[i]]
                if not idx:
                    fold["hypotheses"][h] = {"selected": None, "beats": False}
                    concat[h].append(np.zeros(b - a)); continue
                sel = max(idx, key=lambda i: is_sr[i])
                oos = float(np.prod(1 + r[sel, a:b]) - 1)
                ok = oos > bret.max()
                beats[h] += ok
                concat[h].append(r[sel, a:b])
                fold["hypotheses"][h] = {"selected": names[sel], "is_sharpe": float(is_sr[sel]),
                                         "is_trades": int(is_tr[sel]), "oos_return": oos,
                                         "oos_sharpe": float(oos_sr[sel]),
                                         "oos_trades": int(tr[sel, a:b].sum()), "beats": bool(ok)}
            res["folds"].append(fold)
        dev = r[:, start:]
        active = tr[:, start:].sum(1) > 0
        sr_d = dev[active].mean(1) / dev[active].std(1, ddof=1)
        rh = np.array(rhos, float)
        res["rank_positive_folds"] = int((rh > 0).sum()); res["rank_median"] = float(np.nanmedian(rh))
        res["pbo"] = s1.pbo_cscv(dev[active])
        for h in concat:
            dsr = s1.deflated_sharpe(np.concatenate(concat[h]), n_trials=16, sr_var=float(np.nanvar(sr_d)))
            res["per_hypothesis"][h] = {"folds_beating": beats[h], "deflated_sharpe": dsr}
        res["variant_total_return"] = {n: float(eq[i][-1] - 1) for i, n in enumerate(names)}
        res["variant_round_trips"] = {n: int(tr[i].sum()) for i, n in enumerate(names)}
        report[f"x{mult}"] = res
    a, b = report["x1.0"], report["x1.5"]
    shared = {"rank_persistence": a["rank_positive_folds"] >= 4 and a["rank_median"] >= 0.10,
              "pbo": a["pbo"]["pbo"] < 0.5}
    verdicts = {}
    for h in a["per_hypothesis"]:
        rules = {"beat_benchmarks": a["per_hypothesis"][h]["folds_beating"] >= 4,
                 "deflated_sharpe": a["per_hypothesis"][h]["deflated_sharpe"]["probability"] >= 0.95,
                 "cost_stress": b["per_hypothesis"][h]["folds_beating"] >= 4, **shared}
        verdicts[h] = {"rules": rules, "verdict": "PASS" if all(rules.values()) else "FAIL"}
    report["shared_gates"] = shared
    report["verdicts"] = verdicts
    (EV / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({h: {"verdict": v["verdict"], "beats": [a["per_hypothesis"][h]["folds_beating"],
                                                             b["per_hypothesis"][h]["folds_beating"]],
                          "dsr": round(a["per_hypothesis"][h]["deflated_sharpe"]["probability"], 3)}
                      for h, v in verdicts.items()}, indent=1))
    print("shared:", shared, "rank", a["rank_positive_folds"], round(a["rank_median"], 3),
          "pbo", round(a["pbo"]["pbo"], 3))


if __name__ == "__main__":
    main()
