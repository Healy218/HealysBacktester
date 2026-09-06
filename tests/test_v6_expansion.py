"""Expanded row integration and refusal checks; synthetic data is not admission."""
from datetime import date
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta import v6_expansion as expanded
from nn_meta.feature_contract import assert_decision_safe, feature_spec, FeatureAvailabilityError
from nn_meta.tradingview_features import FEATURE_NAMES
from nn_meta.option_tick_dataset import NUMERIC_FEATURES
from options.data.provider import OptionContract
from tests.test_price_basis import raw_series


class Provider:
    point_in_time_chain = True
    def get_chain(self, symbol, **kwargs):
        return [OptionContract("SPY250103C00100000", "SPY", date(2025, 1, 3), 100., "C")]


@pytest.fixture
def projection(monkeypatch, tmp_path):
    index = pd.DatetimeIndex(["2025-01-02T14:30:00Z"])
    matrix = SimpleNamespace(values=pd.DataFrame(2., index=index, columns=FEATURE_NAMES),
                             available_at=pd.Series(index + pd.Timedelta(minutes=15), index=index))
    inputs = expanded.ExpandedInputs.__new__(expanded.ExpandedInputs)
    inputs.digest = "a" * 64
    inputs.path = tmp_path / "inputs.json"
    inputs.document = {"symbols": {"SPY": {"tick_store": {
        "directory":"store", "task_sha256":"b"*64, "store_sha256":"c"*64}}},
        "tick_feature_policy":{"test":"explicit synthetic"}}
    inputs.matrix = lambda symbol, bars: matrix
    inputs.assert_unchanged = lambda: None
    seen = []
    def join(requests, directory, **kwargs):
        seen.append((requests.copy(), directory, kwargs))
        result = requests.copy()
        for col in NUMERIC_FEATURES:
            result[col] = pd.array([None] * len(result), dtype="Float64")
        result["option_tick_status"] = "covered"
        result.attrs["feature_policy"] = inputs.document["tick_feature_policy"]
        return result
    monkeypatch.setattr(expanded, "join_decisions", join)
    rows = pd.DataFrame([{"symbol":"SPY", "strategy":"ma", "dte":1,
                          "entry_ts":index[0].tz_localize(None), "direction":0, "contract":None}])
    raw = raw_series(index.tz_localize(None), value=100.)
    return inputs, rows, raw, matrix, seen


def test_projection_uses_predecision_selected_contract_and_preserves_missing_ticks(projection):
    inputs, rows, raw, matrix, seen = projection
    result = inputs.append(rows, symbol="SPY", bars=pd.DataFrame(), provider=Provider(), raw_close=raw)
    request = seen[0][0].iloc[0]
    assert request.contract == "SPY250103C00100000"
    assert request.raw_spot == 100. and request.window_end_ns == request.decision_close_ns
    assert request.window_start_ns == rows.entry_ts.iloc[0].value
    assert result.decision_contract.iloc[0] == request.contract
    assert result.contract.iloc[0] is None  # unfilled execution does not erase the decision contract
    assert result[list(NUMERIC_FEATURES)].isna().all().all()
    assert (result[list(FEATURE_NAMES)] == 2.).all().all()
    assert result.attrs["v6_inputs_sha256"] == inputs.digest
    assert seen[0][2]["expected_store_sha256"] == "c" * 64
    assert seen[0][2]["expected_task_sha256"] == "b" * 64
    assert not any(name in rows for name in expanded.EXTRA_FEATURES)


def test_execution_contract_mismatch_refused_before_tick_join(projection):
    inputs, rows, raw, _, seen = projection
    rows["contract"] = "SPY250103C00101000"
    with pytest.raises(ValueError, match="label contract differs"):
        inputs.append(rows, symbol="SPY", bars=pd.DataFrame(), provider=Provider(), raw_close=raw)
    assert not seen


def test_future_or_inexact_bar_features_refused(projection):
    inputs, rows, raw, matrix, _ = projection
    matrix.available_at += pd.Timedelta(nanoseconds=1)
    with pytest.raises(ValueError, match="unavailable"):
        inputs.append(rows, symbol="SPY", bars=pd.DataFrame(), provider=Provider(), raw_close=raw)
    rows["entry_ts"] += pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match="exact raw spot"):
        inputs.append(rows, symbol="SPY", bars=pd.DataFrame(), provider=Provider(), raw_close=raw)


