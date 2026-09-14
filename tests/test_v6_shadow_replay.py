import json

import pandas as pd

from nn_meta.live.v6_shadow import ShadowStore
from nn_meta.training_jobs import sha
from scripts.replay_v6_shadow import run


def test_recorded_forward_signal_quote_and_frozen_exit_replay(tmp_path):
    from types import SimpleNamespace
    store = ShadowStore(tmp_path / "shadow", {"bundle": {"mode": "ev"},
        "portfolio": {"max_concurrent": 1, "position_fraction": 1.0}})
    contract = "SPY260918C00650000"
    batch = pd.DataFrame([dict(symbol="SPY", strategy="ma", dte=5,
        entry_ts=pd.Timestamp("2026-09-14T14:30:00Z"), decision_contract=contract)])
    store.record(batch, scores=[.6], decisions=[.1], bundle=SimpleNamespace(mode="ev", threshold=.05),
        spec={"symbols": {"SPY": {"strategies": {"ma": {"dte": 5}}}}},
        observed_at="2026-09-14T14:45:02Z", evidence={"synthetic": True})
    times = pd.to_datetime(["2026-09-14T14:45:03Z", "2026-09-14T14:46:02Z"], utc=True)
    tape = pd.DataFrame(dict(contract=contract, quote_ts=times, available_at=times,
                             bid=[1.,1.5], ask=[1.02,1.52], bid_size=10, ask_size=10))
    store.record_quotes(tape, observed_at="2026-09-14T14:46:03Z", evidence={"synthetic": True})
    with store.connect() as db:
        key = db.execute("SELECT key FROM candidates").fetchone()[0]
    legs = tmp_path / "legs.parquet"
    pd.DataFrame([dict(trade_id=key, leg_index=0, contract=contract,
        entry_decision_ts="2026-09-14T14:45:02Z", exit_decision_ts="2026-09-14T14:46:02Z",
        exit_observed_at="2026-09-14T14:46:02Z", expiration_ts="2026-09-18T20:00:00Z")]).to_parquet(legs,index=False)
    receipt = tmp_path / "exit_receipt.json"; receipt.write_text('{"test":"synthetic frozen exit"}')
    ev = tmp_path / "evidence.json"
    ev.write_text(json.dumps({"legs_sha256": sha(legs), "exit_policy": "frozen-mechanical-signals",
                             "source_receipts": [{"path": str(receipt), "sha256": sha(receipt)}]}))
    result = run(store.path, legs, ev, sha(ev), tmp_path / "replay")
    assert result["scanner_promotion"] is False
    left, right = [result["policies"][side]["scenarios"]["quotes_base"] for side in ["candidate", "baseline"]]
    assert left["total_return"] == right["total_return"]
    assert left["n_positions"] == 1 and left["independent_ledger_match"]
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 1
