# scripts/run_uv3_full_grid.py — UV3: every move bucket x call/put x stop x target x hold.
"""Implements docs/specs/UV3_FULL_GRID_PREREG_20261011.json (frozen 2026-10-11).

Uses the bars UV2 fetched (nn_meta/data_cache_uv1/stock_full, option_bars_full).

  run     builds per-trade returns for every (session, entry minute, right, stop,
          target, hold), aggregates them into cells by weekday and move bucket,
          runs the 200-permutation family-wise null per instrument and confirms
          candidates on 2026. Single-shot: refuses to overwrite its output.
  check   reproduces UV2's no-stop/no-target 1-hour option and stock returns.

Layout: option returns are float32 arrays (entries, sessions, D) with
D = right x stop x target x hold = 2 x 11 x 21 x 8; NaN = no trade.
Cells are summed with one-hot (day x bucket) matrix products per entry minute.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import run_uv1_midday_fade as uv1  # noqa: E402
import run_uv2_hour_scan as uv2  # noqa: E402

SPEC = REPO / "docs" / "specs" / "UV3_FULL_GRID_PREREG_20261011.json"
CACHE = uv1.CACHE
OUT = REPO / "nn_meta" / "validation" / "uv3-full-grid-20261011-r0"
STOPS = np.array([np.inf] + [0.05 * k for k in range(1, 11)])
TARGETS = np.array([np.inf] + [0.10 * k for k in range(1, 21)])
HOLDS = np.arange(30, 241, 30)
ENTRY = np.arange(15, 389 - 30 + 1, 5)          # 09:45, 09:50, ... 15:25
NE, NS, NT, NH, NB = len(ENTRY), len(STOPS), len(TARGETS), len(HOLDS), 20
W, QMAX, LAST = uv2.NMIN + uv2.TAIL, int(HOLDS.max()), uv2.NMIN - 1
OPT_START, DEV_END, CONF_START = uv2.OPT_START, uv2.DEV_END, uv2.CONF_START
NPERM, SEED, MIN_N = 200, 20261011, 30
DAYS = uv1.DAYS + ("All",)


def bucket_labels() -> list[str]:
    up = [f"up {0.25 * k:.2f}-{0.25 * (k + 1):.2f}%" for k in range(10)]
    dn = [f"down {0.25 * k:.2f}-{0.25 * (k + 1):.2f}%" for k in range(10)]
    return up + dn


def buckets(m: np.ndarray) -> np.ndarray:
    """0..9 up (0, .25], ..., (2.25, 2.5]; 10..19 the same downward; -1 no trade."""
    a = np.where(np.isfinite(m), np.abs(m), np.inf)
    k = np.ceil(np.round(a / 0.0025, 9))
    ok = (k >= 1) & (k <= 10) & (m != 0)
    k = np.where(ok, k - 1, 0).astype(np.int16)
    return np.where(ok, np.where(m > 0, k, 10 + k), -1).astype(np.int16)


# ---------------------------------------------------------------- per-trade returns
def option_session(g: pd.DataFrame, bars: pd.DataFrame, c_row: np.ndarray) -> np.ndarray:
    """(NE, 2, NS, NT, NH) net returns for one session/ticker."""
    out = np.full((NE, 2, NS, NT, NH), np.nan, np.float32)
    spot = c_row[ENTRY - 1]
    Q = np.arange(QMAX + 1)
    absm = ENTRY[:, None] + Q[None, :]                       # absolute minute of path step q
    absc = np.clip(absm, 0, W - 1)
    Eh = ENTRY[:, None] + HOLDS[None, :]
    valid_h = Eh <= LAST
    for r_i, cp in enumerate("CP"):
        gc = g[g.cp == cp].sort_values("strike")
        ks, syms = gc.strike.to_numpy(), gc.symbol.to_numpy()
        if not len(ks):
            continue
        pos = {s: j for j, s in enumerate(syms)}
        bb = bars[bars.symbol.isin(pos)]
        if bb.empty:
            continue
        vw = np.full((len(ks), W), np.nan)
        cl = np.full_like(vw, np.nan)
        r = bb.symbol.map(pos).to_numpy()
        i = (bb.t.dt.hour * 60 + bb.t.dt.minute - 570).to_numpy()
        ok = (i >= 0) & (i < W)
        vw[r[ok], i[ok]] = bb.vw.to_numpy()[ok]
        cl[r[ok], i[ok]] = bb.c.to_numpy()[ok]
        valid = np.isfinite(vw)
        nxt, prv = uv2._next_valid(valid), uv2._prev_valid(valid)
        vff = np.where(prv >= 0, np.take_along_axis(vw, np.clip(prv, 0, None), 1), np.nan)
        if cp == "C":
            j = np.searchsorted(ks, spot, side="right"); have = j < len(ks)
        else:
            j = np.searchsorted(ks, spot, side="left") - 1; have = j >= 0
        have &= np.isfinite(spot)
        j = np.clip(j, 0, len(ks) - 1)
        e_i = nxt[j, ENTRY]
        has_e = have & (e_i <= ENTRY + 5)
        mid_in = vw[j, np.clip(e_i, 0, W - 1)]
        jj = j[:, None]
        # path after the entry fill, relative to the entry mid
        P = vff[jj, absc]
        P = np.where((absm > e_i[:, None]) & (absm <= LAST), P, np.nan)
        rel = P / mid_in[:, None] - 1
        cm = np.fmin.accumulate(np.where(np.isnan(rel), np.inf, rel), axis=1)
        cx = np.fmax.accumulate(np.where(np.isnan(rel), -np.inf, rel), axis=1)
        hs = cm[:, :, None] <= -STOPS[None, None, :]
        q_s = np.where(hs.any(1), hs.argmax(1), 10_000)       # (NE, NS)
        hg = cx[:, :, None] >= TARGETS[None, None, :]
        q_g = np.where(hg.any(1), hg.argmax(1), 10_000)       # (NE, NT)
        # exit after a trigger at step q: next traded minute's VWAP, else the trigger minute's
        n_after = nxt[jj, np.clip(absc + 1, 0, W - 1)]
        ex_q = np.where((n_after < W) & (absc + 1 < W), vw[jj, np.clip(n_after, 0, W - 1)], vff[jj, absc])
        # time exit (UV1/UV2 fallbacks)
        Ehc = np.clip(Eh, 0, W - 1)
        x_i = nxt[jj, Ehc]
        l_i = prv[jj, np.clip(Eh + 5, 0, W - 1)]
        mid_hold = np.where(x_i <= Eh + 5, vw[jj, np.clip(x_i, 0, W - 1)],
                            np.where(l_i >= Eh - 5, cl[jj, np.clip(l_i, 0, W - 1)], 0.0))
        qt = np.minimum(q_s[:, :, None], q_g[:, None, :])     # (NE, NS, NT)
        ex_t = np.take_along_axis(ex_q, np.clip(qt, 0, QMAX).reshape(NE, -1), 1).reshape(NE, NS, NT)
        trig = qt[..., None] < HOLDS[None, None, None, :]
        mid_out = np.where(trig, ex_t[..., None], mid_hold[:, None, None, :])
        debit = (mid_in * (1 + uv1.OPT_COST) + uv1.OPT_FEE)[:, None, None, None]
        credit = np.where(mid_out > 0, mid_out * (1 - uv1.OPT_COST) - uv1.OPT_FEE, 0.0)
        ret = (credit - debit) / debit
        keep = has_e[:, None, None, None] & valid_h[:, None, None, :]
        out[:, r_i] = np.where(keep, ret, np.nan)
    return out


def build(sess: list[str]) -> dict:
    data = {}
    s_arr = np.array(sess)
    opt_rows = np.flatnonzero(s_arr >= OPT_START)
    for sym in uv1.TICKERS:
        st = uv2.load_stock_matrix(sym, sess)
        m = st["c"][:, ENTRY - 1] / st["o"][:, [0]] - 1
        Eh = ENTRY[:, None] + HOLDS[None, :]
        vw = st["vw"]
        R = vw[:, np.clip(Eh, 0, LAST)] / vw[:, ENTRY][:, :, None] - 1 - 2 * uv1.STOCK_COST
        R = np.where((Eh <= LAST)[None], R, np.nan).astype(np.float32)   # (sessions, NE, NH)
        by_exp = uv2.contracts(sym)
        X = np.full((NE, len(opt_rows), 2 * NS * NT * NH), np.nan, np.float32)
        for k, row in enumerate(opt_rows):
            d = sess[row]
            g = by_exp.get(d)
            p = CACHE / "option_bars_full" / f"{d}.parquet"
            if g is None or not p.exists():
                continue
            bars = pd.read_parquet(p)
            bars = bars[bars.symbol.isin(g.symbol) & (bars.v > 0)]
            X[:, k] = option_session(g, bars, st["c"][row]).reshape(NE, -1)
        data[sym] = {"B": buckets(m), "S": np.ascontiguousarray(R.transpose(1, 0, 2)), "O": X}
        print(f"{sym}: returns built", flush=True)
    data["opt_rows"] = opt_rows
    return data


# ---------------------------------------------------------------- cells
class Agg:
    """Precomputed zero-filled sums for one (ticker, instrument, row subset)."""

    def __init__(self, X: np.ndarray, B: np.ndarray, dow: np.ndarray):
        self.F = np.isfinite(X).astype(np.float32)
        self.X0 = np.where(self.F > 0, X, 0).astype(np.float32)
        self.X2 = self.X0 * self.X0
        self.B, self.dow = B, dow

    def cells(self, perm: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        B = self.B if perm is None else self.B[perm]
        ne, ns, D = self.X0.shape
        n = np.empty((ne, 5, NB, D), np.float32); s1 = np.empty_like(n); s2 = np.empty_like(n)
        cols = np.arange(ns)
        for e in range(ne):
            ok = B[:, e] >= 0
            G = np.zeros((5 * NB, ns), np.float32)
            G[(self.dow * NB + B[:, e])[ok], cols[ok]] = 1.0
            n[e] = (G @ self.F[e]).reshape(5, NB, D)
            s1[e] = (G @ self.X0[e]).reshape(5, NB, D)
            s2[e] = (G @ self.X2[e]).reshape(5, NB, D)
        add = lambda a: np.concatenate([a, a.sum(1, keepdims=True)], 1)
        n, s1, s2 = add(n), add(s1), add(s2)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = s1 / n
            var = (s2 - n * mean * mean) / (n - 1)
            t = mean / np.sqrt(np.maximum(var, 0) / n)
        t = np.where(n >= MIN_N, t, np.nan)
        return n, mean, t


def entry_rows(rows: np.ndarray, data: dict, inst: str) -> np.ndarray:
    """Map session rows to the instrument's array rows (options start at OPT_START)."""
    if inst == "S":
        return rows
    return np.searchsorted(data["opt_rows"], rows)