def test_expanded_schema_has_explicit_timing_and_unknown_columns_fail():
    assert len(expanded.EXTRA_FEATURES) == 106
    assert_decision_safe(expanded.EXTRA_FEATURES)
    for name in ("tv_nonexistent", "opt_tick_fill_price"):
        with pytest.raises(FeatureAvailabilityError):
            feature_spec(name)


def test_manifest_needs_external_anchor_and_complete_schema(tmp_path):
    path = tmp_path / "inputs.json"
    path.write_text('{}')
    with pytest.raises(ValueError, match="external SHA256"):
        expanded.ExpandedInputs(path, "0" * 64)
    with pytest.raises(ValueError, match="complete TV13/tick"):
        expanded.ExpandedInputs(path, expanded.sha256(path))
    link = tmp_path / "alias.json"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="symlinks"):
        expanded.sha256(link)


def test_bar_digest_preserves_utc_identity_but_binds_ohlcv():
    bars = pd.DataFrame([[1.,2.,.5,1.5,10.]], columns=["Open","High","Low","Close","Volume"],
                        index=pd.DatetimeIndex(["2025-01-02T14:30:00Z"]))
    naive = bars.copy()
    naive.index = naive.index.tz_localize(None)
    assert expanded.bars_sha256(naive) == expanded.bars_sha256(bars)
    bars.iloc[0, 3] += .01
    assert expanded.bars_sha256(naive) != expanded.bars_sha256(bars)


def test_expanded_config_requires_inputs_and_selects_full_schema(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, NN_META_POOL="v6", NN_META_CAMPAIGN="test-expanded",
               NN_META_V6_EXPANDED="1", NN_META_V6_INPUTS="", NN_META_V6_INPUTS_SHA256="")
    result = subprocess.run([sys.executable, "-c", "from nn_meta import config"],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "sealed feature input" in result.stderr
    env.update(NN_META_V6_INPUTS=str(tmp_path / "inputs.json"), NN_META_V6_INPUTS_SHA256="a"*64)
    code = "from nn_meta import config; from nn_meta.build_meta_dataset import V4_META_FEATURES; from nn_meta.feature_contract import CONTRACT_VERSION; import json; print(json.dumps([config.PROPOSAL_STRATEGIES, V4_META_FEATURES, CONTRACT_VERSION, config.EXEC_CONFIG]))"
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    strategies, features, contract, execution = json.loads(result.stdout.strip().splitlines()[-1])
    assert len(strategies) == 20 and len([s for s in strategies if s.startswith("tv_") and s != "tv_rating"]) == 8
    assert set(expanded.EXTRA_FEATURES) <= set(features) and "prem_spot" not in features
    assert contract == expanded.CONTRACT_VERSION
    assert execution["DECISION_CHAIN_POLICY"] == "previous-date-raw-moneyness-v1"


@pytest.mark.parametrize("enabled", [True, False])
def test_sweep_errors_cannot_silently_remove_expanded_families(monkeypatch, enabled):
    from nn_meta import baseline, config
    index = pd.date_range("2025-01-02", periods=1600, freq="15min")
    bars = pd.DataFrame({"Close": 100.}, index=index)
    signals = pd.DataFrame(False, index=index, columns=["test"])
    monkeypatch.setattr(config, "V6_EXPANDED", enabled)
    monkeypatch.setattr(baseline.proposals, "sweep_signals", lambda *a: (signals, signals, None, None))
    monkeypatch.setattr(baseline, "simulate_and_rank", lambda **kw: {"error": "explicit test failure"})
    if enabled:
        with pytest.raises(ValueError, match="sweep failed"):
            baseline.sweep_train_params("SPY", bars, "ma")
    else:
        assert baseline.sweep_train_params("SPY", bars, "ma") is None


def _synthetic_input_bundle(tmp_path, monkeypatch, *, context_change=None, moneyness=0.):
    """Only the external parity verifier is replaced; binding/context checks run.

    These files are synthetic boundary fixtures, never external Pine evidence.
    The temporary runtime file lets the test mutate a bound source harmlessly.
    """
    from nn_meta import v6_admission
    index = pd.DatetimeIndex(["2025-01-02T14:30:00Z"])
    bars = pd.DataFrame([[100., 101., 99., 100., 1000.]], index=index,
                        columns=["Open", "High", "Low", "Close", "Volume"])
    flags = pd.DataFrame({"htf_change": True, "vwap_reset": True,
                          "available_at": index}, index=index)
    pack_path, evidence, runtime = [tmp_path / name for name in
                                   ("synthetic-pack.json", "synthetic-capture.csv", "synthetic-runtime.py")]
    pack_path.write_text('{"synthetic_boundary_test":true}')
    evidence.write_text('Close\n100.0\n')
    runtime.write_text('constant = 1\n')
    context = {"minimum_tick": .01, "session_policy": "strict", "as_of": "2025-01-02T14:45:00Z",
        "dependency_metadata": {"symbol": "SPY", "calendar_id": "synthetic-test-only",
            "htf_period": "2D", "vwap_anchor": "synthetic", "timeframe_flag_basis": "synthetic",
            "chart_session": "synthetic", "history_origin": index[0].isoformat()}}
    if context_change in ("minimum_tick", "session_policy"):
        context[context_change] = .05 if context_change == "minimum_tick" else "source_literal"
    entry = {"context": context, "bars_sha256": expanded.bars_sha256(bars)}
    if context_change == "vwap_mode":
        flags = flags.drop(columns="vwap_reset")
        vwap_path = tmp_path / "vwap.parquet"
        pd.DataFrame({"vwap": 100., "available_at": index}, index=index).to_parquet(vwap_path)
        entry["vwap_observations"] = {"path": str(vwap_path), "sha256": expanded.sha256(vwap_path)}
    flag_path = tmp_path / "flags.parquet"
    flags.to_parquet(flag_path)
    entry["timeframe_flags"] = {"path": str(flag_path), "sha256": expanded.sha256(flag_path)}
    parity = {"status": "synthetic_boundary_test_only", "model_admission": False,
        "feature_schema": expanded.feature_schema(minimum_tick=.01, session_policy="strict", vwap_mode="reset_flags"),
        "input_files": {str(path): expanded.sha256(path) for path in (pack_path, evidence)},
        "verification_runtime_sha256": {str(runtime): expanded.sha256(runtime)}}
    def verify(path, expected):
        assert path == pack_path and expanded.sha256(path) == expected
        return deepcopy(parity)
    monkeypatch.setattr(v6_admission, "verify_parity_pack", verify)
    document = {"schema": expanded.SCHEMA, "feature_contract_version": expanded.CONTRACT_VERSION,
        "feature_names": list(expanded.EXTRA_FEATURES), "selection_policy": expanded.POLICY_VERSION,
        "symbols": {"SPY": entry}, "moneyness": moneyness,
        "tick_feature_policy": {"allowed_trade_conditions": [209], "condition_references": [
            {"path": str(evidence), "sha256": expanded.sha256(evidence)}]},
        "parity_pack": {"path": str(pack_path), "sha256": expanded.sha256(pack_path)}}
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(document))
    return SimpleNamespace(path=path, digest=expanded.sha256(path), bars=bars,
                           pack=pack_path, evidence=evidence, runtime=runtime)


