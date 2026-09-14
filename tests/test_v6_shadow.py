import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta.live.v6_shadow import ShadowStore, canonical
from nn_meta.live.v6_inputs import LiveSnapshot, SnapshotChain
from nn_meta.v6_expansion import sha256
from nn_meta.option_tick_dataset import request_id


def test_shadow_is_idempotent_preserves_first_observation_and_refuses_policy_change(tmp_path):
    scope = {"model": "frozen", "threshold": .5}
    store = ShadowStore(tmp_path, scope)
    batch = pd.DataFrame(dict(symbol=["SPY"]*3, strategy=["ma"]*3, dte=[1, 5, 10],
                              entry_ts=[pd.Timestamp("2026-09-14T14:30:00Z")]*3, x=[np.nan]*3))
    spec = {"symbols": {"SPY": {"strategies": {"ma": {"dte": 5}}}}}
    bundle = SimpleNamespace(mode="ev", threshold=.05)
    kwargs = dict(scores=[.6, .7, .8], decisions=[.06, .08, .07], bundle=bundle,
                  spec=spec, observed_at="2026-09-14T14:45:02Z", evidence={"test": True})
    assert store.record(batch, **kwargs) == 3
    kwargs["decisions"] = [.1, .1, .2]
    assert store.record(batch, **kwargs) == 0
    report = store.finish(now=kwargs["observed_at"], status="ok", summary={})
    assert report["candidate_rows"] == 3 and report["candidate_selections"] == 1
    assert report["baseline_selections"] == 1 and report["realized_return"] is None
    with store.connect() as db:
        payload = json.loads(db.execute("SELECT payload FROM candidates WHERE candidate=1").fetchone()[0])
        assert payload["row"]["dte"] == 5 and payload["row"]["x"] is None
    with pytest.raises(ValueError, match="fresh shadow scope"):
        ShadowStore(tmp_path, dict(scope, threshold=.6))


def test_scan_shadow_never_delivers_existing_outbox_and_records_all_variants(monkeypatch, tmp_path):
    from tests.test_v4_scan import _bars, _fire_on_last_bar, _bundle, _spec, _surface
    from nn_meta.live import v4_scan
    from nn_meta.live.state import Outbox
    bars = _bars(); _fire_on_last_bar(monkeypatch, bars)
    Outbox(tmp_path / "shadow" / v4_scan.OUTBOX.name).enqueue({"message": "must not send"}, key="old")
    notifier = SimpleNamespace(send=lambda *a, **k: pytest.fail("shadow sent a message"))
    result = v4_scan.scan_pass(bundle=_bundle(base=.9, dte_gain=0), spec=_spec(), surface=_surface(),
        bar_loader=lambda s: bars, notifier=notifier,
        now=(bars.index[-1]+pd.Timedelta(minutes=15)).tz_localize("UTC"),
        state_dir=tmp_path, shadow=True, shadow_scope={"frozen": True}, workers=1)
    assert result["error_count"] == 0 and result["recorded"] > 1
    assert result["alerted"] == result["delivered"] == 0
    assert not (tmp_path / v4_scan.ALERT_STATE.name).exists()
    assert len(Outbox(tmp_path / "shadow" / v4_scan.OUTBOX.name).unacked()) == 1


def test_expanded_scan_refuses_paper_bypass_before_any_alert(monkeypatch, tmp_path):
    from nn_meta.live import v4_scan
    from tests.test_v4_scan import _bundle, _spec, _surface
    monkeypatch.setattr(v4_scan.config, "V6_EXPANDED", True)
    with pytest.raises(ValueError, match="shadow-only"):
        v4_scan.scan_pass(bundle=_bundle(), spec=_spec(), surface=_surface(),
            bar_loader=lambda s: pytest.fail("loaded bars before gate"), notifier=None,
            paper=True, state_dir=tmp_path)


