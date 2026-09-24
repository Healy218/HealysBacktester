"""Read-only, exact-identity export of matured V6 paper position returns."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
from options.paper_pricing import MIDPOINT_POLICY

from .forward import _sha256


class PaperOutcomeError(ValueError):
    """The paper ledger cannot support a trustworthy outcome export."""


def _source_hashes(database: Path) -> dict[str, str | None]:
    return {name: _sha256(path) if path.is_file() else None
            for name, path in (("database", database), ("wal", Path(str(database) + "-wal")))}


def _utc(value: object, *, require_aware: bool) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise PaperOutcomeError("invalid paper timestamp")
    if stamp.tzinfo is None:
        if require_aware:
            raise PaperOutcomeError("paper close timestamp must be timezone-qualified")
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def export_v6_paper_outcomes(database: Path, output_dir: Path, *, through: str) -> dict:
    """Export only fully closed positions; never infer outcomes from cycles.

    The source SQLite database is opened query-only. A source/WAL hash fence
    refuses a concurrent ledger change; a repeat export must use a new empty
    destination, preserving the first publication as historical evidence.
    """
    cutoff = date.fromisoformat(through)
    database = Path(database).resolve()
    output_dir = Path(output_dir).resolve()
    if not database.is_file():
        raise PaperOutcomeError(f"V6 paper database is unavailable: {database}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise PaperOutcomeError("outcome destination must be new and empty")
    before = _source_hashes(database)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        rows = db.execute("SELECT key,symbol,state,payload FROM positions ORDER BY key").fetchall()
        db.execute("COMMIT")
    after = _source_hashes(database)
    if before != after:
        raise PaperOutcomeError("paper database changed during export; retry from a new snapshot")

    outcomes, evidence = [], []
    for key, symbol, state, payload in rows:
        if state != "closed":
            continue
        try:
            position = json.loads(payload)
            entry = _utc(position["entry_ts"], require_aware=False)
            strategy = position["strategy"]
            dte = position["dte"]
            factor = float(position["return_factor"])
            legs = position["legs"]
        except (KeyError, TypeError, ValueError) as exc:
            raise PaperOutcomeError(f"invalid closed paper position: {key}") from exc
        expected_key = f"v6|{symbol}|{strategy}|{entry.tz_localize(None).isoformat()}"
        if (position.get("key") != key or key != expected_key or
                position.get("symbol") != symbol or position.get("state") != "closed" or
                not isinstance(dte, int) or dte < 1 or not isinstance(legs, list) or not legs or
                not math.isfinite(factor) or factor < 0):
            raise PaperOutcomeError(f"closed paper position identity/return is inconsistent: {key}")
        last_leg = legs[-1]
        if not isinstance(last_leg, dict):
            raise PaperOutcomeError(f"invalid paper leg: {key}")
        exit_quote = last_leg.get("exit_quote")
        if position.get("pricing_policy") != MIDPOINT_POLICY:
            raise PaperOutcomeError(f"closed paper position has unsupported pricing policy: {key}")
        if not isinstance(exit_quote, dict):
            raise PaperOutcomeError(f"paper close evidence is incomplete: {key}")
        clocks = [position.get("trigger_at"), exit_quote.get("received_at")]
        if any(value is None for value in clocks):
            raise PaperOutcomeError(f"paper close evidence is incomplete: {key}")
        # Normal settlement follows its trigger; a cash exit after a roll
        # instead follows the last settled leg. The later clock is terminal.
        closed_at = max(_utc(value, require_aware=True) for value in clocks)
        if closed_at < entry:
            raise PaperOutcomeError(f"paper close predates entry: {key}")
        if closed_at.date() > cutoff:
            continue
        outcome = {"symbol": symbol, "strategy": strategy, "dte": dte,
                   "entry_ts": entry, "net_return": factor - 1}
        outcomes.append(outcome)
        evidence.append({"key": key, "entry_ts": entry.isoformat(),
                         "closed_at": closed_at.isoformat(), "dte": dte,
                         "pricing_policy": MIDPOINT_POLICY,
                         "return_factor": factor,
                         "payload_sha256": hashlib.sha256(payload.encode()).hexdigest()})
    frame = pd.DataFrame(outcomes, columns=["symbol", "strategy", "dte", "entry_ts", "net_return"])
    if frame.empty:
        frame = frame.astype({"symbol": "string", "strategy": "string", "dte": "int64",
                             "entry_ts": "datetime64[ns, UTC]", "net_return": "float64"})
    else:
        frame = frame.sort_values(["entry_ts", "symbol", "strategy", "dte"], kind="stable")
        if frame.duplicated(["symbol", "strategy", "dte", "entry_ts"]).any():
            raise PaperOutcomeError("duplicate closed paper candidate identities")
    output_dir.mkdir(parents=True, exist_ok=True)
    outcome_path = output_dir / "outcomes.parquet"
    evidence_path = output_dir / "position-evidence.jsonl"
    frame.to_parquet(outcome_path, index=False)
    evidence_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in evidence))
    manifest = {"schema": "incubator-v6-paper-outcomes-v1", "through": through,
                "source_database": str(database), "source_hashes": before,
                "closed_positions_seen": sum(state == "closed" for _, _, state, _ in rows),
                "exported_rows": len(frame), "read_only": True,
                "files": {"outcomes.parquet": _sha256(outcome_path),
                          "position-evidence.jsonl": _sha256(evidence_path)}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest
