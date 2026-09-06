import pytest
import requests

from options.data.massive_ticks import MassiveTicks, TickDataError
from options.tick_features import window_features


BASE = 1_780_000_000_000_000_000


def quote(t=0, **kwargs):
    return dict(sip_timestamp=BASE + t, bid_price=1., ask_price=1.2, bid_size=30,
                ask_size=10, **kwargs)


def trade(t=1, **kwargs):
    return dict(sip_timestamp=BASE + t, price=1.2, size=5, **kwargs)


def features(q, t, **kwargs):
    # Most chronology tests isolate ordering using synthetic unconditioned
    # trades; that deliberate opt-in is separate from the safe production default.
    kwargs.setdefault("allow_unconditioned_trades", True)
    return window_features(q, t, start_ns=BASE, end_ns=BASE + 100,
                           coverage_start_ns=BASE, coverage_end_ns=BASE + 100,
                           complete=True, max_quote_age_ns=200, **kwargs)


class Response:
    status_code = 200
    def __init__(self, body):
        self.body = body
    def json(self):
        return self.body


class Client:
    def __init__(self, bodies):
        self.bodies, self.calls = iter(bodies), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(next(self.bodies))


def capture(client, **kwargs):
    return MassiveTicks("secret", session=client).capture("SPY260824C00700000", "quotes",
                                                       BASE, BASE + 100, **kwargs)


def test_pagination_preserves_single_nanosecond_and_deduplicates_overlap():
    q = quote(sequence_number=1)
    q2 = quote(1, sequence_number=2)
    client = Client([{"status": "OK", "results": [q], "next_url":
        "https://api.massive.com/v3/quotes/O:SPY260824C00700000?cursor=two&apiKey=secret"},
        {"status": "OK", "results": [q, q2]}])
    rows, manifest = capture(client)
    assert rows[1]["sip_timestamp"] - rows[0]["sip_timestamp"] == 1
    assert manifest["complete"] and manifest["duplicates_removed"] == 1
    assert client.calls[0][1]["params"]["timestamp.lt"] == BASE + 100
    assert "secret" not in client.calls[1][0]
    assert client.calls[0][1]["allow_redirects"] is False


@pytest.mark.parametrize("url", ["https://evil.com/v3/quotes/O:SPY260824C00700000",
    "http://api.massive.com/v3/quotes/O:SPY260824C00700000",
    "https://api.massive.com/v3/trades/O:SPY260824C00700000"])
def test_pagination_cannot_send_auth_to_other_endpoint(url):
    with pytest.raises(TickDataError, match="pagination"):
        capture(Client([{"status": "OK", "results": [], "next_url": url}]))


def test_incomplete_capture_never_reported_complete():
    client = Client([{"status": "OK", "results": [], "next_url":
        "https://api.massive.com/v3/quotes/O:SPY260824C00700000?cursor=2"}])
    with pytest.raises(TickDataError, match="incomplete"):
        capture(client, max_pages=1)


@pytest.mark.parametrize("stamp", [float(BASE), BASE + 100, BASE - 1, True])
def test_imprecise_or_out_of_window_timestamps_refused(stamp):
    q = quote(); q["sip_timestamp"] = stamp
    with pytest.raises(TickDataError):
        capture(Client([{"status": "OK", "results": [q]}]))


def test_conflicting_duplicates_refused():
    q = quote(sequence_number=1); q2 = dict(q, ask_price=9.)
    with pytest.raises(TickDataError, match="conflicting"):
        capture(Client([{"status": "OK", "results": [q, q2]}]))


def test_zero_sequence_trade_multiplicity_is_preserved():
    t = trade(sequence_number=0)
    client = Client([{"status": "OK", "results": [t, dict(t), dict(t, size=2)]}])
    rows, manifest = MassiveTicks("secret", session=client).capture(
        "SPY260824C00700000", "trades", BASE, BASE + 100)
    assert len(rows) == 3 and manifest["records_without_reliable_sequence"] == 3
    assert features([quote()], rows)["reported_contract_volume"] == 12


