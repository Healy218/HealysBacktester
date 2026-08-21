"""Nested, purged V4 evaluation and v31 ablation runner.

This is intentionally parallel to the legacy training/select/walk-forward
commands.  It can evaluate a completed v31 ``meta_dataset.parquet`` without
changing the running v31 pipeline, while enforcing the v4 feature contract and
using one portfolio simulator for NN and LightGBM.

Examples:

    NN_META_POOL=v31 python -m nn_meta.v4_evaluate --ablation
    NN_META_POOL=v31 python -m nn_meta.v4_evaluate --folds 3 --seeds 0,1,2,3,4
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from nn_meta import config
from nn_meta.baseline import load_spec
from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.calibration import calibration_summary
from nn_meta.diagnostics import decile_diagnostic
from nn_meta.ev_sizing import (ev_candidate_rows, ev_selected_rows, evaluate_ev,
                               magnitude_target)
from nn_meta.feature_contract import assert_decision_safe
from nn_meta.mark_stream import execution_frames, load_mark_stream, option_b_blockers
from nn_meta.model import build_magnitude_mlp, build_meta_mlp
from nn_meta.multiple_testing import deflated_sharpe_from_trials
from nn_meta.select_meta import (_EVALUATORS, _portfolio_sim, all_rows,
                                 frozen_mask, portfolio_metrics)
from nn_meta.temporal_validation import (FoldWindow, assign_purged_splits,
                                         expanding_folds, split_summary)
from nn_meta.v4_accounting import (BASE_COSTS, CostScenario,
                                   mark_to_market_portfolio)
from nn_meta.v4_artifacts import (create_manifest, write_manifest,
                                  write_metadata_bundle)


@dataclass
class Predictor:
    family: str
    predict: Callable[[pd.DataFrame], np.ndarray]
    # Magnitude head (v4 EV sizing, 2026-08-21): predicted expected net return
    # per row. ``None`` when no head was trained -> the ``ev`` mode is skipped.
    predict_ev: Callable[[pd.DataFrame], np.ndarray] | None = None


def winsor_bounds(values, quantiles=config.EV_WINSOR_QUANTILES) -> tuple[float, float]:
    """Train-tail clip bounds for the magnitude target (computed on TRAIN only)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    lo, hi = np.quantile(v, quantiles[0]), np.quantile(v, quantiles[1])
    return float(lo), float(hi)


