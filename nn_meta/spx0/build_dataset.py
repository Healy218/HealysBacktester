"""spx0 label builder — one session at a time, v4 causal contract throughout.

Per session and index (SPX via SPY, NDX via QQQ):

  1. Strategies (the v31-frozen SPY/QQQ params) run on the proxy's 5m bars
     with full-history warmup; a long entry proposes a CALL, a short entry a
     PUT. The signal time is the 5m bar CLOSE (``entry_ts``).
  2. The 0DTE contract is the nearest strike to the ratio-mapped proxy close
     among contracts that printed in the last 5 minutes (no print, no trade).
  3. Entry fills on the first 1m option bar AFTER the signal with depth
     (``fills.entry_fill``); no depth -> ``executed=False`` row, kept.
  4. Exit signal = first of: the strategy's exit/opposite signal on a later
     5m bar, the premium stop/target on 1m closes, or the session floor (the
     proxy's last bar). The exit fills on the first bar at/after it with depth
     (``fills.exit_fill``), else settles to intrinsic at the floor.
  5. ``gross_return`` from the fill prints; ``net_return`` after the dollar
     cost scenario; ``und_period_return`` from the proxy over the same span;
     a marks sidecar of the contract's 1m closes between the fills.

Round 2 (SPX0_SPEC "Second design round"): each signal is emitted at every
``TradeVariant`` — long premium stops and sell-premium variants (opposite
right, margin-as-size, loss capped by a stop above entry). The variant code
rides the ``dte`` column, so rank/EV dedupe makes it fold-selectable exactly
like DTE in v4; code 0 reproduces the round-1 long build and is the frozen
baseline. Short returns are per unit posted margin.

Every feature is declared in ``feature_contract`` and computed at or before
the signal bar close. Nothing here reads the option chain past ``entry_ts``
to DECIDE anything; it reads past it only to REALIZE the outcome.

Run:  ./venv/bin/python -m nn_meta.spx0.build_dataset [--days 2025-06-10,...]
      [--limit N] [--out nn_meta/artifacts_spx0]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta import proposals
from nn_meta.baseline import load_spec
from nn_meta.build_meta_dataset import _feature_windows, technical_features
from nn_meta.feature_contract import assert_decision_safe
from nn_meta.mark_stream import stable_trade_id
from nn_meta.spx0 import config as sc
from nn_meta.spx0.contracts import (implied_index_level, parse_occ_frame, pick_atm,
                                    pick_wing, same_day_expiry, session_ratio)
from nn_meta.spx0.costs import (BASE, IndexCostScenario, gross_return,
                                gross_return_short, gross_return_vertical,
                                net_return, net_return_short, net_return_vertical,
                                short_margin, vertical_margin)
from nn_meta.spx0.intraday import intraday_signals
from nn_meta.spx0.fills import (DepthPolicy, FillFailure, entry_fill, exit_fill,
                                intrinsic, spread_entry_fill, spread_exit_fill)
from nn_meta.temporal_validation import assign_purged_splits

TECHNICALS = ["ma_gap", "px_vs_fast", "rsi14", "macd_hist", "bb_z", "ret_1", "ret_8",
              "ret_26", "session_gap", "gap_abs_z", "tod", "dow", "is_first_hour",
              "is_last_hour", "dow_tod"]
CONTEXT = ["dir_short", "dte_frac", "moneyness", "bars_since_signal"]
SPX0_META_FEATURES = TECHNICALS + CONTEXT + sc.SPX0_FEATURES \
    + [f"strat_{s}" for s in sc.STRATEGIES]
BARS_PER_SESSION_5M = 78


# ── proxy bars ───────────────────────────────────────────────────────────────

def load_proxy_1m(index: str) -> pd.DataFrame:
    df = pd.read_parquet(sc.UNDERLYING_1M / f"{sc.PROXY[index]}.parquet")
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def resample_5m(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """Right-labelled 5m bars: the bar stamped 13:35 closes at 13:35 (covers
    13:30-13:34), so a decision at its stamp uses only completed minutes."""
    o = bars_1m.resample(sc.SIGNAL_BAR, label="right", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
    return o.dropna(subset=["Close"])


def proxy_context_features(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """1m-derived spx0_ features, indexed like the 1m bars (looked up at the
    signal close). Rolling windows END at the bar, never straddle it."""
    r = np.log(bars_1m["Close"]).diff()
    day = bars_1m.index.normalize()
    first = bars_1m.groupby(day).cumcount()
    return pd.DataFrame({
        "spx0_rv_30": r.rolling(30).std(),
        "spx0_rv_60": r.rolling(60).std(),
        "spx0_min_since_open": first.astype(float),
    }, index=bars_1m.index)


# ── per-session option frame ─────────────────────────────────────────────────

def load_session_options(day: pd.Timestamp) -> pd.DataFrame:
    path = sc.FLATFILES_1M / f"{pd.Timestamp(day).date()}.parquet"
    df = pd.read_parquet(path)
    parsed = parse_occ_frame(df["occ"])
    df = pd.concat([df, parsed], axis=1)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    z = same_day_expiry(df, day)
    return z.sort_values(["occ", "timestamp"]).reset_index(drop=True)


# ── one session, one index, one strategy ─────────────────────────────────────

def _as_series(sig) -> pd.Series | None:
    """single_signals may hand back a one-column frame; the builder wants a
    boolean Series indexed by bar."""
    if sig is None:
        return None
    if isinstance(sig, pd.DataFrame):
        if sig.shape[1] != 1:
            raise ValueError(f"expected a single signal column, got {sig.shape[1]}")
        sig = sig.iloc[:, 0]
    return sig.fillna(False).astype(bool)


def _first_true_after(sig: pd.Series, t: pd.Timestamp) -> pd.Timestamp | None:
    after = sig[sig.index > t]
    hit = after[after]
    return None if hit.empty else pd.Timestamp(hit.index[0])


def _stop_target_ts(cbars: pd.DataFrame, fill_ts: pd.Timestamp, entry_px: float,
                    variant: sc.TradeVariant) -> pd.Timestamp | None:
    """First 1m close through the variant's premium stop (or target, longs
    only). A long stops BELOW its entry; a short's stop is the loss cap ABOVE
    it (premium rising against the seller)."""
    later = cbars[cbars["timestamp"] > fill_ts]
    if variant.short:
        hit = later[later["Close"] >= variant.stop_frac * entry_px]
    else:
        hit = later[(later["Close"] <= variant.stop_frac * entry_px)
                    | (later["Close"] >= variant.target_mult * entry_px)]
    return None if hit.empty else pd.Timestamp(hit["timestamp"].iloc[0])


def prepare_signals(bars_5m: pd.DataFrame, spec_entry: dict,
                    active: set[str] | None = None) -> dict:
    """Per strategy, ONCE over the full proxy history: the four signal series
    and the technical features (5m clock features re-scaled from the 15m
    convention: 78 bars/session, first/last hour = 12 bars). Intraday-native
    seats (round 3, ``sc.INTRADAY_STRATEGIES``) have no frozen spec entry —
    their params ARE the seat name, competing in-fold like any strategy."""
    out = {}
    bar_of_day = bars_5m.groupby(bars_5m.index.normalize()).cumcount()

    def _clock(feats: pd.DataFrame) -> pd.DataFrame:
        feats["tod"] = bar_of_day / float(BARS_PER_SESSION_5M - 1)
        feats["is_first_hour"] = (bar_of_day < 12).astype(float)
        feats["is_last_hour"] = (bar_of_day >= BARS_PER_SESSION_5M - 12).astype(float)
        feats["dow_tod"] = feats["dow"] * feats["tod"]
        return feats

    for strategy in sc.STRATEGIES:
        if active is not None and strategy not in active:
            continue                       # seat has no variants this round
        if strategy in sc.INTRADAY_STRATEGIES:
            sigs = tuple(_as_series(x) for x in intraday_signals(strategy, bars_5m))
            feats = _clock(technical_features(bars_5m, 12, 26))
            out[strategy] = (sigs, feats)
            continue
        sentry = spec_entry["strategies"].get(strategy)
        if sentry is None:
            continue
        params = sentry["params"]
        sigs = tuple(_as_series(x) for x in proposals.single_signals(strategy, bars_5m, params))
        fast, slow = _feature_windows(strategy, params)
        feats = _clock(technical_features(bars_5m, fast, slow))
        out[strategy] = (sigs, feats)
    return out


def build_session_rows(day: pd.Timestamp, index: str, *, proxy_1m: pd.DataFrame,
                       bars_5m: pd.DataFrame, options: pd.DataFrame,
                       prepared: dict, ctx_1m: pd.DataFrame,
                       depth: DepthPolicy = DepthPolicy(),
                       exit_policy: sc.ExitPolicy = sc.DEFAULT_EXIT,
                       costs: IndexCostScenario = BASE,
                       counters: dict | None = None,
                       variants: tuple[sc.TradeVariant, ...] | None = None
                       ) -> tuple[list[dict], list[dict]]:
    day = pd.Timestamp(day).normalize()
    px_day = proxy_1m[proxy_1m.index.normalize() == day]
    b5_day = bars_5m[bars_5m.index.normalize() == day]
    z = options[options["index"] == index]
    if px_day.empty or b5_day.empty or z.empty:
        return [], []
    floor_ts = pd.Timestamp(px_day.index[-1])                 # proxy 16:00 bar
    last_entry_ts = floor_ts - pd.Timedelta(minutes=sc.LAST_ENTRY_MINUTES_BEFORE_CLOSE)
    first_bar_ts = pd.Timestamp(z["timestamp"].min())
    px_at_first = px_day["Close"].asof(first_bar_ts)
    try:
        ratio = session_ratio(z, float(px_at_first), index=index, first_bar_ts=first_bar_ts)
    except ValueError:
        return [], []
    # Settlement level at the floor: parity-implied from the closing prints
    # (sub-point precision); the ratio-mapped proxy close only as a fallback.
    implied = implied_index_level(z, index=index, at=floor_ts)
    floor_spot = implied if implied is not None else float(px_day["Close"].iloc[-1]) * ratio
    counters = counters if counters is not None else {}
    # No variants supplied: the round-1 single-long build, derived from
    # exit_policy so the legacy call sites (and their outputs) are unchanged.
    # A MAPPING (round 4) assigns each strategy seat its own variant tuple —
    # seats absent from the map propose nothing.
    if variants is None:
        variants = (sc.TradeVariant(0, False, exit_policy.stop_frac,
                                    exit_policy.target_mult),)
    rows, marks = [], []

    for strategy, ((entries, exits, s_ent, s_ext), feats) in prepared.items():
        strat_variants = (variants.get(strategy, ()) if isinstance(variants, dict)
                          else variants)
        if not strat_variants:
            continue

        for sig_right, sig_entry, sig_exit, sig_opp in (
                ("C", entries, exits, s_ent), ("P", s_ent, s_ext, entries)):
            if sig_entry is None:
                continue
            day_sig = sig_entry[(sig_entry.index.normalize() == day) & sig_entry]
            for t in day_sig.index:
                t = pd.Timestamp(t)
                if t > last_entry_ts or t not in bars_5m.index:
                    continue
                key = (index, strategy)
                counters[key] = counters.get(key, 0) + 1
                trade_idx = counters[key]
                # DECISION-side lookups must read the last COMPLETED 1m bar:
                # bars are start-stamped, so the bar stamped t is still forming
                # at the signal close t — reading it leaks ~1 minute of future
                # price into strike selection and features (review 2026-08-24).
                t_done = t - pd.Timedelta(minutes=1)
                spot = float(px_day["Close"].asof(t_done))
                mapped = spot * ratio
                # the symbol keeps the SIGNAL's right so every variant of one
                # signal shares the (symbol, strategy, trade_idx) dedupe key
                symbol = f"{index}-{sig_right}"
                # strategy-driven exit candidates are variant-independent
                sig_exit_ts = []
                for sig in (sig_exit, sig_opp):
                    if sig is not None:
                        u = _first_true_after(sig, t)
                        if u is not None:
                            sig_exit_ts.append(u)
                # features at the signal close (all SIGNAL_CLOSE by construction;
                # 1m-derived context stops at the last completed bar)
                f = feats.loc[t]
                c1 = (ctx_1m.asof(t_done) if t_done >= ctx_1m.index[0]
                      else pd.Series(dtype=float))
                contract_by_right: dict = {}

                for variant in strat_variants:
                    # a short variant SELLS the opposite right: a bullish
                    # signal sells the put, a bearish one sells the call
                    right = (sig_right if not variant.short
                             else ("P" if sig_right == "C" else "C"))
                    if right not in contract_by_right:
                        contract_by_right[right] = pick_atm(
                            z, index=index, right=right, mapped_spot=mapped, at=t)
                    contract = contract_by_right[right]
                    min_to_exp = (floor_ts - t).total_seconds() / 60.0
                    base = {
                        "symbol": symbol, "root": None, "index": index, "strategy": strategy,
                        "trade_idx": trade_idx, "dte": variant.code, "entry_ts": t,
                        "entry_date": day,
                        "direction": 0 if sig_right == "C" else 1, "right": right,
                        "contract": None, "strike": np.nan, "expiration": day,
                        "entry_premium": np.nan, "fill_entry_ts": pd.NaT, "fill_exit_ts": pd.NaT,
                        "fill_lag_s": np.nan, "n_fills": 0, "n_rolls": 0, "executed": False,
                        "gross_return": np.nan, "net_return": np.nan, "exit_ts": pd.NaT,
                        "und_period_return": np.nan, "exit_reason": None, "margin": np.nan,
                        "depth_entry": np.nan, "depth_exit": np.nan, "spx0_ratio": ratio,
                        "wing_contract": None, "wing_strike": np.nan,
                    }
                    base.update({k: float(f[k]) for k in TECHNICALS})
                    rv30 = float(c1.get("spx0_rv_30", np.nan))
                    base.update({
                        "dir_short": 1.0 if sig_right == "P" else 0.0,
                        "dte_frac": min_to_exp / 390.0,
                        "bars_since_signal": 0.0,
                        "spx0_rv_30": rv30,
                        "spx0_rv_60": float(c1.get("spx0_rv_60", np.nan)),
                        "spx0_min_since_open": float(c1.get("spx0_min_since_open", np.nan)),
                        "spx0_min_to_expiry": min_to_exp,
                        "spx0_short": 1.0 if variant.short else 0.0,
                        # verticals carry stop_frac=inf (no stop; the wing IS
                        # the loss bound) — features must stay finite
                        "spx0_stop_frac": (float(variant.stop_frac)
                                           if np.isfinite(variant.stop_frac) else 0.0),
                        "spx0_wing_width_frac": 0.0,
                    })
                    for s_ in sc.STRATEGIES:
                        base[f"strat_{s_}"] = 1.0 if s_ == strategy else 0.0
                    if contract is None:
                        base.update({"moneyness": np.nan, "spx0_depth_signal": 0.0,
                                     "spx0_prem_spot_last": np.nan,
                                     "spx0_prem_rich": np.nan,
                                     "exit_reason": "no_contract"})
                        rows.append(base)
                        continue
                    cbars = z[z["occ"] == contract.occ]
                    before = cbars[cbars["timestamp"] < t]     # completed prints only
                    last_print = before.iloc[-1] if not before.empty else None
                    prem_spot = (float(last_print["Close"]) / mapped
                                 if last_print is not None else np.nan)
                    # premium richness: last premium/spot vs the realized-vol
                    # move to expiry (>1 = premium richer than recent movement)
                    exp_move = rv30 * np.sqrt(max(min_to_exp, 0.0))
                    prem_rich = prem_spot / exp_move if exp_move > 0 else np.nan
                    base.update({
                        "root": contract.root, "contract": contract.occ,
                        "strike": contract.strike,
                        "moneyness": contract.strike / mapped - 1.0,
                        "spx0_depth_signal": float(last_print["Volume"]) if last_print is not None else 0.0,
                        "spx0_prem_spot_last": prem_spot,
                        "spx0_prem_rich": prem_rich,
                    })
                    # ── credit vertical (round 3): sold leg + bought wing ────
                    if variant.wing_strikes > 0:
                        wing = pick_wing(z, short_leg=contract, mapped_spot=mapped,
                                         wing_strikes=variant.wing_strikes, at=t)
                        if wing is None:
                            base["exit_reason"] = "no_wing"
                            rows.append(base)
                            continue
                        wbars = z[z["occ"] == wing.occ]
                        width = abs(contract.strike - wing.strike)
                        base.update({"wing_contract": wing.occ,
                                     "wing_strike": wing.strike,
                                     "spx0_wing_width_frac": width / mapped})
                        fe_ts, fe_short, fe_wing, fe_depth, fail = spread_entry_fill(
                            cbars, wbars, t, depth)
                        if fail is not None:
                            base["exit_reason"] = fail.value
                            rows.append(base)
                            continue
                        credit = fe_short - fe_wing
                        # A credit within a print of the full width prices
                        # near-certain assignment — at 1m close granularity
                        # that is stale-print fiction with degenerate ~0
                        # margin (net −68× showed up in the smoke), not a
                        # fillable market. Cap at 90% of the width.
                        if not 0 < credit <= 0.9 * width:
                            base["exit_reason"] = "no_credit"
                            rows.append(base)
                            continue
                        margin = vertical_margin(width, credit)
                        # loss is bounded by the wing, so no premium stop:
                        # strategy exit / opposite signal, else the floor.
                        exit_sig_ts = max(min([floor_ts] + sig_exit_ts), fe_ts)
                        reason = "floor" if exit_sig_ts == floor_ts else "signal"
                        intr_s = intrinsic(right, contract.strike, floor_spot)
                        intr_w = intrinsic(right, wing.strike, floor_spot)
                        fx_ts, short_x, wing_x, fx_depth, xfail = spread_exit_fill(
                            cbars, wbars, exit_sig_ts, depth,
                            session_floor_ts=floor_ts,
                            intrinsic_short=intr_s, intrinsic_wing=intr_w)
                        settled = xfail is FillFailure.SETTLED_INTRINSIC
                        if settled:
                            reason = "settled_intrinsic"
                        # The closing debit is bounded on BOTH paths: a seller
                        # never pays more than the width to close (cash
                        # settlement is always available and pays at most the
                        # width), and a negative debit is a stale-print
                        # arbitrage, not a fillable price. This is what makes
                        # the vertical's −1×margin loss floor a hard bound.
                        exit_debit = min(max(short_x - wing_x, 0.0), width)
                        g = gross_return_vertical(credit, exit_debit, margin)
                        n = net_return_vertical(credit, exit_debit, margin, costs,
                                                settled=settled)
                        und_exit = float(px_day["Close"].asof(fx_ts))
                        base.update({
                            "entry_premium": credit, "fill_entry_ts": fe_ts,
                            "fill_exit_ts": fx_ts,
                            "fill_lag_s": (fe_ts - t).total_seconds(), "n_fills": 2,
                            "executed": True, "gross_return": g, "net_return": n,
                            "exit_ts": fx_ts,
                            "und_period_return": und_exit / spot - 1.0,
                            "exit_reason": reason, "margin": margin,
                            "depth_entry": fe_depth, "depth_exit": fx_depth,
                        })
                        rows.append(base)
                        tid = (f"{symbol}|{strategy}|{trade_idx}|{variant.code}"
                               f"|{int(pd.Timestamp(t).value)}")
                        # marks: minutes where BOTH legs printed a close
                        joined = cbars[["timestamp", "Close"]].merge(
                            wbars[["timestamp", "Close"]], on="timestamp",
                            suffixes=("_s", "_w"))
                        inner = joined[(joined["timestamp"] > fe_ts)
                                       & (joined["timestamp"] < fx_ts)]
                        marks.append({"trade_id": tid, "mark_ts": fe_ts,
                                      "gross_return": 0.0})
                        for r in inner.itertuples(index=False):
                            # marked value is bounded like the exit: the
                            # spread's liquidation cost lies in [0, width]
                            spread = min(max(float(r.Close_s) - float(r.Close_w),
                                             0.0), width)
                            marks.append({"trade_id": tid,
                                          "mark_ts": pd.Timestamp(r.timestamp),
                                          "gross_return": (credit - spread) / margin})
                        marks.append({"trade_id": tid, "mark_ts": fx_ts,
                                      "gross_return": g})
                        continue

                    fe_ts, fe_px, fe_depth, fail = entry_fill(cbars, t, depth,
                                                              sell=variant.short)
                    if fail is not None:
                        base["exit_reason"] = fail.value
                        rows.append(base)
                        continue
                    # exit signal: strategy exit / opposite entry on a LATER 5m
                    # bar, premium stop (and long target) on 1m closes, or the
                    # session floor.
                    cands = [floor_ts] + sig_exit_ts
                    st = _stop_target_ts(cbars, fe_ts, fe_px, variant)
                    if st is not None:
                        cands.append(st)
                    exit_sig_ts = max(min(cands), fe_ts)
                    reason = ("floor" if exit_sig_ts == floor_ts else
                              "stop_target" if st is not None and exit_sig_ts == st else "signal")
                    fx_ts, fx_px, fx_depth, xfail = exit_fill(
                        cbars, exit_sig_ts, depth, session_floor_ts=floor_ts,
                        intrinsic_at_floor=intrinsic(right, contract.strike, floor_spot),
                        buyback=variant.short)
                    settled = xfail is FillFailure.SETTLED_INTRINSIC
                    if settled:
                        reason = "settled_intrinsic"
                    if variant.short:
                        margin = short_margin(fe_px, variant.stop_frac)
                        g = gross_return_short(fe_px, fx_px, margin)
                        n = net_return_short(fe_px, fx_px, margin, costs, settled=settled)
                    else:
                        margin = np.nan
                        g = gross_return(fe_px, fx_px)
                        n = net_return(fe_px, fx_px, costs)
                    und_exit = float(px_day["Close"].asof(fx_ts))
                    base.update({
                        "entry_premium": fe_px, "fill_entry_ts": fe_ts, "fill_exit_ts": fx_ts,
                        "fill_lag_s": (fe_ts - t).total_seconds(), "n_fills": 1,
                        "executed": True, "gross_return": g, "net_return": n,
                        "exit_ts": fx_ts, "und_period_return": und_exit / spot - 1.0,
                        "exit_reason": reason, "depth_entry": fe_depth, "depth_exit": fx_depth,
                        "margin": margin,
                    })
                    rows.append(base)
                    # marks: contract closes strictly between the fills, bounded
                    # by the fill prints themselves (entry and exit marks
                    # guaranteed), in the row's own per-position return units.
                    tid = (f"{symbol}|{strategy}|{trade_idx}|{variant.code}"
                           f"|{int(pd.Timestamp(t).value)}")
                    inner = cbars[(cbars["timestamp"] > fe_ts) & (cbars["timestamp"] < fx_ts)]
                    marks.append({"trade_id": tid, "mark_ts": fe_ts, "gross_return": 0.0})
                    for r in inner.itertuples(index=False):
                        mg = ((fe_px - float(r.Close)) / margin if variant.short
                              else float(r.Close) / fe_px - 1.0)
                        marks.append({"trade_id": tid, "mark_ts": pd.Timestamp(r.timestamp),
                                      "gross_return": mg})
                    marks.append({"trade_id": tid, "mark_ts": fx_ts, "gross_return": g})
    return rows, marks


# ── driver ───────────────────────────────────────────────────────────────────

def available_sessions() -> list[pd.Timestamp]:
    return sorted(pd.Timestamp(p.stem) for p in sc.FLATFILES_1M.glob("*.parquet"))


def build(days: list[pd.Timestamp], out_dir: Path, *, spec: dict | None = None,
          depth: DepthPolicy = DepthPolicy(), exit_policy: sc.ExitPolicy = sc.DEFAULT_EXIT,
          costs: IndexCostScenario = BASE,
          variants: tuple[sc.TradeVariant, ...] | dict = sc.ROUND4_SEAT_VARIANTS
          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    assert_decision_safe(SPX0_META_FEATURES)
    spec = spec or load_spec()
    out_dir.mkdir(parents=True, exist_ok=True)
    proxies = {i: load_proxy_1m(i) for i in sc.INDEXES}
    bars5 = {i: resample_5m(p) for i, p in proxies.items()}
    ctx = {i: proxy_context_features(p) for i, p in proxies.items()}
    active = set(variants.keys()) if isinstance(variants, dict) else None
    prepared = {}
    for i in sc.INDEXES:
        entry = spec["symbols"].get(sc.PROXY[i])
        if entry is None:
            raise SystemExit(f"baseline spec has no frozen params for {sc.PROXY[i]}")
        prepared[i] = prepare_signals(bars5[i], entry, active)
    counters: dict = {}
    all_rows, all_marks = [], []
    t0 = time.time()
    for k, day in enumerate(days, 1):
        options = load_session_options(day)
        for index in sc.INDEXES:
            r, m = build_session_rows(day, index, proxy_1m=proxies[index], bars_5m=bars5[index],
                                      options=options, prepared=prepared[index], ctx_1m=ctx[index],
                                      depth=depth, exit_policy=exit_policy, costs=costs,
                                      counters=counters, variants=variants)
            all_rows += r
            all_marks += m
        if k % 20 == 0 or k == len(days):
            print(f"[spx0] {k}/{len(days)} sessions, {len(all_rows)} rows, "
                  f"{time.time()-t0:.0f}s", flush=True)
    ds = pd.DataFrame(all_rows)
    marks = pd.DataFrame(all_marks, columns=["trade_id", "mark_ts", "gross_return"])
    if not ds.empty:
        ds["label"] = np.where(ds["net_return"].notna(), (ds["net_return"] > 0).astype(float), np.nan)
        both = ds["net_return"].notna() & ds["und_period_return"].notna()
        ds["label_excess"] = np.where(both, (ds["net_return"] > ds["und_period_return"]).astype(float), np.nan)
        days_u = np.sort(ds["entry_date"].unique())
        if len(days_u) >= 5:
            v, tst = days_u[int(len(days_u) * 0.6)], days_u[int(len(days_u) * 0.8)]
            ds["split"] = assign_purged_splits(
                ds.assign(exit_ts=ds["exit_ts"].fillna(ds["entry_ts"])),
                train_start=pd.Timestamp(days_u[0]), val_start=pd.Timestamp(v),
                test_start=pd.Timestamp(tst), test_end=pd.Timestamp(days_u[-1]), embargo="1D")
        else:
            ds["split"] = "train"          # tiny smoke build; evaluate re-splits anyway
        filled = ds[ds["executed"]]
        assert (filled["fill_lag_s"] > 0).all(), "option fill precedes or equals signal bar"
        tid = stable_trade_id(filled)
        assert set(marks["trade_id"]) == set(tid), "marks/rows trade_id mismatch"
        marks = marks.drop_duplicates(["trade_id", "mark_ts"], keep="last")
    tmp = out_dir / "meta_dataset.parquet.tmp"
    ds.to_parquet(tmp, index=False); tmp.replace(out_dir / "meta_dataset.parquet")
    tmpm = out_dir / "meta_dataset.marks.parquet.tmp"
    marks.to_parquet(tmpm, index=False); tmpm.replace(out_dir / "meta_dataset.marks.parquet")
    (out_dir / "build_manifest.json").write_text(json.dumps({
        "sessions": [str(d.date()) for d in days], "rows": int(len(ds)),
        "executed": int(ds["executed"].sum()) if len(ds) else 0,
        "depth_policy": depth.__dict__, "exit_policy": exit_policy.__dict__,
        "variants": ({k: [v.__dict__ for v in vs] for k, vs in variants.items()}
                     if isinstance(variants, dict)
                     else [v.__dict__ for v in variants]),
        "costs": costs.__dict__, "features": SPX0_META_FEATURES}, indent=2, default=str))
    return ds, marks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", default=None, help="comma-separated YYYY-MM-DD (default: all)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, default=sc.ARTIFACTS)
    args = ap.parse_args()
    days = ([pd.Timestamp(d) for d in args.days.split(",")] if args.days
            else available_sessions())
    if args.limit:
        days = days[:args.limit]
    ds, marks = build(days, args.out)
    ex = ds[ds["executed"]] if len(ds) else ds
    print(f"rows={len(ds)} executed={len(ex)} marks={len(marks)} -> {args.out}")
    if len(ex):
        print(ex.groupby(["dte", "exit_reason"])["net_return"].agg(["size", "mean"]).round(3))


if __name__ == "__main__":
    main()
