from datetime import datetime

from scripts.export_v6_broker_ledger import iso_stamp, newest_first


def test_broker_trade_dates_are_qualified_and_sorted_by_latest_activity():
    rows = [
        {"key": "old", "opened_at": iso_stamp("2026-09-01T10:00:00"),
         "closed_at": iso_stamp("2026-09-03T10:00:00")},
        {"key": "open", "opened_at": iso_stamp("2026-09-05T10:00:00"), "closed_at": None},
        {"key": "closed", "opened_at": iso_stamp("2026-09-02T10:00:00"),
         "closed_at": iso_stamp("2026-09-04T10:00:00")},
    ]
    assert all(datetime.fromisoformat(row["opened_at"]).tzinfo for row in rows)
    assert [row["key"] for row in newest_first(rows)] == ["open", "closed", "old"]