def test_scan_supplies_adapter_before_detection_and_candidate_projection(monkeypatch, tmp_path):
    from nn_meta.live import v4_scan
    from tests.test_v4_scan import _bars, _bundle, _spec, _surface
    monkeypatch.setattr(v4_scan.config, "V6_EXPANDED", True)
    bars = _bars()
    attached, passed = [], []
    def attach(symbol, frame):
        frame.attrs["bound"] = True
        attached.append(symbol)
        return frame
    def detect(symbol, frame, *args):
        assert frame.attrs["bound"]
        return [dict(symbol=symbol, strategy="rsi", direction=0, entry_ts=frame.index[-1],
                     bars_since_signal=1, spot=100.)]
    def construct(proposals, cached, surface, spec, **kwargs):
        assert kwargs == {"test_input": "bound"}
        passed.append(True)
        return proposals.assign(dte_frac=proposals.dte / max(v4_scan.config.DTE_GRID))
    adapter = SimpleNamespace(attach=attach, candidate_kwargs=lambda b: {"test_input": "bound"},
        expanded_inputs=SimpleNamespace(document={"feature_contract_version": "frozen"}),
        evidence=lambda: {"test": True}, assert_unchanged=lambda: None, document={})
    bundle = _bundle(features=["dte_frac"]); bundle.config = {"feature_contract_version": "frozen"}
    monkeypatch.setattr(v4_scan, "fresh_proposals", detect)
    monkeypatch.setattr(v4_scan, "build_candidate_batch", construct)
    result = v4_scan.scan_pass(bundle=bundle, spec=_spec(), surface=_surface(),
        bar_loader=lambda s: bars, notifier=None, now=(bars.index[-1]+pd.Timedelta(minutes=15)).tz_localize("UTC"),
        state_dir=tmp_path, workers=1, live_inputs=adapter, shadow=True, shadow_scope={"test": True})
    assert result["error_count"] == 0 and passed and attached == ["SPY"]


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    from tests.test_v6_expansion import _synthetic_input_bundle
    from nn_meta.price_basis import raw_spot_provenance, RAW_SPOT_SCHEMA_VERSION
    bundle = _synthetic_input_bundle(tmp_path, monkeypatch)
    def save(name, value):
        path = tmp_path / name
        if isinstance(value, pd.DataFrame):
            value.to_parquet(path, index=False)
        else:
            path.write_text(json.dumps(value))
        return {"path": path.name, "sha256": sha256(path)}
    bars = bundle.bars.reset_index(names="timestamp").assign(symbol="SPY", available_at=pd.Timestamp("2025-01-02T14:45:01Z"))
    raw = bars.copy(); raw["timestamp"] = raw.timestamp.dt.tz_localize(None)
    raw.attrs = raw_spot_provenance("15m", provider="synthetic", feed="synthetic")
    surface = pd.DataFrame({"underlying": ["SPY"], "date": pd.to_datetime(["2025-01-01"]),
                           "available_at": ["2025-01-01T21:00:00Z"]})
    surface.attrs = {"surface_schema_version": RAW_SPOT_SCHEMA_VERSION, "option_strike_spot_basis": "raw"}
    ctx = surface.assign(market_iv=.2, rv_iv_spread=.01, beta_60d=1.)
    chain = pd.DataFrame({"symbol": ["SPY"], "contract": ["SPY250103C00100000"],
                         "first_observed_at": ["2025-01-01T14:30:00Z"], "available_at": ["2025-01-01T14:30:01Z"]})
    historical_policy = json.loads(bundle.path.read_text())["tick_feature_policy"]
    historical_policy["max_quote_age_ns"] = 30_000_000_000
    original = json.loads(bundle.path.read_text()); original["tick_feature_policy"] = historical_policy
    bundle.path.write_text(json.dumps(original))
    mapping = {"historical_policy_sha256": hashlib.sha256(canonical(historical_policy).encode()).hexdigest(),
               "condition_namespace": "alpaca_opra_string", "allowed_trade_conditions": ["@"],
               "references": [{"path": str(bundle.evidence), "sha256": sha256(bundle.evidence)}]}
    document = {"schema": "v6-live-snapshot-v1", "captured_at": "2025-01-02T14:45:02Z",
        "parity_policy": "verified", "expanded_inputs": {"path": str(bundle.path), "sha256": sha256(bundle.path)},
        "bars": save("bars.parquet", bars), "raw_bars": save("raw.parquet", raw),
        "surface": save("surface.parquet", surface), "daily_context": save("daily.parquet", ctx),
        "chain": save("chain.parquet", chain), "condition_mapping": save("mapping.json", mapping), "tick_windows": {}}
    manifest = tmp_path / "snapshot.json"; manifest.write_text(json.dumps(document))
    return manifest, document


def test_live_snapshot_binds_raw_bars_chain_and_all_transitive_files(snapshot):
    path, doc = snapshot
    live = LiveSnapshot(path, sha256(path), now="2025-01-02T14:45:03Z")
    bars = live.bar_loader("SPY")
    assert "v6_tradingview_context" in bars.attrs
    assert live.candidate_kwargs({"SPY": bars})["raw_close_by_symbol"]["SPY"].iloc[0] == 100
    source = path.parent / doc["raw_bars"]["path"]
    source.write_bytes(b"modified")
    with pytest.raises(ValueError, match="source changed"):
        live.assert_unchanged()


