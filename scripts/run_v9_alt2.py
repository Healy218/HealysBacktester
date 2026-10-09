# scripts/run_v9_alt2.py — V9 ALT-2: alternative-data direction and big-move test, run once.
"""Implements docs/specs/V9_ALT1_PREREG_20261008.json (frozen 2026-10-08).

Events: OEE admission on the early (2021-04 → 2022-02) and main tables,
unscheduled pre-announcements excluded. Scores from ALT-0 features
(analyst revisions, beat history, sales surprise, combined; attention and
analyst activity for big moves). Trades: 0.5-delta call/put (D1-D4), stock
long/short (D5-D6), 10% OTM strangle (M1-M2). Dev entries 2021-07-01 →
2025-12-31, nine half-year folds, Holm across 8.
Output (<out>/): scores.parquet, trades.parquet, report.json.
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

from nn_meta import v8_fills  # noqa: E402
from nn_meta import v9_oee as oee  # noqa: E402
from nn_meta import v9_oee_eval as ev_  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_v9_oee2", REPO / "scripts" / "run_v9_oee2.py")
r2 = importlib.util.module_from_spec(_spec)
sys.modules["run_v9_oee2"] = r2
_spec.loader.exec_module(r2)

V = r2.V
PREREG = REPO / "docs" / "specs" / "V9_ALT1_PREREG_20261008.json"
TABLES = {"early": V / "v9-oee0-early-20261008-r0" / "events.parquet", "main": r2.EVENTS}
FEATURES = V / "v9-alt0-20261008-r0" / "features.parquet"
LEGS = V / "v9-otm-oos-20261008-r0" / "legs.parquet"
FILINGS = V / "v8-events-20261008-r0" / "sec" / "filings.parquet"
DEFAULT_OUT = V / "v9-alt2-20261008-r0"
DEV = ("2021-07-01", "2025-12-31")
FOLDS = ["2021H2"] + [f"{y}{h}" for y in (2022, 2023, 2024, 2025) for h in ("H1", "H2")]
KS = (1.0, 1.5)
CLOSE_MIN = 16 * 60
VARIANTS = ["D1_revisions_option", "D2_beats_option", "D3_sales_option", "D4_combined_option",
            "D5_revisions_stock", "D6_combined_stock", "M1_attention_strangle", "M2_activity_strangle"]
TABLE_DIR = {"early": "v9-oee0-early-20261008-r0", "main": "v9-oee0-20261008-r0"}


def load_events() -> pd.DataFrame:
    filings = pd.read_parquet(FILINGS)
    wings = pd.DataFrame(columns=["wing_C_strike", "wing_C_reaction", "wing_P_strike", "wing_P_reaction"])
    parts = []
    for name, path in TABLES.items():
        a = ev_.admit(pd.read_parquet(path)).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
        a.index.name = "key"
        a, _ = r2.expiry_day_intrinsic(a, wings)
        a = a[~oee.preannouncement_flags(a, filings)]
        a = a.reset_index()
        a["leg_key"] = name + ":" + a["key"].astype(str)
        a["table"] = TABLE_DIR[name]
        parts.append(a)
    return pd.concat(parts, ignore_index=True).sort_values(["entry_day", "ticker"]).reset_index(drop=True)


def scores(a: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_parquet(FEATURES)
    x = a[["table", "accession", "ticker", "entry_day"]].merge(f.drop(columns=["entry_day"]),
                                                               on=["table", "accession", "ticker"], how="left")
    assert len(x) == len(a)
    sc = pd.DataFrame(index=a.index)

    def pct(col):
        p, t = ev_.trailing_rank(a["entry_day"], x[col].to_numpy(dtype=float))
        return 2 * p - 1, t
    comp = {}
    for col in ("an90_net_pt", "an90_net_rating", "an90_pt_upside", "prior_eps_surprise",
                "prior_sales_surprise", "beats_last4", "ins90_net", "wiki_abn", "an30_n"):
        comp[col], sc[f"tercile_{col}"] = pct(col)
        sc[col] = x[col].to_numpy()

    def combine(cols, need):
        m = np.column_stack([comp[c] for c in cols])
        n = np.isfinite(m).sum(1)
        with np.errstate(all="ignore"):
            v = np.nanmean(np.where(np.isfinite(m), m, np.nan), axis=1)
        return np.where(n >= need, v, np.nan)
    sc["S1"] = comp["an90_net_pt"]
    sc["S2"] = combine(["prior_eps_surprise", "beats_last4"], 1)
    sc["S3"] = comp["prior_sales_surprise"]
    sc["S4"] = combine(["an90_net_pt", "an90_net_rating", "an90_pt_upside", "prior_eps_surprise",
                        "prior_sales_surprise", "beats_last4", "ins90_net"], 3)
    sc["T1"] = sc["tercile_an90_net_pt"]
    sc["T2"] = ev_.trailing_rank(a["entry_day"], sc["S2"].to_numpy())[1]
    sc["T3"] = sc["tercile_prior_sales_surprise"]
    sc["T4"] = ev_.trailing_rank(a["entry_day"], sc["S4"].to_numpy())[1]
    return sc


def option_ret(sm, e, side, k):
    nm, cp = ("call50", "C") if side > 0 else ("put50", "P")
    K, p0, p1 = e[f"{nm}_strike"], e[f"{nm}_entry"], e[f"{nm}_reaction"]
    if not (np.isfinite(p0) and np.isfinite(p1)):
        return None
    dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
    return ev_.long_return([r2.leg(sm, p0, cp, K, e["S_entry"], e["front_dte"])],
                           [r2.leg(sm, p1, cp, K, e["S_reaction"], dte_out)], k)


def stock_ret(e, side, bars, k):
    b = bars.get(e["ticker"])
    if b is None or e["entry_day"] not in b.index or e["reaction_day"] not in b.index:
        return None
    x, y = b.loc[e["entry_day"]], b.loc[e["reaction_day"]]
    yr = int(e["entry_day"][:4])
    hs0 = v8_fills.stock_half_spread_bps([e["ticker"]], [x["close"]], [CLOSE_MIN], [yr])[0]
    hs1 = v8_fills.stock_half_spread_bps([e["ticker"]], [y["close"]], [CLOSE_MIN], [yr])[0]
    c0 = k * (hs0 + v8_fills.SLIPPAGE_BPS) / 1e4
    c1 = k * (hs1 + v8_fills.SLIPPAGE_BPS) / 1e4
    fee = v8_fills.SELL_REG_BPS / 1e4
    if side > 0:
        return y["adj_close"] * (1 - c1) * (1 - fee) / (x["adj_close"] * (1 + c0)) - 1
    sell, buy = x["adj_close"] * (1 - c0) * (1 - fee), y["adj_close"] * (1 + c1)
    return (sell - buy) / sell


def strangle_ret(sm, e, legs, k):
    lg = legs.get(e["leg_key"])
    if lg is None or not {"p10_C", "p10_P"} <= set(lg.index):
        return None
    c, p = lg.loc["p10_C"], lg.loc["p10_P"]
    dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
    return ev_.long_return(
        [r2.leg(sm, x["entry"], x["cp"], x["strike"], e["S_entry"], e["front_dte"]) for x in (c, p)],
        [r2.leg(sm, x["exit"], x["cp"], x["strike"], e["S_reaction"], dte_out) for x in (c, p)], k)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if (args.out / "report.json").exists():
        raise SystemExit(f"{args.out}/report.json exists: ALT-2 runs once")
    args.out.mkdir(parents=True, exist_ok=True)
    assert json.loads(PREREG.read_text())["approved_by"].startswith("user")

    a = load_events()
    sc = scores(a)
    pd.concat([a[["ticker", "entry_day", "leg_key"]], sc], axis=1).to_parquet(args.out / "scores.parquet")
    sm = ev_.SpreadModel(r2.SPREADS)
    bars_df = pd.read_parquet(r2.BARS, columns=["ticker", "date", "close", "adj_close"])
    bars = {t: g.set_index("date") for t, g in bars_df.groupby("ticker")}
    legs_df = pd.read_parquet(LEGS)
    legs_df = legs_df[(legs_df["penny"] == 0.0) & legs_df["leg"].isin(["p10_C", "p10_P"])]
    legs = {k: g.set_index("leg") for k, g in legs_df.groupby("key")}

    plan = {"D1_revisions_option": ("T1", "option"), "D2_beats_option": ("T2", "option"),
            "D3_sales_option": ("T3", "option"), "D4_combined_option": ("T4", "option"),
            "D5_revisions_stock": ("T1", "stock"), "D6_combined_stock": ("T4", "stock"),
            "M1_attention_strangle": ("tercile_wiki_abn", "strangle"),
            "M2_activity_strangle": ("tercile_an30_n", "strangle")}
    rows = []
    for v, (col, kind) in plan.items():
        for i in a.index:
            t = sc.at[i, col]
            if not np.isfinite(t) or t == 0 or (kind == "strangle" and t != 1):
                continue
            e = a.loc[i]
            side = int(t)
            rec = {"variant": v, "ticker": e["ticker"], "entry_day": e["entry_day"],
                   "reaction_day": e["reaction_day"], "side": side, "leg_key": e["leg_key"]}
            for k in KS:
                r = (option_ret(sm, e, side, k) if kind == "option" else
                     stock_ret(e, side, bars, k) if kind == "stock" else strangle_ret(sm, e, legs, k))
                rec[f"ret_{k}"] = r
            rec["dropped"] = "" if rec["ret_1.0"] is not None and np.isfinite(rec["ret_1.0"]) else "missing"
            rows.append(rec)
    tr = pd.DataFrame(rows)
    tr.to_parquet(args.out / "trades.parquet", index=False)

    ok = tr[(tr["dropped"] == "") & (tr["entry_day"] >= DEV[0]) & (tr["entry_day"] <= DEV[1])]
    res, p1 = {}, {}
    for v in VARIANTS:
        t = ok[ok["variant"] == v]
        res[v] = {}
        for k in KS:
            r = t[f"ret_{k}"].to_numpy(dtype=float)
            s = ev_.clustered_t(r, t["reaction_day"].to_numpy())
            fm = t.groupby(ev_.half_year(t["entry_day"]))[f"ret_{k}"].mean()
            s["folds"] = {f: (float(fm[f]) if f in fm.index else None) for f in FOLDS}
            s["folds_positive"] = int(sum(1 for f in FOLDS if f in fm.index and fm[f] > 0))
            if len(r):
                s["hit_rate"] = float((r > 0).mean())
                top = t.sort_values(f"ret_{k}", ascending=False)
                s["top5"] = top.head(5)[["ticker", "entry_day", "side", f"ret_{k}"]].to_dict("records")
                s["mean_without_top_event"] = float(top[f"ret_{k}"].iloc[1:].mean()) if len(r) > 1 else None
            res[v][f"k{k}"] = s
        p1[v] = res[v]["k1.0"]["p_one_sided"]
    adj = ev_.holm(p1)
    for v in VARIANTS:
        s1, s15 = res[v]["k1.0"], res[v]["k1.5"]
        rules = {"edge": bool(s1["mean"] > 0 and s1["t"] >= 2), "multiple_testing": bool(adj[v] < 0.05),
                 "folds": bool(s1["folds_positive"] >= 6), "cost_stress": bool(s15["mean"] > 0 and s15["t"] >= 2)}
        res[v].update(holm_p=adj[v], rules=rules, dev_pass=all(rules.values()))
    dev = (a["entry_day"] >= DEV[0]) & (a["entry_day"] <= DEV[1])
    up = np.sign(a.loc[dev, "realized_move"])
    acc = {}
    for s in ("S1", "S2", "S3", "S4"):
        m = sc.loc[dev, s].notna() & (np.sign(sc.loc[dev, s]) != 0)
        acc[s] = {"n": int(m.sum()), "sign_correct": float((np.sign(sc.loc[dev, s][m]) == up[m]).mean())}
        tt = sc.loc[dev, f"T{s[1]}"]
        mt = tt.isin([1, -1])
        acc[s]["tercile_sign_correct"] = float((np.sign(tt[mt]) == up[mt]).mean())
    big = (a.loc[dev, "realized_move"].abs() > a.loc[dev, "implied_move"])
    mag = {c: big.groupby(sc.loc[dev, f"tercile_{c}"]).mean().round(3).to_dict() for c in ("wiki_abn", "an30_n")}
    report = {"prereg": str(PREREG.relative_to(REPO)), "dev": DEV, "events": len(a), "dev_events": int(dev.sum()),
              "sign_accuracy_dev": acc, "big_move_rate_by_tercile_dev": mag, "variants": res,
              "passed_dev": [v for v in VARIANTS if res[v]["dev_pass"]]}
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print("sign accuracy:", json.dumps(acc))
    print("P(|move| > implied) by tercile:", json.dumps(mag))
    for v in VARIANTS:
        s = res[v]["k1.0"]
        print(f"{v:24s} n={s['n']:5d} mean={s['mean']:+.4f} t={s['t']:+.2f} hit={s.get('hit_rate', float('nan')):.2f} "
              f"holm={adj[v]:.3f} folds+={s['folds_positive']}/9 k1.5={res[v]['k1.5']['mean']:+.4f} "
              f"w/o top={s.get('mean_without_top_event')} pass={res[v]['dev_pass']}")


if __name__ == "__main__":
    main()