def _magnitude_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Rows with a realized signed return — the magnitude head's training set.
    (Unexecuted proposals carry no ``net_return`` and cannot teach size.)"""
    return rows[rows["net_return"].notna()].copy()


def schema_features(schema: str) -> list[str]:
    """Return the requested persisted schema and verify its timing contract."""
    if schema == "v4":
        assert_decision_safe(V4_META_FEATURES)
        return V4_META_FEATURES
    if schema == "legacy":
        return META_FEATURES
    if schema == "spx0":
        from nn_meta.spx0.build_dataset import SPX0_META_FEATURES
        assert_decision_safe(SPX0_META_FEATURES)
        return SPX0_META_FEATURES
    raise ValueError("schema must be 'legacy', 'v4' or 'spx0'")


def legacy_splits(rows: pd.DataFrame, window: FoldWindow) -> pd.Series:
    """Historical entry-only assignment, retained only for ablation controls."""
    entry = pd.to_datetime(rows["entry_ts"]).dt.normalize()
    split = pd.Series("purged", index=rows.index, dtype="object")
    split.loc[(entry >= window.train_start) & (entry < window.val_start)] = "train"
    split.loc[(entry >= window.val_start) & (entry < window.test_start)] = "val"
    split.loc[(entry >= window.test_start) & (entry <= window.test_end)] = "test"
    return split


def _matrix(rows: pd.DataFrame, features: list[str], mean: pd.Series,
            std: pd.Series) -> np.ndarray:
    values = rows[features].copy().fillna(mean)
    return ((values - mean) / std).values.astype("float32")


def _labeled(rows: pd.DataFrame, label: str) -> pd.DataFrame:
    return rows[rows[label].notna()].copy()


def fit_nn(train: pd.DataFrame, val: pd.DataFrame, *, features: list[str],
           label: str, seed: int, epochs: int) -> Predictor:
    """Fit one fold-local MLP; no artifacts are written during an ablation."""
    import tensorflow as tf

    train, val = _labeled(train, label), _labeled(val, label)
    if train.empty or val.empty:
        raise ValueError("NN requires non-empty labeled train and validation rows")
    mean = train[features].mean()
    std = train[features].std().replace(0, 1.0)
    x_train, x_val = _matrix(train, features, mean, std), _matrix(val, features, mean, std)
    y_train, y_val = train[label].astype("float32").values, val[label].astype("float32").values
    tf.keras.utils.set_random_seed(seed)
    model = build_meta_mlp(len(features), config.ARCHITECTURES[0], config.LEARNING_RATES[0])
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=max(3, min(12, epochs // 4)),
        restore_best_weights=True,
    )
    model.fit(x_train, y_train, validation_data=(x_val, y_val),
              epochs=epochs, batch_size=config.BATCH_SIZE, callbacks=[early], verbose=0)

    def predict(rows: pd.DataFrame) -> np.ndarray:
        return model.predict(_matrix(rows, features, mean, std), batch_size=4096,
                             verbose=0).flatten()

    mag = fit_nn_magnitude(train, val, features=features, mean=mean, std=std,
                           seed=seed, epochs=epochs)
    return Predictor("nn", predict, mag.predict)


def fit_nn_magnitude(train: pd.DataFrame, val: pd.DataFrame, *, features: list[str],
                     mean: pd.Series, std: pd.Series, seed: int, epochs: int
                     ) -> Predictor:
    """Magnitude head: regress the signed realized return (winsorized on the
    train tail) with the classifier's scaler, so the two heads see identical
    inputs. Returns a Predictor whose ``predict`` is the expected return."""
    import tensorflow as tf

    train_m, val_m = _magnitude_rows(train), _magnitude_rows(val)
    if train_m.empty or val_m.empty:
        raise ValueError("magnitude head requires executed train and validation rows")
    lo, hi = winsor_bounds(magnitude_target(train_m["net_return"]))
    y_train = np.clip(magnitude_target(train_m["net_return"]), lo, hi).astype("float32")
    y_val = np.clip(magnitude_target(val_m["net_return"]), lo, hi).astype("float32")
    x_train, x_val = _matrix(train_m, features, mean, std), _matrix(val_m, features, mean, std)
    tf.keras.utils.set_random_seed(seed + 10_000)
    model = build_magnitude_mlp(len(features), config.ARCHITECTURES[0], config.LEARNING_RATES[0])
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=max(3, min(12, epochs // 4)),
        restore_best_weights=True,
    )
    model.fit(x_train, y_train, validation_data=(x_val, y_val),
              epochs=epochs, batch_size=config.BATCH_SIZE, callbacks=[early], verbose=0)

    def predict(rows: pd.DataFrame) -> np.ndarray:
        return model.predict(_matrix(rows, features, mean, std), batch_size=4096,
                             verbose=0).flatten()

    pred = Predictor("nn", predict)
    pred.model = model            # persisted by v4_finalize
    pred.bounds = (lo, hi)
    return pred


def fit_gbt(train: pd.DataFrame, val: pd.DataFrame, *, features: list[str],
            label: str, n_estimators: int) -> Predictor:
    """Fit the tree baseline with the same fold-local labels and features."""
    try:
        from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    except ImportError as exc:
        raise RuntimeError("LightGBM is required for --models gbt; install requirements.txt") from exc

    train, val = _labeled(train, label), _labeled(val, label)
    if train.empty or val.empty:
        raise ValueError("GBT requires non-empty labeled train and validation rows")
    model = LGBMClassifier(
        n_estimators=n_estimators, learning_rate=0.02, num_leaves=31,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=200,
        reg_lambda=1.0, random_state=0, n_jobs=-1, verbosity=-1,
    )
    model.fit(train[features], train[label].astype(int),
              eval_set=[(val[features], val[label].astype(int))], eval_metric="auc",
              callbacks=[early_stopping(max(10, n_estimators // 10)), log_evaluation(0)])
    mag = fit_gbt_magnitude(train, val, features=features, n_estimators=n_estimators)
    return Predictor("gbt", lambda rows: model.predict_proba(rows[features])[:, 1],
                     mag.predict)


def fit_gbt_magnitude(train: pd.DataFrame, val: pd.DataFrame, *, features: list[str],
                      n_estimators: int, seed: int = 0) -> Predictor:
    """LightGBM magnitude head (Huber objective on the winsorized signed return)."""
    from lightgbm import LGBMRegressor, early_stopping, log_evaluation

    train_m, val_m = _magnitude_rows(train), _magnitude_rows(val)
    if train_m.empty or val_m.empty:
        raise ValueError("magnitude head requires executed train and validation rows")
    lo, hi = winsor_bounds(magnitude_target(train_m["net_return"]))
    y_train = np.clip(magnitude_target(train_m["net_return"]), lo, hi)
    y_val = np.clip(magnitude_target(val_m["net_return"]), lo, hi)
    model = LGBMRegressor(
        objective="huber", alpha=0.5,
        n_estimators=n_estimators, learning_rate=0.02, num_leaves=31,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=200,
        reg_lambda=1.0, random_state=seed, n_jobs=-1, verbosity=-1,
    )
    model.fit(train_m[features], y_train, eval_set=[(val_m[features], y_val)],
              eval_metric="l1",
              callbacks=[early_stopping(max(10, n_estimators // 10)), log_evaluation(0)])
    pred = Predictor("gbt", lambda rows: model.predict(rows[features]))
    pred.model = model
    pred.bounds = (lo, hi)
    return pred


def fit_family(family: str, train: pd.DataFrame, val: pd.DataFrame, *,
               features: list[str], label: str, seeds: Iterable[int],
               epochs: int, gbt_estimators: int) -> Predictor:
    """Return a fold-local predictor; NN seeds are averaged before policy selection."""
    if family == "gbt":
        return fit_gbt(train, val, features=features, label=label,
                       n_estimators=gbt_estimators)
    if family != "nn":
        raise ValueError(f"unknown model family '{family}'")
    models = [fit_nn(train, val, features=features, label=label, seed=seed,
                     epochs=epochs) for seed in seeds]
    if not models:
        raise ValueError("NN requires at least one seed")
    ev = None
    if all(m.predict_ev is not None for m in models):
        ev = lambda rows: np.mean([m.predict_ev(rows) for m in models], axis=0)
    return Predictor("nn", lambda rows: np.mean([m.predict(rows) for m in models], axis=0),
                     ev)


def policy_predictions(predictor: Predictor, rows: pd.DataFrame, mode: str) -> np.ndarray:
    """The score a policy of ``mode`` decides on: P(win) for filter/rank, the
    magnitude head's expected return for ``ev``."""
    if mode == config.EV_MODE:
        if predictor.predict_ev is None:
            raise ValueError("ev policy selected but the predictor has no magnitude head")
        return predictor.predict_ev(rows)
    return predictor.predict(rows)


