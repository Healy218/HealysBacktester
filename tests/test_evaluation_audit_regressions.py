"""Adversarial accounting/causality cases from the September 5 audit."""
import json

import numpy as np
import pandas as pd
import pytest

from nn_meta.v4_accounting import AccountingDataError, CostScenario, mark_to_market_portfolio
from nn_meta.mark_stream import load_mark_stream, marks_from_legs, execution_frames
from nn_meta.calibration import fit_isotonic
from nn_meta.temporal_validation import expanding_folds, FoldWindow
from nn_meta.vol_features import session_rv
from nn_options_signal.backtest import run_backtest

ZERO = CostScenario(fee=0, slippage=0)


def one_trade():
    return pd.DataFrame({"trade_id": ["a"], "symbol": ["A"],
                         "signal_ts": pd.to_datetime(["2025-01-02 09:30"]),
                         "fill_entry_ts": pd.to_datetime(["2025-01-02 09:45"]),
                         "fill_exit_ts": pd.to_datetime(["2025-01-02 10:00"]),
                         "gross_return": [0.]})


def one_marks(first=0., last=0.):
    return pd.DataFrame({"trade_id": ["a", "a"],
                         "mark_ts": pd.to_datetime(["2025-01-02 09:45", "2025-01-02 10:00"]),
                         "gross_return": [first, last]})


def test_first_nonzero_mark_is_not_discarded():
    m, _ = mark_to_market_portfolio(one_trade(), one_marks(-.9),
                                    max_concurrent=1, position_fraction=1, costs=ZERO)
    assert m["max_drawdown"] == pytest.approx(.9)


def test_terminal_mark_cannot_override_executed_loss():
    with pytest.raises(AccountingDataError, match="terminal mark"):
        mark_to_market_portfolio(one_trade().assign(gross_return=-1), one_marks(last=10),
                                 max_concurrent=1, position_fraction=1)


def test_new_position_cannot_borrow_against_open_paper_gains():
    a = one_trade().assign(fill_exit_ts=pd.Timestamp("2025-01-02 10:30"), gross_return=1.)
    b = a.assign(trade_id="b", symbol="B", signal_ts=pd.Timestamp("2025-01-02 09:45"),
                 fill_entry_ts=pd.Timestamp("2025-01-02 10:00"), gross_return=0.)
    marks = pd.DataFrame({"trade_id": ["a", "a", "a", "b", "b"],
                          "mark_ts": pd.to_datetime(["2025-01-02 09:45", "2025-01-02 10:00",
                                                      "2025-01-02 10:30", "2025-01-02 10:00", "2025-01-02 10:30"]),
                          "gross_return": [0., 1., 1., 0., 0.]})
    result, _ = mark_to_market_portfolio(pd.concat([a,b]), marks,
                                        max_concurrent=2, position_fraction=.5, costs=ZERO)
    assert result["peak_gross_exposure"] <= 1


def test_roll_costs_and_bar_close_event_times():
    legs = []
    for start in ["2025-01-02 09:45", "2025-01-02 10:15"]:
        ts = pd.date_range(start, periods=2, freq="15min")
        legs.append({"entry_open": 1., "exit_close": 1., "bar_ts": ts,
                     "bar_close_ts": ts + pd.Timedelta("15min"), "bar_close": [1., 1.]})
    marks = marks_from_legs(legs).assign(trade_id="a")
    assert marks.iloc[0]["mark_ts"] == pd.Timestamp("2025-01-02 09:45")
    assert marks.iloc[-1]["mark_ts"] == pd.Timestamp("2025-01-02 10:45")
    trade = one_trade().assign(fill_exit_ts=pd.Timestamp("2025-01-02 10:45"), n_fills=2)
    result, _ = mark_to_market_portfolio(trade, marks, max_concurrent=1,
                                        position_fraction=1, costs=CostScenario(fee=.01, slippage=0))
    assert result["total_return"] == pytest.approx((.99/1.01)**2-1)


def test_legacy_persisted_marks_fail_closed(tmp_path):
    path = tmp_path / "old.parquet"
    one_marks().to_parquet(path)
    with pytest.raises(AccountingDataError, match="legacy mark stream"):
        load_mark_stream(path)


def daily_panel():
    return pd.DataFrame([{"date": pd.Timestamp("2025-01-02"), "pred": 1., "entry_open": 10.,
                          "exit_close_h3": 0., "exit_date_h3": pd.Timestamp("2025-01-08"),
                          "ticker": "a", "type": "call", "strike": 100., "dte": 20}])