def make_aggs(data: dict, inst: str, rows: np.ndarray, dow: np.ndarray) -> dict:
    ar = entry_rows(rows, data, inst)
    return {sym: Agg(data[sym][inst][:, ar], data[sym]["B"][rows], dow[rows]) for sym in uv1.TICKERS}


def cmd_run() -> None:
    spec = json.loads(SPEC.read_text())
    if spec.get("status") != "FROZEN":
        raise SystemExit("spec is not frozen")
    if (OUT / "report.json").exists():
        raise SystemExit(f"{OUT}/report.json exists: single-shot")
    sess = uv2.sessions_all()
    s_arr = np.array(sess)
    dow = pd.to_datetime(pd.Series(sess)).dt.dayofweek.to_numpy()
    data = build(sess)
    windows = {"S": np.flatnonzero(s_arr <= DEV_END),
               "O": np.flatnonzero((s_arr >= OPT_START) & (s_arr <= DEV_END))}
    conf_rows = np.flatnonzero(s_arr >= CONF_START)
    rng = np.random.default_rng(SEED)
    labels = bucket_labels()
    report = {"spec": SPEC.name, "run_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "families": {}}
    OUT.mkdir(parents=True, exist_ok=True)
    for inst, rows in windows.items():
        aggs = make_aggs(data, inst, rows, dow)
        obs = {sym: a.cells() for sym, a in aggs.items()}
        allt = np.concatenate([o[2].ravel() for o in obs.values()])
        obs_max, obs_count = float(np.nanmax(allt)), int(np.nansum(allt >= 2))
        n_cells = int(np.isfinite(allt).sum())
        del allt
        null_max, null_count = [], []
        for p_i in range(NPERM):
            perm = rng.permutation(len(rows))
            ts = [a.cells(perm)[2] for a in aggs.values()]
            null_max.append(max(float(np.nanmax(t)) for t in ts))
            null_count.append(sum(int(np.nansum(t >= 2)) for t in ts))
            if p_i % 20 == 19:
                print(f"[{inst}] permutation {p_i + 1}/{NPERM}", flush=True)
        null_max, null_count = np.array(null_max), np.array(null_count)
        thr = float(np.quantile(null_max, 0.95))
        # save every cell with n >= MIN_N
        frames = []
        for sym, (n, mean, t) in obs.items():
            idx = np.nonzero(np.isfinite(t))
            e, d, b, rest = idx
            if inst == "O":
                rgt, stp, tgt, hld = np.unravel_index(rest, (2, NS, NT, NH))
            else:
                rgt = np.full(len(e), 2); stp = np.zeros(len(e), int); tgt = np.zeros(len(e), int); hld = rest
            cat = pd.Categorical.from_codes
            frames.append(pd.DataFrame({
                "ticker": cat(np.full(len(e), uv1.TICKERS.index(sym)), list(uv1.TICKERS)),
                "right": cat(rgt, ["call", "put", "stock"]),
                "entry_et": cat(e, uv2.hm(ENTRY)), "day": cat(d, list(DAYS)),
                "bucket": cat(b, labels), "stop": STOPS[stp], "target": TARGETS[tgt],
                "hold_min": HOLDS[hld], "n": n[idx].astype(np.int32),
                "mean": mean[idx].astype(np.float32), "t": t[idx].astype(np.float32)}))
        cells = pd.concat(frames, ignore_index=True)
        cells.to_parquet(OUT / f"cells_{inst}.parquet")
        top = cells.nlargest(25, "t")
        cand = cells[(cells.t >= 2) & (cells.t > thr)].sort_values("t", ascending=False)
        conf = []
        if len(cand):
            caggs = make_aggs(data, inst, conf_rows, dow)
            cobs = {sym: a.cells() for sym, a in caggs.items()}
            for _, c in cand.iterrows():
                e = list(uv2.hm(ENTRY)).index(c.entry_et)
                d, b = DAYS.index(c.day), labels.index(c.bucket)
                h = int(np.flatnonzero(HOLDS == c.hold_min)[0])
                if inst == "O":
                    flat = np.ravel_multi_index(([ "call", "put"].index(c.right),
                                                 int(np.flatnonzero(STOPS == c.stop)[0]),
                                                 int(np.flatnonzero(TARGETS == c.target)[0]), h), (2, NS, NT, NH))
                else:
                    flat = h
                n, mean, t = (a[e, d, b, flat] for a in cobs[c.ticker])
                conf.append({**{k: (v.item() if hasattr(v, "item") else v) for k, v in c.items()},
                             "conf_n": int(n), "conf_mean": float(mean), "conf_t": float(t),
                             "conf_pass": bool(mean > 0 and t >= 1)})
        report["families"][inst] = {
            "cells_n_ge_30": n_cells, "obs_max_t": obs_max, "obs_count_t_ge_2": obs_count,
            "null_max_t_p50_p95": [float(np.median(null_max)), thr],
            "null_count_t_ge_2_mean_p95": [float(null_count.mean()), float(np.quantile(null_count, 0.95))],
            "max_t_fw_p": float((null_max >= obs_max).mean()),
            "count_p": float((null_count >= obs_count).mean()),
            "candidates": int(len(cand)), "confirmation": conf,
            "top25": json.loads(top.to_json(orient="records"))}
        f = report["families"][inst]
        name = "stock (buy only)" if inst == "S" else "options"
        print(f"\n[{name}] {n_cells:,} cells with n>=30 | t>=2: observed {obs_count:,}, chance "
              f"{f['null_count_t_ge_2_mean_p95'][0]:,.0f} (95th {f['null_count_t_ge_2_mean_p95'][1]:,.0f}), p {f['count_p']:.3f}"
              f" | max t {obs_max:.2f}, chance median {f['null_max_t_p50_p95'][0]:.2f} / 95th {thr:.2f}, p {f['max_t_fw_p']:.3f}")
        print(top.head(20).to_string(index=False, formatters={"mean": lambda x: f"{x*100:+.2f}%"}))
        print(f"candidates: {len(cand)}")
        for c in conf[:50]:
            print(f"  confirm {c['ticker']} {c['right']} {c['day']} {c['bucket']} {c['entry_et']} stop {c['stop']} "
                  f"target {c['target']} hold {c['hold_min']}: dev t {c['t']:.2f} | 2026 n {c['conf_n']} "
                  f"mean {c['conf_mean']*100:+.2f}% t {c['conf_t']:.2f} -> {'PASS' if c['conf_pass'] else 'FAIL'}")
        del aggs
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")


def cmd_check() -> None:
    """No stop, no target, 60-minute hold must equal UV2's option and stock returns."""
    sess = uv2.sessions_all()
    opt = [d for d in sess if d >= OPT_START][:120]
    oi = pd.Index(sess).get_indexer(opt)
    h60 = int(np.flatnonzero(HOLDS == 60)[0])
    e2 = ENTRY - uv2.ENTRY[0]                       # UV2 entries are every minute from 09:45
    for sym in uv1.TICKERS:
        st = uv2.load_stock_matrix(sym, sess)
        _, _, R2 = uv2.stock_returns(st)
        sel = ENTRY <= 329
        R3 = st["vw"][:, ENTRY[sel] + 60] / st["vw"][:, ENTRY[sel]] - 1 - 2 * uv1.STOCK_COST
        print(sym, "stock max |diff|", np.nanmax(np.abs(R3 - R2[:, e2[sel]])))
        sto = {k: v[oi] for k, v in st.items()}
        call2, put2 = uv2.option_returns(sym, opt, sto)
        by_exp = uv2.contracts(sym)
        diffs = []
        for k, d in enumerate(opt):
            g = by_exp.get(d)
            p = CACHE / "option_bars_full" / f"{d}.parquet"
            if g is None or not p.exists():
                continue
            bars = pd.read_parquet(p); bars = bars[bars.symbol.isin(g.symbol) & (bars.v > 0)]
            o = option_session(g, bars, st["c"][oi[k]])
            for r_i, ref in ((0, call2), (1, put2)):
                a, b = o[sel, r_i, 0, 0, h60], ref[k, e2[sel]]
                both = np.isfinite(a) | np.isfinite(b)
                diffs.append(np.nanmax(np.abs(np.where(both, np.nan_to_num(a, nan=9) - np.nan_to_num(b, nan=9), 0))))
        print(sym, f"option sessions {len(opt)}: max |diff| vs UV2 {max(diffs):.2e}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["run", "check"])
    cmd_run() if ap.parse_args().cmd == "run" else cmd_check()


if __name__ == "__main__":
    main()