def evaluate_policy(mode: str, rows: pd.DataFrame, pred: np.ndarray,
                    threshold: float, dd_brake: float | None = None) -> dict:
    """Shared-simulator metrics for any mode (filter / rank / ev). ``dd_brake``
    is the ev mode's drawdown-aware gross scaler (ignored by other modes)."""
    if mode == config.EV_MODE:
        return evaluate_ev(rows, pred, threshold, k=config.MAX_CONCURRENT,
                           f=config.PORTFOLIO_FRACTION, dd_brake=dd_brake,
                           dd_floor=config.EV_DD_FLOOR)
    return _EVALUATORS[mode](rows, pred, threshold)


def format_candidate_grid(policy: dict, baseline_return: float | None = None) -> str:
    """One line per tried candidate: mode/threshold[/brake], kept, val return,
    maxDD, eligible — the refusal diagnostic."""
    lines = [f"  baseline return: {baseline_return}"]
    for c in policy.get("candidate_grid", []):
        ret = c["total_return"]; dd = c["max_drawdown"]
        lines.append(
            f"  {policy_label(c):<24} kept={c['n_kept']:<5} "
            f"ret={'n/a' if ret is None else f'{ret:+.1%}':<9} "
            f"maxDD={'n/a' if dd is None else f'{dd:.1%}':<7} "
            f"{'ELIGIBLE' if c['eligible'] else '-'}")
    return "\n".join(lines)


def policy_label(policy: dict) -> str:
    """``mode/threshold`` plus the EV brake when one is set, for reports/logs."""
    label = f"{policy['mode']}/{policy['threshold']}"
    if policy.get("dd_brake") is not None:
        label += f" brake={policy['dd_brake']}"
    return label


def _policy_rank(policy: dict) -> tuple[bool, float]:
    """Sort key that ranks any gate-passing policy above every gate-failing one,
    breaking ties on validation return. Shared by the within-family threshold/
    mode choice and the cross-family pick so both honor the same gate — a policy
    that cleared no gate is never crowned over one that did just for a higher
    raw return."""
    ret = policy["metrics"]["total_return"]
    return (bool(policy.get("eligible")), ret if ret is not None else -np.inf)


def _select_winner(selected: list[dict]) -> dict:
    """Cross-family winner among per-family policies (each already the best
    threshold/mode for its family). Eligibility dominates return, so a fold
    where nothing cleared the gate yields an ineligible winner rather than a
    silently-promoted least-bad family."""
    return max(selected, key=_policy_rank)


def _passes_gate(metrics: dict, baseline: dict, dd_cap: float | None = None) -> bool:
    """The eligibility gate, identical for every mode: kept >= MIN_KEPT_TRADES,
    beat the frozen baseline, maxDD <= ``dd_cap`` (default the shared
    MAX_DRAWDOWN_CAP; the spx0 pool passes its tighter 0.25)."""
    cap = config.MAX_DRAWDOWN_CAP if dd_cap is None else float(dd_cap)
    return bool(
        metrics["n_kept"] >= config.MIN_KEPT_TRADES
        and metrics["total_return"] is not None
        and (baseline["total_return"] is None
             or metrics["total_return"] > baseline["total_return"])
        and (metrics["max_drawdown"] or 0) <= cap
    )


