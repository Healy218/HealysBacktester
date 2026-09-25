from datetime import datetime, timedelta, timezone

import pytest

from integrations.alpaca_paper.v6_pricing import entry_preview, mark_limit

NOW = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)


def quote(**changes):
    value = dict(bid="1.00", ask="1.20", bid_size=10, ask_size=8,
                 received_at=NOW.isoformat(), sip_timestamp_ns=int(NOW.timestamp() * 1e9),
                 last="1.08")
    value.update(changes)
    return value


def test_explicit_mark_is_preferred_to_midpoint_and_last():
    mark = mark_limit(quote(mark="1.13"), now=NOW, after=NOW - timedelta(seconds=2))
    assert mark["mark_source"] == "provider_mark"
    assert mark["limit_price"] == "1.13"
    assert mark["last_price"] == "1.08"
    assert entry_preview(options_buying_power="100000", size_fraction=.1, mark=mark)["preview_contracts"] == 8


def test_midpoint_is_used_only_when_no_provider_mark_exists():
    mark = mark_limit(quote(), now=NOW, after=NOW - timedelta(seconds=2))
    assert mark["limit_price"] == "1.10"
    assert mark["mark_source"] == "bid_ask_midpoint"
    with pytest.raises(ValueError, match="provider mark"):
        mark_limit(quote(mark="1.30"), now=NOW, after=NOW - timedelta(seconds=2))


def test_stale_quote_and_fraction_above_v6_cap_are_refused():
    old = NOW - timedelta(seconds=31)
    with pytest.raises(ValueError, match="stale"):
        mark_limit(quote(sip_timestamp_ns=int(old.timestamp() * 1e9)),
                   now=NOW, after=old - timedelta(seconds=1))
    mark = mark_limit(quote(), now=NOW, after=NOW - timedelta(seconds=2))
    with pytest.raises(ValueError, match="invalid account"):
        entry_preview(options_buying_power="100000", size_fraction=.2, mark=mark)
