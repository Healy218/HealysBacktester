# scripts/run_v9_ove3.py — V9 OVE-3: the pre-registered options-flow walk-forward, run once.
"""Implements docs/specs/V9_OVE2_PREREG_20261008.json (frozen 2026-10-08):

  A1-A4  unusual short-dated OTM / block options buying (stock 5 days, or
         0.5-delta options), noise-filtered
  B1-B2  FINRA off-exchange short ratio (DIX reading), alone and with A1
  E1-E3  call-vs-put OTM premium imbalance in the 5 days before earnings,
         traded with the OEE structures (ATM option, 10% OTM leg, stock)

Output (<out>/): signals.parquet, trades.parquet, report.json.
"""
from __future__ import annotations

import argparse
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

from nn_meta import v8_fills, v8_vol  # noqa: E402
from nn_meta import v9_oee as oee  # noqa: E402
from nn_meta import v9_oee_eval as ev_  # noqa: E402
from nn_meta.v8_parallel import autosize_workers  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_v9_oee2", REPO / "scripts" / "run_v9_oee2.py")
r2 = importlib.util.module_from_spec(_spec)
sys.modules["run_v9_oee2"] = r2
_spec.loader.exec_module(r2)

V = r2.V
PREREG = REPO / "docs" / "specs" / "V9_OVE2_PREREG_20261008.json"
FLOW = V / "v9-ove1-20261008-r0" / "flow.parquet"
ADMISSION = V / "v8-liquidity-20261008-r0" / "admission.parquet"
POOL = REPO / "docs" / "specs" / "V8_POOL_PIT2021_20261007.json"
LEGS = V / "v9-oee-h4-20261008-r0" / "legs.parquet"
DEFAULT_OUT = V / "v9-ove3-20261008-r0"
DEV_AB = ("2022-03-01", "2025-12-31")
DEV_E = r2.DEV
HOLD = 5
KS = (1.0, 1.5)
FOLDS_AB = ["2022H1", "2022H2", "2023H1", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2"]
VARIANTS = ["A1_otm_call_buying_stock", "A2_otm_call_buying_call", "A3_otm_put_buying_put",
            "A4_aggressive_block_calls_stock", "B1_dix_long", "B2_flow_plus_dix",
            "E1_flow_atm_option", "E2_flow_otm_leg", "E3_flow_stock"]
OPEN_MIN, CLOSE_MIN = 9 * 60 + 30, 16 * 60


# ── signals ──────────────────────────────────────────────────────────────────

def abnormal(f: pd.DataFrame, col: str) -> pd.Series:
    x = np.log1p(f[col])
    g = x.groupby(f["ticker"])
    m = g.transform(lambda s: s.shift(1).rolling(20, min_periods=15).mean())
    sd = g.transform(lambda s: s.shift(1).rolling(20, min_periods=15).std())
    return (x - m) / sd.replace(0, np.nan)


def ab_signals(f: pd.DataFrame, adm: pd.DataFrame, etfs: set) -> pd.DataFrame:
    f = f[~f["ticker"].isin(etfs)].sort_values(["ticker", "date"]).copy()
    f = f.merge(adm, on=["ticker", "date"], how="left")
    f["ret"] = f.groupby("ticker")["S"].pct_change()
    prints = f["call_trades"] + f["put_trades"]
    near_e = (f["days_since_earnings"] <= 2) | (f["days_to_earnings"] <= 5)
    base = (f["admitted"].fillna(False).astype(bool) & (f["ret"].abs() < 0.03)
            & (prints >= 50) & ~near_e)
    tot = f["st_otm_call_prem"] + f["st_otm_put_prem"]
    cs = f["st_otm_call_prem"] / tot.replace(0, np.nan)
    a1 = base & (abnormal(f, "st_otm_call_prem") >= 2) & (cs >= 0.65)
    a3 = base & (abnormal(f, "st_otm_put_prem") >= 2) & ((1 - cs) >= 0.65)
    a4 = base & (abnormal(f, "block_call_vol") >= 2) & (
        f["st_otm_call_prem_at_high"] / f["st_otm_call_prem"].replace(0, np.nan) >= 0.5)
    r = f["finra_short_ratio"]
    q90 = r.groupby(f["ticker"]).transform(lambda s: s.shift(1).rolling(60, min_periods=40).quantile(0.9))
    b1 = base & (r > q90)
    b1_prev = b1.groupby(f["ticker"]).shift(1, fill_value=False)
    out = f[["ticker", "date"]].copy()
    out["A1"], out["A3"], out["A4"], out["B1"] = a1, a3, a4, b1
    out["B2"] = a1 & (b1 | b1_prev)
    return out


# ── stock trades ─────────────────────────────────────────────────────────────

def stock_ret(ticker, raw_in, adj_in, min_in, raw_out, adj_out, min_out, year, k) -> float:
    hs_in = v8_fills.stock_half_spread_bps([ticker], [raw_in], [min_in], [year])[0]
    hs_out = v8_fills.stock_half_spread_bps([ticker], [raw_out], [min_out], [year])[0]
    buy = adj_in * (1 + k * (hs_in + v8_fills.SLIPPAGE_BPS) / 1e4)
    sell = adj_out * (1 - k * (hs_out + v8_fills.SLIPPAGE_BPS) / 1e4)
    return sell * (1 - v8_fills.SELL_REG_BPS / 1e4) / buy - 1


def stock_trades(sig: pd.DataFrame, name: str, bars: dict, days: list[str]) -> list[dict]:
    """Long from the open of t+1 to the close of t+HOLD; no re-entry while open."""
    pos = {d: i for i, d in enumerate(days)}
    rows, busy = [], {}
    for t, d in sig[["ticker", "date"]].itertuples(index=False):
        i = pos[d]
        if i + HOLD >= len(days) or busy.get(t, -1) >= i + 1:
            continue
        din, dout = days[i + 1], days[i + HOLD]
        b = bars.get(t)
        if b is None or din not in b.index or dout not in b.index:
            rows.append({"variant": name, "ticker": t, "signal_day": d, "dropped": "no_bars"}); continue
        busy[t] = i + HOLD
        x, y = b.loc[din], b.loc[dout]
        rec = {"variant": name, "ticker": t, "signal_day": d, "entry_day": din, "exit_day": dout, "dropped": ""}
        for k in KS:
            rec[f"ret_{k}"] = stock_ret(t, x["open"], x["adj_open"], OPEN_MIN, y["close"], y["adj_close"],
                                        CLOSE_MIN, int(din[:4]), k)
        rows.append(rec)
    return rows


# ── option trades (A2, A3) ───────────────────────────────────────────────────

def _opt_month(job):
    month_files, sigs, cp = job
    tix = sorted({s["ticker"] for s in sigs})
    cols = ["date", "ticker", "expiry", "cp", "strike", "close", "volume"]
    ch = pd.concat([pd.read_parquet(r2.CHAINS / f"{m}.parquet", columns=cols,
                                    filters=[("ticker", "in", tix)]) for m in month_files],
                   ignore_index=True)
    ch = ch[ch["cp"] == cp]
    out = []
    for s in sigs:
        c = ch[ch["ticker"] == s["ticker"]]
        day = c[(c["date"] == s["entry_day"]) & (c["volume"] > 0) & (c["close"] > 0)].copy()
        day["dte"] = (pd.to_datetime(day["expiry"]) - pd.Timestamp(s["entry_day"])).dt.days
        day = day[(day["dte"] >= 5) & (day["dte"] <= 21)]
        rec = {"key": s["key"]}
        if day.empty:
            out.append({**rec, "why": "no_contract"}); continue
        expiry = day["expiry"].min()
        e = day[day["expiry"] == expiry]
        T = max((pd.Timestamp(expiry) - pd.Timestamp(s["entry_day"])).days, 0.5) / 365
        F = s["S_in"]       # spot as forward (short-dated; rates ignored)
        iv = v8_vol.implied_vol(e["close"].to_numpy(), F, e["strike"].to_numpy(), T, cp == "C")
        ok = np.isfinite(iv)
        if not ok.any():
            out.append({**rec, "why": "no_iv"}); continue
        e = e[ok].assign(iv=iv[ok])
        d1 = (np.log(F / e["strike"]) + 0.5 * e["iv"] ** 2 * T) / (e["iv"] * math.sqrt(T))
        nd1 = 0.5 * (1 + np.vectorize(math.erf)(d1 / math.sqrt(2)))
        delta = nd1 if cp == "C" else nd1 - 1
        row = e.iloc[int(np.argmin(np.abs(delta - (0.5 if cp == "C" else -0.5))))]
        K = float(row["strike"])
        if expiry < s["exit_day"]:       # expired before exit: intrinsic at its expiry-day close
            S_x = s["closes"][max(d for d in s["closes"] if d <= expiry)]
            x, how = (max(S_x - K, 0.0) if cp == "C" else max(K - S_x, 0.0)), "intrinsic_expired"
            dte_out = 0
        else:
            x = oee._close(ch[ch["ticker"] == s["ticker"]], s["exit_day"], expiry, cp, K)
            how = "traded" if np.isfinite(x) else "missing"
            dte_out = (pd.Timestamp(expiry) - pd.Timestamp(s["exit_day"])).days
        out.append({**rec, "why": "", "expiry": expiry, "strike": K, "entry": float(row["close"]),
                    "exit": x, "exit_how": how, "dte_in": int(row["dte"]), "dte_out": dte_out})
    return out


def option_trades(sig: pd.DataFrame, name: str, cp: str, raw: dict, days: list[str], sm, cap) -> list[dict]:
    pos = {d: i for i, d in enumerate(days)}
    recs, busy = [], {}
    for t, d in sig[["ticker", "date"]].itertuples(index=False):
        i = pos[d]
        if i + HOLD >= len(days) or busy.get(t, -1) >= i + 1:
            continue
        din, dout = days[i + 1], days[i + HOLD]
        r = raw.get(t)
        if r is None or din not in r.index or dout not in r.index:
            continue
        busy[t] = i + HOLD
        recs.append({"key": len(recs), "ticker": t, "signal_day": d, "entry_day": din, "exit_day": dout,
                     "S_in": float(r.loc[din]), "S_out": float(r.loc[dout])})
    have = {p.stem for p in r2.CHAINS.glob("*.parquet")}
    by_month: dict[str, list] = {}
    for rec in recs:
        by_month.setdefault(rec["entry_day"][:7], []).append(rec)
    for rec in recs:                     # raw closes over the hold (expiry-before-exit)
        r = raw[rec["ticker"]]
        rec["closes"] = {d: float(v) for d, v in r.loc[rec["entry_day"]:rec["exit_day"]].items()}
    jobs = []
    for m, rs in by_month.items():
        hi = max(x["exit_day"] for x in rs)[:7]
        jobs.append((sorted(x for x in have if m <= x <= hi), rs, cp))
    workers, why = autosize_workers(per_worker_mb=1500, cap=cap)
    print(f"{name}: {len(recs)} option trades, {len(jobs)} months; {why}", flush=True)
    with ProcessPoolExecutor(workers) as ex:
        res = {x["key"]: x for part in ex.map(_opt_month, jobs) for x in part}
    rows = []
    for rec in recs:
        o = res[rec["key"]]
        base = {"variant": name, "ticker": rec["ticker"], "signal_day": rec["signal_day"],
                "entry_day": rec["entry_day"], "exit_day": rec["exit_day"]}
        if o["why"] or not np.isfinite(o["exit"]):
            rows.append({**base, "dropped": o["why"] or "missing_exit"}); continue
        out = {**base, "dropped": "", "exit_how": o["exit_how"]}
        for k in KS:
            out[f"ret_{k}"] = ev_.long_return(
                [r2.leg(sm, o["entry"], cp, o["strike"], rec["S_in"], o["dte_in"])],
                [r2.leg(sm, o["exit"], cp, o["strike"], rec["S_out"], o["dte_out"])], k)
        rows.append(out)
    return rows


# ── evaluation ───────────────────────────────────────────────────────────────

def stats(t: pd.DataFrame, k: float, folds: list[str]) -> dict:
    r = t[f"ret_{k}"].to_numpy()
    out = ev_.clustered_t(r, t["signal_day"].to_numpy())
    if len(r):
        out.update(hit_rate=float((r > 0).mean()),
                   quantiles={q: float(np.quantile(r, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)})
        top = np.sort(r)[::-1]
        out["mean_excl_top5"] = float(top[5:].mean()) if len(top) > 5 else None
    fm = t.groupby(ev_.half_year(t["signal_day"]))[f"ret_{k}"].mean() if len(t) else pd.Series(dtype=float)
    out["folds"] = {f: (float(fm[f]) if f in fm.index else None) for f in folds}
    out["folds_positive"] = int(sum(1 for f in folds if f in fm.index and fm[f] > 0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    if (args.out / "report.json").exists():
        raise SystemExit(f"{args.out}/report.json exists: OVE-3 runs once")
    args.out.mkdir(parents=True, exist_ok=True)
    assert json.loads(PREREG.read_text())["approved_by"].startswith("user")

    flow = pd.read_parquet(FLOW)
    etfs = set(json.loads(POOL.read_text())["rule"]["etfs_every_month"])
    adm = pd.read_parquet(ADMISSION, columns=["ticker", "date", "admitted"])
    bars_df = pd.read_parquet(r2.BARS, columns=["ticker", "date", "open", "close", "adj_open", "adj_close"])
    days = sorted(bars_df["date"].unique())
    bars = {t: g.set_index("date") for t, g in bars_df.groupby("ticker")}
    raw = {t: g["close"] for t, g in bars.items()}
    sm = ev_.SpreadModel(r2.SPREADS)

    sig = ab_signals(flow, adm, etfs)
    sig.to_parquet(args.out / "signals.parquet", index=False)
    dev = (sig["date"] >= DEV_AB[0]) & (sig["date"] <= DEV_AB[1])
    rows = []
    rows += stock_trades(sig[dev & sig["A1"]], "A1_otm_call_buying_stock", bars, days)
    rows += option_trades(sig[dev & sig["A1"]], "A2_otm_call_buying_call", "C", raw, days, sm, args.workers)
    rows += option_trades(sig[dev & sig["A3"]], "A3_otm_put_buying_put", "P", raw, days, sm, args.workers)
    rows += stock_trades(sig[dev & sig["A4"]], "A4_aggressive_block_calls_stock", bars, days)
    rows += stock_trades(sig[dev & sig["B1"]], "B1_dix_long", bars, days)
    rows += stock_trades(sig[dev & sig["B2"]], "B2_flow_plus_dix", bars, days)

    # ── E family on the OEE events ──
    a = ev_.admit(pd.read_parquet(r2.EVENTS)).sort_values(["entry_day", "ticker"]).reset_index(drop=True)
    a.index.name = "key"
    pos = {d: i for i, d in enumerate(days)}
    fl = flow.set_index(["ticker", "date"])
    imb = np.full(len(a), np.nan)
    for j, (t, e) in enumerate(zip(a["ticker"], a["entry_day"])):
        i = pos[e]
        keys = [(t, d) for d in days[max(i - 4, 0):i + 1]]
        x = fl.reindex(keys)
        c, p = x["st_otm_call_prem"].sum(), x["st_otm_put_prem"].sum()
        if x["st_otm_call_prem"].notna().sum() == 5 and c + p > 0:
            imb[j] = (c - p) / (c + p)
    _, ter = ev_.trailing_rank(a["entry_day"], imb)
    a["imbalance"], a["tercile"] = imb, ter
    a.reset_index()[["key", "ticker", "entry_day", "imbalance", "tercile"]].to_parquet(args.out / "e_scores.parquet")
    wings = pd.DataFrame(columns=["wing_C_strike", "wing_C_reaction", "wing_P_strike", "wing_P_reaction"])
    a_px, _ = r2.expiry_day_intrinsic(a, wings)
    legs = pd.read_parquet(LEGS)
    L = {k: g.set_index("leg") for k, g in legs.groupby("key")}
    in_e = (a["entry_day"] >= DEV_E[0]) & (a["entry_day"] <= DEV_E[1])
    for k in a.index[in_e & a["tercile"].isin([1, -1])]:
        e = a_px.loc[k]
        side = int(a.at[k, "tercile"])
        base = {"ticker": e["ticker"], "signal_day": e["entry_day"], "entry_day": e["entry_day"],
                "exit_day": e["reaction_day"]}
        dte_in = e["front_dte"]
        dte_out = (pd.Timestamp(e["front_expiry"]) - pd.Timestamp(e["reaction_day"])).days
        # E1: 0.5-delta option
        nm, cp = ("call50", "C") if side > 0 else ("put50", "P")
        K, p0, p1 = e[f"{nm}_strike"], e[f"{nm}_entry"], e[f"{nm}_reaction"]
        rec = {**base, "variant": "E1_flow_atm_option"}
        if np.isfinite(p0) and np.isfinite(p1):
            for kk in KS:
                rec[f"ret_{kk}"] = ev_.long_return([r2.leg(sm, p0, cp, K, e["S_entry"], dte_in)],
                                                   [r2.leg(sm, p1, cp, K, e["S_reaction"], dte_out)], kk)
            rows.append({**rec, "dropped": ""})
        else:
            rows.append({**rec, "dropped": "missing_exit"})
        # E2: 10% OTM leg on that side
        ln = "p10_C" if side > 0 else "p10_P"
        rec = {**base, "variant": "E2_flow_otm_leg"}
        lg = L.get(k)
        if lg is not None and ln in lg.index and np.isfinite(lg.at[ln, "exit"]):
            x = lg.loc[ln]
            for kk in KS:
                rec[f"ret_{kk}"] = ev_.long_return(
                    [r2.leg(sm, x["entry"], x["cp"], x["strike"], e["S_entry"], dte_in)],
                    [r2.leg(sm, x["exit"], x["cp"], x["strike"], e["S_reaction"], dte_out)], kk)
            rows.append({**rec, "dropped": ""})
        else:
            rows.append({**rec, "dropped": "no_leg"})
        # E3: long stock, top tercile only, entry close -> reaction close
        if side > 0:
            b = bars[e["ticker"]]
            x, y = b.loc[e["entry_day"]], b.loc[e["reaction_day"]]
            rec = {**base, "variant": "E3_flow_stock", "dropped": ""}
            for kk in KS:
                rec[f"ret_{kk}"] = stock_ret(e["ticker"], x["close"], x["adj_close"], CLOSE_MIN,
                                             y["close"], y["adj_close"], CLOSE_MIN, int(e["entry_day"][:4]), kk)
            rows.append(rec)

    tr = pd.DataFrame(rows)
    tr.to_parquet(args.out / "trades.parquet", index=False)
    ok = tr[tr["dropped"] == ""]
    res, p1 = {}, {}
    for v in VARIANTS:
        t = ok[ok["variant"] == v]
        folds = ev_.FOLDS if v.startswith("E") else FOLDS_AB
        res[v] = {f"k{k}": stats(t, k, folds) for k in KS}
        res[v]["dropped"] = tr[tr["variant"] == v]["dropped"].value_counts().to_dict()
        p1[v] = res[v]["k1.0"]["p_one_sided"]
    adj_p = ev_.holm(p1)
    for v in VARIANTS:
        s1, s15 = res[v]["k1.0"], res[v]["k1.5"]
        need = 4 if v.startswith("E") else 6
        rules = {"edge": bool(s1["mean"] > 0 and s1["t"] >= 2),
                 "multiple_testing": bool(adj_p[v] < 0.05),
                 "folds": bool(s1["folds_positive"] >= need),
                 "cost_stress": bool(s15["mean"] > 0 and s15["t"] >= 2)}
        res[v].update(holm_p=adj_p[v], rules=rules, dev_pass=all(rules.values()))
    de = a[in_e & a["tercile"].isin([1, -1])]
    e_acc = float((np.sign(de["tercile"]) == np.sign(de["realized_move"])).mean())
    report = {"prereg": str(PREREG.relative_to(REPO)), "dev_ab": DEV_AB, "dev_e": DEV_E,
              "signal_days_dev": {c: int((dev & sig[c]).sum()) for c in ("A1", "A3", "A4", "B1", "B2")},
              "e_sign_accuracy_dev": {"n": len(de), "correct": e_acc},
              "variants": res, "passed_dev": [v for v in VARIANTS if res[v]["dev_pass"]],
              "confirmation": "run only for dev passes (B family needs FINRA 2026 first)"}
    (args.out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print("E sign accuracy:", report["e_sign_accuracy_dev"])
    for v in VARIANTS:
        s = res[v]["k1.0"]
        print(f"{v:34s} n={s['n']:5d} mean={s['mean']:+.4f} t={s['t']:+.2f} hit={s.get('hit_rate', float('nan')):.2f} "
              f"holm={adj_p[v]:.3f} folds+={s['folds_positive']} k1.5={res[v]['k1.5']['mean']:+.4f} "
              f"excl_top5={s.get('mean_excl_top5')} pass={res[v]['dev_pass']}")


if __name__ == "__main__":
    main()
