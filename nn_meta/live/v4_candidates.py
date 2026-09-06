"""V4 live candidate-batch constructor.

Builds candidate feature rows for a fresh signal using the SAME offline
primitives (`technical_features`, `join_surface_asof`, the one-hot maps) and the
v4 causal schema (`V4_META_FEATURES`) — crucially WITHOUT executing an option,
so there is no `prem_spot` and no next-option-open dependency.  This is the
constructor the live scanner must consume to reach v4 parity; the deployed
legacy scorer is intentionally left unchanged and still depends on `prem_spot`.

Parity is by construction: the same functions produce the offline dataset row
and the live candidate row, so `assert_candidate_parity` can compare them field
by field on the causal schema.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nn_meta import config
from nn_meta.build_meta_dataset import (V4_META_FEATURES, _feature_windows,
                                        join_surface_asof, technical_features)
from nn_meta.feature_contract import assert_decision_safe
from nn_meta.live.v4_parity import assert_feature_parity

# Cross-sectional context joined from the daily caches (as of the prior close),
# not computable from a single symbol's bars alone.
_CONTEXT_ONLY = ("market_iv", "rv_iv_spread", "beta_60d")


def _trade_context(direction, dte, bars_since_signal) -> dict:
    """Proposal-metadata features — all known at signal close, no option fill."""
    return {
        "dir_short": float(direction),
        "dte_frac": dte / max(config.DTE_GRID),
        # Same decision-time target as build_meta_dataset. Listed/executed
        # strike and technical history's adjustment basis are not features.
        "moneyness": float(np.log1p(config.EXEC_CONFIG.get("MONEYNESS", 0.0))),
        "bars_since_signal": float(np.log1p(bars_since_signal)),
    }


def build_candidate_batch(proposals: pd.DataFrame,
                          bars_by_symbol: dict[str, pd.DataFrame],
                          surface: pd.DataFrame, spec: dict, *,
                          context: pd.DataFrame | None = None,
                          expanded_inputs=None, option_provider=None,
                          raw_close_by_symbol=None) -> pd.DataFrame:
    """Construct a v4 causal candidate batch from closed underlying bars.

    ``proposals`` needs symbol, strategy, dte, direction, strike, entry_ts, and
    an optional bars_since_signal (default 1 = next bar).  Features are computed
    as of each proposal's signal bar; no option is executed, so the batch is
    ``prem_spot``-free and decision-safe by the v4 feature contract.
    """
    rows = []
    if config.V6_EXPANDED and (expanded_inputs is None or option_provider is None
                               or raw_close_by_symbol is None):
        raise ValueError("expanded v6 candidates require verified feature inputs, PIT chain and raw closes; live adapter not configured")
    for p in proposals.itertuples(index=False):
        bars = bars_by_symbol[p.symbol]
        entry_ts = pd.Timestamp(p.entry_ts)
        params = spec["symbols"][p.symbol]["strategies"][p.strategy].get("params", {})
        f_w, s_w = _feature_windows(p.strategy, params)
        feats = technical_features(bars, f_w, s_w).loc[:entry_ts]
        if feats.empty:
            raise ValueError(f"no underlying bars at or before {entry_ts} for {p.symbol}")
        row = feats.iloc[-1].to_dict()
        lag = getattr(p, "bars_since_signal", 1)
        row.update(_trade_context(p.direction, p.dte, lag))
        row.update({"symbol": p.symbol, "strategy": p.strategy, "dte": p.dte,
                    "entry_ts": entry_ts, "entry_date": entry_ts.normalize()})
        if config.V6_EXPANDED:
            row["direction"] = p.direction
        rows.append(row)

    batch = pd.DataFrame(rows)
    if config.V6_EXPANDED and not batch.empty:
        batch = pd.concat([expanded_inputs.append(group, symbol=symbol,
                          bars=bars_by_symbol[symbol], provider=option_provider,
                          raw_close=raw_close_by_symbol[symbol])
                           for symbol, group in batch.groupby("symbol", sort=False)])
    batch = join_surface_asof(batch, surface)
    for s in config.PROPOSAL_STRATEGIES:
        batch[f"strat_{s}"] = (batch["strategy"] == s).astype(float)
    sector = batch["symbol"].map(config.SECTOR_MAP)
    for g in config.SECTOR_GROUPS:
        batch[f"sec_{g}"] = (sector == g).astype(float)
    for col in _CONTEXT_ONLY:
        batch[col] = np.nan
    if context is not None:
        batch = _merge_context(batch, context)

    assert_decision_safe(V4_META_FEATURES)
    if "prem_spot" in batch.columns:
        raise ValueError("v4 candidate batch must not contain prem_spot")
    missing = set(V4_META_FEATURES) - set(batch.columns)
    if missing:
        raise ValueError(f"candidate batch missing v4 features: {sorted(missing)}")
    audit = ["decision_contract", "option_tick_request_id", "option_tick_status"] if config.V6_EXPANDED else []
    return batch[["symbol", "strategy", "dte", "entry_ts"] + audit + V4_META_FEATURES]


def _merge_context(batch: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    """As-of merge of market_iv / rv_iv_spread / beta_60d from the prior close."""
    context = context.sort_values("date")
    out = []
    for sym, grp in batch.sort_values("entry_date").groupby("symbol"):
        c = context[context["underlying"] == sym]
        if c.empty:
            out.append(grp)
            continue
        merged = pd.merge_asof(grp, c.drop(columns=["underlying"]),
                               left_on="entry_date", right_on="date",
                               allow_exact_matches=False, suffixes=("", "_ctx"))
        for col in _CONTEXT_ONLY:
            if f"{col}_ctx" in merged.columns:
                merged[col] = merged[f"{col}_ctx"]
                merged = merged.drop(columns=[f"{col}_ctx"])
        out.append(merged.drop(columns=["date"], errors="ignore"))
    return pd.concat(out, ignore_index=True)


def assert_candidate_parity(offline: pd.DataFrame, live: pd.DataFrame, *,
                            feature_names: list[str] | None = None,
                            atol: float = 1e-10) -> None:
    """Single-row v4 feature parity between an offline row and a live candidate."""
    assert_feature_parity(offline, live, feature_names or V4_META_FEATURES, atol=atol)
