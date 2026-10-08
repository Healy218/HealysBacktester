# scripts/run_v9_oee2.py — V9 OEE-2: the pre-registered walk-forward, run once.
"""Implements docs/specs/V9_OEE1_PREREG_20261008.json exactly (frozen and
approved 2026-10-08): eight variants (H1a-d direction, H2a-b IV run-up,
H3a-b cheap implied move) on the OEE-0 event table, dev entries 2023-01-01 →
2025-12-31 (2022 burn-in), then the 2026 confirmation for dev passes only.

Output (<out>/): trades.parquet (every candidate trade, both cost multiples),
report.json. Wing prices for H2b come from one chain pass over its
candidate events (process pool over entry months).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_event_signals as es  # noqa: E402
from nn_meta import v9_oee as oee  # noqa: E402
from nn_meta import v9_oee_eval as ev_  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

V = REPO / "nn_meta" / "validation"
EVENTS = V / "v9-oee0-20261008-r0" / "events.parquet"
FACTS = V / "v8-events-20261008-r0" / "sec" / "facts.parquet"
BARS = V / "v8-data-20261008-r0" / "bars_1d.parquet"
CHAINS = V / "v8-stage2-20261008-r0" / "chains"
SPREADS = V / "v8-spreads-option-20261008-r0" / "model.json"
PREREG = REPO / "docs" / "specs" / "V9_OEE1_PREREG_20261008.json"
DEFAULT_OUT = V / "v9-oee2-20261008-r0"
DEV = ("2023-01-01", "2025-12-31")
CONF = ("2026-01-01", "2026-09-14")
KS = (1.0, 1.5)
VARIANTS = ["H1a_combined", "H1b_sue", "H1c_momentum", "H1d_skew",
            "H2a_low_runup_long_straddle", "H2b_high_runup_short_fly",
            "H3a_cheap_tercile", "H3b_cheap_absolute"]


# ── H2b wings ────────────────────────────────────────────────────────────────

def _wings(job):
    months, evs = job
    tix = sorted({e["ticker"] for e in evs})
    cols = ["date", "ticker", "expiry", "cp", "strike", "close", "volume"]
    ch = pd.concat([pd.read_parquet(CHAINS / f"{m}.parquet", columns=cols,
                                    filters=[("ticker", "in", tix)]) for m in months],
                   ignore_index=True)
    out = []
    for e in evs:
        c = ch[(ch["ticker"] == e["ticker"]) & (ch["expiry"] == e["front_expiry"])]
        on_e = c[(c["date"] == e["entry_day"]) & (c["volume"] > 0) & (c["close"] > 0)]
        K, w = e["straddle_strike"], e["implied_move"] * e["S_entry"]
        rec = {"key": e["key"]}
        for cp, side in (("C", 1), ("P", -1)):
            cand = on_e[(on_e["cp"] == cp) & ((on_e["strike"] - K) * side > 0)]
            if cand.empty:
                break
            row = cand.loc[(cand["strike"] - (K + side * w)).abs().idxmin()]
            Kw = float(row["strike"])
            x = oee._close(c, e["reaction_day"], e["front_expiry"], cp, Kw)
            if not np.isfinite(x) and e["front_expiry"] == e["reaction_day"]:
                S_R = e["S_reaction"]
                x = max(S_R - Kw, 0.0) if cp == "C" else max(Kw - S_R, 0.0)
            rec.update({f"wing_{cp}_strike": Kw, f"wing_{cp}_entry": float(row["close"]),
                        f"wing_{cp}_reaction": x})
        out.append(rec)
    return out


def wing_prices(cand: pd.DataFrame, days: list[str], cap: int | None) -> pd.DataFrame:
    have = {p.stem for p in CHAINS.glob("*.parquet")}
    jobs = []
    for m, g in cand.groupby(cand["entry_day"].str[:7]):
        hi = g["reaction_day"].max()[:7]
        jobs.append((sorted(x for x in have if m <= x <= hi), g.to_dict("records")))
    workers, why = autosize_workers(per_worker_mb=1500, cap=cap)
    print(f"H2b wings: {len(cand)} events, {len(jobs)} months; {why}", flush=True)
    with ProcessPoolExecutor(workers) as ex:
        rows = [r for part in ex.map(_wings, jobs) for r in part]
    return pd.DataFrame(rows)


# ── trades ───────────────────────────────────────────────────────────────────

def leg(sm, price, cp, K, S, dte):
    return price, sm.half_spread(price, dte, ev_.otm(cp, K, S))


def trades_for(a: pd.DataFrame, variant: str, side: pd.Series, sm, wings: pd.DataFrame | None):
    rows = []
    for key, s in side.dropna().items():
        if s == 0:
            continue
        e = a.loc[key]
        dte_in = e["front_dte"]
        dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
        S0, S1 = e["S_entry"], e["S_reaction"]
        rec = {"key": key, "variant": variant, "ticker": e["ticker"], "entry_day": e["entry_day"],
               "reaction_day": e["reaction_day"], "side": int(s)}
        if variant.startswith("H1"):
            name, cp = ("call50", "C") if s > 0 else ("put50", "P")
            K, p0, p1 = e[f"{name}_strike"], e[f"{name}_entry"], e[f"{name}_reaction"]
            if not (np.isfinite(p0) and np.isfinite(p1)):
                rows.append({**rec, "dropped": "missing_exit"}); continue
            for k in KS:
                rec[f"ret_{k}"] = ev_.long_return([leg(sm, p0, cp, K, S0, dte_in)],
                                                  [leg(sm, p1, cp, K, S1, dte_out)], k)
        elif variant == "H2b_high_runup_short_fly":
            w = wings.loc[key] if key in wings.index else None
            need = ["wing_C_entry", "wing_C_reaction", "wing_P_entry", "wing_P_reaction"]
            if w is None or any(c not in w or not np.isfinite(w[c]) for c in need):
                rows.append({**rec, "dropped": "missing_wing"}); continue
            K = e["straddle_strike"]
            short_in = [leg(sm, e["call_atm_entry"], "C", K, S0, dte_in),
                        leg(sm, e["put_atm_entry"], "P", K, S0, dte_in)]
            short_out = [leg(sm, e["call_atm_reaction"], "C", K, S1, dte_out),
                         leg(sm, e["put_atm_reaction"], "P", K, S1, dte_out)]
            long_in = [leg(sm, w["wing_C_entry"], "C", w["wing_C_strike"], S0, dte_in),
                       leg(sm, w["wing_P_entry"], "P", w["wing_P_strike"], S0, dte_in)]
            long_out = [leg(sm, w["wing_C_reaction"], "C", w["wing_C_strike"], S1, dte_out),
                        leg(sm, w["wing_P_reaction"], "P", w["wing_P_strike"], S1, dte_out)]
            width = max(w["wing_C_strike"] - K, K - w["wing_P_strike"])
            for k in KS:
                rec[f"ret_{k}"] = ev_.fly_return(short_in, long_in, short_out, long_out, width, k)
            if not np.isfinite(rec[f"ret_{KS[0]}"]):
                rows.append({**rec, "dropped": "no_max_loss"}); continue
        else:                                                    # long ATM straddle
            K = e["straddle_strike"]
            if not (np.isfinite(e["call_atm_reaction"]) and np.isfinite(e["put_atm_reaction"])):
                rows.append({**rec, "dropped": "missing_exit"}); continue
            for k in KS:
                rec[f"ret_{k}"] = ev_.long_return(
                    [leg(sm, e["call_atm_entry"], "C", K, S0, dte_in),
                     leg(sm, e["put_atm_entry"], "P", K, S0, dte_in)],
                    [leg(sm, e["call_atm_reaction"], "C", K, S1, dte_out),
                     leg(sm, e["put_atm_reaction"], "P", K, S1, dte_out)], k)
        rows.append({**rec, "dropped": ""})
    return rows


# ── evaluation ───────────────────────────────────────────────────────────────

def book(t: pd.DataFrame, k: float, days: list[str]) -> dict:
    """Fixed 1% of initial equity premium per trade, P&L booked on the reaction day."""
    if t.empty:
        return {}
    pnl = t.groupby("reaction_day")[f"ret_{k}"].sum() * 0.01
    lo, hi = t["entry_day"].min(), t["reaction_day"].max()
    grid = [d for d in days if lo <= d <= hi]
    s = pnl.reindex(grid, fill_value=0.0)
    eq = 1 + s.cumsum()
    return {"total": float(s.sum()), "sharpe": float(s.mean() / s.std() * math.sqrt(252)) if s.std() > 0 else None,
            "max_drawdown": float((eq / eq.cummax() - 1).min())}


def window_stats(t: pd.DataFrame, k: float, days, folds: bool) -> dict:
    r = t[f"ret_{k}"].to_numpy()
    out = ev_.clustered_t(r, t["reaction_day"].to_numpy())
    if len(r):
        out.update(hit_rate=float((r > 0).mean()),
                   quantiles={q: float(np.quantile(r, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
                   book_1pct=book(t, k, days),
                   by_session=t.groupby("session")[f"ret_{k}"].agg(["size", "mean"]).to_dict("index"))
    if folds:
        fm = t.groupby(ev_.half_year(t["entry_day"]))[f"ret_{k}"].agg(["size", "mean"])
        out["folds"] = {f: fm.loc[f].to_dict() if f in fm.index else {"size": 0, "mean": None}
                        for f in ev_.FOLDS}
        out["folds_positive"] = int(sum(1 for f in ev_.FOLDS if f in fm.index and fm.loc[f, "mean"] > 0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    if (args.out / "report.json").exists():
        raise SystemExit(f"{args.out}/report.json exists: OEE-2 runs once")
    args.out.mkdir(parents=True, exist_ok=True)
    prereg = json.loads(PREREG.read_text())
    assert prereg["approved_by"].startswith("user"), "pre-registration not approved"

    a = ev_.admit(pd.read_parquet(EVENTS)).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
    a.index.name = "key"
    tau = a["tau_utc"].dt.tz_convert("America/New_York")
    h = tau.dt.hour + tau.dt.minute / 60
    a["session"] = np.select([h < 9.5, h < 16], ["pre_market", "intraday"], "after_close")
    bars = pd.read_parquet(BARS, columns=["ticker", "date", "adj_close"])
    days = sorted(bars["date"].unique())
    adj = bars[bars["ticker"].isin(set(a["ticker"]) | {"QQQ"})].pivot(index="date", columns="ticker",
                                                                       values="adj_close")
    facts = pd.read_parquet(FACTS, columns=["ticker", "tag", "unit", "start", "end", "val",
                                            "available_at_utc"])
    sue = es.sue_table({"tickers": sorted(a["ticker"].unique()), "facts": facts})
    feats = pd.DataFrame(index=a.index)
    feats["sue"] = ev_.sue_feature(a, sue)
    feats["revenue_accel"] = ev_._asof(a, ev_.revenue_table(facts), "revenue_accel")
    feats["momentum"] = ev_.momentum(a, adj, days)
    feats["skew"] = -a["skew_put_call"]
    feats["iv_runup"] = a["iv_runup"]
    feats["move_ratio"] = ev_.prior_move_ratio(a)

    pct, ter = {}, {}
    for c in feats:
        pct[c], ter[c] = ev_.trailing_rank(a["entry_day"], feats[c].to_numpy())
    comp = np.column_stack([pct[c] for c in ("sue", "revenue_accel", "momentum", "skew")]) - 0.5
    n_comp = np.isfinite(comp).sum(1)
    score = np.where(n_comp >= 2, np.nanmean(np.where(np.isfinite(comp), comp, np.nan), axis=1), np.nan)
    feats["h1a_score"] = score
    _, ter["h1a_score"] = ev_.trailing_rank(a["entry_day"], score)
    for c in ter:
        feats[f"tercile_{c}"] = ter[c]
    feats.to_parquet(args.out / "features.parquet")

    side = {
        "H1a_combined": pd.Series(ter["h1a_score"], index=a.index),
        "H1b_sue": pd.Series(ter["sue"], index=a.index),
        "H1c_momentum": pd.Series(ter["momentum"], index=a.index),
        "H1d_skew": pd.Series(ter["skew"], index=a.index),
        "H2a_low_runup_long_straddle": pd.Series(np.where(ter["iv_runup"] == -1, 1, np.nan), index=a.index),
        "H2b_high_runup_short_fly": pd.Series(np.where(ter["iv_runup"] == 1, -1, np.nan), index=a.index),
        "H3a_cheap_tercile": pd.Series(np.where(ter["move_ratio"] == -1, 1, np.nan), index=a.index),
        "H3b_cheap_absolute": pd.Series(np.where(feats["move_ratio"] < 0.8, 1, np.nan), index=a.index),
    }
    fly_keys = side["H2b_high_runup_short_fly"].dropna().index
    wc = a.loc[fly_keys].reset_index()
    wings = wing_prices(wc, days, args.workers).set_index("key")
    sm = ev_.SpreadModel(SPREADS)
    rows = []
    for v in VARIANTS:
        rows += trades_for(a, v, side[v], sm, wings)
    tr = pd.DataFrame(rows).merge(a[["session"]], left_on="key", right_index=True)
    tr.to_parquet(args.out / "trades.parquet", index=False)

    ok = tr[tr["dropped"] == ""]
    in_dev = (ok["entry_day"] >= DEV[0]) & (ok["entry_day"] <= DEV[1])
    in_conf = (ok["entry_day"] >= CONF[0]) & (ok["entry_day"] <= CONF[1])
    # H2 monotone requirement on all admitted dev events with a run-up tercile
    dv = a[(a["entry_day"] >= DEV[0]) & (a["entry_day"] <= DEV[1])]
    ratio = (dv["realized_move"].abs() / dv["implied_move"]).groupby(pd.Series(ter["iv_runup"], index=a.index)[dv.index]).mean()
    mono = bool(all(t in ratio.index for t in (-1, 0, 1)) and ratio[-1] > ratio[0] > ratio[1])

    res, p1 = {}, {}
    for v in VARIANTS:
        t = ok[(ok["variant"] == v) & in_dev]
        res[v] = {f"k{k}": window_stats(t, k, days, folds=True) for k in KS}
        res[v]["dropped_dev"] = (tr[(tr["variant"] == v) & (tr["entry_day"] >= DEV[0])
                                    & (tr["entry_day"] <= DEV[1])]["dropped"].value_counts().to_dict())
        p1[v] = res[v]["k1.0"]["p_one_sided"]
    adj_p = ev_.holm(p1)
    for v in VARIANTS:
        s1, s15 = res[v]["k1.0"], res[v]["k1.5"]
        rules = {
            "edge": bool(s1["mean"] > 0 and s1["t"] >= 2),
            "multiple_testing": bool(adj_p[v] < 0.05),
            "folds": bool(s1.get("folds_positive", 0) >= 4),
            "cost_stress": bool(s15["mean"] > 0 and s15["t"] >= 2),
        }
        if v.startswith("H2"):
            rules["h2_monotone"] = mono
        res[v].update(holm_p=adj_p[v], rules=rules, dev_pass=all(rules.values()))
        if res[v]["dev_pass"]:
            t = ok[(ok["variant"] == v) & in_conf]
            c = window_stats(t, 1.0, days, folds=False)
            res[v]["confirmation"] = {**c, "pass": bool(c["mean"] > 0 and c["t"] >= 1)}
    report = {
        "prereg": str(PREREG.relative_to(REPO)),
        "events_admitted": len(a), "dev_window": DEV, "confirmation_window": CONF,
        "feature_coverage_dev": feats.loc[dv.index].notna().mean().round(3).to_dict(),
        "h2_move_to_implied_by_runup_tercile_dev": {str(int(k)): float(x) for k, x in ratio.items()},
        "h2_monotone": mono,
        "variants": res,
        "passed_dev": [v for v in VARIANTS if res[v]["dev_pass"]],
        "passed_confirmation": [v for v in VARIANTS if res[v].get("confirmation", {}).get("pass")],
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    for v in VARIANTS:
        s = res[v]["k1.0"]
        print(f"{v:30s} n={s['n']:4d} mean={s['mean']:+.3f} t={s['t']:+.2f} holm={adj_p[v]:.3f} "
              f"folds+={s.get('folds_positive')} k1.5 mean={res[v]['k1.5']['mean']:+.3f} "
              f"pass={res[v]['dev_pass']}" + (f" conf={res[v]['confirmation']['pass']}"
                                               if "confirmation" in res[v] else ""))
    print("H2 |move|/implied by run-up tercile:", report["h2_move_to_implied_by_runup_tercile_dev"])


if __name__ == "__main__":
    main()
