# scripts/run_uv2_hour_scan.py — UV2: UV1's rule, 1-hour hold, every entry minute.
"""Implements docs/specs/UV2_HOUR_SCAN_PREREG_20261011.json (frozen 2026-10-11).

  fetch   full-session SIP 1-minute SPY/QQQ bars and full-day 1-minute bars for
          every same-day contract within the session's price range +/- $1
          (reuses UV1's calendar and contract lists). Resumable.
  run     the single scan: 30,240 cells, 200-permutation family-wise null per
          instrument, 2026 confirmation for candidates only. Refuses to overwrite.

Minute index i counts from 09:30 ET (0) to 15:59 (389); entries i = 15..329
(09:45..14:59), exit at i + 60. Matrices are sessions x minutes, numpy throughout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import run_uv1_midday_fade as uv1  # noqa: E402

SPEC = REPO / "docs" / "specs" / "UV2_HOUR_SCAN_PREREG_20261011.json"
CACHE = uv1.CACHE
OUT = REPO / "nn_meta" / "validation" / "uv2-hour-scan-20261011-r0"
NMIN, HOLD = 390, 60
ENTRY = np.arange(15, 330)                 # 09:45 .. 14:59
TAIL = 6                                    # option bars kept to 16:05 for exit fallbacks
OPT_START, DEV_END, CONF_START = "2024-01-18", "2025-12-31", "2026-01-02"
NPERM, SEED = 200, 20261011
DAYS = uv1.DAYS


def hm(i: np.ndarray | int) -> str | list[str]:
    f = lambda k: f"{9 + (30 + k) // 60:02d}:{(30 + k) % 60:02d}"
    return f(i) if np.isscalar(i) else [f(k) for k in i]


# ---------------------------------------------------------------- fetch
def fetch_stock_year(h: dict, sym: str, year: int) -> None:
    p = CACHE / "stock_full" / f"{sym}_{year}.parquet"
    if p.exists():
        return
    end = min(f"{year}-12-31", uv1.END)
    pages = uv1._pages(f"{uv1.DATA}/v2/stocks/bars", h, {
        "symbols": sym, "timeframe": "1Min", "feed": "sip", "adjustment": "raw",
        "start": f"{year}-01-01T00:00:00Z", "end": f"{end}T23:59:59Z", "limit": 10000}, "bars")
    df = pd.DataFrame([b for pg in pages for b in (pg.get(sym) or [])])
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(uv1.ET)
    t = df["t"].dt.strftime("%H:%M")
    df = df[(t >= "09:30") & (t <= "15:59")]
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)


def load_stock_matrix(sym: str, sessions: list[str]) -> dict[str, np.ndarray]:
    df = pd.concat([pd.read_parquet(p) for p in sorted((CACHE / "stock_full").glob(f"{sym}_*.parquet"))])
    d = df["t"].dt.strftime("%Y-%m-%d")
    i = (df["t"].dt.hour * 60 + df["t"].dt.minute - 570).to_numpy()
    out = {}
    row = pd.Index(sessions).get_indexer(d)
    ok = row >= 0
    for f in ("o", "c", "vw", "h", "l"):
        m = np.full((len(sessions), NMIN), np.nan)
        m[row[ok], i[ok]] = df[f].to_numpy()[ok]
        out[f] = m
    return out


def fetch_option_day(h: dict, d: str, syms: list[str]) -> None:
    p = CACHE / "option_bars_full" / f"{d}.parquet"
    if p.exists() or not syms:
        return
    s = pd.Timestamp(f"{d} 09:30", tz=uv1.ET).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    e = pd.Timestamp(f"{d} 16:06", tz=uv1.ET).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for k in range(0, len(syms), 100):
        pages = uv1._pages(f"{uv1.DATA}/v1beta1/options/bars", h, {
            "symbols": ",".join(syms[k:k + 100]), "timeframe": "1Min", "start": s, "end": e,
            "limit": 10000}, "bars")
        rows += [dict(b, symbol=sym) for pg in pages for sym, v in pg.items() for b in v]
    df = pd.DataFrame(rows, columns=["symbol", "t", "o", "h", "l", "c", "v", "n", "vw"])
    if len(df):
        df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(uv1.ET)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)


def contracts(sym: str) -> dict[str, pd.DataFrame]:
    ct = pd.concat([pd.read_parquet(p) for p in sorted((CACHE / "contracts").glob(f"{sym}_*.parquet"))])
    return {e: g for e, g in ct.groupby("expiry")}


def sessions_all() -> list[str]:
    cal = pd.read_parquet(CACHE / "calendar.parquet")
    return cal[(cal.date >= "2016-01-04") & (cal.date <= uv1.END) & (cal.close == "16:00")].date.tolist()


def cmd_fetch() -> None:
    load_dotenv(REPO / ".env")
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_PAPER_API_KEY"],
         "APCA-API-SECRET-KEY": os.environ["ALPACA_PAPER_API_SECRET"]}
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda j: fetch_stock_year(h, *j), [(s, y) for s in uv1.TICKERS for y in range(2016, 2027)]))
    print("stock bars done", flush=True)
    sess = [d for d in sessions_all() if d >= OPT_START]
    want: dict[str, list[str]] = {d: [] for d in sess}
    for sym in uv1.TICKERS:
        st = load_stock_matrix(sym, sess)
        by_exp = contracts(sym)
        for k, d in enumerate(sess):
            g = by_exp.get(d)
            lo, hi = np.nanmin(st["l"][k]), np.nanmax(st["h"][k])
            if g is None or not np.isfinite(lo):
                continue
            want[d] += g[(g.strike >= np.floor(lo) - 1) & (g.strike <= np.ceil(hi) + 1)].symbol.tolist()
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda kv: fetch_option_day(h, kv[0], kv[1]), want.items()))
    print(f"option bars done: {len(want)} sessions, {sum(map(len, want.values()))} contract-days", flush=True)


# ---------------------------------------------------------------- matrices
def stock_returns(st: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """m, b (signals at each entry minute) and R (entry VWAP -> VWAP 60 later)."""
    c, o, vw = st["c"], st["o"], st["vw"]
    m = c[:, ENTRY - 1] / o[:, [0]] - 1
    b = c[:, ENTRY - 1] / o[:, ENTRY - 15] - 1
    R = vw[:, ENTRY + HOLD] / vw[:, ENTRY] - 1
    return m, b, R


def _next_valid(valid: np.ndarray) -> np.ndarray:
    """nxt[..., j] = smallest k >= j with valid[..., k], else a large sentinel."""
    n = valid.shape[-1]
    idx = np.where(valid, np.arange(n), n + 10_000)
    return np.minimum.accumulate(idx[..., ::-1], axis=-1)[..., ::-1]


def _prev_valid(valid: np.ndarray) -> np.ndarray:
    n = valid.shape[-1]
    idx = np.where(valid, np.arange(n), -10_000)
    return np.maximum.accumulate(idx, axis=-1)


def option_returns(sym: str, sess: list[str], st: dict) -> tuple[np.ndarray, np.ndarray]:
    """Net per-trade return of the first-OTM call / put bought at each entry minute."""
    W = NMIN + TAIL
    call = np.full((len(sess), len(ENTRY)), np.nan)
    put = np.full_like(call, np.nan)
    by_exp = contracts(sym)
    for k, d in enumerate(sess):
        g = by_exp.get(d)
        p = CACHE / "option_bars_full" / f"{d}.parquet"
        if g is None or not p.exists():
            continue
        bars = pd.read_parquet(p)
        bars = bars[bars.symbol.isin(g.symbol) & (bars.v > 0)]
        spot = st["c"][k, ENTRY - 1]
        for cp, out in (("C", call), ("P", put)):
            gc = g[g.cp == cp].sort_values("strike")
            ks, syms = gc.strike.to_numpy(), gc.symbol.to_numpy()
            if not len(ks):
                continue
            pos = {s: j for j, s in enumerate(syms)}
            vw = np.full((len(ks), W), np.nan)
            cl = np.full_like(vw, np.nan)
            bb = bars[bars.symbol.isin(pos)]
            if bb.empty:
                continue
            r = bb.symbol.map(pos).to_numpy()
            i = (bb.t.dt.hour * 60 + bb.t.dt.minute - 570).to_numpy()
            ok = (i >= 0) & (i < W)
            vw[r[ok], i[ok]] = bb.vw.to_numpy()[ok]
            cl[r[ok], i[ok]] = bb.c.to_numpy()[ok]
            valid = np.isfinite(vw)
            nxt, prv = _next_valid(valid), _prev_valid(valid)
            # first OTM strike: calls lowest strike > spot, puts highest strike < spot
            if cp == "C":
                j = np.searchsorted(ks, spot, side="right")
                have = j < len(ks)
            else:
                j = np.searchsorted(ks, spot, side="left") - 1
                have = j >= 0
            have &= np.isfinite(spot)
            j = np.clip(j, 0, len(ks) - 1)
            e_i = nxt[j, ENTRY]
            has_e = have & (e_i <= ENTRY + 5)
            e_i = np.clip(e_i, 0, W - 1)
            mid_in = vw[j, e_i]
            x_i = nxt[j, ENTRY + HOLD]
            has_x = x_i <= ENTRY + HOLD + 5
            x_i = np.clip(x_i, 0, W - 1)
            l_i = prv[j, np.minimum(ENTRY + HOLD + 5, W - 1)]
            has_l = l_i >= ENTRY + HOLD - 5
            l_i = np.clip(l_i, 0, W - 1)
            mid_out = np.where(has_x, vw[j, x_i], np.where(has_l, cl[j, l_i], 0.0))
            debit = mid_in * (1 + uv1.OPT_COST) + uv1.OPT_FEE
            credit = np.where(mid_out > 0, mid_out * (1 - uv1.OPT_COST) - uv1.OPT_FEE, 0.0)
            out[k] = np.where(has_e, (credit - debit) / debit, np.nan)
    return call, put


# ---------------------------------------------------------------- statistics
def cell_stats(X: np.ndarray, day_masks: dict[str, np.ndarray]) -> dict[str, tuple]:
    """Per weekday subset: n, mean, t over sessions for every entry minute (NaN = no trade)."""
    out = {}
    fin = np.isfinite(X)
    X0 = np.where(fin, X, 0.0)
    for day, msk in day_masks.items():
        n = fin[msk].sum(0)
        s1 = X0[msk].sum(0)
        s2 = (X0[msk] ** 2).sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = s1 / n
            var = (s2 - n * mean ** 2) / (n - 1)
            t = mean / np.sqrt(var / n)
        t = np.where(n >= 30, t, np.nan)
        out[day] = (n, mean, t)
    return out


def trades_for(sig: np.ndarray, m: np.ndarray, direction: str, inst: str,
               R: np.ndarray | None = None, call=None, put=None) -> np.ndarray:
    s = np.sign(sig)
    s = np.where(np.isfinite(m) & (np.abs(m) < uv1.THRESH), s, 0.0)
    bet = -s if direction == "fade" else s          # +1 = up (long / call), -1 = down
    if inst == "S":
        return np.where(bet != 0, bet * R - 2 * uv1.STOCK_COST, np.nan)
    return np.where(bet > 0, call, np.where(bet < 0, put, np.nan))


def family(inst: str, data: dict, rows: np.ndarray, perm: np.ndarray | None, day_masks) -> dict:
    """All cells of one instrument; perm reorders the signal rows (null) or None (observed)."""
    res = {}
    for sym, dd in data.items():
        m, b = dd["m"][rows], dd["b"][rows]
        if perm is not None:
            m, b = m[perm], b[perm]
        for signame, sig in (("A", m), ("B", b)):
            for direction in ("fade", "follow"):
                X = trades_for(sig, m, direction, inst,
                               R=dd.get("R", np.empty(0))[rows] if inst == "S" else None,
                               call=dd["call"][rows] if inst == "O" else None,
                               put=dd["put"][rows] if inst == "O" else None)
                for day, st in cell_stats(X, day_masks).items():
                    res[(signame, direction, sym, day)] = st
    return res


def summarize(res: dict) -> tuple[float, int]:
    ts = np.concatenate([v[2] for v in res.values()])
    return float(np.nanmax(ts)), int(np.nansum(ts >= 2))


def cmd_run() -> None:
    spec = json.loads(SPEC.read_text())
    if spec.get("status") != "FROZEN":
        raise SystemExit("spec is not frozen")
    if (OUT / "report.json").exists():
        raise SystemExit(f"{OUT}/report.json exists: the scan is single-shot")
    sess = sessions_all()
    dates = pd.to_datetime(pd.Series(sess))
    dow = dates.dt.dayofweek.to_numpy()
    data = {}
    for sym in uv1.TICKERS:
        st = load_stock_matrix(sym, sess)
        m, b, R = stock_returns(st)
        data[sym] = {"m": m, "b": b, "R": R, "st": st}
    opt_idx = np.flatnonzero(np.array(sess) >= OPT_START)
    for sym in uv1.TICKERS:
        st_o = {k: v[opt_idx] for k, v in data[sym]["st"].items()}
        call, put = option_returns(sym, [sess[i] for i in opt_idx], st_o)
        full_c = np.full(data[sym]["m"].shape, np.nan); full_c[opt_idx] = call
        full_p = np.full_like(full_c, np.nan); full_p[opt_idx] = put
        data[sym]["call"], data[sym]["put"] = full_c, full_p
    print("matrices built", flush=True)
    s_arr = np.array(sess)
    windows = {"S": np.flatnonzero(s_arr <= DEV_END),
               "O": np.flatnonzero((s_arr >= OPT_START) & (s_arr <= DEV_END))}
    conf_rows = np.flatnonzero(s_arr >= CONF_START)
    rng = np.random.default_rng(SEED)
    report = {"spec": SPEC.name, "run_at_utc": pd.Timestamp.now(tz="UTC").isoformat(), "families": {}}
    for inst, rows in windows.items():
        dm = {DAYS[k]: dow[rows] == k for k in range(5)}
        dm["All"] = np.ones(len(rows), bool)
        obs = family(inst, data, rows, None, dm)
        obs_max, obs_count = summarize(obs)
        null_max, null_count = [], []
        for _ in range(NPERM):
            pm, pc = summarize(family(inst, data, rows, rng.permutation(len(rows)), dm))
            null_max.append(pm); null_count.append(pc)
        null_max, null_count = np.array(null_max), np.array(null_count)
        thr = float(np.quantile(null_max, 0.95))
        flat = []
        for key, (n, mean, t) in obs.items():
            for j in range(len(ENTRY)):
                if np.isfinite(t[j]):
                    flat.append({"signal": key[0], "direction": key[1], "ticker": key[2], "day": key[3],
                                 "entry_et": hm(int(ENTRY[j])), "n": int(n[j]), "mean": float(mean[j]),
                                 "t": float(t[j]), "fw_p": float((null_max >= t[j]).mean())})
        cells = pd.DataFrame(flat).sort_values("t", ascending=False)
        cand = cells[(cells.t >= 2) & (cells.t > thr)]
        conf = []
        if len(cand):
            cdm = {DAYS[k]: dow[conf_rows] == k for k in range(5)}
            cdm["All"] = np.ones(len(conf_rows), bool)
            cres = family(inst, data, conf_rows, None, cdm)
            for _, c in cand.iterrows():
                n, mean, t = cres[(c.signal, c.direction, c.ticker, c.day)]
                j = hm(list(ENTRY)).index(c.entry_et)
                conf.append(dict(c, conf_n=int(n[j]), conf_mean=float(mean[j]), conf_t=float(t[j]),
                                 conf_pass=bool(mean[j] > 0 and t[j] >= 1)))
        OUT.mkdir(parents=True, exist_ok=True)
        cells.to_parquet(OUT / f"cells_{inst}.parquet")
        report["families"][inst] = {
            "cells": int(len(cells)), "obs_max_t": obs_max, "obs_count_t_ge_2": obs_count,
            "null_max_t_p50_p95": [float(np.median(null_max)), thr],
            "null_count_t_ge_2_mean_p95": [float(null_count.mean()), float(np.quantile(null_count, 0.95))],
            "max_t_fw_p": float((null_max >= obs_max).mean()),
            "count_p": float((null_count >= obs_count).mean()),
            "candidates": int(len(cand)), "confirmation": conf,
            "top20": cells.head(20).to_dict("records")}
        f = report["families"][inst]
        print(f"\n[{'stock' if inst == 'S' else 'options'}] {f['cells']} cells | t>=2: observed {obs_count}, "
              f"chance {f['null_count_t_ge_2_mean_p95'][0]:.0f} (95th {f['null_count_t_ge_2_mean_p95'][1]:.0f}), p {f['count_p']:.3f} | "
              f"max t observed {obs_max:.2f}, chance median {f['null_max_t_p50_p95'][0]:.2f} / 95th {thr:.2f}, p {f['max_t_fw_p']:.3f}")
        print(cells.head(15)[["signal", "direction", "ticker", "day", "entry_et", "n", "mean", "t", "fw_p"]]
              .to_string(index=False, formatters={"mean": lambda x: f"{x*100:+.3f}%"}))
        print("candidates:", len(cand))
        for c in conf:
            print(f"  confirm {c['signal']} {c['direction']} {c['ticker']} {c['day']} {c['entry_et']}: "
                  f"2026 n {c['conf_n']} mean {c['conf_mean']*100:+.3f}% t {c['conf_t']:.2f} -> {'PASS' if c['conf_pass'] else 'FAIL'}")
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["fetch", "run"])
    cmd_fetch() if ap.parse_args().cmd == "fetch" else cmd_run()


if __name__ == "__main__":
    main()
