"""Decision chronology, strict coverage, eligibility and immutable artifact tests."""
import copy
import gzip
import hashlib
import json
from datetime import date

import pandas as pd
import pytest

from nn_meta import option_tick_dataset as dataset
from nn_meta.decision_contracts import DecisionContractSelector
from options.data.massive_ticks import MassiveTicks, TickDataError, canonical_bytes
from options.data.provider import OptionContract

BASE = 1_780_000_000_000_000_000
SECOND = 1_000_000_000
OCC = "SPY260824C00766000"


def request(**changes):
    row = dict(symbol="SPY", contract=OCC, window_start_ns=BASE,
               window_end_ns=BASE + 10 * SECOND, decision_close_ns=BASE + 10 * SECOND,
               selected_at_ns=BASE + 10 * SECOND, raw_spot_available_ns=BASE + 10 * SECOND,
               raw_spot=766., chain_available_ns=BASE - SECOND, consumer_ids=["ma:5"])
    return row | changes


def quote(t=0, **changes):
    return dict(sip_timestamp=BASE + t * SECOND, sequence_number=t + 1,
                bid_price=1., ask_price=1.2, bid_size=30., ask_size=10.) | changes


def trade(t=2, **changes):
    return dict(sip_timestamp=BASE + t * SECOND, sequence_number=0,
                price=1.2, size=10, conditions=[209]) | changes


def capture(directory, *, quotes=None, trades=None, start=BASE, end=BASE + 20 * SECOND, contract=OCC):
    directory.mkdir()
    quotes = [quote()] if quotes is None else quotes
    trades = [trade(), trade(3, price=5., size=5, conditions=[999]),
              trade(4, size=7, conditions=[]), trade(5, size=100, correction=1)] if trades is None else trades
    entry = {"contract": contract, "captures": {}, "files": {}}
    for kind, rows in (("quotes", quotes), ("trades", trades)):
        class Response:
            status_code = 200
            def json(self):
                return {"status": "OK", "results": rows}
        class Client:
            def get(self, *args, **kwargs):
                return Response()
        verified, manifest = MassiveTicks("synthetic-key", session=Client()).capture(contract, kind, start, end)
        blob = gzip.compress(canonical_bytes(verified), mtime=0)
        name = f"{contract}.{kind}.json.gz"
        (directory / name).write_bytes(blob)
        entry["captures"][kind] = manifest
        entry["files"][name] = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
    report = {"complete": True, "plan": {"contracts": [contract], "start_ns": start, "end_ns": end},
              "contracts": [entry]}
    (directory / "manifest.json").write_bytes(canonical_bytes(report))
    return directory