def test_daily_initial_loss_is_drawdown_and_recorded_at_exit():
    result = run_backtest(daily_panel(), "pred", 3)
    assert result["max_drawdown"] == pytest.approx(-result["total_return"])
    assert result["equity_curve"].iloc[0]["date"] == pd.Timestamp("2025-01-08")


def test_daily_missing_future_exit_never_substitutes_lower_ranked_winner():
    good = daily_panel().assign(exit_close_h3=20.)
    missing = daily_panel().assign(ticker="missing", pred=2., exit_close_h3=np.nan, exit_date_h3=pd.NaT)
    with pytest.raises(ValueError, match="lacks a valid exit valuation"):
        run_backtest(pd.concat([missing, good]), "pred", 3)


def test_isotonic_equal_score_order_is_irrelevant():
    a = fit_isotonic([.5,.5,.6], [1,0,0]).predict([.5,.6])
    b = fit_isotonic([.5,.5,.6], [0,1,0]).predict([.5,.6])
    assert np.allclose(a, b)
    assert np.allclose(a, 1/3)


def test_last_fold_includes_remainder_day():
    dates = pd.Series(pd.date_range("2025-01-01", periods=20, freq="B"))
    assert expanding_folds(dates, n_folds=3)[-1].test_end == dates.iloc[-1]


def test_daily_vol_is_available_after_final_minute_closes():
    bars = pd.DataFrame({"Open": [100.,100.], "Close": [100.,101.]},
                        index=pd.to_datetime(["2025-01-02 20:58", "2025-01-02 20:59"]))
    assert session_rv(bars).iloc[0]["available_at"] == pd.Timestamp("2025-01-02 21:00")


def test_conditional_evaluation_refuses_baseline_optimization_overlap():
    from nn_meta.v4_evaluate import evaluate_window
    window = FoldWindow(*map(pd.Timestamp, ["2024-01-01", "2025-01-01", "2025-03-01", "2025-04-01"]))
    with pytest.raises(ValueError, match="overlaps frozen baseline"):
        evaluate_window(pd.DataFrame(), window, spec={"train_window": ["2024-01-01", "2025-02-01"]},
                         schema="v4", purged=True, label="label", models=[], seeds=[], epochs=1,
                         gbt_estimators=1, embargo="1D")


def test_sparse_horizon_labels_crossing_partition_are_unavailable():
    from nn_options_signal.build_dataset import purge_label_boundaries
    frame = pd.DataFrame({"split": ["val", "val"], "entry_open": [1.,1.]})
    for h in [3,5]:
        frame[f"label_h{h}"] = [2.,2.]
        frame[f"exit_close_h{h}"] = [3.,3.]
        frame[f"exit_date_h{h}"] = pd.to_datetime(["2026-04-10", "2026-03-30"])
    out = purge_label_boundaries(frame)
    assert len(out) == 2 and out["entry_open"].notna().all()
    assert pd.isna(out.loc[0,"label_h5"]) and pd.isna(out.loc[0,"exit_close_h5"])
    assert out.loc[1,"label_h5"] == 2


def test_walkforward_experiment_identity_covers_parameters_and_input_bytes(tmp_path, monkeypatch):
    import nn_meta.walkforward_meta as wf
    p = tmp_path / "input.parquet"; p.write_bytes(b"input1")
    for name in ["UNDERLYING_15M_PARQUET", "SURFACE_DATASET_PARQUET", "BASELINE_SPEC_JSON"]:
        monkeypatch.setattr(wf.config, name, p)
    first = wf.experiment_key({"threshold": .5}, 3, False)
    assert first != wf.experiment_key({"threshold": .6}, 3, False)
    assert first != wf.experiment_key({"threshold": .5}, 4, False)
    p.write_bytes(b"input2")
    assert first != wf.experiment_key({"threshold": .5}, 3, False)
    rows = pd.DataFrame({"symbol": ["A", "B"], "x": [1,2]})
    assert wf.frame_digest(rows) != wf.frame_digest(rows.iloc[::-1].reset_index(drop=True))


