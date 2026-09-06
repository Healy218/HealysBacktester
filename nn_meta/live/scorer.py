# nn_meta/live/scorer.py
"""NN scorer for the live scanner — P(win) for a fresh signal.

Reuses the EXACT training featurization (nothing reimplemented): the same
technical features, the same slot-executor to price the frozen-DTE contract
(prem_spot / moneyness), and the same surface + context joins. The model_final
ensemble then scores the single-row feature vector; the scanner keeps the
signal iff the mean P(win) clears the bundle's threshold.

Live simplification vs the backtest's rank mode: we score at the symbol's
FROZEN DTE (the contract we suggest) and gate on the threshold, rather than
cross-sectionally ranking DTE variants — one signal at a time, alert-only.

Staleness note: surface features (IV / PC-ratio / beta) come from the daily
cache; for a live "today" signal with no fresh surface row the as-of join
yields NaN, which predict_rows imputes to the train mean. A nightly surface
refresh (TODO) removes that gap.
"""
from __future__ import annotations

import json
from typing import Optional

import numpy as np
import pandas as pd

from utils.logging_utils import setup_logging
from options.execution import to_naive_utc
from nn_meta import config
from nn_meta.feature_contract import CONTRACT_VERSION
from nn_meta.baseline import execute_at_dte, load_spec, propose_trades
from nn_meta.build_meta_dataset import (META_FEATURES, _SURFACE_COLS,
                                        _feature_windows, add_context_features,
                                        join_surface_asof, load_surface_features,
                                        technical_features)
from nn_meta.providers import get_provider
from nn_meta.select_meta import predict_rows
from nn_meta.live.scanner import Signal

logger = setup_logging(log_file="logs/backtester.log")


class NNScorer:
    """Callable ``scorer(signal, bars) -> P(win)`` for Scanner."""

    def __init__(self, provider=None, spec: Optional[dict] = None,
                 surface: Optional[pd.DataFrame] = None):
        ens_path = config.MODEL_FINAL_DIR / "ensemble_config.json"
        if not ens_path.exists():
            raise FileNotFoundError(
                f"{ens_path} missing — train + select the meta-model first.")
        self.ens = json.loads(ens_path.read_text())
        if self.ens.get("feature_contract_version") != CONTRACT_VERSION:
            raise ValueError("legacy ensemble has a stale/missing feature contract; "
                             "rebuild, retrain and select before live scoring")
        self.threshold = float(self.ens["threshold"])
        self.spec = spec or load_spec()
        # live=True: identical for v2/v3 (hybrid either way); required under
        # v31, whose default provider is the history-only flat-files reader.
        self.provider = provider or get_provider(live=True)
        self.surface = surface if surface is not None else load_surface_features()

    def _feature_row(self, sig: Signal, bars: pd.DataFrame) -> Optional[pd.DataFrame]:
        entry = self.spec["symbols"][sig.symbol]
        strat = entry["best_strategy"]
        e = entry["strategies"][strat]

        trades = propose_trades(bars, strat, e["params"],
                                bars.index[0], bars.index[-1])
        if not trades:
            return None
        # the fresh signal is the newest trade; its bars-since-previous gap
        entry_ts = [to_naive_utc(t[0]) for t in trades]
        pos = bars.index.searchsorted(entry_ts)
        gap = pos[-1] - pos[-2] if len(pos) > 1 else pos[-1]
        trade = trades[-1]

        # price the frozen-DTE contract through the SAME executor as training
        records, _ = execute_at_dte(sig.symbol, [trade], bars, e["dte"],
                                    self.provider, str(bars.index[-1].date()))
        r = records[0]
        spot = sig.spot
        prem, strike = r["entry_premium"], r["strike"]

        feats = technical_features(bars, *_feature_windows(strat, e["params"]))
        frow = feats.iloc[-1]

        row = {
            "symbol": sig.symbol, "strategy": strat,
            "entry_ts": sig.bar_ts, "entry_date": sig.bar_ts.normalize(),
            "dir_short": float(sig.direction),
            "dte_frac": e["dte"] / max(config.DTE_GRID),
            "prem_spot": (prem / spot) if (prem and spot) else np.nan,
            "moneyness": float(np.log1p(config.EXEC_CONFIG.get("MONEYNESS", 0.0))),
            "bars_since_signal": float(np.log1p(gap)),
            **{k: frow.get(k, np.nan) for k in feats.columns},
        }
        df = pd.DataFrame([row])
        df = join_surface_asof(df, self.surface)
        df = add_context_features(df, self.surface)
        # ensure every model feature exists (missing → NaN → imputed downstream)
        for col in META_FEATURES:
            if col not in df.columns:
                df[col] = np.nan
        return df

    def __call__(self, sig: Signal, bars: pd.DataFrame) -> Optional[float]:
        try:
            row = self._feature_row(sig, bars)
        except Exception as exc:
            logger.error(f"[live-score] {sig.symbol}: featurize failed: {exc}")
            return None
        if row is None:
            return None
        preds = [predict_rows(rid, row)[0] for rid in self.ens["run_ids"]]
        return float(np.mean(preds))