def choose_policy(rows: pd.DataFrame, predictions: np.ndarray, spec: dict,
                  thresholds: Iterable[float] = config.KEEP_THRESHOLDS,
                  mark_stream: pd.DataFrame | None = None,
                  costs: CostScenario = BASE_COSTS,
                  ev_predictions: np.ndarray | None = None,
                  ev_thresholds: Iterable[float] = config.EV_THRESHOLDS,
                  dd_cap: float | None = None,
                  ev_dd_brakes: Iterable[float | None] = config.EV_DD_BRAKES) -> dict:
    """Choose mode and threshold on validation only.

    With ``mark_stream`` supplied (Option B), every candidate policy — and the
    frozen baseline it must beat — is scored through the mark-to-market ledger
    instead of the legacy shared simulator, so SELECTION itself sees the
    interim mark path. Without a stream the legacy behavior is bit-identical.

    With ``ev_predictions`` (the magnitude head's expected return per row) the
    ``ev`` mode joins the grid: rank-and-size by EV at each ``ev_thresholds``
    cut, through the same gate and (if supplied) the same ledger. Without it
    the grid is exactly filter × rank as before. Each EV threshold is tried at
    every ``ev_dd_brakes`` gross scaler (``None`` = unbraked), so the brake is
    fold-selectable on validation exactly like the threshold.
    """
    if len(rows) != len(predictions):
        raise ValueError("row/prediction length mismatch")
    if ev_predictions is not None and len(rows) != len(ev_predictions):
        raise ValueError("row/ev prediction length mismatch")
    fmask = frozen_mask(rows, spec)
    ledger = mark_stream is not None
    if ledger:
        base_rows = rows[fmask].reset_index(drop=True)
        baseline = _ledger_policy_metrics(
            base_rows, np.zeros(len(base_rows)), "filter", 0.0, mark_stream,
            costs=costs)
    else:
        baseline = portfolio_metrics(rows[fmask])
    candidates = []
    for mode in config.EVAL_MODES:
        eval_rows = rows[fmask].reset_index(drop=True) if mode == "filter" else rows.reset_index(drop=True)
        eval_pred = predictions[fmask] if mode == "filter" else predictions
        for threshold in thresholds:
            metrics = (_ledger_policy_metrics(eval_rows, eval_pred, mode,
                                              float(threshold), mark_stream,
                                              costs=costs) if ledger
                       else _EVALUATORS[mode](eval_rows, eval_pred, float(threshold)))
            candidates.append({
                "mode": mode,
                "threshold": float(threshold),
                "metrics": metrics,
                "baseline_return": baseline["total_return"],
                "eligible": _passes_gate(metrics, baseline, dd_cap),
            })
    if ev_predictions is not None:
        ev_rows = rows.reset_index(drop=True)
        ev_pred = np.asarray(ev_predictions, dtype=float)
        for threshold in ev_thresholds:
            for brake in ev_dd_brakes:
                brake = None if brake is None else float(brake)
                metrics = (_ledger_policy_metrics(ev_rows, ev_pred, config.EV_MODE,
                                                  float(threshold), mark_stream,
                                                  costs=costs, dd_brake=brake)
                           if ledger else
                           evaluate_policy(config.EV_MODE, ev_rows, ev_pred,
                                           float(threshold), dd_brake=brake))
                candidates.append({
                    "mode": config.EV_MODE, "threshold": float(threshold),
                    "dd_brake": brake,
                    "metrics": metrics, "baseline_return": baseline["total_return"],
                    "eligible": _passes_gate(metrics, baseline, dd_cap),
                })
    # An eligible policy always outranks an ineligible one; ties break on
    # validation return. When nothing clears the gate the least-bad candidate
    # is still returned (callers need something to report), but it carries
    # eligible=False so consumers can refuse to promote it.
    winner = max(candidates, key=_policy_rank)
    # Every candidate is a "trial"; its Sharpe feeds the deflation later.
    winner["candidate_sharpes"] = [c["metrics"]["per_trade_sharpe"] for c in candidates]
    # The whole grid, compactly, so a refusal can be read (which candidates
    # failed which gate term) instead of only the least-bad winner.
    winner["candidate_grid"] = [{
        "mode": c["mode"], "threshold": c["threshold"], "dd_brake": c.get("dd_brake"),
        "n_kept": c["metrics"]["n_kept"], "total_return": c["metrics"]["total_return"],
        "max_drawdown": c["metrics"]["max_drawdown"], "eligible": c["eligible"],
    } for c in candidates]
    winner["selection_basis"] = "ledger" if ledger else "shared_sim"
    return winner


def _candidate_rows(rows: pd.DataFrame, pred: np.ndarray, mode: str,
                    threshold: float) -> pd.DataFrame:
    """Thresholded (and, for rank, DTE-deduped) candidate pool for one policy,
    matching the shared filter/rank evaluators."""
    if mode == config.EV_MODE:
        return ev_candidate_rows(rows, pred, threshold)
    cands = rows.assign(pred=pred)
    cands = cands[cands["pred"] >= threshold]
    if mode == "rank":
        cands = cands.sort_values("pred", ascending=False) \
            .drop_duplicates(["symbol", "strategy", "trade_idx"])
    return cands


def _selected_rows(cands: pd.DataFrame, mode: str = "rank",
                   dd_brake: float | None = None) -> pd.DataFrame:
    """Rows the slot portfolio actually enters (its own slot decision). For the
    ``ev`` mode the EV-sized portfolio decides and each row carries its
    ``size_fraction`` for the ledger (already brake-scaled when ``dd_brake``)."""
    if mode == config.EV_MODE:
        return ev_selected_rows(cands, config.MAX_CONCURRENT, config.PORTFOLIO_FRACTION,
                                dd_brake=dd_brake, dd_floor=config.EV_DD_FLOOR)
    cands = cands.dropna(subset=["entry_ts", "exit_ts", "net_return"])
    if cands.empty:
        return cands
    _, _, entered = _portfolio_sim(cands, config.MAX_CONCURRENT,
                                   config.PORTFOLIO_FRACTION)
    return cands.loc[[e[0] for e in entered]]


def marked_metrics(rows: pd.DataFrame, pred: np.ndarray, mode: str,
                   threshold: float, mark_stream: pd.DataFrame, *,
                   costs: CostScenario = BASE_COSTS,
                   dd_brake: float | None = None) -> dict | None:
    """Mark-to-market metrics for the trades this policy enters.

    The shared slot portfolio makes the entry/exit decisions (skip semantics);
    only those entered trades and their observed marks are then routed through
    the fail-closed ledger, which re-derives drawdown and exposure from the
    per-contract mark path rather than the final ``net_return``.  Returns
    ``None`` when the portfolio enters nothing.
    """
    selected = _selected_rows(_candidate_rows(rows, pred, mode, threshold), mode,
                              dd_brake=dd_brake)
    if selected.empty:
        return None
    trades, marks = execution_frames(selected, mark_stream)
    metrics, _ = mark_to_market_portfolio(
        trades, marks, max_concurrent=config.MAX_CONCURRENT,
        position_fraction=config.PORTFOLIO_FRACTION, costs=costs)
    return metrics


def _ledger_policy_metrics(rows: pd.DataFrame, pred: np.ndarray, mode: str,
                           threshold: float, mark_stream: pd.DataFrame, *,
                           costs: CostScenario = BASE_COSTS,
                           dd_brake: float | None = None) -> dict:
    """Policy metrics in the SHARED metric schema, computed through the
    mark-to-market ledger (Option B selection basis).

    The slot portfolio still makes entry decisions (identical skip semantics
    to the legacy path), but return, drawdown and exposure come from the
    per-contract mark path — so a policy whose interim marks crater can no
    longer look placid just because its FINAL returns were fine. Keys mirror
    ``select_meta.portfolio_metrics`` so the eligibility gate, ``_policy_rank``
    and the deflation pipeline work unchanged; ledger-only extras
    (turnover/exposure/cost_scenario) ride along.
    """
    empty = {"n": 0, "n_kept": 0, "n_proposals": len(rows), "total_return": None,
             "max_drawdown": None, "win_rate": None, "mean_return": None,
             "per_trade_sharpe": None, "total_ex_top3": None,
             "cost_scenario": costs.name, "basis": "ledger"}
    selected = _selected_rows(_candidate_rows(rows, pred, mode, threshold), mode,
                              dd_brake=dd_brake)
    if selected.empty:
        return empty
    trades, marks = execution_frames(selected, mark_stream)
    m, _ = mark_to_market_portfolio(
        trades, marks, max_concurrent=config.MAX_CONCURRENT,
        position_fraction=config.PORTFOLIO_FRACTION, costs=costs)
    rets = selected["net_return"].to_numpy(dtype=float)
    # ex-top3 through the SAME ledger: drop the three best trades and re-mark —
    # the house outlier-dependence check, now on the stricter accounting.
    if len(selected) > 3:
        keep = selected.drop(index=selected["net_return"].nlargest(3).index)
        if keep.empty:
            ex_total = 0.0
        else:
            t2, m2 = execution_frames(keep, mark_stream)
            ex_metrics, _ = mark_to_market_portfolio(
                t2, m2, max_concurrent=config.MAX_CONCURRENT,
                position_fraction=config.PORTFOLIO_FRACTION, costs=costs)
            ex_total = ex_metrics["total_return"]
    else:
        ex_total = 0.0
    out = dict(empty)
    out.update({
        "n": len(selected), "n_kept": len(selected),
        "total_return": m["total_return"], "max_drawdown": m["max_drawdown"],
        "win_rate": float((rets > 0).mean()), "mean_return": float(rets.mean()),
        "per_trade_sharpe": float(rets.mean() / rets.std(ddof=1))
        if len(rets) > 1 and rets.std(ddof=1) > 0 else None,
        "total_ex_top3": ex_total,
        "turnover": m["turnover"],
        "peak_gross_exposure": m["peak_gross_exposure"],
        "mean_gross_exposure": m["mean_gross_exposure"],
    })
    return out