@pytest.fixture
def evidence(tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text('{"selection":"synthetic prior-date chain and raw close"}')
    condition = tmp_path / "conditions.json"
    condition.write_text('{"namespace":"massive_integer","synthetic_test_code":209}')
    return selection, condition


def task(evidence, requests=None, *, admit=True):
    return dataset.create_task_manifest(requests or [request()], selection_reference_paths=[evidence[0]],
        feature_policy=dataset.feature_policy(allowed_trade_conditions=[209] if admit else [],
            condition_reference_paths=[evidence[1]] if admit else [],
            condition_policy_id="synthetic-test-only" if admit else "none"))


def build(tmp_path, evidence, *, requests=None, quotes=None, trades=None, admit=True):
    t = task(evidence, requests, admit=admit)
    source = capture(tmp_path / "capture", quotes=quotes, trades=trades)
    output = tmp_path / "store"
    manifest = dataset.materialize_store(t, [source], output)
    return t, source, output, manifest


def read(t, output, manifest):
    return dataset.load_feature_store(output, expected_task_sha256=t["task_sha256"],
                                      expected_store_sha256=manifest["store_sha256"])


def join(t, output, manifest, rows, **kwargs):
    return dataset.join_decisions(rows, output, expected_task_sha256=t["task_sha256"],
                                 expected_store_sha256=manifest["store_sha256"], **kwargs)


@pytest.mark.parametrize("changes", [
    {"window_end_ns": BASE + 10 * SECOND + 1},
    {"selected_at_ns": BASE + 10 * SECOND + 1},
    {"raw_spot_available_ns": BASE + 10 * SECOND + 1},
    {"chain_available_ns": BASE + 10 * SECOND + 1},
    {"decision_close_ns": float(BASE + 10 * SECOND)},
    {"decision_close_ns": True}, {"raw_spot": float("nan")}, {"raw_spot": 0},
    {"symbol": "QQQ"}, {"future_profit": 2.},
])
def test_requests_refuse_future_information_imprecise_keys_and_outcomes(evidence, changes):
    with pytest.raises(TickDataError):
        task(evidence, [request(**changes)])


def test_shared_strategies_and_dte_contexts_dedupe_but_conflicting_raw_spot_fails(evidence):
    a = request(selection_policy="prior-date-v1", right="C", target_dte=5)
    b = request(consumer_ids=["rsi:7"], selection_policy="prior-date-v1", right="C", target_dte=7)
    t = task(evidence, [a, b])
    assert len(t["requests"]) == 1
    assert t["requests"][0]["consumer_ids"] == ["ma:5", "rsi:7"]
    assert len(t["requests"][0]["selection_contexts"]) == 2
    assert len(dataset.plan_capture_windows(t)) == 1
    with pytest.raises(TickDataError, match="ambiguous selection"):
        task(evidence, [a, b | {"raw_spot": 765.}])


def test_capture_plan_coalesces_touching_windows_and_keeps_real_gaps(evidence):
    second = request(window_start_ns=BASE + 10 * SECOND, window_end_ns=BASE + 20 * SECOND,
                     decision_close_ns=BASE + 20 * SECOND)
    third = request(window_start_ns=BASE + 30 * SECOND, window_end_ns=BASE + 40 * SECOND,
                    decision_close_ns=BASE + 40 * SECOND)
    t = task(evidence, [request(), second, third])
    plan = dataset.plan_capture_windows(t)
    assert [(p["start_ns"], p["end_ns"]) for p in plan] == [
        (BASE, BASE + 20 * SECOND), (BASE + 30 * SECOND, BASE + 40 * SECOND)]
    assert len(plan[0]["request_ids"]) == 2
    assert len(dataset.plan_capture_windows(t, max_span_ns=10 * SECOND)) == 3


def test_condition_allowlist_requires_bound_evidence_and_never_changes_default(evidence):
    with pytest.raises(TickDataError, match="bound reference"):
        dataset.feature_policy(allowed_trade_conditions=[209])
    for codes in ([True], ["209"], [209, 209]):
        with pytest.raises(TickDataError):
            dataset.feature_policy(allowed_trade_conditions=codes, condition_reference_paths=[evidence[1]])
    assert dataset.feature_policy()["allowed_trade_conditions"] == []
    assert dataset.feature_policy()["allow_unconditioned_trades"] is False


def test_materialized_features_separate_reported_and_actually_eligible_trades(tmp_path, evidence):
    t, source, output, manifest = build(tmp_path, evidence)
    row = read(t, output, manifest).iloc[0]
    assert row.reported_trade_count == 3 and row.reported_contract_volume == 22
    assert row.eligible_trade_count == 1 and row.eligible_contract_volume == 10
    assert row.condition_excluded_trade_count == 2 and row.condition_excluded_contract_volume == 12
    assert row.opt_tick_trade_count_per_second == .1
    assert row.opt_tick_trade_volume_per_second == 1.
    assert row.opt_tick_trade_vwap_mid_bps == pytest.approx((1.2 / 1.1 - 1) * 10000)
    assert row.opt_tick_signed_volume_fraction == 1.
    assert row.opt_tick_valid_quote_fraction == 1.
    assert row.opt_tick_size_imbalance == .5
    assert manifest["model_admission"] is False
    with pytest.raises(TickDataError, match="fresh immutable"):
        dataset.materialize_store(t, [source], output)


def test_default_excludes_all_unknown_trade_conditions_and_preserves_missing_measurements(tmp_path, evidence):
    t, _, output, manifest = build(tmp_path, evidence, admit=False)
    row = read(t, output, manifest).iloc[0]
    assert row.reported_trade_count == 3 and row.eligible_trade_count == 0
    assert row.opt_tick_trade_count_per_second == 0  # verified zero eligible observations
    assert pd.isna(row.opt_tick_trade_vwap_mid_bps)
    assert pd.isna(row.opt_tick_signed_volume_fraction)


def test_complete_empty_capture_is_distinct_from_missing_capture(tmp_path, evidence):
    t, _, output, manifest = build(tmp_path, evidence, quotes=[], trades=[])
    row = read(t, output, manifest).iloc[0]
    assert row.option_tick_status == "covered" and row.opt_tick_valid_quote_fraction == 0
    assert pd.isna(row.opt_tick_spread_bps) and pd.isna(row.opt_tick_quote_age_seconds)
    assert pd.isna(row.opt_tick_trade_vwap_mid_bps)


@pytest.mark.parametrize("mode", ["missing", "partial", "ambiguous"])
def test_missing_partial_or_ambiguous_window_refused_without_publishing(tmp_path, evidence, mode):
    t = task(evidence)
    captures = [] if mode == "missing" else [capture(tmp_path / "a", end=BASE + (9 if mode == "partial" else 20) * SECOND)]
    if mode == "ambiguous":
        captures.append(capture(tmp_path / "b"))
    output = tmp_path / "store"
    with pytest.raises(TickDataError, match="missing or ambiguous"):
        dataset.materialize_store(t, captures, output)
    assert not output.exists()


def test_full_request_inventory_requires_both_contracts(tmp_path, evidence):
    t = task(evidence, [request(), request(contract=OCC.replace("C", "P"))])
    source = capture(tmp_path / "capture")
    with pytest.raises(TickDataError, match="coverage"):
        dataset.materialize_store(t, [source], tmp_path / "store")
    assert not (tmp_path / "store").exists()


def test_later_ticks_do_not_change_earlier_features(tmp_path, evidence):
    t = task(evidence)
    a = capture(tmp_path / "a", quotes=[quote()], trades=[trade()])
    b = capture(tmp_path / "b", quotes=[quote(), quote(11, bid_price=100, ask_price=101)],
                trades=[trade(), trade(12, price=999, size=1000000)])
    ma = dataset.materialize_store(t, [a], tmp_path / "sa")
    mb = dataset.materialize_store(t, [b], tmp_path / "sb")
    pd.testing.assert_frame_equal(read(t, tmp_path / "sa", ma)[list(dataset.NUMERIC_FEATURES)],
                                  read(t, tmp_path / "sb", mb)[list(dataset.NUMERIC_FEATURES)])


@pytest.mark.parametrize("changed", ["rows", "task", "capture", "evidence", "extra_store_file"])
def test_tampered_bytes_and_file_inventory_refused(tmp_path, evidence, changed):
    t, source, output, manifest = build(tmp_path, evidence)
    path = {"rows": output / "features.parquet", "task": output / "task.json",
            "capture": source / f"{OCC}.quotes.json.gz", "evidence": evidence[0],
            "extra_store_file": output / "unexpected.json"}[changed]
    if changed == "extra_store_file":
        path.write_text("{}")
    else:
        data = bytearray(path.read_bytes()); data[len(data) // 2] ^= 1; path.write_bytes(data)
    with pytest.raises((TickDataError, ValueError)):
        read(t, output, manifest)


def test_rehashed_forged_manifest_refused_by_external_anchor(tmp_path, evidence):
    t, _, output, manifest = build(tmp_path, evidence)
    changed = copy.deepcopy(manifest)
    changed["row_count"] += 1
    changed["store_sha256"] = dataset._hash({k: v for k, v in changed.items() if k != "store_sha256"})
    (output / "manifest.json").write_bytes(canonical_bytes(changed))
    with pytest.raises(TickDataError, match="external hash"):
        read(t, output, manifest)


def test_store_manifest_symlink_and_inconsistent_coverage_metadata_refused(tmp_path, evidence):
    t, _, output, manifest = build(tmp_path, evidence)
    path = output / "manifest.json"
    original = path.read_bytes()
    elsewhere = tmp_path / "copied-manifest.json"
    elsewhere.write_bytes(original)
    path.unlink()
    path.symlink_to(elsewhere)
    with pytest.raises(TickDataError, match="symlink"):
        read(t, output, manifest)
    path.unlink()
    changed = copy.deepcopy(manifest)
    rid = next(iter(changed["coverage"]))
    changed["coverage"][rid]["end_ns"] += 1
    changed["store_sha256"] = dataset._hash({k: v for k, v in changed.items() if k != "store_sha256"})
    path.write_bytes(canonical_bytes(changed))
    # Even a caller supplying the revised artifact anchor cannot waive its
    # inconsistent request/capture coverage assertions.
    with pytest.raises(TickDataError, match="coverage metadata"):
        read(t, output, changed)


def test_source_change_refused_on_read_and_during_materialization(tmp_path, evidence, monkeypatch):
    t, source, output, manifest = build(tmp_path, evidence)
    original = dataset.implementation_identity
    monkeypatch.setattr(dataset, "implementation_identity", lambda: {"changed": True})
    with pytest.raises(TickDataError, match="source or runtime"):
        read(t, output, manifest)
    monkeypatch.setattr(dataset, "implementation_identity", original)
    compute = dataset.compute_feature_row
    def changing(*args, **kwargs):
        result = compute(*args, **kwargs)
        monkeypatch.setattr(dataset, "implementation_identity", lambda: {"changed": True})
        return result
    monkeypatch.setattr(dataset, "compute_feature_row", changing)
    with pytest.raises(TickDataError, match="source or runtime"):
        dataset.materialize_store(t, [source], tmp_path / "incomplete")
    assert not (tmp_path / "incomplete/manifest.json").exists()


def test_exact_join_preserves_shared_consumers_order_and_refuses_lookahead_fallback(tmp_path, evidence):
    t, _, output, manifest = build(tmp_path, evidence)
    row = {k: t["requests"][0][k] for k in ("request_id", *dataset.KEY_COLUMNS)}
    decisions = pd.DataFrame([row | {"family": "rsi"}, row | {"family": "ma"}], index=[7, 7])
    result = join(t, output, manifest, decisions)
    assert result.index.tolist() == [7, 7] and result.family.tolist() == ["rsi", "ma"]
    assert result.opt_tick_trade_count_per_second.tolist() == [.1, .1]
    changed = decisions.copy()
    changed.loc[:, "decision_close_ns"] += 1
    with pytest.raises(TickDataError, match="missing or.*inconsistent"):
        join(t, output, manifest, changed)
    changed["request_id"] = [dataset.request_id(r) for r in changed.to_dict("records")]
    with pytest.raises(TickDataError, match="missing"):
        join(t, output, manifest, changed)


def test_root_selector_unselected_request_is_preserved_without_fake_observations(tmp_path, evidence):
    class EmptyProvider:
        point_in_time_chain = True
        def get_chain(self, *args, **kwargs):
            return []
    req = DecisionContractSelector(EmptyProvider()).request("SPY", signal_bar_open="2026-08-24T13:30:00Z",
            right="C", raw_spot=766., target_dte=5, consumer_ids=["ma:5"])
    t = task(evidence, [req])
    manifest = dataset.materialize_store(t, [], tmp_path / "store")
    assert manifest["selected_request_count"] == 0 and manifest["unselected_request_count"] == 1
    rows = pd.DataFrame(t["requests"])
    with pytest.raises(TickDataError, match="unselected"):
        join(t, tmp_path / "store", manifest, rows)
    result = join(t, tmp_path / "store", manifest, rows, allow_unselected=True)
    assert result[list(dataset.NUMERIC_FEATURES)].isna().all().all()
    assert result.option_tick_status.tolist() == ["unselected"]


def test_selected_root_request_through_verified_store_and_join(tmp_path, evidence):
    occ = "SPY260825C00765000"
    class Provider:
        point_in_time_chain = True
        def get_chain(self, symbol, **kwargs):
            assert symbol == "SPY" and kwargs["as_of"] == date(2026, 8, 23)
            assert kwargs["expiration_gte"] == date(2026, 8, 25)
            return [OptionContract(occ, "SPY", date(2026, 8, 25), 765., "C")]
        def get_contract_bars(self, *args, **kwargs):
            pytest.fail("decision features must not inspect execution success")
    req = DecisionContractSelector(Provider()).request("SPY", signal_bar_open="2026-08-24T13:30:00Z",
            right="C", raw_spot=765.4, target_dte=1, consumer_ids=["ma:1"])
    t = task(evidence, [req])
    start, end = req["window_start_ns"], req["window_end_ns"]
    source = capture(tmp_path / "capture", start=start, end=end, contract=occ,
        quotes=[quote(sip_timestamp=start), quote(1, sip_timestamp=end-SECOND)],
        trades=[trade(sip_timestamp=start + SECOND)])
    manifest = dataset.materialize_store(t, [source], tmp_path / "store")
    actual = join(t, tmp_path / "store", manifest, pd.DataFrame(t["requests"]))
    assert actual.contract.tolist() == [occ] and actual.option_tick_status.tolist() == ["covered"]
    assert actual.opt_tick_trade_count_per_second.iloc[0] == pytest.approx(1 / 900)
    assert actual.opt_tick_trade_volume_per_second.iloc[0] == pytest.approx(10 / 900)


def test_cli_preview_then_immutable_prepare_and_ingest(tmp_path, evidence, capsys):
    from scripts.prepare_option_tick_features import main
    requests, policy = tmp_path / "requests.json", tmp_path / "policy.json"
    requests.write_bytes(canonical_bytes([request(), request(consumer_ids=["rsi:5"])]))
    policy.write_bytes(canonical_bytes(dataset.feature_policy()))
    output = tmp_path / "prepared"
    args = ["prepare", "--requests", str(requests), "--policy", str(policy),
            "--selection-reference", str(evidence[0]), "--output", str(output)]
    assert main(args) == 0 and not output.exists()
    preview = json.loads(capsys.readouterr().out)
    assert preview["capture_plan"]["request_count"] == 1
    assert preview["capture_plan"]["downloads_started"] is False
    assert main(args + ["--run"]) == 0
    written = json.loads(capsys.readouterr().out)
    assert written["task_sha256"] == preview["task_sha256"]
    assert (output / "manifest.json").is_file()
    assert main(args + ["--run"]) == 1
    capsys.readouterr()
    source = capture(tmp_path / "capture")
    ingest = ["materialize", "--task", str(output / "task.json"),
              "--expected-task-sha256", written["task_sha256"], "--capture", str(source),
              "--output", str(tmp_path / "store")]
    assert main(ingest) == 0 and not (tmp_path / "store").exists()
    assert json.loads(capsys.readouterr().out)["capture_contents_verified"] is False
    assert main(ingest + ["--run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["capture_contents_verified"] and result["store_sha256"]
    assert result["downloads_started"] is False


def test_cli_refuses_unreviewed_task_hash_or_missing_coverage(tmp_path, evidence, capsys):
    from scripts.prepare_option_tick_features import main
    t = task(evidence)
    path = tmp_path / "task.json"
    path.write_bytes(canonical_bytes(t))
    output = tmp_path / "store"
    args = ["materialize", "--task", str(path), "--output", str(output),
            "--expected-task-sha256", "0" * 64, "--run"]
    assert main(args) == 1 and not output.exists()
    assert "review anchor" in capsys.readouterr().err
    args[-2] = t["task_sha256"]
    assert main(args) == 1 and not output.exists()
    assert "coverage" in capsys.readouterr().err


def test_capture_batch_planning_groups_equal_windows_without_changing_requests(evidence):
    from scripts.prepare_option_tick_features import capture_plan
    requests = [request(contract=f"SPY260824C{(760+i)*1000:08d}") for i in range(11)]
    t = task(evidence, requests)
    plan = capture_plan(t)
    assert [len(b["contracts"]) for b in plan["capture_batches"]] == [10, 1]
    assert sum(len(w["request_ids"]) for w in plan["windows"]) == 11
    assert plan["task_sha256"] == t["task_sha256"]
