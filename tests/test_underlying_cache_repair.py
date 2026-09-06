"""Raw repair guards, real calendars and provider pagination without network."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
import requests

from scripts import repair_underlying_cache as repair


def sessions():
    return repair.calendar_sessions([
        {"date": "2025-03-28", "open": "09:30", "close": "16:00"},
        {"date": "2025-03-31", "open": "09:30", "close": "16:00"},
        {"date": "2025-04-01", "open": "09:30", "close": "16:00"},
    ], "2025-03-28", "2025-04-01")


def panel(day="2025-03-28", symbols=("SPY",)):
    rows = [[s, t, 100., 101., 99., 100., 50.] for s in symbols for t in sessions()[day]]
    return pd.DataFrame(rows, columns=repair.KEYS + repair.COLS)


def test_calendar_handles_dst_early_close_and_holiday_absence():
    result = repair.calendar_sessions([
        {"date": "2025-03-07", "open": "09:30", "close": "16:00"},
        {"date": "2025-03-10", "open": "09:30", "close": "16:00"},
        {"date": "2025-07-03", "open": "09:30", "close": "13:00"},
    ], "2025-03-07", "2025-07-04")
    assert result["2025-03-07"][0].hour == 14
    assert result["2025-03-10"][0].hour == 13
    assert len(result["2025-07-03"]) == 14
    assert "2025-07-04" not in result


@pytest.mark.parametrize("value", ["../old", "/tmp/out", "a/b", "a b", ".", "a" * 65])
def test_candidate_rejects_traversal(value, tmp_path):
    with pytest.raises(repair.RepairError, match="simple"):
        repair.candidate_dir(value, tmp_path)


def test_candidate_rejects_symlink(tmp_path):
    path = tmp_path / "nn_meta" / "data_candidates"
    path.parent.mkdir()
    path.symlink_to(tmp_path)
    with pytest.raises(repair.RepairError, match="symlink"):
        repair.candidate_dir("pilot", tmp_path)


def test_per_symbol_coverage_surfaces_missing_session_and_observed_lifetimes():
    data = pd.concat([panel(), panel("2025-04-01"), panel("2025-03-31", ("NEW",))])
    result = repair.inventory(data, sessions(), set(sessions()))
    assert result["missing_underlying_days"] == []
    assert result["missing_sessions_by_symbol"] == {"SPY": ["2025-03-31"]}
    assert result["terminal_symbols_requiring_lifetime_review"] == {"NEW": "2025-03-31"}
    assert result["missing_option_days"] == []


def test_partial_session_is_reported_without_fabrication():
    result = repair.inventory(panel().iloc[:-1], sessions(), set(sessions()))
    assert result["partial_sessions_by_symbol"]["SPY"]["2025-03-28"] == {"observed": 25, "expected_slots": 26}
    assert result["missing_sessions_by_symbol"]["SPY"] == ["2025-03-31", "2025-04-01"]


class Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def bar(stamp):
    return dict(t=stamp, o=100, h=101, l=99, c=100, v=50)


def test_alpaca_pagination_alias_and_close_boundary():
    class Client:
        calls = []

        def get(self, url, **kwargs):
            self.calls.append(dict(kwargs["params"]))
            assert kwargs["headers"] == {"secret": "hidden"}
            if len(self.calls) == 1:
                return Response({"bars": {"BRK.B": [bar("2025-03-31T13:30:00Z")]}, "next_page_token": "second"})
            return Response({"bars": {"BRK.B": [bar("2025-03-31T13:45:00Z"), bar("2025-03-31T20:00:00Z")]}})

    client = Client()
    result = repair.fetch_day("2025-03-31", sessions(), {"BRKB": "BRK.B"}, {"secret": "hidden"}, client)
    assert len(result) == 2 and result.symbol.tolist() == ["BRKB", "BRKB"]
    assert client.calls[1]["page_token"] == "second"
    assert client.calls[0]["adjustment"] == "all" and client.calls[0]["feed"] == "sip"
    assert result.timestamp.dt.tz is None


def test_transport_does_not_expose_credentials():
    class Client:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError("http://provider?apiKey=secret-string")

    with pytest.raises(repair.RepairError) as exc:
        repair.fetch_day("2025-03-31", sessions(), {"SPY": "SPY"}, {}, Client())
    assert "secret-string" not in str(exc.value)


def test_repeated_pagination_refused():
    class Client:
        def get(self, *args, **kwargs):
            return Response({"bars": {}, "next_page_token": "same"})

    with pytest.raises(repair.RepairError, match="pagination"):
        repair.fetch_day("2025-03-31", sessions(), {"SPY": "SPY"}, {}, Client())


def test_raw_daily_request_uses_raw_basis_and_normalized_session_dates():
    class Client:
        def get(self, url, **kwargs):
            assert kwargs["params"]["adjustment"] == "raw"
            assert kwargs["params"]["timeframe"] == "1Day"
            assert kwargs["params"]["start"] == "2025-03-31T00:00:00+00:00"
            assert kwargs["params"]["end"] == "2025-04-01T00:00:00+00:00"
            return Response({"bars": {"SPY": [bar("2025-03-31T04:00:00Z")]}})

    frame = repair.fetch_day("2025-03-31", sessions(), {"SPY": "SPY"}, {}, Client(),
                             interval="1Day", adjustment="raw")
    assert frame.timestamp.tolist() == [pd.Timestamp("2025-03-31")]


def test_overlap_mismatch_and_existing_bar_refused():
    old = panel()
    refs = old.copy()
    refs.loc[0, "Close"] = 100.5
    comparison = repair.compare_reference(old, refs)
    with pytest.raises(repair.RepairError, match="reference mismatch"):
        repair.merge_repairs(old, panel("2025-03-31"), sessions(), ["2025-03-31"], comparison)
    matching = repair.compare_reference(old, old)
    with pytest.raises(repair.RepairError, match="replace an existing"):
        repair.merge_repairs(old, old, sessions(), ["2025-03-28"], matching)
    merged = repair.merge_repairs(old, panel("2025-03-31"), sessions(), ["2025-03-31"], matching)
    pd.testing.assert_frame_equal(merged.iloc[:26], old)


def test_stage_preserves_original_bytes_and_copies_other_inputs(tmp_path):
    source, destination = tmp_path / "old", tmp_path / "new"
    source.mkdir()
    old = panel()
    old.to_parquet(source / "underlying_15m.parquet", index=False)
    (source / "options.parquet").write_bytes(b"unchanged-option-data")
    before = repair.cache_hashes(source)
    merged = pd.concat([old, panel("2025-03-31")], ignore_index=True)
    repair.stage_cache(source, destination, merged, {"source_underlying_sha256": before["underlying_15m.parquet"]})
    assert repair.cache_hashes(source) == before
    assert (source / "options.parquet").stat().st_ino != (destination / "options.parquet").stat().st_ino
    assert (destination / "options.parquet").read_bytes() == b"unchanged-option-data"
    assert len(pd.read_parquet(destination / "underlying_15m.parquet")) == 52
    with pytest.raises(repair.RepairError, match="new path"):
        repair.stage_cache(source, destination, merged, {})


def test_changed_source_and_symlink_refused_before_copy(tmp_path):
    source, destination = tmp_path / "old", tmp_path / "new"
    source.mkdir()
    path = source / "underlying_15m.parquet"
    panel().to_parquet(path)
    with pytest.raises(repair.RepairError, match="changed"):
        repair.stage_cache(source, destination, panel(), {"source_underlying_sha256": "stale"})
    assert not destination.exists()
    (source / "link").symlink_to(path)
    with pytest.raises(repair.RepairError, match="symlink"):
        repair.cache_hashes(source)


def test_calendar_trim_removes_only_known_closed_market_rows_and_records_counts():
    original = panel()
    late = original.iloc[:1].copy()
    late["timestamp"] = pd.Timestamp("2025-03-28 20:00:00")
    combined = pd.concat([original, late], ignore_index=True)
    cleaned, evidence = repair.clip_to_calendar(combined, sessions())
    pd.testing.assert_frame_equal(cleaned, original)
    assert evidence["removed_rows"] == 1
    assert evidence["by_day_symbol"] == [{"date": "2025-03-28", "symbol": "SPY", "rows": 1}]
    assert len(evidence["removed_rows_sha256"]) == 64


def test_full_vintage_replacement_requires_complete_matching_history():
    old = pd.concat([panel(), panel("2025-04-01")], ignore_index=True)
    fresh = pd.concat([panel(), panel("2025-03-31"), panel("2025-04-01")], ignore_index=True)
    fresh[repair.COLS[:4]] *= .99
    references = fresh[fresh.timestamp.dt.date == pd.Timestamp("2025-03-28").date()]
    changed, evidence = repair.replace_vintage(old, fresh, references, ["SPY"], sessions())
    pd.testing.assert_frame_equal(changed, fresh)
    assert evidence["old_vs_fresh"]["different_rows"] == 52
    with pytest.raises(repair.RepairError, match="reference"):
        repair.replace_vintage(old, fresh, panel(), ["SPY"], sessions())
    with pytest.raises(repair.RepairError, match="shortened"):
        repair.replace_vintage(old, fresh.iloc[:26], references, ["SPY"], sessions())


def test_pre_identity_history_cannot_enter_warmup_and_only_documented_halts_pass():
    data = pd.concat([panel(symbols=("FIG",)), panel("2025-03-31", ("FIG",))], ignore_index=True)
    exceptions = {"identity_starts": {"FIG": {"date": "2025-03-31"}},
                  "nontrading_sessions": {"CLSK": {"2024-11-08": {"reason": "documented halt"}}}}
    trimmed, evidence = repair.clip_identity_history(data, exceptions)
    assert len(trimmed) == 26 and evidence["by_symbol"] == {"FIG": 26}
    report = {"missing_sessions_by_symbol": {"CLSK": ["2024-11-08"]},
              "missing_underlying_days": [], "missing_option_days": [], "off_session_rows": 0,
              "noncalendar_underlying_days": [], "noncalendar_option_days": []}
    assert repair.classify_coverage(report, exceptions)["passed"]
    report["missing_sessions_by_symbol"]["CLSK"].append("2024-11-12")
    assert not repair.classify_coverage(report, exceptions)["passed"]


def test_adopt_derivation_requires_complete_unchanged_chain_and_preserves_prior_parts(tmp_path):
    from nn_meta.price_basis import RAW_SPOT_SCHEMA_VERSION
    destination, derived = tmp_path / "candidate", tmp_path / "derived"
    cache = destination / "cache"
    (cache / "bars_daily").mkdir(parents=True)
    (derived / "bars_daily").mkdir(parents=True)
    (cache / "underlying_daily_raw.parquet").write_bytes(b"vendor-raw-daily")
    (cache / "repair_manifest.json").write_text("{}")
    universe = pd.DataFrame({"ticker": ["O:SPY250331C00100000"], "underlying": ["SPY"],
                             "expiration": pd.to_datetime(["2025-03-31"]),
                             "life_start": pd.to_datetime(["2025-03-28"]), "strike": [100.], "type": ["call"]})
    for filename in ("universe.parquet", "contracts.parquet"):
        universe.to_parquet(cache / filename)
    universe.attrs.update(universe_price_basis_schema=RAW_SPOT_SCHEMA_VERSION,
                          contract_scope="all_observed_contracts", source="flatfiles_15m",
                          strike_filter="none", derivation_provenance={"verified": True})
    for filename in ("universe.parquet", "contracts.parquet"):
        universe.to_parquet(derived / filename)
    pd.DataFrame({"ticker": ["old"]}).to_parquet(cache / "bars_daily/old.parquet")
    pd.DataFrame({"ticker": ["new", "another"]}).to_parquet(derived / "bars_daily/new.parquet")
    manifest = {"status": "building", "daily_rows": 2, "input_inventory": [],
                "derivation_provenance": {"input_cache": str(cache.resolve()),
                    "flatfile_inventory_sha256": repair.hashlib.sha256(b"[]").hexdigest(),
                    "raw_daily_sha256": repair.sha256(cache / "underlying_daily_raw.parquet")},
                "output_sha256": {p.relative_to(derived).as_posix(): repair.sha256(p)
                                  for p in derived.rglob("*.parquet")}}
    (derived / "derivation_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(repair.RepairError, match="incomplete"):
        repair.adopt_derivation(destination, derived)
    manifest["status"] = "complete"
    (derived / "derivation_manifest.json").write_text(json.dumps(manifest))
    repair.adopt_derivation(destination, derived)
    assert (destination / "context_history/before_raw_option_filter/bars_daily/old.parquet").exists()
    assert not (cache / "bars_daily/old.parquet").exists()
    assert (cache / "bars_daily/new.parquet").exists()
    result = json.loads((cache / "repair_manifest.json").read_text())
    assert result["option_derivation"]["all_observed_scope_unchanged"]
    assert result["option_derivation"]["old_daily_rows"] == 1


@pytest.mark.parametrize("mismatch", [False, True])
def test_warmup_repair_requires_matching_reference_and_exact_raw_keys(tmp_path, monkeypatch, mismatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    original = pd.concat([panel(), panel("2025-04-01")], ignore_index=True)
    path = cache / "underlying_15m.parquet"
    original.to_parquet(path, index=False)
    raw = pd.concat([panel(), panel("2025-03-31"), panel("2025-04-01")], ignore_index=True)
    raw[repair.KEYS].to_parquet(cache / "underlying_15m_raw.parquet", index=False)
    (cache / "repair_manifest.json").write_text(json.dumps({"window": ["2025-04-01", "2025-04-01"]}))
    before = repair.sha256(path)
    records = [{"date": d, "open": "09:30", "close": "16:00"} for d in sessions()]

    def fetch(day, *args, **kwargs):
        if day == "SPY":
            return raw.copy()  # full capture still disagrees with the new reference
        result = panel(day)
        if mismatch and day == "2025-03-28":
            result.loc[0, "Close"] = 100.5
        return result

    monkeypatch.setattr(repair, "fetch_day", fetch)
    if mismatch:
        with pytest.raises(repair.RepairError, match="reference"):
            repair.repair_warmup(tmp_path, records, {"SPY": "SPY"}, {}, "2025-03-28", "2025-04-01")
        assert repair.sha256(path) == before
    else:
        repair.repair_warmup(tmp_path, records, {"SPY": "SPY"}, {}, "2025-03-28", "2025-04-01")
        pd.testing.assert_frame_equal(pd.read_parquet(path), raw)
        assert json.loads((cache / "repair_manifest.json").read_text())["warmup_repair"]["added_rows"] == 26


def fresh_candidate(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    original = panel()
    original.to_parquet(cache / "underlying_15m.parquet", index=False)
    fresh = pd.concat([panel(), panel("2025-03-31"), panel("2025-04-01")], ignore_index=True)
    fresh.to_parquet(cache / "underlying_15m_raw.parquet", index=False)
    (cache / "stock_history_exceptions.json").write_text("{}")
    (cache / "repair_manifest.json").write_text(json.dumps({"window": ["2025-04-01", "2025-04-01"]}))
    records = [{"date": d, "open": "09:30", "close": "16:00"} for d in sessions()]
    return cache, fresh, records


def test_full_adjusted_fetch_preserves_previous_and_rejects_mutated_checkpoint(tmp_path, monkeypatch):
    cache, fresh, records = fresh_candidate(tmp_path)
    before = repair.sha256(cache / "underlying_15m.parquet")

    def fetch(symbol, history, aliases, headers, **kwargs):
        assert kwargs == {"interval": "15Min", "adjustment": "all"}
        assert symbol == "SPY" and aliases == {"SPY": "SPY"}
        return fresh

    monkeypatch.setattr(repair, "fetch_day", fetch)
    repair.fetch_adjusted_intraday(tmp_path, records, {"SPY": "SPY"}, {}, "2025-03-28", "2025-04-01", 1)
    assert repair.sha256(tmp_path / "context_history/underlying_15m_before_full_refresh.parquet") == before
    pd.testing.assert_frame_equal(pd.read_parquet(cache / "underlying_15m.parquet"), fresh)
    manifest = json.loads((cache / "repair_manifest.json").read_text())
    assert manifest["full_adjusted_refresh"]["rows"] == 78
    checkpoint = tmp_path / "adjusted_15m_parts/SPY.parquet"
    payload = bytearray(checkpoint.read_bytes())
    payload[10] ^= 1  # same size mutation must not be accepted as a checkpoint
    checkpoint.write_bytes(payload)
    with pytest.raises(repair.RepairError, match="captured-byte hash"):
        repair.fetch_adjusted_intraday(tmp_path, records, {"SPY": "SPY"}, {}, "2025-03-28", "2025-04-01", 1)


def test_full_adjusted_fetch_refuses_shortened_raw_timeline_before_replacing(tmp_path, monkeypatch):
    cache, fresh, records = fresh_candidate(tmp_path)
    before = repair.sha256(cache / "underlying_15m.parquet")
    monkeypatch.setattr(repair, "fetch_day", lambda *args, **kwargs: fresh.iloc[:-1])
    with pytest.raises(repair.RepairError, match="timestamps differ"):
        repair.fetch_adjusted_intraday(tmp_path, records, {"SPY": "SPY"}, {}, "2025-03-28", "2025-04-01", 1)
    assert repair.sha256(cache / "underlying_15m.parquet") == before
    assert not (tmp_path / "context_history").exists()


def test_sealed_candidate_cannot_be_resealed_after_an_edit(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "repair_manifest.json").write_text(json.dumps({"sealed_cache_sha256": {"input": "old-hash"}}))
    (cache / "input").write_bytes(b"edited-data")
    with pytest.raises(repair.RepairError, match="immutable"):
        repair.seal_candidate(tmp_path)


def test_adopted_option_parts_reject_extra_legacy_files_and_changed_bytes(tmp_path):
    (tmp_path / "bars_daily").mkdir()
    expected = {}
    for name in ("contracts.parquet", "universe.parquet", "bars_daily/bars_part_0000.parquet"):
        (tmp_path / name).write_bytes(b"validated")
        expected[name] = repair.sha256(tmp_path / name)
    manifest = {"options_daily_raw_filter_verified": True, "option_derivation": {"output_sha256": expected}}
    repair.verify_adopted_outputs(tmp_path, manifest)
    extra = tmp_path / "bars_daily/bars_part_9999.parquet"
    extra.write_bytes(b"legacy part")
    with pytest.raises(repair.RepairError, match="inventory changed"):
        repair.verify_adopted_outputs(tmp_path, manifest)
    extra.unlink()
    (tmp_path / "bars_daily/bars_part_0000.parquet").write_bytes(b"corrupted")
    with pytest.raises(repair.RepairError, match="inputs changed"):
        repair.verify_adopted_outputs(tmp_path, manifest)


@pytest.mark.parametrize("volume,expected", [(0., True), (1., False)])
def test_full_history_coverage_accepts_only_evidenced_zero_volume_warmup(tmp_path, volume, expected):
    cache, fresh, records = fresh_candidate(tmp_path)
    # One complete missing warmup day in both actual intraday price series.
    available = fresh[fresh.timestamp.dt.date != pd.Timestamp("2025-03-31").date()]
    other = fresh.copy()
    other["symbol"] = "QQQ"
    available = pd.concat([available, other], ignore_index=True)
    for name in ("underlying_15m.parquet", "underlying_15m_raw.parquet"):
        available.to_parquet(cache / name, index=False)
    daily = pd.DataFrame({"underlying": ["SPY"], "date": pd.to_datetime(["2025-03-31"]), "volume": [volume]})
    for name in ("underlying_daily.parquet", "underlying_daily_raw.parquet"):
        daily.to_parquet(cache / name, index=False)
    (cache / "exchange_calendar.json").write_text(json.dumps({"coverage_start": "2025-03-28",
            "coverage_end": "2025-04-01", "sessions": records}))
    (cache / "flatfiles_15m").mkdir()
    (cache / "flatfiles_15m/2025-04-01.parquet").touch()
    manifest = {"window": ["2025-04-01", "2025-04-01"]}
    with pytest.raises(repair.RepairError, match="full fresh adjusted"):
        repair.final_stock_coverage(cache, manifest)
    manifest["full_adjusted_refresh"] = {"window": ["2025-03-28", "2025-04-01"],
        "symbols": 2, "rows": 130, "lineage": repair.LINEAGE}
    if expected:
        result = repair.final_stock_coverage(cache, manifest)
        assert result["coverage_result"]["passed"] and result["full_stock_history_coverage"]["passed"]
        assert result["vendor_zero_volume_warmup_sessions"][0]["date"] == "2025-03-31"
    else:
        with pytest.raises(repair.RepairError, match="coverage is incomplete"):
            repair.final_stock_coverage(cache, manifest)


@pytest.mark.parametrize("pool,campaign,candidate,ok", [
    ("v6", "tonight", "repaired", True), ("v5", "tonight", "repaired", True),
    ("v6", "", "repaired", False), ("v3", "tonight", "repaired", False),
    ("v6", "tonight", "../old", False),
])
def test_data_override_requires_isolated_campaign(pool, campaign, candidate, ok):
    result = subprocess.run([sys.executable, "-c", "from nn_meta import config; print(config.DATA_CACHE)"],
                            cwd=repair.ROOT, env=dict(os.environ, NN_META_POOL=pool,
                            NN_META_CAMPAIGN=campaign, NN_META_DATA_CANDIDATE=candidate),
                            capture_output=True, text=True)
    assert (result.returncode == 0) is ok
    if ok:
        assert f"data_candidates/{candidate}/cache" in result.stdout