def test_transport_errors_do_not_leak_key():
    class Broken:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError("apiKey=secret")
    with pytest.raises(TickDataError) as e:
        capture(Broken())
    assert "secret" not in str(e.value)


def test_known_quote_and_trade_features():
    result = features([quote()], [trade()])
    assert result["time_weighted_spread_bps"] == pytest.approx(2000 / 1.1)
    assert result["time_weighted_size_imbalance"] == .5
    assert result["reported_contract_volume"] == result["quote_test_signed_volume"] == 5
    assert result["quote_test_classified_volume_fraction"] == 1


def test_future_and_same_timestamp_quotes_cannot_sign_earlier_trade():
    for t in (1, 2, 100):
        assert features([quote(t)], [trade(1)])["quote_test_signed_volume"] == 0


def test_future_ticks_do_not_change_closed_window():
    original = features([quote()], [trade()])
    assert features([quote(), quote(100)], [trade(), trade(100)]) == original


def test_invalid_latest_quote_ends_valid_duration_and_cannot_supply_execution_price():
    invalid = dict(quote(50), bid_price=2.)
    result = features([quote(), invalid], [])
    assert result["valid_quote_time_fraction"] == .5
    assert result["last_bid"] is None


def test_stale_quote_has_missing_values_not_zero_spread():
    result = features([quote(-300)], [])
    assert result["last_bid"] is None and result["time_weighted_spread_bps"] is None
    assert result["valid_quote_time_fraction"] == 0


def test_conditioned_and_corrected_trades_are_explicit():
    result = features([quote()], [trade(1, conditions=[209]), trade(2, correction=1)])
    assert result["reported_contract_volume"] == 5
    assert result["quote_test_signed_volume"] == 0
    assert result["excluded_invalid_or_corrected_trades"] == 1
    assert features([quote()], [trade(1, conditions=[209])], allowed_trade_conditions=[209])["quote_test_signed_volume"] == 5


def test_receipt_late_quote_is_not_available_to_prior_trade():
    q, t = quote(available_at_ns=BASE + 20), trade(10, available_at_ns=BASE + 11)
    assert features([q], [t], availability="receipt")["quote_test_signed_volume"] == 0
    assert features([q], [t])["quote_test_signed_volume"] == 5


def test_out_of_order_old_quote_does_not_replace_newer_state():
    old = dict(quote(5, available_at_ns=BASE + 30), ask_price=5.)
    current = quote(10, available_at_ns=BASE + 20)
    result = features([old, current], [], availability="receipt")
    assert result["last_ask"] == 1.2


def test_missing_receipt_and_incomplete_coverage_refused():
    with pytest.raises(TickDataError):
        features([quote()], [], availability="receipt")
    with pytest.raises(TickDataError, match="coverage"):
        window_features([], [], start_ns=BASE, end_ns=BASE + 100,
                        coverage_start_ns=BASE, coverage_end_ns=BASE + 100)


def test_same_time_new_quote_cannot_fall_back_to_older_book_for_trade_signing():
    assert features([quote(0), dict(quote(10), ask_price=2.)], [trade(10)])["quote_test_signed_volume"] == 0
    q0 = quote(0, available_at_ns=BASE)
    q1 = dict(quote(5, available_at_ns=BASE + 10), ask_price=2.)
    t = trade(8, available_at_ns=BASE + 10)
    assert features([q0, q1], [t], availability="receipt")["quote_test_signed_volume"] == 0


def test_receipt_delayed_trade_cannot_sign_against_stale_quote():
    result = window_features([quote(available_at_ns=BASE)],
        [trade(1, available_at_ns=BASE + 500)], start_ns=BASE, end_ns=BASE + 1000,
        coverage_start_ns=BASE, coverage_end_ns=BASE + 1000, complete=True,
        max_quote_age_ns=100, availability="receipt")
    assert result["reported_contract_volume"] == 5 and result["quote_test_signed_volume"] == 0