def test_runtime_context_matches_the_bound_parity_schema(tmp_path, monkeypatch):
    bundle = _synthetic_input_bundle(tmp_path, monkeypatch)
    inputs = expanded.ExpandedInputs(bundle.path, bundle.digest)
    context = inputs.context("SPY", bundle.bars)
    assert context["minimum_tick"] == .01
    assert context["timeframe_flags"].index.equals(bundle.bars.index)


@pytest.mark.parametrize("setting", ["minimum_tick", "session_policy", "vwap_mode"])
def test_different_runtime_context_cannot_reuse_another_parity_schema(tmp_path, monkeypatch, setting):
    bundle = _synthetic_input_bundle(tmp_path, monkeypatch, context_change=setting)
    inputs = expanded.ExpandedInputs(bundle.path, bundle.digest)
    with pytest.raises(ValueError, match="differs from the verified parity pack"):
        inputs.context("SPY", bundle.bars)
    assert "SPY" not in inputs._contexts


@pytest.mark.parametrize("kind", ["evidence", "runtime"])
def test_cached_context_refuses_changed_evidence_or_runtime_when_pack_unchanged(tmp_path, monkeypatch, kind):
    bundle = _synthetic_input_bundle(tmp_path, monkeypatch)
    inputs = expanded.ExpandedInputs(bundle.path, bundle.digest)
    inputs.context("SPY", bundle.bars)
    original_pack = bundle.pack.read_bytes()
    path = getattr(bundle, kind)
    original = path.read_bytes()
    path.write_bytes(original.replace(b"1", b"2", 1))  # same byte count
    assert len(path.read_bytes()) == len(original) and bundle.pack.read_bytes() == original_pack
    with pytest.raises(ValueError, match="evidence or runtime changed"):
        inputs.context("SPY", bundle.bars)  # hit the cached-context path


@pytest.mark.parametrize("execution_moneyness,accepted", [(0., False), (.1, True)])
def test_manifest_and_execution_moneyness_must_match(tmp_path, monkeypatch, execution_moneyness, accepted):
    from nn_meta import config
    bundle = _synthetic_input_bundle(tmp_path, monkeypatch, moneyness=.1)
    monkeypatch.setattr(config, "V6_EXPANDED", True)
    monkeypatch.setattr(config, "V6_INPUTS", str(bundle.path))
    monkeypatch.setattr(config, "V6_INPUTS_SHA256", bundle.digest)
    monkeypatch.setattr(config, "EXEC_CONFIG", dict(config.EXEC_CONFIG, MONEYNESS=execution_moneyness))
    if accepted:
        assert expanded.from_environment.__wrapped__().document["moneyness"] == .1
    else:
        with pytest.raises(ValueError, match="moneyness policies differ"):
            expanded.from_environment.__wrapped__()


def _unselected_projection_store(projection, monkeypatch, tmp_path):
    from nn_meta import option_tick_dataset as dataset
    inputs, rows, raw, matrix, _ = projection
    class EmptyProvider:
        point_in_time_chain = True
        def get_chain(self, *args, **kwargs):
            return []
    provider = EmptyProvider()
    req = expanded.DecisionContractSelector(provider).request("SPY", signal_bar_open=matrix.values.index[0],
            right="C", raw_spot=100., target_dte=1)
    evidence = tmp_path / "synthetic-selection.json"
    evidence.write_text('{"synthetic_empty_prior_date_chain":true}')
    task = dataset.create_task_manifest([req], selection_reference_paths=[evidence],
                                        feature_policy=dataset.feature_policy())
    directory = tmp_path / "unselected-store"
    manifest = dataset.materialize_store(task, [], directory)
    inputs.document["symbols"]["SPY"]["tick_store"] = {"directory": str(directory),
        "task_sha256": task["task_sha256"], "store_sha256": manifest["store_sha256"]}
    inputs.document["tick_feature_policy"] = task["feature_policy"]
    monkeypatch.setattr(expanded, "join_decisions", dataset.join_decisions)
    return inputs, rows, raw, provider


def test_no_chain_remains_explicit_but_missing_selected_ticks_fail(projection, monkeypatch, tmp_path):
    from options.data.massive_ticks import TickDataError
    inputs, rows, raw, provider = _unselected_projection_store(projection, monkeypatch, tmp_path)
    result = inputs.append(rows, symbol="SPY", bars=pd.DataFrame(), provider=provider, raw_close=raw)
    assert result.option_tick_status.tolist() == ["unselected"]
    assert result.decision_contract.isna().all()
    assert result[list(NUMERIC_FEATURES)].isna().all().all()
    assert result.option_tick_request_id.str.fullmatch(r"[0-9a-f]{64}").all()
    # The same symbol/time with a selected OCC is a different required key.
    # It cannot use the explicit no-contract record as missing-tick coverage.
    with pytest.raises(TickDataError, match="required decision window is missing"):
        inputs.append(rows, symbol="SPY", bars=pd.DataFrame(), provider=Provider(), raw_close=raw)


def test_live_candidate_preserves_unselected_contract_audit_columns(projection, monkeypatch, tmp_path):
    from nn_meta import config
    from nn_meta.live import v4_candidates
    inputs, rows, raw, provider = _unselected_projection_store(projection, monkeypatch, tmp_path)
    monkeypatch.setattr(config, "V6_EXPANDED", True)
    # Surface values are independent of this metadata projection boundary.
    monkeypatch.setattr(v4_candidates, "join_surface_asof", lambda batch, surface: batch.copy())
    monkeypatch.setattr(v4_candidates, "V4_META_FEATURES", ["moneyness", *NUMERIC_FEATURES])
    monkeypatch.setattr(v4_candidates, "technical_features", lambda bars, fast, slow:
                        pd.DataFrame({"ma_gap": [0.]}, index=raw.index))
    spec = {"symbols": {"SPY": {"strategies": {"ma": {
        "params": {"fast_window": 2, "slow_window": 3}}}}}}
    result = v4_candidates.build_candidate_batch(rows, {"SPY": pd.DataFrame()}, pd.DataFrame(), spec,
        expanded_inputs=inputs, option_provider=provider, raw_close_by_symbol={"SPY": raw})
    assert result.option_tick_status.tolist() == ["unselected"]
    assert result.decision_contract.isna().all()
    assert result.option_tick_request_id.str.fullmatch(r"[0-9a-f]{64}").all()
    assert result[list(NUMERIC_FEATURES)].isna().all().all()
