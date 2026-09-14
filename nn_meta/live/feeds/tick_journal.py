"""Append-only Alpaca OPRA observations, partitioned by UTC receipt day.

Use the SDK's ``raw_data=True`` mode: model construction converts msgpack
nanoseconds to Python datetime microseconds and discards unknown fields. The
raw payload below is a lossless *reserialization of the decoded message*, not
the original websocket packet. Receipt time means entry to the SDK callback,
after decoding/dispatch, and does not establish continuous feed coverage.

``sip_timestamp`` is an adapter alias for Alpaca's documented ``t`` field;
Alpaca calls this a timestamp, without specifying a separate SIP clock. No
vendor sequence, correction message, or aggressor side is synthesized.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import math
import os
import re
import time
import uuid
from datetime import datetime, timezone
from numbers import Integral
from pathlib import Path

import msgpack
import pandas as pd

SCHEMA = "alpaca-option-ticks-v1"
RECEIPT_BASIS = "sdk_handler_entry_after_decode"
_OCC = re.compile(r"[A-Z][A-Z0-9.]*[0-9]{6}[CP][0-9]{8}\Z")


class TickJournalError(ValueError):
    pass


def _ns(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise TickJournalError("timestamp must be a nonnegative integer nanosecond value")
    return int(value)


def canonical_contract(value: str) -> str:
    if not isinstance(value, str):
        raise TickJournalError("contract must be a string")
    value = value.strip().upper().removeprefix("O:")
    if not _OCC.fullmatch(value):
        raise TickJournalError("contract must be an OCC option symbol")
    try:
        datetime.strptime(value[-15:-9], "%y%m%d")
    except ValueError as exc:
        raise TickJournalError("invalid OCC expiry date") from exc
    return value


def event_timestamp_ns(value) -> int:
    """Preserve msgpack and RFC3339 nanoseconds; never accept floating epochs."""
    if isinstance(value, msgpack.Timestamp):
        return _ns(value.seconds * 1_000_000_000 + value.nanoseconds)
    if not isinstance(value, (str, datetime, pd.Timestamp)):
        raise TickJournalError("unsupported or missing event timestamp")
    try:
        stamp = pd.Timestamp(value)
        if pd.isna(stamp) or stamp.tzinfo is None:
            raise TickJournalError("event timestamp must be timezone aware")
        return _ns(stamp.value)
    except (ValueError, OverflowError) as exc:
        raise TickJournalError("invalid event timestamp") from exc


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def normalize_message(raw: dict, *, received_at_ns: int) -> dict:
    """Extract common fields without changing or filtering the preserved raw tick."""
    received = _ns(received_at_ns)
    if not isinstance(raw, dict) or raw.get("T") not in ("q", "t"):
        raise TickJournalError("expected a raw quote or trade message")
    contract = canonical_contract(raw.get("S"))
    payload = msgpack.packb(raw, use_bin_type=True)
    record = {
        "schema": SCHEMA, "provider": "alpaca", "feed": "opra",
        "condition_namespace": "alpaca_opra_string", "model_admission": False,
        "kind": "quotes" if raw["T"] == "q" else "trades", "contract": contract,
        "event_timestamp_basis": "alpaca_t_no_separate_sip_clock_asserted",
        "available_at_ns": received, "received_at_ns": received,
        "receipt_basis": RECEIPT_BASIS,
        "raw_msgpack_b64": base64.b64encode(payload).decode("ascii"),
        "raw_msgpack_sha256": hashlib.sha256(payload).hexdigest(),
        "raw_encoding": "decoded_message_reserialized_msgpack",
    }
    try:
        event = event_timestamp_ns(raw.get("t"))
    except TickJournalError as exc:
        event = None
        record["normalization_error"] = str(exc)
    record.update(event_timestamp_ns=event, sip_timestamp=event,
                  receipt_precedes_event=event is not None and received < event)
    conditions = raw.get("c")
    record["conditions"] = ([conditions] if isinstance(conditions, str)
                            else conditions if isinstance(conditions, list)
                            and all(isinstance(code, (str, int)) and not isinstance(code, bool)
                                    for code in conditions) else None)
    record["conditions_available"] = "c" in raw
    # Preserve unexpected condition representations in raw; do not misclassify
    # them as ordinary trades in the normalized view.
    if conditions is not None and not isinstance(conditions, (str, list)):
        record["conditions"] = None
    if raw["T"] == "q":
        for source, target in (("bp", "bid_price"), ("ap", "ask_price"),
                               ("bs", "bid_size"), ("as", "ask_size")):
            record[target] = _number(raw.get(source))
    else:
        record.update(price=_number(raw.get("p")), size=_number(raw.get("s")),
                      correction=raw.get("correction", 0),
                      correction_available="correction" in raw)
    # These fields are not documented for the current OPRA stream. Only carry
    # their unambiguous long names if a future SDK supplies them.
    if "sequence_number" in raw:
        record["sequence_number"] = raw["sequence_number"]
    return record


class TickJournal:
    """One writer; bounded distinct contract admissions per receipt day.

    Admission records are fsynced before ticks can be appended. Existing days
    retain their admission budget across reconnects/restarts. Ticks are written
    immediately to append-only files and fsynced by ``flush``. Disk errors must
    be exposed by the caller; counters and control events never certify gap-free
    capture. A crash with a partial final line refuses further appends until
    an operator preserves/repairs that incomplete capture explicitly.
    """

    def __init__(self, root: Path | str, *, max_contracts: int = 1000):
        if isinstance(max_contracts, bool) or not isinstance(max_contracts, int) or not 1 <= max_contracts <= 1000:
            raise TickJournalError("max_contracts must be an integer from 1 to 1000")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_contracts = max_contracts
        self.capture_id = uuid.uuid4().hex
        self.sequence = 0
        self.rows = {"quotes": 0, "trades": 0}
        self.skipped_contract_ticks = 0
        self.normalization_errors = 0
        self.last_received_at_ns = None
        self.last_event_timestamp_ns = None
        self.last_fsync_at_ns = None
        self.fsynced_rows = 0
        self._desired: set[str] = set()
        self._admitted: set[str] = set()
        self._day = None
        self._files: dict[str, int] = {}
        self._lock = os.open(self.root / ".writer.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self._lock)
            self._lock = None
            raise TickJournalError("another writer owns this tick journal") from exc

    @staticmethod
    def _append(fd, record):
        data = (json.dumps(record, separators=(",", ":"), sort_keys=True,
                           allow_nan=False) + "\n").encode()
        while data:
            written = os.write(fd, data)
            if written <= 0:
                raise OSError("journal write made no progress")
            data = data[written:]

    def _open(self, name):
        if name not in self._files:
            path = self.root / self._day / f"{name}.jsonl"
            if path.exists() and path.stat().st_size:
                with path.open("rb") as check:
                    check.seek(-1, os.SEEK_END)
                    if check.read(1) != b"\n":
                        raise TickJournalError(f"incomplete journal tail: {path}")
            self._files[name] = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        return self._files[name]

    def _rotate(self, received_at_ns):
        if self._lock is None:
            raise TickJournalError("journal is closed")
        day = datetime.fromtimestamp(_ns(received_at_ns) // 1_000_000_000, timezone.utc).date().isoformat()
        if day == self._day:
            return
        self.flush()
        for fd in self._files.values():
            os.close(fd)
        self._files.clear()
        path = self.root / day
        path.mkdir(parents=True, exist_ok=True)
        admitted = set()
        if (path / "contracts.jsonl").exists():
            if (path / "contracts.jsonl").stat().st_size:
                with (path / "contracts.jsonl").open("rb") as source:
                    source.seek(-1, os.SEEK_END)
                    if source.read(1) != b"\n":
                        raise TickJournalError("incomplete admission journal tail")
            with (path / "contracts.jsonl").open() as source:
                for line in source:
                    record = json.loads(line)
                    if record.get("schema") != SCHEMA:
                        raise TickJournalError("unknown admission schema")
                    admitted.add(canonical_contract(record["contract"]))
        if len(admitted) > self.max_contracts:
            raise TickJournalError("existing daily contract set exceeds configured limit")
        self._day, self._admitted = day, admitted
        self._control("writer_started", received_at_ns,
                      daily_contract_limit=self.max_contracts, coverage_complete=False)

    def _control(self, kind, received, **fields):
        self._append(self._open("control"), {
            "schema": SCHEMA, "capture_id": self.capture_id, "event": kind,
            "observed_at_ns": _ns(received), "timestamp_basis": "local_control_observation", **fields})

    def control(self, kind: str, *, received_at_ns=None, **fields):
        received = time.time_ns() if received_at_ns is None else _ns(received_at_ns)
        self._rotate(received)
        self._control(kind, received, **fields)

    def set_contracts(self, contracts, *, received_at_ns=None) -> set[str]:
        received = time.time_ns() if received_at_ns is None else _ns(received_at_ns)
        desired = {canonical_contract(value) for value in contracts}
        if len(desired) > 1000:
            raise TickJournalError("subscription set exceeds the 1000 contract bound")
        self._rotate(received)
        before = self._admitted.copy()
        for contract in sorted(desired - self._admitted)[:self.max_contracts - len(self._admitted)]:
            fd = self._open("contracts")
            self._append(fd, {"schema": SCHEMA, "capture_id": self.capture_id,
                              "contract": contract, "admitted_at_ns": received})
            # Crash recovery must see admission before a corresponding tick.
            os.fsync(fd)
            self._admitted.add(contract)
        if desired != self._desired or self._admitted != before:
            self._control("desired_contracts", received,
                          requested=sorted(desired), recording=sorted(desired & self._admitted),
                          refused_daily_limit=sorted(desired - self._admitted))
        self._desired = desired
        return desired & self._admitted

    def record(self, raw: dict, *, received_at_ns: int, received_monotonic_ns=None) -> bool:
        received = _ns(received_at_ns)
        day = datetime.fromtimestamp(received // 1_000_000_000, timezone.utc).date().isoformat()
        if day != self._day:
            self.set_contracts(self._desired, received_at_ns=received)
        if self._lock is None:
            raise TickJournalError("journal is closed")
        if not isinstance(raw, dict):
            raise TickJournalError("expected raw SDK message")
        contract = canonical_contract(raw.get("S"))
        if contract not in self._desired or contract not in self._admitted:
            self.skipped_contract_ticks += 1
            return False
        record = normalize_message(raw, received_at_ns=received)
        record.update(capture_id=self.capture_id, journal_sequence=self.sequence)
        if received_monotonic_ns is not None:
            record["received_monotonic_ns"] = _ns(received_monotonic_ns)
        self._append(self._open(record["kind"]), record)
        self.sequence += 1
        self.rows[record["kind"]] += 1
        self.normalization_errors += int("normalization_error" in record)
        self.last_received_at_ns = received
        self.last_event_timestamp_ns = record["event_timestamp_ns"]
        return True

    def flush(self):
        for fd in self._files.values():
            os.fsync(fd)
        if self._files:
            self.last_fsync_at_ns = time.time_ns()
            self.fsynced_rows = sum(self.rows.values())

    def status(self):
        return {"capture_id": self.capture_id, "receipt_day": self._day,
                "daily_contract_limit": self.max_contracts,
                "daily_admitted_contracts": len(self._admitted),
                "recording_contracts": len(self._desired & self._admitted),
                "refused_daily_limit": len(self._desired - self._admitted),
                "appended_quotes": self.rows["quotes"], "appended_trades": self.rows["trades"],
                "fsynced_rows": self.fsynced_rows, "last_fsync_at_ns": self.last_fsync_at_ns,
                "skipped_contract_ticks": self.skipped_contract_ticks,
                "normalization_errors": self.normalization_errors,
                "last_received_at_ns": self.last_received_at_ns,
                "last_event_timestamp_ns": self.last_event_timestamp_ns,
                "coverage_complete": False, "receipt_basis": RECEIPT_BASIS}

    def close(self):
        if self._lock is None:
            return
        try:
            self.flush()
        finally:
            for fd in self._files.values():
                os.close(fd)
            self._files.clear()
            fcntl.flock(self._lock, fcntl.LOCK_UN)
            os.close(self._lock)
            self._lock = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