@pytest.mark.parametrize("key,a,b", [
    ("contract", "SPY260918C00500000", "QQQ260918C00500000"),
    ("provider", "alpaca", "massive"),
    ("condition_namespace", "alpaca_opra_string", "massive_integer"),
    ("event_timestamp_basis", "alpaca_t", "massive_sip"),
])
def test_mixed_declared_tick_scope_is_refused(key, a, b):
    with pytest.raises(TickDataError, match="mixed"):
        features([quote(**{key: a})], [trade(**{key: b})])


def test_mixed_unreliable_and_positive_quote_sequences_do_not_create_order():
    for unreliable in ({}, {"sequence_number": 0}, {"sequence_number": None}):
        with pytest.raises(TickDataError, match="ambiguous"):
            features([quote(**unreliable), dict(quote(sequence_number=1), ask_price=2.)], [])


def test_duplicate_vendor_identity_uses_earliest_receipt_without_double_counting():
    early = quote(sequence_number=7, available_at_ns=BASE + 1,
                  received_at_ns=BASE + 1, journal_sequence=1, capture_id="old")
    late = dict(early, available_at_ns=BASE + 20, received_at_ns=BASE + 20,
                journal_sequence=3, capture_id="new")
    t = trade(5, available_at_ns=BASE + 6)
    forward = features([early, late], [t], availability="receipt")
    reverse = features([late, early], [t], availability="receipt")
    assert forward == reverse
    assert forward["quote_updates"] == 1 and forward["quote_test_signed_volume"] == 5


def test_future_unavailable_bad_metadata_does_not_mutate_closed_receipt_window():
    original = features([quote(available_at_ns=BASE)], [], availability="receipt")
    future = {"available_at_ns": BASE + 100, "sip_timestamp": None,
              "sequence_number": "bad", "contract": "unrelated future contract"}
    assert features([quote(available_at_ns=BASE), future], [], availability="receipt") == original


def test_truthy_string_is_not_complete_capture_attestation():
    with pytest.raises(TickDataError, match="coverage"):
        window_features([], [], start_ns=BASE, end_ns=BASE + 100,
                        coverage_start_ns=BASE, coverage_end_ns=BASE + 100, complete="false")


def test_provider_page_count_mismatch_cannot_be_complete():
    with pytest.raises(TickDataError, match="incomplete"):
        capture(Client([{"status": "OK", "results_count": 1}]))
    with pytest.raises(TickDataError, match="not an object"):
        capture(Client([{"status": "OK", "results": [None]}]))


def test_null_unreliable_sequence_preserves_trade_multiplicity():
    t = trade(sequence_number=None)
    client = Client([{"status": "OK", "results": [t, dict(t)]}])
    rows, manifest = MassiveTicks("secret", session=client).capture(
        "SPY260824C00700000", "trades", BASE, BASE + 100)
    assert manifest["records_without_reliable_sequence"] == 2
    assert features([quote()], rows)["reported_contract_volume"] == 10


