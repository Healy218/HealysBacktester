from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from incubator.live_features import publish_v6_features
from incubator.outcomes import join_matured_outcomes
from incubator.v6_paper_outcomes import PaperOutcomeError, export_v6_paper_outcomes
from options.paper_pricing import MIDPOINT_POLICY


def _paper_db(path: Path, *, corrupt: bool = False) -> Path:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE positions(key TEXT PRIMARY KEY,symbol TEXT,state TEXT,payload TEXT)")
        for symbol, state, factor in (("SPY", "closed", 1.25), ("QQQ", "open", 1.0)):
            key = f"v6|{symbol}|ma|2026-09-21T19:15:00"
            position = {"key": "wrong" if corrupt and symbol == "SPY" else key,
                        "symbol": symbol, "strategy": "ma", "dte": 5,
                        "entry_ts": "2026-09-21T19:15:00", "state": state,
                        "pricing_policy": MIDPOINT_POLICY,
                        "return_factor": factor, "trigger_at": "2026-09-22T19:00:00+00:00",
                        "legs": [{"exit_quote": {"received_at": "2026-09-22T19:01:00+00:00"}}]}
            db.execute("INSERT INTO positions VALUES (?,?,?,?)",
                       (key, symbol, state, json.dumps(position)))
    return path


def test_closed_v6_paper_export_and_exact_join(tmp_path: Path) -> None:
    database = _paper_db(tmp_path / "paper.sqlite3")
    source = tmp_path / "candidates.parquet"
    pd.DataFrame({"symbol": ["SPY", "QQQ"], "strategy": ["ma", "ma"],
                  "dte": [5, 5], "entry_ts": ["2026-09-21T19:15:00Z"] * 2,
                  "x": [1.0, 2.0]}).to_parquet(source)
    publish_v6_features([source], tmp_path / "features", {"features": ["x"]}, "2026-09-21")
    result = export_v6_paper_outcomes(database, tmp_path / "outcomes", through="2026-09-22")
    assert result["closed_positions_seen"] == result["exported_rows"] == 1
    assert result["source_hashes"]["database"]
    outcome = pd.read_parquet(tmp_path / "outcomes" / "outcomes.parquet")
    assert outcome["net_return"].tolist() == [0.25]
    joined = join_matured_outcomes(tmp_path / "features", [tmp_path / "outcomes" / "outcomes.parquet"],
                                   tmp_path / "ready")
    assert joined["matched_rows"] == joined["pending_rows"] == 1
    with pytest.raises(PaperOutcomeError, match="new and empty"):
        export_v6_paper_outcomes(database, tmp_path / "outcomes", through="2026-09-22")


def test_v6_paper_export_never_uses_future_or_invalid_close(tmp_path: Path) -> None:
    database = _paper_db(tmp_path / "paper.sqlite3")
    early = export_v6_paper_outcomes(database, tmp_path / "early", through="2026-09-21")
    assert early["closed_positions_seen"] == 1
    assert early["exported_rows"] == 0
    bad = _paper_db(tmp_path / "bad.sqlite3", corrupt=True)
    with pytest.raises(PaperOutcomeError, match="identity/return"):
        export_v6_paper_outcomes(bad, tmp_path / "bad-out", through="2026-09-22")
    assert not (tmp_path / "bad-out").exists()


def test_v6_paper_export_rejects_legacy_pricing_and_missing_exit_quote(tmp_path: Path) -> None:
    database = _paper_db(tmp_path / "paper.sqlite3")
    with sqlite3.connect(database) as db:
        row = db.execute("SELECT payload FROM positions WHERE symbol='SPY'").fetchone()[0]
        position = json.loads(row)
        position["pricing_policy"] = "legacy-ask-bid"
        db.execute("UPDATE positions SET payload=? WHERE symbol='SPY'", (json.dumps(position),))
    with pytest.raises(PaperOutcomeError, match="pricing policy"):
        export_v6_paper_outcomes(database, tmp_path / "legacy", through="2026-09-22")
    with sqlite3.connect(database) as db:
        position["pricing_policy"] = MIDPOINT_POLICY
        position["legs"][-1]["exit_quote"] = None
        db.execute("UPDATE positions SET payload=? WHERE symbol='SPY'", (json.dumps(position),))
    with pytest.raises(PaperOutcomeError, match="close evidence"):
        export_v6_paper_outcomes(database, tmp_path / "missing", through="2026-09-22")