def test_mark_manifest_identifies_intermediate_path(tmp_path):
    from nn_meta.v4_artifacts import create_manifest, write_manifest, validate_manifest, ArtifactValidationError
    dataset = tmp_path / "ds.parquet"; pd.DataFrame({"symbol": ["A"]}).to_parquet(dataset)
    spec = tmp_path / "spec.json"; spec.write_text('{}')
    marks = tmp_path / "marks.parquet"; one_marks().to_parquet(marks)
    manifest = create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                               feature_names=["rsi14"], provider_metadata={}, mark_stream_path=marks,
                               evaluation_config={"gate_bar": "risk"})
    path = write_manifest(manifest, tmp_path / "manifest.json")
    validate_manifest(path, dataset_path=dataset, baseline_spec_path=spec,
                       feature_names=["rsi14"], mark_stream_path=marks)
    one_marks(first=-.9).to_parquet(marks)
    with pytest.raises(ArtifactValidationError, match="mark stream hash"):
        validate_manifest(path, dataset_path=dataset, baseline_spec_path=spec,
                           feature_names=["rsi14"], mark_stream_path=marks)


def test_verify_requires_all_files_the_loader_will_read(tmp_path):
    from nn_meta.v4_artifacts import create_manifest, write_manifest, ArtifactValidationError
    from nn_meta.v4_loader import verify_bundle
    from nn_meta.feature_contract import CONTRACT_VERSION
    dataset = tmp_path / "ds.parquet"; pd.DataFrame({"symbol": ["A"]}).to_parquet(dataset)
    spec = tmp_path / "spec.json"; spec.write_text('{}')
    bundle = tmp_path / "bundle"; (bundle / "seed").mkdir(parents=True)
    cfg = bundle / "ensemble_config.json"
    cfg.write_text(json.dumps({"feature_contract_version": CONTRACT_VERSION, "family": "gbt",
                               "features": ["rsi14"], "run_ids": ["seed"], "mode": "rank"}))
    (bundle / "seed/model.joblib").write_bytes(b"weights")
    manifest = create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                               feature_names=["rsi14"], provider_metadata={}, output_artifacts=[cfg])
    write_manifest(manifest, bundle / "manifest.json")
    with pytest.raises(ArtifactValidationError, match="omits load-critical"):
        verify_bundle(bundle)


def test_atomic_exchange_survives_interruption_before_cleanup(tmp_path, monkeypatch):
    import nn_meta.v4_finalize as fz
    final = tmp_path / "final"; final.mkdir(); (final / "old").write_text("old")
    staging = tmp_path / "staging"; staging.mkdir(); (staging / "new").write_text("new")
    def interrupted(*a, **kw):
        raise RuntimeError("simulated interruption after exchange")
    monkeypatch.setattr(fz.shutil, "rmtree", interrupted)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        fz._atomic_swap(staging, final)
    assert (final / "new").is_file()
    assert (staging / "old").is_file()


def test_selected_marks_are_filtered_before_validation(monkeypatch):
    import nn_meta.mark_stream as ms
    rows = pd.DataFrame({"symbol": ["A"], "strategy": ["x"], "trade_idx": [1], "dte": [5],
                         "entry_ts": [pd.Timestamp("2025-01-02 09:30")],
                         "fill_entry_ts": [pd.Timestamp("2025-01-02 09:45")],
                         "fill_exit_ts": [pd.Timestamp("2025-01-02 10:00")], "gross_return": [0.]})
    selected = one_marks().assign(trade_id=ms.stable_trade_id(rows).iloc[0])
    universe = pd.concat([selected, one_marks().assign(trade_id="unselected")])
    original = ms.validate_mark_stream; seen = []
    def capture(frame):
        seen.append(len(frame)); return original(frame)
    monkeypatch.setattr(ms, "validate_mark_stream", capture)
    execution_frames(rows, universe)
    assert seen == [2]


def test_later_volatility_cannot_reclassify_first_fold_regimes(monkeypatch):
    from nn_meta.vol_features import evaluate_symbol
    import nn_meta.vol_forecast as vf
    class FixedGarch:
        def forecast_at(self, returns, t):
            return .001
    monkeypatch.setattr(vf.GARCH11, "fit", lambda returns: FixedGarch())
    rng = np.random.default_rng(22)
    frame = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=300, freq="B"),
                          "low_coverage": False, "rv_1m": rng.uniform(.0001, .001, 300),
                          "ret_cc": rng.normal(0,.01,300)})
    first = evaluate_symbol(frame)[0]
    changed = frame.copy(); changed.loc[220:, "rv_1m"] *= 1000
    assert evaluate_symbol(changed)[0] == first


