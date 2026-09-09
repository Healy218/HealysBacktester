"""Durable, atomic live-scanner state.

The live scanner must survive restarts without double-alerting, losing a
notification, or corrupting its paper-trade record.  Every mutation is written
through a temp file + ``os.replace`` (atomic on POSIX), and every object rebuilds
its state from disk on construction, so a crash between any two writes leaves a
consistent file.  Drift (PSI) and health snapshots round out the live-readiness
telemetry.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
import fcntl
import shutil
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def atomic_write_json(path: Path, obj) -> None:
    """Write JSON via a same-directory temp file and atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def state_lock(path):
    """Serialize a complete read/modify/write transaction on POSIX."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def serialized(path_for_call):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with state_lock(path_for_call(*args, **kwargs)):
                return fn(*args, **kwargs)
        return wrapped
    return decorate


@contextmanager
def preview_state(source):
    """Snapshot live state into an ephemeral directory for a read-only preview."""
    with tempfile.TemporaryDirectory(prefix="live-preview-") as tmp:
        with state_lock(Path(source) / ".live.lock"):
            for path in Path(source).glob("*.json"):
                shutil.copy2(path, Path(tmp) / path.name)
        yield Path(tmp)


def refreshed(attribute, default_factory):
    """Reload under a per-file lock before mutation, including stale instances."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            with state_lock(self.path.with_name(self.path.name + ".lock")):
                setattr(self, attribute, _load_json(self.path, default_factory()))
                return fn(self, *args, **kwargs)
        return wrapped
    return decorate


class AlertState:
    """Idempotent alert dedupe keyed by a caller-chosen string."""

    def __init__(self, path):
        self.path = Path(path)
        self._seen: dict[str, str] = _load_json(self.path, {})

    def seen(self, key: str) -> bool:
        return key in self._seen

    @refreshed("_seen", dict)
    def mark(self, key: str, *, ts: datetime | None = None) -> bool:
        """Record ``key``; return True only the first time (alert iff True)."""
        if key in self._seen:
            return False
        self._seen[key] = (ts or _utcnow()).isoformat()
        atomic_write_json(self.path, self._seen)
        return True


class Outbox:
    """At-least-once notification outbox: enqueue -> (send) -> acknowledge.

    Unacknowledged entries are replayed after a restart, and an idempotency
    ``key`` prevents the same logical notification being enqueued twice.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._entries: list[dict] = _load_json(self.path, [])

    @refreshed("_entries", list)
    def enqueue(self, payload: dict, *, key: str | None = None) -> str:
        if key is not None:
            existing = next((e for e in self._entries if e.get("key") == key), None)
            if existing is not None:
                return existing["id"]
        entry = {"id": uuid.uuid4().hex, "key": key, "payload": payload,
                 "status": "pending", "ts": _utcnow().isoformat()}
        self._entries.append(entry)
        atomic_write_json(self.path, self._entries)
        return entry["id"]

    def unacked(self) -> list[dict]:
        """Entries still needing delivery (pending or sent but not acked)."""
        return [e for e in self._entries if e["status"] != "acked"]

    @refreshed("_entries", list)
    def _set_status(self, entry_id: str, status: str) -> None:
        for e in self._entries:
            if e["id"] == entry_id:
                e["status"] = status
                atomic_write_json(self.path, self._entries)
                return
        raise KeyError(entry_id)

    def mark_sent(self, entry_id: str) -> None:
        self._set_status(entry_id, "sent")

    def acknowledge(self, entry_id: str) -> None:
        self._set_status(entry_id, "acked")


class PaperLedger:
    """Append-only paper-trade ledger with realized/unrealized P&L."""

    def __init__(self, path):
        self.path = Path(path)
        self._trades: list[dict] = _load_json(self.path, [])

    @refreshed("_trades", list)
    def open(self, trade_id: str, symbol: str, entry_ts, price: float,
             qty: float = 1.0, **extra) -> None:
        """``extra`` (2026-09-09): the resolved OCC ``contract`` and its
        ``entry_mid`` at alert time, so the paper record names the option
        actually alerted, not just the underlying's spot."""
        if any(t["trade_id"] == trade_id for t in self._trades):
            raise ValueError(f"trade_id already recorded: {trade_id}")
        self._trades.append({"trade_id": trade_id, "symbol": symbol,
                             "entry_ts": str(entry_ts), "entry_price": float(price),
                             "qty": float(qty), "exit_ts": None, "exit_price": None,
                             **{k: v for k, v in extra.items() if v is not None}})
        atomic_write_json(self.path, self._trades)

    @refreshed("_trades", list)
    def close(self, trade_id: str, exit_ts, price: float) -> None:
        for t in self._trades:
            if t["trade_id"] == trade_id and t["exit_price"] is None:
                t["exit_ts"], t["exit_price"] = str(exit_ts), float(price)
                atomic_write_json(self.path, self._trades)
                return
        raise KeyError(f"no open trade {trade_id}")

    def open_positions(self) -> list[dict]:
        return [t for t in self._trades if t["exit_price"] is None]

    def realized_pnl(self) -> float:
        return float(sum((t["exit_price"] - t["entry_price"]) * t["qty"]
                         for t in self._trades if t["exit_price"] is not None))

    def equity(self, start_cash: float, marks: dict[str, float] | None = None) -> float:
        marks = marks or {}
        unrealized = sum((marks.get(t["symbol"], t["entry_price"]) - t["entry_price"])
                         * t["qty"] for t in self.open_positions())
        return float(start_cash + self.realized_pnl() + unrealized)


def population_stability_index(expected, actual, *, bins: int = 10,
                               eps: float = 1e-6) -> float:
    """PSI drift between a reference and current sample (0 = identical)."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    exp_frac = np.histogram(expected, edges)[0] / max(len(expected), 1)
    act_frac = np.histogram(actual, edges)[0] / max(len(actual), 1)
    exp_frac = np.clip(exp_frac, eps, None)
    act_frac = np.clip(act_frac, eps, None)
    return float(np.sum((act_frac - exp_frac) * np.log(act_frac / exp_frac)))


def health_snapshot(*, last_run_ts: datetime, now: datetime | None = None,
                    error_count: int = 0, scanned: int = 0, alerted: int = 0,
                    max_staleness: timedelta = timedelta(minutes=30)) -> dict:
    """Scanner health: staleness, throughput, and an overall healthy flag."""
    now = now or _utcnow()
    age = now - last_run_ts
    stale = age > max_staleness
    return {"age_seconds": age.total_seconds(), "stale": stale,
            "error_count": int(error_count), "scanned": int(scanned),
            "alerted": int(alerted), "healthy": (not stale) and error_count == 0}
