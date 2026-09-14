"""Durable, isolated V6 observations. No notifier or broker dependency."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from nn_meta.live.state import atomic_write_json


def json_value(value):
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return None
        raise ValueError("infinity in shadow observation")
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def canonical(value):
    return json.dumps(json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


class ShadowStore:
    def __init__(self, root, scope):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "observations.sqlite3"
        self.scope = scope
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS scope (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS candidates (key TEXT PRIMARY KEY, signal_key TEXT NOT NULL,
                    observed_at TEXT NOT NULL, candidate INTEGER NOT NULL, baseline INTEGER NOT NULL,
                    payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS passes (id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL,
                    status TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quotes (key TEXT PRIMARY KEY, observed_at TEXT NOT NULL, payload TEXT NOT NULL);
            """)
            expected = canonical(scope)
            previous = db.execute("SELECT payload FROM scope WHERE id=1").fetchone()
            if previous and previous[0] != expected:
                raise ValueError("shadow model/policy changed; start a fresh shadow scope")
            db.execute("INSERT OR IGNORE INTO scope VALUES (1, ?)", (expected,))

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def record(self, batch, *, scores, decisions, bundle, spec, observed_at, evidence):
        scores, decisions = np.asarray(scores), np.asarray(decisions)
        if (scores.shape != (len(batch),) or decisions.shape != scores.shape
                or not np.isfinite(scores).all() or not np.isfinite(decisions).all()):
            raise ValueError("shadow predictions must be finite and aligned")
        if ((scores < 0) | (scores > 1)).any():
            raise ValueError("shadow probabilities are outside [0,1]")
        frame = batch.assign(score=scores, decision=decisions).reset_index(drop=True)
        accepted = frame.decision >= bundle.threshold
        if bundle.mode in {"rank", "ev"}:
            best = frame.loc[accepted].sort_values("decision", ascending=False) \
                .drop_duplicates(["symbol", "strategy", "entry_ts"]).index
            accepted &= frame.index.isin(best)
        elif bundle.mode != "filter":
            raise ValueError("unsupported shadow policy")
        written = 0
        with self.connect() as db:
            for i, row in frame.iterrows():
                signal_key = f"{row.symbol}|{row.strategy}|{pd.Timestamp(row.entry_ts).isoformat()}"
                key = f"{signal_key}|{int(row.dte)}"
                baseline = int(row.dte) == int(spec["symbols"][row.symbol]["strategies"][row.strategy]["dte"])
                payload = canonical({"row": row.to_dict(), "evidence": evidence,
                    "signal_close_ts": (pd.Timestamp(row.entry_ts) + pd.Timedelta(minutes=15)).isoformat(),
                    "candidate_selected": bool(accepted.iloc[i]), "baseline_selected": baseline,
                    "selection_basis": "threshold/DTE selection before portfolio capacity and executable fills"})
                # First observed prediction wins permanently. A retry/new snapshot
                # cannot rewrite a past decision with later data.
                cursor = db.execute("INSERT OR IGNORE INTO candidates VALUES (?,?,?,?,?,?)",
                    (key, signal_key, pd.Timestamp(observed_at).isoformat(), int(accepted.iloc[i]), int(baseline), payload))
                written += cursor.rowcount
        return written

    def record_quotes(self, quotes, *, observed_at, evidence):
        from nn_meta.execution_validation import QuoteTape, utc
        tape = QuoteTape(quotes)
        now = utc(observed_at)
        with self.connect() as db:
            for frame in tape.groups.values():
                for row in frame.to_dict("records"):
                    if row["available_at"] > now:
                        raise ValueError("shadow quote was unavailable at observation")
                    identity = canonical({k: row[k] for k in ("contract", "available_at")})
                    key = hashlib.sha256(identity.encode()).hexdigest()
                    payload = canonical({"quote": row, "evidence": evidence})
                    previous = db.execute("SELECT payload FROM quotes WHERE key=?", (key,)).fetchone()
                    if previous and json.loads(previous[0])["quote"] != json.loads(payload)["quote"]:
                        raise ValueError("conflicting forward quote identity")
                    db.execute("INSERT OR IGNORE INTO quotes VALUES (?,?,?)", (key, now.isoformat(), payload))

    def finish(self, *, now, status, summary):
        with self.connect() as db:
            db.execute("INSERT INTO passes(observed_at,status,payload) VALUES (?,?,?)",
                       (pd.Timestamp(now).isoformat(), status, canonical(summary)))
        report = self.summary()
        atomic_write_json(self.root / "summary.json", report)
        return report

    def summary(self):
        with self.connect() as db:
            count, signals, selected, baseline, first, last = db.execute(
                "SELECT count(*), count(DISTINCT signal_key), coalesce(sum(candidate),0), "
                "coalesce(sum(baseline),0), min(observed_at), max(observed_at) FROM candidates").fetchone()
            passes, errors = db.execute("SELECT count(*), coalesce(sum(status != 'ok'),0) FROM passes").fetchone()
            last_pass = db.execute("SELECT observed_at FROM passes ORDER BY id DESC LIMIT 1").fetchone()
            quotes = db.execute("SELECT count(*) FROM quotes").fetchone()[0]
        return {"schema": "v6-shadow-summary-v1", "research_only": True, "scanner_promotion": False,
            "scope_sha256": hashlib.sha256(canonical(self.scope).encode()).hexdigest(),
            "bundle_sha256": self.scope.get("artifacts", {}).get("ensemble_config.json"),
            "candidate_rows": count, "signals": signals, "candidate_selections": selected,
            "baseline_selections": baseline, "first_observed_at": first, "last_observed_at": last,
            "passes": passes, "failed_passes": errors, "quote_observations": quotes,
            "last_pass_at": last_pass[0] if last_pass else None,
            "realized_return": None, "execution_status": "awaiting frozen exit plans and quote replay",
            "limitations": ["Signals are observations, not executed positions or realized returns.",
                            "TradingView parity, receipt/SIP parity and execution validation remain required."]}
