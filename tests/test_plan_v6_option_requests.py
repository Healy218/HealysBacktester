from datetime import date
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta import providers
from nn_meta.decision_contracts import DecisionContractSelector
from nn_meta.price_basis import raw_spot_provenance
from nn_meta.tradingview_proposals import STRATEGIES
from options.data.provider import OptionContract
from scripts import plan_v6_option_requests as planner


@pytest.fixture
def configured(monkeypatch, tmp_path):
    values = dict(V6_EXPANDED=True, POOL="v6", CAMPAIGN="test-expanded",
        PROPOSAL_STRATEGIES=[*planner.config.PROPOSAL_STRATEGIES_V5, "keltner", "bbw_squeeze", *STRATEGIES],
        TRAIN_START="2024-01-02", TRAIN_END="2024-01-03", WINDOW_START="2024-01-02",
        WINDOW_END="2024-01-05", MAX_SIGNALS_PER_NAME=2, DTE_GRID=[1, 5], DTE_GRID_WEEKLY=[2, 7],
        WEEKLY_DTE_ENABLED=True, UNDERLYINGS=["SPY"], DATA_CACHE=tmp_path / "cache")
    for name, value in values.items():
        monkeypatch.setattr(planner.config, name, value)
    index = pd.to_datetime(["2024-01-02 14:30", "2024-01-03 14:30", "2024-01-04 14:30", "2024-01-05 14:30"])
    bars = pd.DataFrame({"Open": 50., "High": 51., "Low": 49., "Close": 50., "Volume": 10.}, index=index)
    bars.attrs["v6_tradingview_context"] = {"sentinel": "validated by ExpandedInputs"}
    raw = pd.Series([100., 102., 104., 106.], index=index)
    raw.attrs = dict(raw_spot_provenance("15m", provider="fixture", feed="fixture"), symbol="SPY")
    return bars, raw