def test_legacy_fold_purges_training_and_validation_exit_overlap(monkeypatch):
    import nn_meta.walkforward_meta as wf
    monkeypatch.setattr(wf.config, "WINDOW_START", "2025-01-01")
    rows = pd.DataFrame({"entry_ts": pd.to_datetime(["2025-01-02", "2025-01-10", "2025-01-18", "2025-01-20", "2025-01-22"]),
                         "exit_ts": pd.to_datetime(["2025-01-21", "2025-01-11", "2025-01-19", "2025-01-23", "2025-01-23"])})
    splits = wf.fold_splits(rows, "2025-01-20", "2025-01-21", "2025-01-31")
    assert splits.iloc[0] == "purged" and splits.iloc[3] == "purged"
    assert splits.iloc[1] == "train" and splits.iloc[-1] == "test"


def test_option_cache_change_invalidates_walkforward_checkpoint(tmp_path, monkeypatch):
    import nn_meta.walkforward_meta as wf
    monkeypatch.setattr(wf.config, "DATA_CACHE", tmp_path)
    for name in ["UNDERLYING_15M_PARQUET", "SURFACE_DATASET_PARQUET", "BASELINE_SPEC_JSON"]:
        monkeypatch.setattr(wf.config, name, tmp_path / (name + ".parquet"))
    raw = tmp_path / "flatfiles_15m" / "2025-01-02.parquet"; raw.parent.mkdir()
    raw.write_bytes(b"same-sized quote v1")
    key = wf.experiment_key({}, 3, False)
    raw.write_bytes(b"same-sized quote v2")
    assert wf.experiment_key({}, 3, False) != key


def test_roll_turnover_uses_grown_reinvestment_not_initial_allocation():
    legs = []
    for start, entry, exit_price in [("2025-01-02 09:45",1.,2.), ("2025-01-02 10:15",2.,3.)]:
        ts = pd.date_range(start, periods=2, freq="15min")
        legs.append({"entry_open": entry, "exit_close": exit_price, "bar_ts": ts,
                     "bar_close_ts": ts + pd.Timedelta("15min"), "bar_close": [entry,exit_price]})
    marks = marks_from_legs(legs).assign(trade_id="a")
    trade = one_trade().assign(fill_exit_ts=pd.Timestamp("2025-01-02 10:45"), n_fills=2, gross_return=2.)
    result, _ = mark_to_market_portfolio(trade, marks, max_concurrent=1, position_fraction=1, costs=ZERO)
    assert result["total_return"] == 2
    assert result["turnover"] == 8  # buy1, sell2, buy2, sell3


def test_current_dataset_must_match_exact_baseline_spec():
    from nn_meta.feature_contract import CONTRACT_VERSION, baseline_spec_fingerprint, require_current_dataset
    rows = pd.DataFrame({"x": [1]})
    spec = {"train_window": ["2024-01-01", "2024-12-31"], "symbols": {}}
    rows.attrs.update(feature_contract_version=CONTRACT_VERSION,
                       baseline_spec_sha256=baseline_spec_fingerprint(spec))
    require_current_dataset(rows, spec)
    with pytest.raises(ValueError, match="baseline fingerprint"):
        require_current_dataset(rows, {**spec, "symbols": {"A": {}}})


@pytest.mark.parametrize("pool, flags, membership", [("v5", ["--no-membership"], False), ("v5", [], True), ("v6", [], True)])
def test_prewarm_and_walkforward_share_lightweight_namespace(tmp_path, monkeypatch, pool, flags, membership):
    import importlib.util
    import sys
    from nn_meta.feature_contract import CONTRACT_VERSION
    from nn_meta.wf_context import experiment_key
    from nn_meta import config
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("audit_wf_prewarm", Path(__file__).parents[1] / "scripts/wf_prewarm.py")
    prewarm = importlib.util.module_from_spec(spec); spec.loader.exec_module(prewarm)
    monkeypatch.setattr(config, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(config, "DATA_CACHE", tmp_path / "cache")
    monkeypatch.setattr(config, "POOL", pool)
    winning = {"feature_contract_version": CONTRACT_VERSION, "threshold": .6}
    winner = tmp_path / "winner.json"; winner.write_text(json.dumps(winning))
    monkeypatch.setattr(sys, "argv", ["wf_prewarm", "merge-rows", "--fold", "1", "--folds", "4", "--winner", str(winner)] + flags)
    monkeypatch.setattr(prewarm, "cmd_merge_rows", lambda args: None)
    prewarm.main()
    assert prewarm.WF_DIR == config.ARTIFACTS / "wf" / experiment_key(winning, 4, membership)
