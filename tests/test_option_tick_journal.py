import base64
import hashlib
import json

import msgpack
import pandas as pd
import pytest

from nn_meta.live.feeds.tick_journal import (
    TickJournal, TickJournalError, canonical_contract, event_timestamp_ns,
    normalize_message,
)

A = "SPY260918C00500000"
B = "SPY260918P00500000"
C = "QQQ260918C00500000"
NOW = pd.Timestamp("2026-09-05T14:00:00.123456789Z").value
DAY = "2026-09-05"


def quote(contract=A, event=NOW):
    return {"T": "q", "S": contract, "t": msgpack.Timestamp(event // 10**9, event % 10**9),
            "bp": 1.2, "ap": 1.3, "bs": 4, "as": 8, "bx": "A", "ax": "B", "c": "R"}


def trade(contract=A, event=NOW):
    return {"T": "t", "S": contract, "t": msgpack.Timestamp(event // 10**9, event % 10**9),
            "p": 1.3, "s": 2, "x": "A", "c": "SL"}


def rows(root, kind, day=DAY):
    return [json.loads(line) for line in (root / day / f"{kind}.jsonl").read_text().splitlines()]


def test_raw_msgpack_roundtrip_keeps_nanoseconds_unknown_fields_and_conditions():
    raw = quote()
    raw.update(vendor_future={"bytes": b"\x00\xff", "number": 2**63 + 1})
    record = normalize_message(raw, received_at_ns=NOW + 51)
    payload = base64.b64decode(record["raw_msgpack_b64"])
    assert msgpack.unpackb(payload) == raw
    assert record["raw_msgpack_sha256"] == hashlib.sha256(payload).hexdigest()
    assert raw["t"].nanoseconds == 123456789
    assert record["event_timestamp_ns"] == record["sip_timestamp"] == NOW
    assert record["available_at_ns"] == NOW + 51
    assert record["receipt_basis"] == "sdk_handler_entry_after_decode"
    assert record["conditions"] == ["R"]
    assert record["condition_namespace"] == "alpaca_opra_string"
    assert record["model_admission"] is False
    assert "sequence_number" not in record
    t = normalize_message(trade(), received_at_ns=NOW + 52)
    assert t["conditions"] == ["SL"]  # One OPRA code, never split into characters.
    assert t["correction"] == 0 and not t["correction_available"]


def test_timestamp_exactness_and_rejection_of_ambiguous_epochs():
    assert event_timestamp_ns("2026-09-05T09:00:00.123456789-05:00") == NOW
    assert event_timestamp_ns(pd.Timestamp(NOW, tz="UTC")) == NOW
    for value in (NOW, float(NOW), "2026-09-05T14:00:00", pd.NaT, None, True):
        with pytest.raises(TickJournalError):
            event_timestamp_ns(value)


def test_invalid_market_values_and_bad_timestamp_still_preserve_raw():
    raw = quote()
    raw.update(bp=2, ap=1, bs=0, t="bad timestamp")
    record = normalize_message(raw, received_at_ns=NOW)
    assert record["bid_price"] == 2 and record["ask_price"] == 1
    assert record["bid_size"] == 0
    assert record["sip_timestamp"] is None and "normalization_error" in record
    assert msgpack.unpackb(base64.b64decode(record["raw_msgpack_b64"])) == raw
    raw = quote()
    raw["bp"] = float("nan")
    assert normalize_message(raw, received_at_ns=NOW)["bid_price"] is None


def test_receipt_clock_skew_remains_explicit_and_missing_conditions_not_signable():
    raw = trade()
    del raw["c"]
    result = normalize_message(raw, received_at_ns=NOW - 1)
    assert result["receipt_precedes_event"] and result["available_at_ns"] == NOW - 1
    assert result["conditions"] is None and not result["conditions_available"]


def test_append_duplicate_trades_with_no_vendor_id_and_flush_status(tmp_path):
    with TickJournal(tmp_path) as journal:
        assert journal.set_contracts([A], received_at_ns=NOW) == {A}
        journal.record(quote(), received_at_ns=NOW + 1, received_monotonic_ns=123)
        before = (tmp_path / DAY / "quotes.jsonl").read_bytes()
        journal.record(quote(event=NOW + 2), received_at_ns=NOW + 3)
        journal.record(trade(), received_at_ns=NOW + 4)
        journal.record(trade(), received_at_ns=NOW + 5)
        assert (tmp_path / DAY / "quotes.jsonl").read_bytes().startswith(before)
        assert journal.status()["fsynced_rows"] == 0
        journal.flush()
        assert journal.status()["fsynced_rows"] == 4
        assert not journal.status()["coverage_complete"]
    qs, ts = rows(tmp_path, "quotes"), rows(tmp_path, "trades")
    assert qs[0]["received_monotonic_ns"] == 123
    assert [t["journal_sequence"] for t in ts] == [2, 3]
    assert ts[0]["raw_msgpack_b64"] == ts[1]["raw_msgpack_b64"]
    assert all("sequence_number" not in row and "id" not in row for row in ts)


def test_daily_unique_contract_budget_survives_watch_churn_and_restart(tmp_path):
    with TickJournal(tmp_path, max_contracts=2) as journal:
        journal.set_contracts([A, B], received_at_ns=NOW)
        assert journal.set_contracts([B, C], received_at_ns=NOW + 1) == {B}
        assert not journal.record(quote(C), received_at_ns=NOW + 2)
        assert not journal.record(quote(A), received_at_ns=NOW + 3)
        assert journal.record(quote(B), received_at_ns=NOW + 4)
        assert journal.status()["refused_daily_limit"] == 1
    with TickJournal(tmp_path, max_contracts=2) as journal:
        assert journal.set_contracts([C], received_at_ns=NOW + 5) == set()
        assert journal.status()["daily_admitted_contracts"] == 2
    assert len(rows(tmp_path, "contracts")) == 2


def test_day_rotation_uses_receipt_day_and_resets_daily_budget(tmp_path):
    next_day = pd.Timestamp("2026-09-06T00:00:00.000000001Z").value
    with TickJournal(tmp_path, max_contracts=1) as journal:
        journal.set_contracts([A], received_at_ns=NOW)
        assert journal.set_contracts([B], received_at_ns=NOW + 1) == set()
        # Automatic rotation admits current desired contract; late event stays
        # in today's RECEIPT partition without altering yesterday's files.
        assert journal.record(quote(B), received_at_ns=next_day)
        assert journal.status()["receipt_day"] == "2026-09-06"
    assert rows(tmp_path, "quotes", "2026-09-06")[0]["event_timestamp_ns"] == NOW
    assert rows(tmp_path, "contracts", "2026-09-06")[0]["contract"] == B


def test_single_writer_and_closed_journal_fail_explicitly(tmp_path):
    journal = TickJournal(tmp_path)
    with pytest.raises(TickJournalError, match="another writer"):
        TickJournal(tmp_path)
    journal.set_contracts([A], received_at_ns=NOW)
    journal.close()
    with pytest.raises(TickJournalError, match="closed"):
        journal.record(quote(), received_at_ns=NOW)
    with TickJournal(tmp_path):
        pass


@pytest.mark.parametrize("kind", ["quotes", "contracts"])
def test_partial_tail_refuses_append_without_modifying_capture(tmp_path, kind):
    with TickJournal(tmp_path) as journal:
        journal.set_contracts([A], received_at_ns=NOW)
        journal.record(quote(), received_at_ns=NOW + 1)
    path = tmp_path / DAY / f"{kind}.jsonl"
    with path.open("ab") as destination:
        destination.write(b'{"partial":')
    before = path.read_bytes()
    with TickJournal(tmp_path) as journal:
        with pytest.raises(TickJournalError, match="incomplete"):
            journal.set_contracts([A], received_at_ns=NOW + 2)
            journal.record(quote(), received_at_ns=NOW + 3)
    assert path.read_bytes() == before


def test_contract_validation_and_daily_limit_validation(tmp_path):
    assert canonical_contract("o:spy1260918c00500000") == "SPY1260918C00500000"
    for invalid in ("*", "../SPY260918C00500000", "SPY269918C00500000", None):
        with pytest.raises(TickJournalError):
            canonical_contract(invalid)
    for limit in (0, 1001, True, 2.0):
        with pytest.raises(TickJournalError):
            TickJournal(tmp_path, max_contracts=limit)