def test_stale_snapshot_and_missing_receipt_coverage_are_refused(snapshot):
    path, _ = snapshot
    with pytest.raises(ValueError, match="stale"):
        LiveSnapshot(path, sha256(path), now="2025-01-03T14:45:03Z")
    live = LiveSnapshot(path, sha256(path), now="2025-01-02T14:45:03Z")
    with pytest.raises(ValueError, match="pre-subscribe"):
        live.tick_features({"contract": "SPY250103C00100000", "request_id": "absent"})


def test_chain_requires_previous_date_actual_availability():
    frame = pd.DataFrame({"symbol": ["SPY"]*2, "contract": ["SPY260918C00650000", "SPY260918C00655000"],
        "first_observed_at": ["2026-09-13T20:00:00Z"]*2,
        "available_at": ["2026-09-13T20:00:01Z", "2026-09-14T13:00:00Z"]})
    chain = SnapshotChain(frame, now=pd.Timestamp("2026-09-14T14:00:00Z"))
    from datetime import date
    contracts = chain.get_chain("SPY", right="C", expiration_gte=date(2026,9,18),
                               expiration_lte=date(2026,9,18), as_of=date(2026,9,13))
    assert [c.strike for c in contracts] == [650.]


def test_receipt_features_exclude_late_and_unmapped_trades_and_verify_raw_bytes(snapshot):
    from nn_meta.live.feeds.tick_journal import normalize_message
    from nn_meta.option_tick_dataset import NUMERIC_FEATURES
    path, doc = snapshot
    contract = "SPY250103C00100000"
    start, end = pd.Timestamp("2025-01-02T14:30:00Z").value, pd.Timestamp("2025-01-02T14:45:00Z").value
    request = dict(symbol="SPY", contract=contract, window_start_ns=start,
                   window_end_ns=end, decision_close_ns=end)
    request["request_id"] = request_id(request)
    ticks = []
    for raw, at in [
        ({"T":"q","S":contract,"t":"2025-01-02T14:44:40Z","bp":1.,"ap":1.02,"bs":10,"as":10}, end-19_000_000_000),
        ({"T":"t","S":contract,"t":"2025-01-02T14:44:42Z","p":1.02,"s":2,"c":["@"]}, end-17_000_000_000),
        ({"T":"t","S":contract,"t":"2025-01-02T14:44:43Z","p":2.,"s":100,"c":["X"]}, end-16_000_000_000),
        ({"T":"t","S":contract,"t":"2025-01-02T14:44:44Z","p":3.,"s":100,"c":["@"]}, end+1)]:
        ticks.append(normalize_message(raw, received_at_ns=at))
    tick_path = path.parent / "ticks.jsonl"
    tick_path.write_text("\n".join(json.dumps(r) for r in ticks)+"\n")
    coverage = dict(schema="v6-receipt-coverage-v1", contract=contract, availability_basis="receipt",
        status="reviewed_complete_capture", reviewed_by="synthetic test only", start_ns=start,
        end_ns=end, gap_count=0, journal_errors=0, ticks_sha256=sha256(tick_path),
        references=[{"path": "synthetic-capture.csv", "sha256": sha256(path.parent / "synthetic-capture.csv")}])
    coverage_path = path.parent / "coverage.json"; coverage_path.write_text(json.dumps(coverage))
    doc["tick_windows"][request["request_id"]] = {
        "coverage": {"path": coverage_path.name, "sha256": sha256(coverage_path)},
        "ticks": {"path": tick_path.name, "sha256": sha256(tick_path)}}
    path.write_text(json.dumps(doc))
    live = LiveSnapshot(path, sha256(path), now="2025-01-02T14:45:03Z")
    features = live.tick_features(request)
    assert features["eligible_contract_volume"] == 2
    assert features["reported_contract_volume"] == 102
    assert set(NUMERIC_FEATURES) <= set(features)
    live._ticks[str(tick_path)][0]["bid_price"] = .1
    with pytest.raises(ValueError, match="differ from raw"):
        live.tick_features(request)


def test_snapshot_seal_preserves_inputs_and_refuses_overwrite(snapshot, tmp_path):
    from scripts.seal_v6_live_snapshot import seal
    path, doc = snapshot
    original = path.read_bytes()
    output = tmp_path / "sealed"
    args = dict(training_inputs=doc["expanded_inputs"]["path"],
                training_sha256=doc["expanded_inputs"]["sha256"], now="2025-01-02T14:45:03Z")
    digest = seal(path, output, **args)
    assert digest == sha256(output / "snapshot.json")
    assert path.read_bytes() == original
    assert json.loads((output / "complete.json").read_text())["scanner_promotion"] is False
    with pytest.raises(ValueError, match="fresh"):
        seal(path, output, **args)