def _rows_for_split(ds: pd.DataFrame, split: str) -> pd.DataFrame:
    return all_rows(ds, split).reset_index(drop=True)


def evaluate_window(ds: pd.DataFrame, window: FoldWindow, *, spec: dict,
                    schema: str, purged: bool, label: str,
                    models: Iterable[str], seeds: Iterable[int], epochs: int,
                    gbt_estimators: int, embargo: str,
                    mark_stream: pd.DataFrame | None = None,
                    dd_cap: float | None = None,
                    thresholds: Iterable[float] = config.KEEP_THRESHOLDS) -> dict:
    """Nested temporal evaluation for one fold or global ablation window."""
    ds = ds.copy()
    split = assign_purged_splits(
        ds, train_start=window.train_start, val_start=window.val_start,
        test_start=window.test_start, test_end=window.test_end, embargo=embargo,
    ) if purged else legacy_splits(ds, window)
    ds["split"] = split
    features = schema_features(schema)
    missing = set(features) - set(ds.columns)
    if missing:
        raise ValueError(f"dataset missing model features: {sorted(missing)}")
    train = ds[ds["split"] == "train"]
    val_rows, test_rows = _rows_for_split(ds, "val"), _rows_for_split(ds, "test")
    if train.empty or val_rows.empty or test_rows.empty:
        raise ValueError("purging left an empty train, validation, or test partition")

    fitted: dict[str, Predictor] = {}
    selected: list[dict] = []
    for family in models:
        predictor = fit_family(family, train, ds[ds["split"] == "val"],
                               features=features, label=label, seeds=seeds,
                               epochs=epochs, gbt_estimators=gbt_estimators)
        policy = choose_policy(val_rows, predictor.predict(val_rows), spec,
                               thresholds=thresholds, mark_stream=mark_stream,
                               ev_predictions=(predictor.predict_ev(val_rows)
                                               if predictor.predict_ev else None),
                               dd_cap=dd_cap)
        policy["family"] = family
        fitted[family] = predictor
        selected.append(policy)

    winner = _select_winner(selected)
    family = winner["family"]
    test_pred = fitted[family].predict(test_rows)
    # The score the winning POLICY decides on (EV for the ev mode) — P(win)
    # still drives calibration and the score-decile diagnostic below.
    test_policy_pred = policy_predictions(fitted[family], test_rows, winner["mode"])
    # Calibration is fit on the winner's validation predictions only, then
    # scored on test — the test labels never inform the mapping.
    calibration = calibration_summary(
        val_rows[label], fitted[family].predict(val_rows),
        test_rows[label], test_pred, method="auto")
    fmask = frozen_mask(test_rows, spec)
    test_eval_rows = test_rows[fmask].reset_index(drop=True) if winner["mode"] == "filter" else test_rows
    test_eval_pred = test_policy_pred[fmask] if winner["mode"] == "filter" else test_policy_pred
    brake = winner.get("dd_brake")
    winner_test = evaluate_policy(winner["mode"], test_eval_rows, test_eval_pred,
                                  winner["threshold"], dd_brake=brake)
    winner_marked = (marked_metrics(test_eval_rows, test_eval_pred,
                                    winner["mode"], winner["threshold"], mark_stream,
                                    dd_brake=brake)
                     if mark_stream is not None else None)
    # Deflate the winner's test Sharpe by the whole grid of tried configurations.
    trial_sharpes = [s for p in selected for s in p.get("candidate_sharpes", [])]
    entered_test = _selected_rows(_candidate_rows(
        test_eval_rows, test_eval_pred, winner["mode"], winner["threshold"]),
        winner["mode"], dd_brake=brake)
    deflated = deflated_sharpe_from_trials(
        entered_test["net_return"] if len(entered_test) else [], trial_sharpes)
    # Track the v3.1 top-decile inversion (win rate up, mean return down) on
    # the full test candidate pool for the winning family.
    score_deciles = decile_diagnostic(test_pred, test_rows["net_return"])
    # Same diagnostic on the magnitude head: the EV head earns its place only
    # if ITS top deciles stop inverting (mean return rising with predicted EV).
    ev_deciles = (decile_diagnostic(fitted[family].predict_ev(test_rows),
                                    test_rows["net_return"])
                  if fitted[family].predict_ev is not None else None)

    by_model = {}
    for policy in selected:
        family = policy["family"]
        pred = policy_predictions(fitted[family], test_rows, policy["mode"])
        frows = test_rows[fmask].reset_index(drop=True) if policy["mode"] == "filter" else test_rows
        fpred = pred[fmask] if policy["mode"] == "filter" else pred
        by_model[family] = {
            "mode": policy["mode"], "threshold": policy["threshold"],
            "dd_brake": policy.get("dd_brake"),
            "validation": policy["metrics"],
            "test": evaluate_policy(policy["mode"], frows, fpred, policy["threshold"],
                                    dd_brake=policy.get("dd_brake")),
        }
    return {
        "schema": schema, "purged": purged, "embargo": embargo,
        "dd_cap": config.MAX_DRAWDOWN_CAP if dd_cap is None else float(dd_cap),
        "window": {k: str(v.date()) for k, v in window.__dict__.items()},
        "split_summary": split_summary(ds, split).to_dict(orient="records"),
        "winner": {"family": winner["family"], "mode": winner["mode"],
                   "threshold": winner["threshold"], "dd_brake": winner.get("dd_brake"),
                   "validation": winner["metrics"],
                   "eligible": bool(winner.get("eligible")),
                   "selection_basis": winner.get("selection_basis", "shared_sim"),
                   "baseline_return": winner.get("baseline_return"),
                   "test": winner_test, "marked": winner_marked,
                   "calibration": calibration, "deflated_sharpe": deflated,
                   "score_deciles": score_deciles, "ev_deciles": ev_deciles},
        "models": by_model,
    }


