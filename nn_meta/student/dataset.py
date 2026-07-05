# nn_meta/student/dataset.py
"""Per-bar student panel: features + teacher state + counterfactual weights.

One row per (symbol, 15m bar) over the data window:
  - features: the per-bar technicals from build_meta_dataset.technical_features
    (computed with the symbol's FROZEN fast/slow) + daily surface features
    as-of the previous close. No trade-context features — the student decides
    per bar, before any trade exists.
  - teacher_state: 0 flat / 1 long / 2 short, from the frozen baseline's
    proposed trade timeline.
  - clone labels (stage 1): teacher_state verbatim.
  - finetune labels (stage 2): win-trade bars keep teacher_state
    (weight ∝ net_return at the frozen DTE, from the meta dataset);
    loss-trade bars are relabeled FLAT (weight ∝ |net_return|); bars outside
    trades stay FLAT at STUDENT_FLAT_WEIGHT. Trades with no executed option
    label get weight 0 (they teach nothing).

Run:  python -m nn_meta.student.dataset
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from utils.logging_utils import setup_logging
from options.execution import to_naive_utc
from nn_meta import config
from nn_meta.baseline import load_spec, load_underlying_15m, propose_trades
from nn_meta.build_meta_dataset import (_SURFACE_COLS, assign_split,
                                        load_surface_features,
                                        technical_features)

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-STUDENT-DS"

BAR_FEATURES = ["ma_gap", "px_vs_fast", "rsi14", "macd_hist", "bb_z",
                "ret_1", "ret_8", "ret_26", "session_gap", "tod", "dow"]
STUDENT_FEATURES = BAR_FEATURES + _SURFACE_COLS

FLAT, LONG, SHORT = 0, 1, 2


def _trade_returns_lookup(meta_ds: pd.DataFrame, symbol: str, dte: int) -> pd.Series:
    """entry_ts → realized net option return for the symbol's frozen DTE."""
    m = (meta_ds["symbol"] == symbol) & (meta_ds["dte"] == dte) \
        & meta_ds["net_return"].notna()
    sub = meta_ds[m]
    return pd.Series(sub["net_return"].values, index=pd.DatetimeIndex(sub["entry_ts"]))


def build_symbol_panel(symbol: str, spec_entry: dict,
                       meta_ds: pd.DataFrame) -> pd.DataFrame:
    bars = load_underlying_15m(symbol)
    if bars.empty:
        return pd.DataFrame()

    trades = propose_trades(bars, spec_entry["fast"], spec_entry["slow"],
                            config.WINDOW_START, config.WINDOW_END)
    feats = technical_features(bars, spec_entry["fast"], spec_entry["slow"])
    idx = bars.index

    state = np.full(len(idx), FLAT, dtype=np.int8)
    trade_ret = np.full(len(idx), np.nan)          # realized return of covering trade
    ret_lookup = _trade_returns_lookup(meta_ds, symbol, spec_entry["dte"])

    for ent_ts, ext_ts, direction in trades:
        e, x = to_naive_utc(ent_ts), to_naive_utc(ext_ts)
        i = idx.searchsorted(e)
        j = idx.searchsorted(x)                     # exit bar excluded (flat again)
        state[i:j] = LONG if direction == 0 else SHORT
        if e in ret_lookup.index:
            trade_ret[i:j] = float(ret_lookup.loc[e])

    panel = feats.copy()
    panel = panel[panel.index >= pd.Timestamp(config.WINDOW_START)]
    aligned = panel.index
    pos = idx.searchsorted(aligned)
    panel["teacher_state"] = state[pos]
    panel["trade_return"] = trade_ret[pos]
    panel["symbol"] = symbol
    panel["entry_date"] = panel.index.normalize()
    return panel.reset_index().rename(columns={"timestamp": "bar_ts"})


def finetune_labels(panel: pd.DataFrame) -> pd.DataFrame:
    """Stage-2 counterfactual labels + weights (vectorized)."""
    st = panel["teacher_state"].values
    r = panel["trade_return"].values
    in_trade = st != FLAT

    label = st.copy()
    weight = np.full(len(panel), config.STUDENT_FLAT_WEIGHT)

    win = in_trade & (r > 0)
    lose = in_trade & (r <= 0)
    unlabeled = in_trade & np.isnan(r)

    weight[win] = np.clip(r[win], 0, config.STUDENT_WIN_WEIGHT_CLIP)
    label[lose] = FLAT                              # counterfactual: skip losers
    weight[lose] = np.clip(np.abs(r[lose]), 0, config.STUDENT_LOSE_WEIGHT_CLIP)
    weight[unlabeled] = 0.0                         # unexecuted trades teach nothing

    panel["ft_label"] = label
    panel["ft_weight"] = weight
    return panel


def main() -> None:
    config.ensure_dirs()
    spec = load_spec()
    meta_ds = pd.read_parquet(config.META_DATASET_PARQUET)
    surface = load_surface_features()

    frames = []
    for sym, entry in spec["symbols"].items():
        panel = build_symbol_panel(sym, entry, meta_ds)
        if panel.empty:
            print(f"[{sym}] no panel")
            continue
        n_tr = (panel["teacher_state"] != FLAT).sum()
        print(f"[{sym}] {len(panel)} bars | in-trade {n_tr / len(panel):.0%} | "
              f"labeled-return bars "
              f"{panel['trade_return'].notna().sum() / max(n_tr, 1):.0%} of in-trade",
              flush=True)
        frames.append(panel)
    if not frames:
        raise SystemExit("no panels built")

    ds = pd.concat(frames, ignore_index=True)

    # surface as-of previous close (same join as the meta dataset)
    parts = []
    for sym, grp in ds.groupby("symbol"):
        s = surface[surface["underlying"] == sym]
        grp = grp.sort_values("entry_date")
        if s.empty:
            for c in _SURFACE_COLS:
                grp[c] = np.nan
            parts.append(grp)
            continue
        parts.append(pd.merge_asof(
            grp, s.drop(columns=["underlying"]),
            left_on="entry_date", right_on="date",
            allow_exact_matches=False).drop(columns=["date"]))
    ds = pd.concat(parts, ignore_index=True)

    ds = finetune_labels(ds)
    ds["split"] = assign_split(ds["entry_date"])
    ds = ds[ds["split"] != "purged"].reset_index(drop=True)
    ds.to_parquet(config.STUDENT_DATASET_PARQUET, index=False)

    print(f"\nstudent panel: {len(ds)} bars → {config.STUDENT_DATASET_PARQUET}")
    for s in ("train", "val", "test"):
        sub = ds[ds["split"] == s]
        dist = sub["teacher_state"].value_counts(normalize=True).round(3).to_dict()
        print(f"  {s:5s}: {len(sub):7d} bars | state dist {dist}")
    relabeled = ((ds["teacher_state"] != FLAT) & (ds["ft_label"] == FLAT)).mean()
    print(f"  stage-2: {relabeled:.1%} of bars counterfactually relabeled flat")


if __name__ == "__main__":
    main()