class LocalChain:
    point_in_time_chain = True

    def __init__(self):
        self.calls = []

    def get_chain(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return [OptionContract(symbol="SPY240105C00100000", underlying="SPY", expiration=date(2024, 1, 5), right="C", strike=100.)] if kwargs["right"] == "C" else []

    def get_option_bars(self, *args, **kwargs):
        raise AssertionError("option bars must never be read")


def install_sweeps(monkeypatch, bars, *, skips=True):
    calls = []
    strategies = planner.config.PROPOSAL_STRATEGIES

    def sweep(symbol, actual, strategy, start, end):
        assert actual is bars
        calls.append(("sweep", strategy, start, end))
        if skips and strategy == strategies[0]:
            return None
        return {"strategy": strategy, "params": {"setup_identity": "ORB"} if strategy == "tv_setup" else {"test": 7},
                "train_sharpe": float("nan")}

    def propose(actual, strategy, params, start, end):
        assert actual is bars
        assert params == ({"setup_identity": "ORB"} if strategy == "tv_setup" else {"test": 7})
        calls.append(("propose", strategy, start, end))
        if end == planner.config.TRAIN_END:
            if skips and strategy == strategies[1]:
                return []
            return [(bars.index[0], bars.index[1], 0)]
        if skips and strategy == strategies[2]:
            return []
        return [(bars.index[0], bars.index[1], 0), (bars.index[2], bars.index[3], 1),
                (bars.index[3], bars.index[3], 0)]

    monkeypatch.setattr(planner.baseline, "sweep_train_params", sweep)
    monkeypatch.setattr(planner.baseline, "propose_trades", propose)
    return calls


def test_all_twenty_train_selection_weeklies_raw_spot_and_distinct_skips(configured, monkeypatch):
    bars, raw = configured
    calls = install_sweeps(monkeypatch, bars)
    chain = LocalChain()
    requests, evidence = planner.plan_symbol("SPY", bars, raw, DecisionContractSelector(chain), weekly_symbols=["SPY"])
    assert len(evidence["families"]) == 20
    assert len([c for c in calls if c[0] == "sweep"]) == 20
    assert all(c[2:] == ("2024-01-02", "2024-01-03") for c in calls if c[0] == "sweep")
    assert [evidence["families"][s]["status"] for s in planner.config.PROPOSAL_STRATEGIES[:3]] == [
        "no_freezable_params", "no_train_events", "no_full_window_events"]
    assert evidence["dte_grid"] == [1, 2, 5, 7]
    assert len(requests) == 17 * 2 * 4
    assert {r["raw_spot"] for r in requests} == {100., 104.}  # never adjusted Close=50
    assert {r["status"] for r in requests} == {"selected", "unselected"}
    assert requests[0]["consumer_ids"] == ["SPY:squeeze:0:1"]
    assert requests[1]["consumer_ids"] == ["SPY:squeeze:1:1"]
    assert evidence["families"]["tv_setup"]["sweep"]["params"] == {"setup_identity": "ORB"}
    assert evidence["families"]["tv_setup"]["sweep"]["train_sharpe"] is None
    assert all(item["as_of"] < date(2024, 1, 5) for _, item in chain.calls)
    assert evidence["families"]["tv_setup"]["full_truncated"] is True
    assert evidence["requests_sha256"] == planner._hash(requests)


def test_nonweekly_uses_only_base_grid(configured, monkeypatch):
    bars, raw = configured
    install_sweeps(monkeypatch, bars)
    requests, evidence = planner.plan_symbol("SPY", bars, raw, DecisionContractSelector(LocalChain()), weekly_symbols=[])
    assert evidence["dte_grid"] == [1, 5]
    assert len(requests) == 17 * 2 * 2


@pytest.mark.parametrize("problem", ["wrong_symbol", "missing_raw", "adjusted", "context", "unexpanded"])
def test_required_inputs_fail_closed(configured, monkeypatch, problem):
    bars, raw = configured
    if problem == "wrong_symbol":
        raw.attrs["symbol"] = "QQQ"
    elif problem == "missing_raw":
        raw = raw.iloc[:-1]
    elif problem == "adjusted":
        raw.attrs["adjustment"] = "all"
    elif problem == "context":
        bars.attrs = {}
    else:
        monkeypatch.setattr(planner.config, "V6_EXPANDED", False)
    monkeypatch.setattr(planner.baseline, "sweep_train_params", lambda *a: pytest.fail("must fail before sweep"))
    with pytest.raises(ValueError):
        planner.plan_symbol("SPY", bars, raw, DecisionContractSelector(LocalChain()), weekly_symbols=[])


def test_train_exit_guard_and_context_errors_propagate(configured, monkeypatch):
    bars, raw = configured
    install_sweeps(monkeypatch, bars, skips=False)
    monkeypatch.setattr(planner.baseline, "propose_trades", lambda *a: [(bars.index[0], bars.index[-1], 0)])
    with pytest.raises(ValueError, match="TRAIN trade leaked"):
        planner.plan_symbol("SPY", bars, raw, DecisionContractSelector(LocalChain()), weekly_symbols=[])
    def broken(*args):
        raise ValueError("missing exact Pine context")
    monkeypatch.setattr(planner.baseline, "sweep_train_params", broken)
    with pytest.raises(ValueError, match="missing exact Pine context"):
        planner.plan_symbol("SPY", bars, raw, DecisionContractSelector(LocalChain()), weekly_symbols=[])


def test_train_cap_precedes_guard_as_in_freeze(configured, monkeypatch):
    bars, raw = configured
    install_sweeps(monkeypatch, bars, skips=False)
    monkeypatch.setattr(planner.baseline, "propose_trades", lambda *a: [
        (bars.index[0], bars.index[1], 0), (bars.index[0], bars.index[1], 0),
        (bars.index[0], bars.index[-1], 0)])
    requests, evidence = planner.plan_symbol("SPY", bars, raw, DecisionContractSelector(LocalChain()), weekly_symbols=[])
    assert len(requests) == 80  # duplicate consumers preserved, later dataset handles shared request keys
    assert all(r["train_truncated"] for r in evidence["families"].values())


def install_cli(monkeypatch, tmp_path, bars, raw):
    for name in ("UNDERLYING_15M_PARQUET", "UNDERLYING_15M_RAW_PARQUET", "UNIVERSE_PARQUET"):
        path = tmp_path / name
        path.write_text(name)
        monkeypatch.setattr(planner.config, name, path)
    expanded = SimpleNamespace(document={"symbols": {"SPY": {}}},
        assert_unchanged=lambda: None, input_files=lambda: {})
    monkeypatch.setattr(planner, "from_environment", lambda: expanded)
    monkeypatch.setattr(planner, "weekly_expiry_symbols", lambda *args: ["SPY"])
    monkeypatch.setattr(planner.baseline, "load_underlying_15m", lambda *args: bars)
    monkeypatch.setattr(planner, "load_raw_close_15m", lambda *args, **kwargs: raw)
    monkeypatch.setattr(planner, "_source_hashes", lambda: {"fixture": "a" * 64})
    monkeypatch.setattr(providers, "get_provider", lambda **kwargs: LocalChain() if kwargs == {"allow_fetch": False} else pytest.fail("fetch policy"))


def test_cli_preview_validates_without_sweeps_or_writes(configured, monkeypatch, tmp_path):
    bars, raw = configured
    install_cli(monkeypatch, tmp_path, bars, raw)
    monkeypatch.setattr(planner.baseline, "sweep_train_params", lambda *a: pytest.fail("preview swept"))
    output = tmp_path / "preview"
    result = planner.plan(SimpleNamespace(output=output, symbols="SPY", run=False))
    assert not output.exists()
    assert result["written"] is False and result["inventory_computed"] is False
    assert result["tick_stores_bound"] is False


def test_cli_run_writes_bound_requests_and_keeps_pending_ticks(configured, monkeypatch, tmp_path):
    bars, raw = configured
    install_cli(monkeypatch, tmp_path, bars, raw)
    install_sweeps(monkeypatch, bars)
    output = tmp_path / "requests"
    result = planner.plan(SimpleNamespace(output=output, symbols="SPY", run=True))
    assert result["written"] and result["inventory_computed"]
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["complete"] and not manifest["freeze_completed"]
    for name, digest in manifest["files_sha256"].items():
        assert planner.sha256(output / name) == digest
    provenance = json.loads((output / "selection_provenance.json").read_text())
    assert provenance["symbol_selections"]["SPY"]["requests"] == 136
    assert not provenance["tick_stores_bound"] and not provenance["option_outcomes_read"]
    with pytest.raises(ValueError, match="fresh"):
        planner.plan(SimpleNamespace(output=output, symbols="SPY", run=True))


def test_cli_refuses_source_or_input_race_before_output(configured, monkeypatch, tmp_path):
    bars, raw = configured
    install_cli(monkeypatch, tmp_path, bars, raw)
    install_sweeps(monkeypatch, bars)
    hashes = iter([{"first": "a" * 64}, {"changed": "b" * 64}])
    monkeypatch.setattr(planner, "_source_hashes", lambda: next(hashes))
    output = tmp_path / "race"
    with pytest.raises(ValueError, match="changed during"):
        planner.plan(SimpleNamespace(output=output, symbols="SPY", run=True))
    assert not output.exists()


@pytest.mark.parametrize("symbols", ["SPY,SPY", "QQQ", "", "SPY,"])
def test_explicit_scope_validation(configured, monkeypatch, tmp_path, symbols):
    bars, raw = configured
    install_cli(monkeypatch, tmp_path, bars, raw)
    if symbols == "":
        monkeypatch.setattr(planner.config, "UNDERLYINGS", [])
    with pytest.raises(ValueError, match="distinct configured"):
        planner.plan(SimpleNamespace(output=tmp_path / "invalid", symbols=symbols, run=False))


def test_weekly_classification_race_is_not_an_inventory(configured, monkeypatch, tmp_path):
    bars, raw = configured
    install_cli(monkeypatch, tmp_path, bars, raw)
    def changing(*args):
        planner.config.UNIVERSE_PARQUET.write_text("new catalogue")
        return ["SPY"]
    monkeypatch.setattr(planner, "weekly_expiry_symbols", changing)
    with pytest.raises(ValueError, match="catalogue changed"):
        planner.plan(SimpleNamespace(output=tmp_path / "race", symbols="SPY", run=True))
    assert not (tmp_path / "race").exists()


def test_source_snapshot_includes_canonical_pine_and_adaptation_manifests(monkeypatch, tmp_path):
    source = tmp_path / "indicators" / "tradingview_sources"
    source.mkdir(parents=True)
    pine, manifest = source / "pinned.pine", source / "adapter.json"
    pine.write_text("source-v1")
    manifest.write_text("{}")
    (tmp_path / "requirements.txt").write_text("requirements")
    monkeypatch.setattr(planner, "ROOT", tmp_path)
    before = planner._source_hashes()
    assert str(pine) in before and str(manifest) in before
    pine.write_text("source-v2")
    assert planner._source_hashes() != before


def test_selected_historical_aliases_preserved_and_conflicts_refused():
    request = {"status": "selected", "contract": "FB240105C00100000", "symbol": "META"}
    assert planner._root_aliases([request]) == {"FB": "META"}
    with pytest.raises(ValueError, match="ambiguous"):
        planner._root_aliases([request, dict(request, symbol="FB")])