def _json_default(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _window_from_config() -> FoldWindow:
    return FoldWindow(
        train_start=pd.Timestamp(config.TRAIN_START),
        val_start=pd.Timestamp(config.VAL_START),
        test_start=pd.Timestamp(config.TEST_START),
        test_end=pd.Timestamp(config.TEST_END),
    )


def _write_report(results: list[dict], output: Path) -> None:
    lines = ["# V4 causal evaluation", "",
             "Each row uses fold-local model/policy selection and the shared slot portfolio.",
             "The marked column is the mark-to-market ledger result and is `pending` "
             "until a per-contract mark stream is supplied via `--marks`.",
             "",
             "The **gate** column reports whether the winning policy cleared the "
             "eligibility gate on validation (kept ≥ "
             f"{config.MIN_KEPT_TRADES} trades, beat the frozen baseline, maxDD ≤ "
             f"{config.MAX_DRAWDOWN_CAP:.0%}). A ⚠ row's winner is the least-bad "
             "config, not a config that passed — its test numbers are diagnostic "
             "only and must not be promoted.", "",
             "| run | schema | purged | winner | gate | mode / threshold | test return | maxDD | marked return / maxDD |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, result in enumerate(results, 1):
        win, test = result["winner"], result["winner"]["test"]
        ret = test["total_return"]
        dd = test["max_drawdown"]
        gate_cell = "✓" if win.get("eligible") else "⚠ none cleared"
        if win.get("selection_basis") == "ledger":
            gate_cell += " 🄻"          # policy SELECTED through the m2m ledger
        marked = win.get("marked")
        if marked is None:
            marked_cell = "pending"
        else:
            marked_cell = f"{marked['total_return']:+.1%} / {marked['max_drawdown']:.1%}"
        brake_cell = ("" if win.get("dd_brake") is None
                      else f" brake {win['dd_brake']:.2f}")
        lines.append(
            f"| {i} | {result['schema']} | {result['purged']} | {win['family']} | "
            f"{gate_cell} | {win['mode']} / {win['threshold']:.2f}{brake_cell} | "
            f"{'n/a' if ret is None else f'{ret:+.1%}'} | "
            f"{'n/a' if dd is None else f'{dd:.1%}'} | {marked_cell} |"
        )
    cal_rows = [(i, r["winner"]["calibration"]) for i, r in enumerate(results, 1)
                if r["winner"].get("calibration")]
    if cal_rows:
        lines += ["", "## Calibration (winner, test — fit on validation only)", "",
                  "| run | method | Brier raw | Brier calibrated |",
                  "|---|---|---|---|"]
        for i, cal in cal_rows:
            lines.append(f"| {i} | {cal['method']} | {cal['brier_raw']:.4f} | "
                         f"{cal['brier_calibrated']:.4f} |")
    dsr_rows = [(i, r["winner"]["deflated_sharpe"]) for i, r in enumerate(results, 1)
                if r["winner"].get("deflated_sharpe")]
    if dsr_rows:
        lines += ["", "## Deflated Sharpe (winner, test — deflated by the policy grid)", "",
                  "| run | Sharpe | trials | E[max Sharpe] | deflated Sharpe |",
                  "|---|---|---|---|---|"]
        for i, d in dsr_rows:
            lines.append(f"| {i} | {d['sharpe']:.3f} | {d['n_trials']} | "
                         f"{d['expected_max_sharpe']:.3f} | {d['deflated_sharpe']:.3f} |")
    for i, result in enumerate(results, 1):
        for key, title in (("score_deciles", "Score deciles"),
                           ("ev_deciles", "EV-head deciles (predicted expected return)")):
            diag = result["winner"].get(key)
            if not diag:
                continue
            flag = " ⚠ top-decile inversion" if diag["inverted"] else ""
            lines += ["", f"## {title} (run {i}, winner test){flag}", "",
                      "| decile | n | mean score | win rate | mean return |",
                      "|---|---|---|---|---|"]
            for d in diag["deciles"]:
                lines.append(f"| {d['decile']} | {d['n']} | {d['mean_score']:.3f} | "
                             f"{d['win_rate']:.3f} | {d['mean_return']:+.4f} |")
    output.write_text("\n".join(lines) + "\n")
    output.with_suffix(".json").write_text(json.dumps(results, indent=2, default=_json_default))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=config.META_DATASET_PARQUET)
    ap.add_argument("--label", default="label_excess", choices=["label", "label_excess"])
    ap.add_argument("--models", default="nn,gbt", help="comma-separated: nn,gbt")
    ap.add_argument("--seeds", default="0,1,2,3,4", help="NN ensemble seeds")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--gbt-estimators", type=int, default=600)
    ap.add_argument("--embargo", default="1D")
    ap.add_argument("--folds", type=int, default=0, help="expanding nested folds")
    ap.add_argument("--marks", type=Path, default=None,
                    help="per-contract 15m mark stream; enables mark-to-market "
                         "accounting of the winning policy's trades")
    ap.add_argument("--ablation", action="store_true",
                    help="run legacy/v4 schemas with and without exit-time purging")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=None,
                    help="write a verifiable input manifest next to the report")
    ap.add_argument("--metadata-bundle", type=Path, default=None,
                    help="optional portable zip of manifest, baseline spec, and reports")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.folds and args.ablation:
        raise SystemExit("choose either --folds or --ablation")
    if args.smoke:
        args.seeds, args.epochs, args.gbt_estimators = "0", 5, 50

    ds = pd.read_parquet(args.dataset)
    spec = load_spec()
    if args.marks:
        # Fail closed BEFORE training if the dataset can't support the ledger,
        # rather than surfacing a silent `pending` in every row (which reads as
        # "Option B ran" when it did not). See mark_stream.option_b_blockers.
        blockers = option_b_blockers(ds.columns, mark_stream_exists=Path(args.marks).exists())
        if blockers:
            raise SystemExit("cannot run mark-to-market accounting (Option B):\n  - "
                             + "\n  - ".join(blockers))
    mark_stream = load_mark_stream(args.marks) if args.marks else None
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    output = args.output or config.REPORTS_DIR / (
        "v4_ablation_report.md" if args.ablation else "v4_walkforward_report.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    if args.ablation:
        window = _window_from_config()
        for schema, purged in (("legacy", False), ("v4", False),
                               ("legacy", True), ("v4", True)):
            print(f"running schema={schema} purged={purged}", flush=True)
            results.append(evaluate_window(
                ds, window, spec=spec, schema=schema, purged=purged,
                label=args.label, models=models, seeds=seeds, epochs=args.epochs,
                gbt_estimators=args.gbt_estimators, embargo=args.embargo,
                mark_stream=mark_stream,
            ))
    else:
        folds = expanding_folds(ds["entry_ts"], n_folds=args.folds or 3)
        for i, window in enumerate(folds, 1):
            print(f"running nested fold {i}/{len(folds)}", flush=True)
            results.append(evaluate_window(
                ds, window, spec=spec, schema="v4", purged=True,
                label=args.label, models=models, seeds=seeds, epochs=args.epochs,
                gbt_estimators=args.gbt_estimators, embargo=args.embargo,
                mark_stream=mark_stream,
            ))
    _write_report(results, output)
    manifest_path = args.manifest or output.with_suffix(".manifest.json")
    manifest = create_manifest(
        dataset_path=args.dataset, baseline_spec_path=config.BASELINE_SPEC_JSON,
        feature_names=schema_features("v4" if not args.ablation else "legacy"),
        provider_metadata={"pool": config.POOL, "interval": config.INTERVAL,
                           "options_history_constraint": "15m; approximately two years"},
        code_root=config.ROOT.parent,
    )
    write_manifest(manifest, manifest_path)
    if args.metadata_bundle:
        write_metadata_bundle(args.metadata_bundle, manifest_path=manifest_path,
                              baseline_spec_path=config.BASELINE_SPEC_JSON,
                              reports=[output, output.with_suffix(".json")])
    print(f"wrote {output}, {output.with_suffix('.json')}, and {manifest_path}")


if __name__ == "__main__":
    main()