def make_bundle(tmp_path):
    import gzip
    import hashlib
    import json
    from options.data.massive_ticks import canonical_bytes
    contract = "SPY260824C00700000"
    captures, files = {}, {}
    data = {}
    for kind, rows in (("quotes", [quote(sequence_number=1)]), ("trades", [trade(sequence_number=0)])):
        data[kind], captures[kind] = MassiveTicks("secret", session=Client([
            {"status": "OK", "results": rows}])).capture(contract, kind, BASE, BASE + 100)
        payload = gzip.compress(canonical_bytes(data[kind]), mtime=0)
        name = f"{contract}.{kind}.json.gz"
        (tmp_path / name).write_bytes(payload)
        files[name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    report = {"plan": {"contracts": [contract], "start_ns": BASE, "end_ns": BASE + 100},
              "complete": True, "contracts": [{"contract": contract, "captures": captures, "files": files}]}
    (tmp_path / "manifest.json").write_text(json.dumps(report))
    return contract, report, data


def test_verified_capture_binds_contract_window_completeness_and_raw_hash(tmp_path):
    import copy
    from options.tick_features import verified_window_features
    from scripts.capture_option_ticks import load_verified_capture
    contract, report, data = make_bundle(tmp_path)
    loaded_report, loaded = load_verified_capture(tmp_path)
    assert loaded_report == report and loaded[contract] == data
    entry = report["contracts"][0]
    kwargs = dict(quote_manifest=entry["captures"]["quotes"], trade_manifest=entry["captures"]["trades"],
                  contract=contract, start_ns=BASE, end_ns=BASE + 100)
    assert verified_window_features(data["quotes"], data["trades"], **kwargs)["reported_contract_volume"] == 5
    for field, value in (("complete", "true"), ("contract", "O:QQQ260824C00700000"),
                         ("end_ns", BASE + 99), ("records_sha256", "0" * 64)):
        changed = copy.deepcopy(kwargs)
        changed["quote_manifest"][field] = value
        with pytest.raises(TickDataError):
            verified_window_features(data["quotes"], data["trades"], **changed)
    altered = [dict(data["quotes"][0], ask_price=9.)]
    with pytest.raises(TickDataError, match="SHA256"):
        verified_window_features(altered, data["trades"], **kwargs)


def test_bundle_compressed_payload_tamper_is_refused(tmp_path):
    from scripts.capture_option_ticks import load_verified_capture
    contract, _, _ = make_bundle(tmp_path)
    path = tmp_path / f"{contract}.quotes.json.gz"
    path.write_bytes(path.read_bytes() + b"extra")
    with pytest.raises(TickDataError, match="SHA256"):
        load_verified_capture(tmp_path)


def test_capture_implementation_hashes_bind_current_files():
    import hashlib
    from pathlib import Path
    from scripts.capture_option_ticks import implementation_hashes
    root = Path(__file__).resolve().parents[1]
    hashes = implementation_hashes()
    assert set(hashes) == {"options/data/massive_ticks.py", "options/tick_features.py", "scripts/capture_option_ticks.py"}
    for name, sha in hashes.items():
        assert sha == hashlib.sha256((root / name).read_bytes()).hexdigest()


@pytest.mark.parametrize("fields", [{}, {"conditions": []}, {"conditions": None}])
def test_unknown_historical_conditions_are_unsigned_unless_explicitly_allowed(fields):
    result = features([quote()], [trade(**fields)], allow_unconditioned_trades=False)
    assert result["reported_contract_volume"] == 5
    assert result["quote_test_signed_volume"] == 0
    assert not result["allow_unconditioned_trades"]
    assert features([quote()], [trade(**fields)], allow_unconditioned_trades=True)["quote_test_signed_volume"] == 5


def test_allowlist_does_not_imply_permission_for_missing_conditions():
    result = features([quote()], [trade()], allowed_trade_conditions=[209],
                      allow_unconditioned_trades=False)
    assert result["quote_test_signed_volume"] == 0
    # 209 is just a supplied synthetic code in this fixture; no market meaning
    # or eligibility is inferred from its numeric value.
    explicit = features([quote()], [trade(conditions=[209])], allowed_trade_conditions=[209],
                        allow_unconditioned_trades=False)
    assert explicit["quote_test_signed_volume"] == 5


def test_verified_features_default_to_unsigned_unknown_conditions(tmp_path):
    from options.tick_features import verified_window_features
    contract, report, data = make_bundle(tmp_path)
    entry = report["contracts"][0]
    kwargs = dict(quote_manifest=entry["captures"]["quotes"], trade_manifest=entry["captures"]["trades"],
                  contract=contract, start_ns=BASE, end_ns=BASE + 100)
    assert verified_window_features(data["quotes"], data["trades"], **kwargs)["quote_test_signed_volume"] == 0
    assert verified_window_features(data["quotes"], data["trades"], **kwargs,
                                   allow_unconditioned_trades=True)["quote_test_signed_volume"] == 5
