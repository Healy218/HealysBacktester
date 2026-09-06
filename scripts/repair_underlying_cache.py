"""Stage missing stock sessions without changing a historical research cache.

Run as a module. `inventory` is read-only; `fetch` and `stage` preview unless
--run is explicit. Fetch uses Alpaca SIP / all corporate-action adjustments,
matching the original vectorbt download. Massive split-adjusted stock bars
are deliberately not accepted as repairs to that archive.

An independently downloaded Alpaca exchange calendar JSON is required. Each
missing session is fetched together with its previous intact session so the
new feed can be compared with the existing bytes before it is merged. Missing
bars are never synthesized. Existing partial-session bars and gaps are
reported separately from completely absent sessions, including early closes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
COLS = ["Open", "High", "Low", "Close", "Volume"]
KEYS = ["symbol", "timestamp"]
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
LINEAGE = {"provider": "alpaca", "feed": "sip", "adjustment": "all",
           "interval": "15Min", "timestamps": "UTC naive bar open",
           "session_filter": "exchange calendar open inclusive, close exclusive"}


class RepairError(ValueError):
    pass


def sha256(path: Path) -> str:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise RepairError("input changed while hashing")
    return digest.hexdigest()


def candidate_dir(value: str, root: Path = ROOT) -> Path:
    if not NAME.fullmatch(value):
        raise RepairError("candidate must be a simple 1–64 character name")
    path = root / "nn_meta" / "data_candidates" / value
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise RepairError("candidate path contains a symlink")
    if path.exists() and any(p.is_symlink() for p in path.rglob("*")):
        raise RepairError("candidate contains a symlink")
    return path


def calendar_sessions(records: list[dict], start: str, end: str) -> dict[str, pd.DatetimeIndex]:
    """Use the provider's independently supplied holiday/early-close calendar."""
    result = {}
    if start > end or not isinstance(records, list):
        raise RepairError("invalid calendar window")
    for item in records:
        day = item["date"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise RepairError("invalid calendar date")
        if day in result:
            raise RepairError("duplicate calendar session")
        if not start <= day <= end:
            continue
        lo = pd.Timestamp(day + " " + item["open"], tz="America/New_York")
        hi = pd.Timestamp(day + " " + item["close"], tz="America/New_York")
        if lo >= hi or lo.minute % 15 or hi.minute % 15 or lo.weekday() > 4:
            raise RepairError("invalid exchange session boundaries")
        result[day] = pd.date_range(lo, hi, freq="15min", inclusive="left").tz_convert("UTC").tz_localize(None)
    if not result:
        raise RepairError("calendar has no sessions in pinned window")
    return dict(sorted(result.items()))


def validate_panel(panel: pd.DataFrame) -> pd.DataFrame:
    if not set(KEYS + COLS).issubset(panel.columns):
        raise RepairError("underlying panel must contain symbol, timestamp and OHLCV")
    frame = panel[KEYS + COLS].copy()
    if not pd.api.types.is_datetime64_any_dtype(frame.timestamp.dtype):
        raise RepairError("timestamps must be datetime values")
    if frame.timestamp.dt.tz is not None:
        frame["timestamp"] = frame.timestamp.dt.tz_convert("UTC").dt.tz_localize(None)
    if frame[KEYS].isna().any().any() or frame.duplicated(KEYS).any():
        raise RepairError("null or duplicate bar keys")
    if any(not pd.api.types.is_numeric_dtype(frame[c]) for c in COLS):
        raise RepairError("OHLCV must be numeric")
    if not np.isfinite(frame[COLS].to_numpy()).all() or (frame.Volume < 0).any():
        raise RepairError("OHLCV must be finite with nonnegative volume")
    if ((frame.High < frame[["Open", "Close", "Low"]].max(axis=1))
            | (frame.Low > frame[["Open", "Close", "High"]].min(axis=1))).any():
        raise RepairError("invalid OHLC range")
    return frame


def inventory(panel: pd.DataFrame, sessions: dict, option_days: set[str]) -> dict:
    """Audit each observed symbol's lifetime, without inventing pre-IPO bars.

    Symbols present on the archive's final observed date are expected through
    the pinned end; older terminal dates are separately surfaced for review,
    not automatically treated as post-delisting missing data. Intra-session
    deficits can be real no-trade intervals and are reported, never filled.
    """
    day_column = panel.timestamp.dt.strftime("%Y-%m-%d")
    actual_days = set(day_column)
    expected_days = set(sessions)
    last_observed = max(actual_days)
    scoped = panel[day_column.isin(expected_days)].copy()
    scoped["day"] = day_column[day_column.isin(expected_days)]
    counts = scoped.groupby(["symbol", "day"]).size()
    ranges = panel.groupby("symbol").timestamp.agg(["min", "max"])
    absent, partial, terminal = {}, {}, {}
    valid_stamps = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in sessions.values()]))
    off_session = scoped[~scoped.timestamp.isin(valid_stamps)]
    for symbol, row in ranges.iterrows():
        first, last = row["min"].date().isoformat(), row["max"].date().isoformat()
        if last != last_observed:
            terminal[symbol] = last
        expected = [d for d in sessions if first <= d and (d <= last or last == last_observed)]
        missing, deficits = [], {}
        for day in expected:
            count = int(counts.get((symbol, day), 0))
            if not count:
                missing.append(day)
            elif count != len(sessions[day]):
                deficits[day] = {"observed": count, "expected_slots": len(sessions[day])}
        if missing:
            absent[symbol] = missing
        if deficits:
            partial[symbol] = deficits
    return {"calendar_sessions": len(sessions), "symbols": len(ranges),
            "missing_underlying_days": sorted(expected_days - actual_days),
            "missing_option_days": sorted(expected_days - option_days),
            "noncalendar_underlying_days": sorted(d for d in actual_days - expected_days
                                                    if min(sessions) <= d <= max(sessions)),
            "noncalendar_option_days": sorted(d for d in option_days - expected_days
                                                if min(sessions) <= d <= max(sessions)),
            "missing_sessions_by_symbol": absent,
            "partial_sessions_by_symbol": partial,
            "terminal_symbols_requiring_lifetime_review": terminal,
            "off_session_rows": len(off_session)}


def repair_days(report: dict, sessions: dict) -> tuple[list[str], list[str]]:
    days = report["missing_underlying_days"]
    if not days:
        raise RepairError("no globally missing underlying sessions to repair")
    ordered = list(sessions)
    references = []
    for day in days:
        previous = [d for d in ordered[:ordered.index(day)] if d not in days]
        if not previous:
            raise RepairError("missing first session needs an explicit earlier reference window")
        references.append(previous[-1])
    return days, sorted(set(references))


def fetch_day(day: str, sessions: dict, aliases: dict[str, str], headers: dict,
              client=None, interval: str = "15Min", adjustment: str = "all") -> pd.DataFrame:
    """Paginate bounded requests with an explicit price basis; redact failures."""
    client = client or requests.Session()
    reverse = {}
    for symbol, fetched in aliases.items():
        reverse.setdefault(fetched, []).append(symbol)
    index = sessions[day]
    if interval not in ("15Min", "1Day"):
        raise RepairError("unsupported repair interval")
    if adjustment not in ("all", "raw"):
        raise RepairError("unsupported repair adjustment")
    if interval == "1Day":
        index = index.normalize().unique()
    params = {"symbols": ",".join(sorted(reverse)), "timeframe": interval,
              "start": index[0].tz_localize("UTC").isoformat(),
              "end": (index[-1] + (pd.Timedelta(days=1) if interval == "1Day"
                                   else pd.Timedelta(minutes=15))).tz_localize("UTC").isoformat(),
              "adjustment": adjustment, "feed": "sip", "limit": 10000, "sort": "asc"}
    rows, seen_tokens = [], set()
    while True:
        try:
            response = client.get("https://data.alpaca.markets/v2/stocks/bars",
                                  params=params, headers=headers, timeout=60)
        except requests.RequestException:
            raise RepairError(f"Alpaca transport failed on {day}") from None
        if response.status_code != 200:
            raise RepairError(f"Alpaca HTTP {response.status_code} on {day}")
        try:
            body = response.json()
        except ValueError:
            raise RepairError(f"invalid Alpaca JSON on {day}") from None
        for fetched, bars in (body.get("bars") or {}).items():
            if fetched not in reverse:
                raise RepairError("provider returned an unrequested symbol")
            for bar in bars:
                stamp = pd.Timestamp(bar["t"]).tz_convert("UTC").tz_localize(None)
                if interval == "1Day":
                    stamp = stamp.normalize()
                if stamp not in index:  # endpoint may include the close boundary
                    continue
                for symbol in reverse[fetched]:
                    rows.append([symbol, stamp, *[float(bar[c]) for c in ("o", "h", "l", "c", "v")]])
        token = body.get("next_page_token")
        if not token:
            break
        if token in seen_tokens:
            raise RepairError("provider repeated a pagination token")
        seen_tokens.add(token)
        params["page_token"] = token
    if not rows:
        return pd.DataFrame({"symbol": pd.Series(dtype=str), "timestamp": pd.Series(dtype="datetime64[ns]"),
                             **{c: pd.Series(dtype=float) for c in COLS}})
    return validate_panel(pd.DataFrame(rows, columns=KEYS + COLS))


def compare_reference(original: pd.DataFrame, references: pd.DataFrame) -> dict:
    old = original.set_index(KEYS)[COLS]
    new = references.set_index(KEYS)[COLS]
    shared = old.index.intersection(new.index)
    differences = new.loc[shared] - old.loc[shared]
    unequal = differences.ne(0).any(axis=1)
    by_symbol = unequal.groupby(level="symbol").agg(["size", "sum"])
    return {"overlap_rows": len(shared), "different_rows": int(unequal.sum()),
            "symbols": {symbol: {"overlap_rows": int(row["size"]), "different_rows": int(row["sum"])}
                        for symbol, row in by_symbol.iterrows()},
            "max_absolute_difference": differences.abs().max().fillna(0).to_dict()}


def merge_repairs(original: pd.DataFrame, additions: pd.DataFrame, sessions: dict,
                  days: list[str], comparison: dict) -> pd.DataFrame:
    old, new = validate_panel(original), validate_panel(additions)
    if new.empty:
        raise RepairError("no repair bars returned")
    allowed = pd.DatetimeIndex(np.concatenate([sessions[d].to_numpy() for d in days]))
    if not new.timestamp.isin(allowed).all():
        raise RepairError("repair contains bars outside the requested missing sessions")
    if not set(new.symbol).issubset(set(old.symbol)):
        raise RepairError("repair introduces a new research symbol")
    old_keys = pd.MultiIndex.from_frame(old[KEYS])
    new_keys = pd.MultiIndex.from_frame(new[KEYS])
    if len(old_keys.intersection(new_keys)):
        raise RepairError("repair would replace an existing bar")
    unproven = [symbol for symbol in new.symbol.unique()
                if not comparison["symbols"].get(symbol, {}).get("overlap_rows")
                or comparison["symbols"][symbol]["different_rows"]]
    if unproven:
        raise RepairError("reference mismatch or no overlap for: " + ",".join(sorted(unproven)))
    return pd.concat([old, new], ignore_index=True).sort_values(KEYS).reset_index(drop=True)


def clip_to_calendar(panel: pd.DataFrame, sessions: dict) -> tuple[pd.DataFrame, dict]:
    """Remove known closed-market bars within the calendar's explicit span."""
    valid = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in sessions.values()]))
    days = panel.timestamp.dt.strftime("%Y-%m-%d")
    in_span = days.between(min(sessions), max(sessions))
    removed = panel[in_span & ~panel.timestamp.isin(valid)]
    counts = removed.groupby([removed.timestamp.dt.strftime("%Y-%m-%d"), "symbol"]).size()
    evidence = {"removed_rows": len(removed),
                "by_day_symbol": [{"date": d, "symbol": s, "rows": int(n)} for (d, s), n in counts.items()],
                "removed_rows_sha256": hashlib.sha256(
                    removed.sort_values(KEYS).to_csv(index=False).encode()).hexdigest()}
    return panel.drop(index=removed.index).reset_index(drop=True), evidence


def clip_identity_history(panel: pd.DataFrame, exceptions: dict) -> tuple[pd.DataFrame, dict]:
    """Exclude issuer-incompatible predecessor history before feature warmup."""
    mask = pd.Series(False, index=panel.index)
    for symbol, record in exceptions.get("identity_starts", {}).items():
        mask |= (panel.symbol == symbol) & (panel.timestamp < pd.Timestamp(record["date"]))
    removed = panel[mask]
    return panel[~mask].reset_index(drop=True), {
        "removed_rows": len(removed),
        "by_symbol": {s: int(n) for s, n in removed.groupby("symbol").size().items()},
        "removed_rows_sha256": hashlib.sha256(removed.sort_values(KEYS).to_csv(index=False).encode()).hexdigest()}


def classify_coverage(report: dict, exceptions: dict) -> dict:
    accepted, unexpected = {}, {}
    for symbol, days in report["missing_sessions_by_symbol"].items():
        known = exceptions.get("nontrading_sessions", {}).get(symbol, {})
        if good := [d for d in days if d in known]:
            accepted[symbol] = good
        if bad := [d for d in days if d not in known]:
            unexpected[symbol] = bad
    return {"documented_nontrading_sessions": accepted,
            "unexpected_missing_sessions_by_symbol": unexpected,
            "passed": not (unexpected or report["missing_underlying_days"]
                            or report["missing_option_days"] or report["off_session_rows"]
                            or report["noncalendar_underlying_days"] or report["noncalendar_option_days"])}


def replace_vintage(original: pd.DataFrame, refresh: pd.DataFrame,
                    references: pd.DataFrame, symbols: list[str], sessions: dict) -> tuple[pd.DataFrame, dict]:
    """Replace a whole symbol's history when a corporate-action vintage moved."""
    refreshed = validate_panel(refresh)
    if set(refreshed.symbol) != set(symbols):
        raise RepairError("full-history refresh symbol set is incomplete")
    if not refreshed.timestamp.isin(pd.DatetimeIndex(np.concatenate(
            [idx.to_numpy() for idx in sessions.values()]))).all():
        raise RepairError("full-history refresh contains off-calendar bars")
    reference = references[references.symbol.isin(symbols)]
    fresh_comparison = compare_reference(refreshed, reference)
    if (fresh_comparison["different_rows"] or fresh_comparison["overlap_rows"] != len(reference)):
        raise RepairError("full-history refresh does not match freshly fetched references")
    # Full-history refresh cannot silently shorten a symbol's observed lifetime.
    old_ranges = original[original.symbol.isin(symbols)].groupby("symbol").timestamp.agg(["min", "max"])
    new_ranges = refreshed.groupby("symbol").timestamp.agg(["min", "max"])
    if (new_ranges["min"].dt.normalize() > old_ranges["min"].dt.normalize()).any() or (
            new_ranges["max"].dt.normalize() < old_ranges["max"].dt.normalize()).any():
        raise RepairError("full-history refresh shortened a symbol lifetime")
    changed = compare_reference(original[original.symbol.isin(symbols)], refreshed)
    result = pd.concat([original[~original.symbol.isin(symbols)], refreshed], ignore_index=True)
    return result.sort_values(KEYS).reset_index(drop=True), {"symbols": symbols, "rows": len(refreshed),
            "reason": "fresh all-adjusted references differ from historical adjustment vintage",
            "old_vs_fresh": changed, "fresh_reference_parity": fresh_comparison}


def cache_hashes(source: Path) -> dict:
    result = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise RepairError("source cache contains symlinks")
        if path.is_file():
            if path.name.startswith(".env") or path.suffix in (".key", ".pem"):
                raise RepairError("unexpected credential file in source cache")
            result[str(path.relative_to(source))] = sha256(path)
    return result


def stage_cache(source: Path, destination: Path, repaired: pd.DataFrame, manifest: dict) -> None:
    """Copy all original files to a fresh namespace, verify, replace only copy."""
    if destination.exists() or destination.resolve().is_relative_to(source.resolve()):
        raise RepairError("staged cache must be a new path outside the source cache")
    before = cache_hashes(source)
    if before.get("underlying_15m.parquet") != manifest["source_underlying_sha256"]:
        raise RepairError("original underlying changed after repair planning")
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    if cache_hashes(destination) != before or cache_hashes(source) != before:
        raise RepairError("source or copy changed while staging")
    output = destination / "underlying_15m.parquet"
    repaired.to_parquet(output, index=False)
    manifest = dict(manifest, original_cache_sha256=before,
                    candidate_underlying_sha256=sha256(output))
    (destination / "repair_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def complete_context(destination: Path, records: list[dict], aliases: dict, headers: dict, end: str):
    """Fetch both daily price bases; surface IV always uses raw spot."""
    cache = destination / "cache"
    manifest_path = cache / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("context_status") == "refreshed_raw_spot":
        raise RepairError("candidate context already refreshed; use a new candidate for another vintage")
    if sha256(cache / "underlying_15m.parquet") != manifest["candidate_underlying_sha256"]:
        raise RepairError("candidate underlying changed after staging")
    start = min(r["date"] for r in records)
    history = calendar_sessions(records, start, end)
    index = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in history.values()]))
    exceptions = json.loads((cache / "stock_history_exceptions.json").read_text())
    daily_path = cache / "underlying_daily.parquet"
    surface_path = cache / "surface_daily.parquet"
    if manifest.get("context_sha256", {}).get(daily_path.name) == sha256(daily_path):
        daily = pd.read_parquet(daily_path)
        excluded = manifest.get("context_identity_trim", {})
    else:
        fetched = fetch_day("daily-history", {"daily-history": index}, aliases, headers, interval="1Day")
        fetched, excluded = clip_identity_history(fetched, exceptions)
        daily = _daily_schema(fetched)
    raw = fetch_day("daily-raw-history", {"daily-raw-history": index}, aliases, headers,
                    interval="1Day", adjustment="raw")
    raw, raw_excluded = clip_identity_history(raw, exceptions)
    raw_daily = _daily_schema(raw)
    from nn_meta.price_basis import raw_spot_provenance, require_raw_panel
    raw_daily.attrs.update(raw_spot_provenance("1d", provider="alpaca", feed="sip"))
    require_raw_panel(raw_daily, "1d")
    intraday = pd.read_parquet(cache / "underlying_15m.parquet", columns=KEYS)
    wanted = pd.MultiIndex.from_arrays([intraday.symbol, intraday.timestamp.dt.normalize()]).unique()
    actual = pd.MultiIndex.from_frame(daily[["underlying", "date"]])
    if len(wanted.difference(actual)):
        raise RepairError("fresh daily history lacks observed intraday symbol sessions")
    if len(wanted.difference(pd.MultiIndex.from_frame(raw_daily[["underlying", "date"]]))):
        raise RepairError("raw daily history lacks observed intraday symbol sessions")
    # Daily close and final 15m close can legitimately differ due trade-bar
    # construction. Bind provider/feed/adjustment and use matching vintage,
    # rather than pretending aggregation equality proves equivalence.
    manifest["previous_context_sha256"] = {p.name: sha256(p) for p in (daily_path, surface_path)}
    manifest["context_status"] = "refresh_in_progress"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary = daily_path.with_suffix(".tmp")
    daily.to_parquet(temporary, index=False)
    temporary.replace(daily_path)
    raw_daily_path = cache / "underlying_daily_raw.parquet"
    raw_daily.to_parquet(raw_daily_path, index=False)
    from nn_meta.build_surface import load_daily_bars, build_surface
    from nn_meta import config
    bars = load_daily_bars()
    surface = build_surface(bars, daily, raw_spot=raw_daily, root_aliases=config.TICKER_ALIASES)
    temporary = surface_path.with_suffix(".tmp")
    surface.to_parquet(temporary, index=False)
    temporary.replace(surface_path)
    manifest.update(context_status="refreshed_raw_spot", context_lineage=dict(LINEAGE, interval="1Day"),
                    context_rows={"daily": len(daily), "surface": len(surface)},
                    context_identity_trim=excluded, raw_context_identity_trim=raw_excluded,
                    raw_daily_provenance=raw_spot_provenance("1d", provider="alpaca", feed="sip"),
                    context_sha256={p.name: sha256(p) for p in (daily_path, raw_daily_path, surface_path)},
                    unresolved_model_gates=["Raw 15m spot and corrected raw-spot universe must be completed and validated before label generation."])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Daily context refreshed: {len(daily):,} daily / {len(surface):,} surface rows.", flush=True)


def _daily_schema(frame):
    result = frame.rename(columns={"symbol": "underlying", "timestamp": "date",
                                   **{c: c.lower() for c in COLS}})
    result["vwap"], result["transactions"] = pd.NA, pd.NA
    return result.sort_values(["underlying", "date"]).reset_index(drop=True)


def verify_adopted_outputs(cache: Path, manifest: dict, hashes: dict | None = None) -> None:
    """The completed derivation owns the exact option-part inventory."""
    adopted = manifest.get("option_derivation")
    if not adopted or not manifest.get("options_daily_raw_filter_verified"):
        raise RepairError("surface requires a completed option derivation adoption")
    expected = adopted["output_sha256"]
    actual_names = {p.relative_to(cache).as_posix() for p in (cache / "bars_daily").glob("*.parquet")}
    actual_names.update(("contracts.parquet", "universe.parquet"))
    if actual_names != set(expected):
        raise RepairError("adopted option-part inventory changed after derivation")
    current = {name: hashes.get(name) if hashes is not None else sha256(cache / name) for name in actual_names}
    if current != expected:
        raise RepairError("adopted option inputs changed before surface rebuild or seal")


def rebuild_surface_context(destination: Path):
    """Finish only after option daily bars were rederived with raw moneyness."""
    from nn_meta.build_surface import load_daily_bars, build_surface
    from nn_meta import config
    from nn_meta.price_basis import require_raw_panel
    cache = destination / "cache"
    manifest_path = cache / "repair_manifest.json"
    before_manifest = json.loads(manifest_path.read_text())
    verify_adopted_outputs(cache, before_manifest)
    daily = pd.read_parquet(cache / "underlying_daily.parquet")
    raw = require_raw_panel(pd.read_parquet(cache / "underlying_daily_raw.parquet"), "1d")
    bars = load_daily_bars()  # validates broad/raw-filter universe + every part
    surface = build_surface(bars, daily, raw_spot=raw, root_aliases=config.TICKER_ALIASES)
    path = cache / "surface_daily.parquet"
    prior = destination / "context_history" / "surface_before_raw_filter.parquet"
    prior.parent.mkdir(exist_ok=True)
    if not prior.exists():
        shutil.copy2(path, prior)
    temporary = path.with_suffix(".tmp")
    surface.to_parquet(temporary, index=False)
    temporary.replace(path)
    manifest = json.loads(manifest_path.read_text())
    manifest.update(context_status="refreshed_raw_spot", options_daily_raw_filter_verified=True,
                    surface_raw_filter_rows=len(bars), surface_rows=len(surface),
                    context_sha256={name: sha256(cache / name) for name in (
                        "underlying_daily.parquet", "underlying_daily_raw.parquet", "surface_daily.parquet")},
                    universe_sha256=sha256(cache / "universe.parquet"),
                    exchange_calendar_sha256=sha256(cache / "exchange_calendar.json"))
    gates = []
    if not (cache / "underlying_15m_raw.parquet").exists():
        gates.append("Separate raw15m stock spot is not complete.")
    if not manifest.get("raw_intraday_coverage", {}).get("missing_technical_timestamps") == 0:
        gates.append("Raw intraday coverage is not verified against adjusted technical timestamps.")
    manifest["unresolved_model_gates"] = gates
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Surface rederived from {len(bars):,} raw-filtered option daily rows: {len(surface):,} surface rows.", flush=True)


def adopt_derivation(destination: Path, derived: Path):
    """Verify complete broad-chain derivation, then replace candidate-only inputs."""
    cache = destination / "cache"
    manifest_path = derived / "derivation_manifest.json"
    derivation = json.loads(manifest_path.read_text())
    if derivation.get("status") != "complete":
        raise RepairError("option derivation is incomplete")
    source = derivation["derivation_provenance"]
    if source["raw_daily_sha256"] != sha256(cache / "underlying_daily_raw.parquet"):
        raise RepairError("raw daily bytes changed after option derivation")
    if Path(source["input_cache"]).resolve() != cache.resolve():
        raise RepairError("option derivation came from another cache")
    inventory = [{"name": p.name, "bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns}
                 for p in sorted((cache / "flatfiles_15m").glob("*.parquet"))]
    if inventory != derivation.get("input_inventory") or hashlib.sha256(
            json.dumps(inventory, sort_keys=True).encode()).hexdigest() != source.get("flatfile_inventory_sha256"):
        raise RepairError("flatfile inventory changed during option derivation")
    repair_record = json.loads((cache / "repair_manifest.json").read_text())
    original_hashes = repair_record.get("original_cache_sha256", {})
    for p in (cache / "flatfiles_15m").glob("*.parquet"):
        if original_hashes.get(p.relative_to(cache).as_posix()) != sha256(p):
            raise RepairError("flatfile bytes differ from preserved source during derivation")
    actual_hashes = {p.relative_to(derived).as_posix(): sha256(p) for p in derived.rglob("*.parquet")}
    if actual_hashes != derivation["output_sha256"]:
        raise RepairError("option derivation outputs changed after completion")
    before = pd.read_parquet(cache / "universe.parquet")
    after = pd.read_parquet(derived / "universe.parquet")
    from nn_meta.price_basis import require_raw_universe
    require_raw_universe(after)
    columns = ["ticker", "underlying", "expiration", "life_start", "strike", "type"]
    # Rebuilding the surface filter must not narrow the complete chain or
    # change the first date on which a listed contract becomes selectable.
    if not before[columns].sort_values("ticker").reset_index(drop=True).equals(
            after[columns].sort_values("ticker").reset_index(drop=True)):
        raise RepairError("all-observed contract scope or first-seen dates changed")
    old_rows = sum(len(pd.read_parquet(p, columns=["ticker"])) for p in (cache / "bars_daily").glob("*.parquet"))
    history = destination / "context_history" / "before_raw_option_filter"
    if history.exists():
        raise RepairError("candidate already adopted an option derivation")
    history.mkdir(parents=True)
    shutil.move(str(cache / "bars_daily"), str(history / "bars_daily"))
    shutil.copytree(derived / "bars_daily", cache / "bars_daily")
    for filename in ("universe.parquet", "contracts.parquet"):
        shutil.copy2(cache / filename, history / filename)
        shutil.copy2(derived / filename, cache / filename)
    shutil.copy2(manifest_path, cache / "option_derivation_manifest.json")
    repair_path = cache / "repair_manifest.json"
    repair = json.loads(repair_path.read_text())
    repair.update(option_derivation={"path": str(derived), "manifest_sha256": sha256(manifest_path),
                                    "universe_contracts": len(after), "all_observed_scope_unchanged": True,
                                    "old_daily_rows": old_rows, "raw_filtered_daily_rows": derivation["daily_rows"],
                                    "output_sha256": actual_hashes},
                  options_daily_raw_filter_verified=True,
                  context_status="raw_option_daily_ready_surface_pending")
    repair_path.write_text(json.dumps(repair, indent=2, sort_keys=True) + "\n")
    print(f"Adopted raw-filtered option context: {len(after):,} unchanged contracts; {old_rows:,} → {derivation['daily_rows']:,} daily rows.", flush=True)


def final_stock_coverage(cache: Path, manifest: dict) -> dict:
    """Recheck the full fresh timeline, with explicit evidence for no-bar days."""
    refresh = manifest.get("full_adjusted_refresh", {})
    if not refresh or refresh.get("lineage") != LINEAGE:
        raise RepairError("full fresh adjusted history is required before sealing")
    panel = validate_panel(pd.read_parquet(cache / "underlying_15m.parquet"))
    raw = pd.read_parquet(cache / "underlying_15m_raw.parquet", columns=KEYS)
    if (refresh.get("rows") != len(panel) or refresh.get("symbols") != panel.symbol.nunique()
            or not pd.MultiIndex.from_frame(panel[KEYS]).sort_values().equals(
                pd.MultiIndex.from_frame(raw).sort_values())):
        raise RepairError("full fresh raw and adjusted stock timelines are inconsistent")
    calendar = json.loads((cache / "exchange_calendar.json").read_text())
    start, end = refresh["window"]
    if calendar.get("coverage_start", "9999") > start or calendar.get("coverage_end", "") < end:
        raise RepairError("calendar does not cover the complete stock history")
    if not panel.timestamp.between(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1),
                                   inclusive="left").all():
        raise RepairError("fresh history contains bars outside its captured window")
    full_sessions = calendar_sessions(calendar["sessions"], start, end)
    exceptions = json.loads((cache / "stock_history_exceptions.json").read_text())
    for symbol, record in exceptions.get("identity_starts", {}).items():
        if ((panel.symbol == symbol) & (panel.timestamp < pd.Timestamp(record["date"]))).any():
            raise RepairError("issuer-incompatible predecessor bars remain in fresh history")
    # The warmup extends earlier than the option archive. Its stock coverage is
    # checked independently; only the model window asserts option-day coverage.
    full_report = inventory(panel, full_sessions, set(full_sessions))
    first_pass = classify_coverage(full_report, exceptions)
    raw_daily = pd.read_parquet(cache / "underlying_daily_raw.parquet")
    adjusted_daily = pd.read_parquet(cache / "underlying_daily.parquet")
    zero_volume = []
    for symbol, days in first_pass["unexpected_missing_sessions_by_symbol"].items():
        for day in days:
            if day >= manifest["window"][0]:
                continue
            rows = [frame[(frame.underlying == symbol) & (frame.date == pd.Timestamp(day))]
                    for frame in (raw_daily, adjusted_daily)]
            if all(len(row) == 1 and row.iloc[0].volume == 0 for row in rows):
                evidence = {"symbol": symbol, "date": day, "provider": "alpaca", "feed": "sip",
                            "raw_daily_volume": 0, "adjusted_daily_volume": 0,
                            "interpretation": "provider reports zero daily volume; no intraday bars synthesized"}
                zero_volume.append(evidence)
                exceptions.setdefault("nontrading_sessions", {}).setdefault(symbol, {})[day] = evidence
    full_result = classify_coverage(full_report, exceptions)
    baseline_sessions = calendar_sessions(calendar["sessions"], *manifest["window"])
    option_days = {p.stem for p in (cache / "flatfiles_15m").glob("*.parquet")}
    baseline_report = inventory(panel, baseline_sessions, option_days)
    baseline_result = classify_coverage(baseline_report, exceptions)
    if not full_result["passed"] or not baseline_result["passed"]:
        raise RepairError("final full-history or baseline session coverage is incomplete: " +
                          json.dumps({"full_history": full_result, "baseline": baseline_result}, sort_keys=True))
    return {"coverage_result": baseline_result, "final_baseline_inventory": baseline_report,
            "full_stock_history_coverage": full_result, "final_stock_history_inventory": full_report,
            "vendor_zero_volume_warmup_sessions": zero_volume,
            "raw_and_adjusted_timestamps_identical": True}


def seal_candidate(destination: Path):
    """Bind validated candidate input bytes; an edited fresh campaign must fail."""
    from scripts.research_local import _omit_input
    cache = destination / "cache"
    path = cache / "repair_manifest.json"
    manifest = json.loads(path.read_text())
    if manifest.get("sealed_cache_sha256"):
        raise RepairError("sealed candidate is immutable; use a fresh candidate")
    if (not manifest.get("coverage_result", {}).get("passed")
            or manifest.get("context_status") != "refreshed_raw_spot"
            or not manifest.get("options_daily_raw_filter_verified")
            or manifest.get("unresolved_model_gates")):
        raise RepairError("cannot seal an incomplete data candidate")
    stock_coverage = final_stock_coverage(cache, manifest)
    hashes = {name: digest for name, digest in cache_hashes(cache).items()
              if name != "repair_manifest.json" and not _omit_input(Path(name))}
    verify_adopted_outputs(cache, manifest, hashes)
    original_flatfiles = {name: digest for name, digest in manifest["original_cache_sha256"].items()
                          if name.startswith("flatfiles_15m/")}
    current_flatfiles = {name: digest for name, digest in hashes.items() if name.startswith("flatfiles_15m/")}
    if current_flatfiles != original_flatfiles:
        raise RepairError("candidate option flatfiles changed after their validated derivation")
    required = {"underlying_15m.parquet": manifest["candidate_underlying_sha256"],
                "underlying_15m_raw.parquet": manifest["raw_intraday_sha256"],
                "exchange_calendar.json": manifest["exchange_calendar_sha256"],
                **manifest["context_sha256"], **manifest["option_derivation"]["output_sha256"]}
    if any(hashes.get(name) != digest for name, digest in required.items()):
        raise RepairError("candidate changed after its data validation")
    originals = cache_hashes(Path(manifest["source_cache"]))
    if originals != manifest["original_cache_sha256"]:
        raise RepairError("historical source cache changed during repair")
    manifest.update(stock_coverage)
    manifest.update(sealed_cache_sha256=hashes, original_cache_preserved=True,
                    sealed_at_utc=datetime.now(timezone.utc).isoformat(),
                    sealed_cache_digest=hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest())
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Sealed {len(hashes)} candidate inputs; every historical source-cache file is unchanged.", flush=True)


def fetch_auxiliary_daily(destination, records, symbols, headers, start, end):
    """Fetch explicit old option roots when the current ticker lacks their past."""
    from nn_meta.price_basis import raw_spot_provenance, require_raw_panel
    if not symbols or any(not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,24}", s) for s in symbols):
        raise RepairError("auxiliary symbols must be explicit simple option roots")
    cache = destination / "cache"
    path = cache / "underlying_daily_raw.parquet"
    existing = require_raw_panel(pd.read_parquet(path), "1d")
    if set(symbols) & set(existing.underlying):
        raise RepairError("auxiliary root already exists; preserve it and use a new candidate")
    history = calendar_sessions(records, start, end)
    index = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in history.values()]))
    fetched = fetch_day("auxiliary-daily", {"auxiliary-daily": index}, {s: s for s in symbols}, headers,
                        interval="1Day", adjustment="raw")
    if set(fetched.symbol) != set(symbols):
        raise RepairError("provider did not return every requested auxiliary root")
    additional = _daily_schema(fetched)
    additional.attrs.update(raw_spot_provenance("1d", provider="alpaca", feed="sip"))
    require_raw_panel(additional, "1d")
    auxiliary_path = destination / ("auxiliary_raw_daily_" + "_".join(symbols) + ".parquet")
    if auxiliary_path.exists():
        raise RepairError("auxiliary fetch output already exists")
    additional.to_parquet(auxiliary_path, index=False)
    combined = pd.concat([existing, additional], ignore_index=True).sort_values(["underlying", "date"])
    combined.attrs.update(raw_spot_provenance("1d", provider="alpaca", feed="sip"))
    require_raw_panel(combined, "1d")
    manifest_path = cache / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    before = sha256(path)
    temporary = path.with_suffix(".tmp")
    combined.to_parquet(temporary, index=False)
    temporary.replace(path)
    manifest["auxiliary_raw_daily"] = {"symbols": symbols, "rows": len(additional),
        "previous_raw_daily_sha256": before, "auxiliary_sha256": sha256(auxiliary_path),
        "raw_daily_sha256": sha256(path), "price_basis": "raw", "provider": "alpaca", "feed": "sip"}
    manifest["options_daily_raw_filter_verified"] = False
    manifest["context_status"] = "requires_raw_filter_rederive"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Auxiliary raw daily: {len(additional):,} rows for {','.join(symbols)}.", flush=True)


def repair_warmup(destination, records, aliases, headers, start, end):
    """Repair pre-window technical gaps revealed by the complete raw timeline."""
    cache = destination / "cache"
    manifest_path = cache / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("sealed_cache_sha256"):
        raise RepairError("sealed candidate is immutable; use a fresh candidate")
    path = cache / "underlying_15m.parquet"
    original = validate_panel(pd.read_parquet(path))
    raw_keys = pd.read_parquet(cache / "underlying_15m_raw.parquet", columns=KEYS)
    missing = pd.MultiIndex.from_frame(raw_keys).difference(pd.MultiIndex.from_frame(original[KEYS]))
    if not len(missing):
        raise RepairError("raw and technical timelines already match")
    days = sorted(set(pd.DatetimeIndex(missing.get_level_values("timestamp")).strftime("%Y-%m-%d")))
    if any(d >= manifest["window"][0] for d in days):
        raise RepairError("this bounded repair only accepts pre-window warmup gaps")
    history = calendar_sessions(records, start, end)
    ordered = list(history)
    if any(day not in ordered or ordered.index(day) == 0 for day in days):
        raise RepairError("warmup gap needs an earlier intact calendar reference session")
    reference_days = sorted(set(ordered[ordered.index(day) - 1] for day in days))
    downloaded = {}
    out = destination / "warmup_repair"
    out.mkdir(exist_ok=True)
    for day in sorted(set(days + reference_days)):
        frame = fetch_day(day, history, aliases, headers)
        frame.to_parquet(out / f"{day}.parquet", index=False)
        downloaded[day] = frame
    references = pd.concat([downloaded[d] for d in reference_days], ignore_index=True)
    comparison = compare_reference(original, references)
    additions = pd.concat([downloaded[d] for d in days], ignore_index=True)
    additions = additions[pd.MultiIndex.from_frame(additions[KEYS]).isin(missing)]
    if len(additions) != len(missing):
        raise RepairError("warmup fetch did not cover every missing technical timestamp")
    # Earlier corporate actions can alter only the pre-window history, while
    # all later reference sessions still match. Replace that symbol's whole
    # adjusted history from the same vendor vintage before joining new bars.
    changed = sorted(s for s in additions.symbol.unique()
                     if comparison["symbols"].get(s, {}).get("different_rows"))
    refreshed_evidence = None
    if changed:
        index = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in history.values()]))
        refreshed = []
        for symbol in changed:
            frame = fetch_day(symbol, {symbol: index}, {symbol: aliases[symbol]}, headers)
            frame.to_parquet(out / f"full_{symbol}.parquet", index=False)
            refreshed.append(frame)
        original, refreshed_evidence = replace_vintage(original, pd.concat(refreshed, ignore_index=True),
                                                       references, changed, history)
        additions = additions[~additions.symbol.isin(changed)]
    repaired = merge_repairs(original, additions, history, days, comparison)
    if not pd.MultiIndex.from_frame(repaired[KEYS]).sort_values().equals(
            pd.MultiIndex.from_frame(raw_keys).sort_values()):
        raise RepairError("raw and repaired technical keys do not match")
    before = sha256(path)
    temporary = path.with_suffix(".tmp")
    repaired.to_parquet(temporary, index=False)
    temporary.replace(path)
    manifest.update(candidate_underlying_sha256=sha256(path), warmup_repair={
        "days": days, "reference_days": reference_days, "added_rows": len(additions),
        "full_history_refresh": refreshed_evidence,
        "previous_underlying_sha256": before, "reference_comparison": comparison,
        "download_sha256": {p.name: sha256(p) for p in out.glob("*.parquet")}},
        raw_and_adjusted_timestamps_identical=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Warmup repaired: {len(additions):,} bars; {len(repaired):,} identical raw/adjusted timestamps.", flush=True)


def fetch_raw_intraday(destination: Path, records: list[dict], aliases: dict,
                       headers: dict, start: str, end: str, workers: int):
    """Checkpoint raw spot separately from adjusted technical history."""
    from nn_meta.price_basis import raw_spot_provenance, require_raw_panel
    cache = destination / "cache"
    manifest_path = cache / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if sha256(cache / "underlying_15m.parquet") != manifest["candidate_underlying_sha256"]:
        raise RepairError("candidate technical history changed before raw fetch")
    path = cache / "underlying_15m_raw.parquet"
    if path.exists():
        raise RepairError("raw intraday panel already exists; preserve it and use a new candidate")
    history = calendar_sessions(records, start, end)
    index = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in history.values()]))
    exceptions = json.loads((cache / "stock_history_exceptions.json").read_text())
    parts = destination / "raw_15m_parts"
    parts.mkdir(exist_ok=True)
    scope_path = parts / "scope.json"
    scope = {"window": [start, end], "aliases": aliases,
             "technical_sha256": manifest["candidate_underlying_sha256"],
             "exceptions_sha256": sha256(cache / "stock_history_exceptions.json"),
             "provenance": raw_spot_provenance("15m", provider="alpaca", feed="sip")}
    if scope_path.exists() and json.loads(scope_path.read_text()) != scope:
        raise RepairError("raw fetch scope changed; use a new candidate")
    scope_path.write_text(json.dumps(scope, sort_keys=True, indent=2) + "\n")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_day, symbol, {symbol: index}, {symbol: fetched}, headers,
                                   interval="15Min", adjustment="raw"): symbol
                   for symbol, fetched in aliases.items() if not (parts / f"{symbol}.parquet").exists()}
        for future in as_completed(futures):
            symbol = futures[future]
            frame, _ = clip_identity_history(future.result(), exceptions)
            frame.attrs.update(raw_spot_provenance("15m", provider="alpaca", feed="sip"))
            require_raw_panel(frame, "15m")
            temporary = parts / f"{symbol}.parquet.tmp"
            frame.to_parquet(temporary, index=False)
            temporary.replace(parts / f"{symbol}.parquet")
            print(f"Raw spot {symbol}: {len(frame):,} bars", flush=True)
    raw = pd.concat([require_raw_panel(pd.read_parquet(parts / f"{s}.parquet"), "15m")
                     for s in sorted(aliases)], ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    raw.attrs.update(raw_spot_provenance("15m", provider="alpaca", feed="sip"))
    technical = pd.read_parquet(cache / "underlying_15m.parquet", columns=KEYS)
    missing = pd.MultiIndex.from_frame(technical).difference(pd.MultiIndex.from_frame(raw[KEYS]))
    if len(missing):
        (destination / "raw_coverage_gaps.json").write_text(json.dumps(
            [{"symbol": s, "timestamp": str(t)} for s, t in missing], indent=2) + "\n")
        raise RepairError(f"raw spot is missing {len(missing)} adjusted technical timestamps")
    raw.to_parquet(path, index=False)
    # Read manifest again: context refresh may have completed alongside fetch.
    manifest = json.loads(manifest_path.read_text())
    manifest.update(raw_intraday_provenance=raw_spot_provenance("15m", provider="alpaca", feed="sip"),
                    raw_intraday_sha256=sha256(path), raw_intraday_rows=len(raw),
                    raw_intraday_coverage={"missing_technical_timestamps": 0,
                                          "raw_parts_sha256": {p.name: sha256(p) for p in sorted(parts.glob("*.parquet"))}})
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Raw intraday spot complete: {len(raw):,} bars / {len(aliases)} symbols.", flush=True)


def fetch_adjusted_intraday(destination, records, aliases, headers, start, end, workers):
    """Replace the entire technical history with one explicit fresh policy."""
    cache = destination / "cache"
    manifest_path = cache / "repair_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("sealed_cache_sha256"):
        raise RepairError("sealed candidate is immutable; use a fresh candidate")
    history = calendar_sessions(records, start, end)
    index = pd.DatetimeIndex(np.concatenate([idx.to_numpy() for idx in history.values()]))
    exceptions_path = cache / "stock_history_exceptions.json"
    exceptions = json.loads(exceptions_path.read_text())
    parts = destination / "adjusted_15m_parts"
    parts.mkdir(exist_ok=True)
    scope = {"window": [start, end], "aliases": aliases,
             "lineage": LINEAGE, "exceptions_sha256": sha256(exceptions_path),
             "raw_sha256": sha256(cache / "underlying_15m_raw.parquet")}
    scope_path = parts / "scope.json"
    if scope_path.exists() and json.loads(scope_path.read_text()) != scope:
        raise RepairError("adjusted full-fetch scope changed; use a fresh candidate")
    scope_path.write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")
    remaining = []
    for symbol in aliases:
        part, digest = parts / f"{symbol}.parquet", parts / f"{symbol}.sha256"
        if part.exists():
            if not digest.exists() or digest.read_text().strip() != sha256(part):
                raise RepairError("adjusted checkpoint lacks matching captured-byte hash")
        else:
            remaining.append(symbol)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_day, symbol, {symbol: index}, {symbol: aliases[symbol]},
                                   headers, interval="15Min", adjustment="all"): symbol for symbol in remaining}
        for future in as_completed(futures):
            symbol = futures[future]
            frame, _ = clip_identity_history(future.result(), exceptions)
            frame = validate_panel(frame)
            frame.attrs.update(provider="alpaca", feed="sip", adjustment="all", interval="15m")
            path = parts / f"{symbol}.parquet"
            temporary = path.with_suffix(".tmp")
            frame.to_parquet(temporary, index=False)
            temporary.replace(path)
            (parts / f"{symbol}.sha256").write_text(sha256(path) + "\n")
            print(f"Fresh technical {symbol}: {len(frame):,} bars", flush=True)
    panel = pd.concat([pd.read_parquet(parts / f"{symbol}.parquet") for symbol in sorted(aliases)],
                      ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    panel = validate_panel(panel)
    panel.attrs.update(provider="alpaca", feed="sip", adjustment="all", interval="15m")
    raw = pd.read_parquet(cache / "underlying_15m_raw.parquet", columns=KEYS)
    if not pd.MultiIndex.from_frame(panel[KEYS]).sort_values().equals(pd.MultiIndex.from_frame(raw).sort_values()):
        raise RepairError("full fresh raw and adjusted stock timestamps differ; investigate before sealing")
    original = cache / "underlying_15m.parquet"
    previous = destination / "context_history" / "underlying_15m_before_full_refresh.parquet"
    previous.parent.mkdir(exist_ok=True)
    if previous.exists():
        raise RepairError("fresh adjusted panel was already installed")
    before = sha256(original)
    shutil.copy2(original, previous)
    temporary = original.with_suffix(".tmp")
    panel.to_parquet(temporary, index=False)
    temporary.replace(original)
    manifest = json.loads(manifest_path.read_text())
    manifest.update(candidate_underlying_sha256=sha256(original),
                    raw_and_adjusted_timestamps_identical=True,
                    full_adjusted_refresh={"symbols": len(aliases), "rows": len(panel),
                        "window": [start, end], "lineage": LINEAGE,
                        "previous_underlying_sha256": before,
                        "parts_sha256": {p.name: sha256(p) for p in sorted(parts.glob("*.parquet"))}})
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Full fresh technical history complete: {len(panel):,} bars; exact raw/adjusted timestamp equality.", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("inventory", "fetch", "refresh", "stage", "context", "raw", "surface", "auxiliary", "adopt", "seal", "warmup", "adjusted"))
    ap.add_argument("--candidate")
    ap.add_argument("--output-candidate", help="stage into a fresh candidate name while preserving downloads")
    ap.add_argument("--symbols", help="comma-separated exact historical option roots for auxiliary daily fetch")
    ap.add_argument("--derivation", type=Path, help="completed isolated option derivation for adopt")
    ap.add_argument("--calendar", type=Path, required=True)
    ap.add_argument("--source-cache", type=Path, default=ROOT / "nn_meta" / "data_cache_v5")
    ap.add_argument("--start", default="2024-08-26")
    ap.add_argument("--end", default="2026-08-24")
    ap.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)))
    ap.add_argument("--report", type=Path, help="optional inventory report output (must not exist)")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args(argv)
    if args.workers < 1:
        ap.error("workers must be positive")
    try:
        source = args.source_cache.resolve()
        original_path = source / "underlying_15m.parquet"
        original = validate_panel(pd.read_parquet(original_path))
        records = json.loads(args.calendar.read_text())
        sessions = calendar_sessions(records, args.start, args.end)
        options = {p.stem for p in (source / "flatfiles_15m").glob("*.parquet")}
        report = inventory(original, sessions, options)
        summary = {key: value for key, value in report.items()
                   if key not in ("missing_sessions_by_symbol", "partial_sessions_by_symbol")}
        summary.update(source_cache=str(source), symbols_with_missing_sessions=len(report["missing_sessions_by_symbol"]),
                       symbols_with_partial_sessions=len(report["partial_sessions_by_symbol"]))
        print(json.dumps(summary, indent=2), flush=True)
        if args.action == "inventory":
            if args.report:
                with args.report.open("x") as handle:
                    json.dump(report, handle, indent=2)
            return 0
        destination = candidate_dir(args.candidate or "")
        output_destination = candidate_dir(args.output_candidate) if args.output_candidate else destination
        if args.output_candidate and args.action != "stage":
            raise RepairError("output-candidate is only valid for stage")
        days, references = repair_days(report, sessions)
        displayed_lineage = dict(LINEAGE)
        if args.action in ("raw", "auxiliary"):
            displayed_lineage["adjustment"] = "raw"
        if args.action in ("context", "auxiliary", "surface"):
            displayed_lineage["interval"] = "1Day"
        if args.action in ("context", "surface"):
            displayed_lineage["adjustment"] = "all for technical returns; raw for option spot/IV"
        print(json.dumps({"action": args.action, "mode": "RUN" if args.run else "PREVIEW",
                          "candidate": str(destination), "output_candidate": str(output_destination), "repair_days": days,
                          "reference_days": references,
                          "full_history_window": [original.timestamp.min().date().isoformat(), args.end]
                              if args.action in ("raw", "context", "auxiliary") else None,
                          "lineage": displayed_lineage}), flush=True)
        if not args.run:
            return 0
        os.environ["NN_META_POOL"] = "v6"
        if args.action in ("context", "raw", "surface", "auxiliary", "adopt", "seal", "warmup", "adjusted"):
            os.environ["NN_META_CAMPAIGN"] = "data-context-repair"
            os.environ["NN_META_DATA_CANDIDATE"] = args.candidate
        from nn_meta import config
        aliases = {s: config.FETCH_ALIASES.get(s) or config.TICKER_ALIASES.get(s, s)
                   for s in sorted(original.symbol.unique())}
        scope = {"source_cache": str(source), "source_underlying_sha256": sha256(original_path),
                 "calendar_sha256": sha256(args.calendar), "window": [args.start, args.end],
                 "repair_days": days, "reference_days": references,
                 "aliases": aliases, "lineage": LINEAGE}
        if args.action == "surface":
            rebuild_surface_context(destination)
            return 0
        if args.action == "seal":
            seal_candidate(destination)
            return 0
        if args.action == "adopt":
            if args.derivation is None:
                raise RepairError("adopt requires an explicit completed derivation")
            adopt_derivation(destination, args.derivation)
            return 0
        if args.action in ("context", "raw", "auxiliary", "warmup", "adjusted"):
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            headers = {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", ""),
                       "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET", "")}
            if not all(headers.values()):
                raise RepairError("Alpaca credentials are unavailable")
            if args.action == "context":
                complete_context(destination, records, aliases, headers, args.end)
            elif args.action == "auxiliary":
                fetch_auxiliary_daily(destination, records, (args.symbols or "").upper().split(","), headers,
                                      original.timestamp.min().date().isoformat(), args.end)
            elif args.action == "warmup":
                repair_warmup(destination, records, aliases, headers,
                              original.timestamp.min().date().isoformat(), args.end)
            elif args.action == "adjusted":
                fetch_adjusted_intraday(destination, records, aliases, headers,
                                       original.timestamp.min().date().isoformat(), args.end, args.workers)
            else:
                fetch_raw_intraday(destination, records, aliases, headers,
                                   original.timestamp.min().date().isoformat(), args.end, args.workers)
            return 0
        if args.action in ("fetch", "refresh"):
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            headers = {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", ""),
                       "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET", "")}
            if not all(headers.values()):
                raise RepairError("Alpaca credentials are unavailable")
            destination.mkdir(parents=True, exist_ok=True)
            scope_path = destination / "fetch_scope.json"
            if scope_path.exists():
                if json.loads(scope_path.read_text()) != scope:
                    raise RepairError("fetch input changed; use a new candidate name")
            else:
                scope_path.write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")
            (destination / "calendar.json").write_text(json.dumps(records, indent=2) + "\n")
            downloads = destination / "downloads"
            downloads.mkdir(exist_ok=True)
            if args.action == "refresh":
                refs = pd.concat([pd.read_parquet(downloads / f"{d}.parquet") for d in references])
                comparison = compare_reference(original, refs)
                changed_symbols = sorted(s for s, row in comparison["symbols"].items() if row["different_rows"])
                if not changed_symbols:
                    raise RepairError("no mismatched symbol vintages require refresh")
                history_start = original.timestamp.min().date().isoformat()
                history_sessions = calendar_sessions(records, history_start, args.end)
                history_index = pd.DatetimeIndex(np.concatenate([i.to_numpy() for i in history_sessions.values()]))
                full = destination / "full_history"
                full.mkdir(exist_ok=True)
                with ThreadPoolExecutor(max_workers=args.workers) as executor:
                    futures = {executor.submit(fetch_day, symbol, {symbol: history_index},
                               {symbol: aliases[symbol]}, headers): symbol for symbol in changed_symbols
                               if not (full / f"{symbol}.parquet").exists()}
                    for future in as_completed(futures):
                        symbol = futures[future]
                        frame = future.result()
                        temporary = full / f"{symbol}.parquet.tmp"
                        frame.to_parquet(temporary, index=False)
                        temporary.replace(full / f"{symbol}.parquet")
                        print(f"Refreshed vintage {symbol}: {len(frame):,} bars", flush=True)
                (destination / "full_history_hashes.json").write_text(json.dumps(
                    {p.name: sha256(p) for p in sorted(full.glob("*.parquet"))}, indent=2) + "\n")
                return 0
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(fetch_day, d, sessions, aliases, headers): d
                           for d in sorted(set(days + references))
                           if not (downloads / f"{d}.parquet").exists()}
                for future in as_completed(futures):
                    day = futures[future]
                    frame = future.result()
                    temporary = downloads / f"{day}.parquet.tmp"
                    frame.to_parquet(temporary, index=False)
                    temporary.replace(downloads / f"{day}.parquet")
                    print(f"Fetched {day}: {len(frame):,} bars / {frame.symbol.nunique()} symbols", flush=True)
            download_hashes = {p.name: sha256(p) for p in sorted(downloads.glob("*.parquet"))}
            (destination / "download_hashes.json").write_text(json.dumps(download_hashes, indent=2) + "\n")
            return 0
        if json.loads((destination / "fetch_scope.json").read_text()) != scope:
            raise RepairError("fetch inputs changed; use a new candidate name")
        downloads = destination / "downloads"
        hashes = json.loads((destination / "download_hashes.json").read_text())
        if hashes != {p.name: sha256(p) for p in sorted(downloads.glob("*.parquet"))}:
            raise RepairError("download bytes changed after fetch")
        refs = pd.concat([pd.read_parquet(downloads / f"{d}.parquet") for d in references], ignore_index=True)
        adds = pd.concat([pd.read_parquet(downloads / f"{d}.parquet") for d in days], ignore_index=True)
        comparison = compare_reference(original, refs)
        (destination / "reference_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
        history_start = original.timestamp.min().date().isoformat()
        history_sessions = calendar_sessions(records, history_start, args.end)
        cleaned, removed = clip_to_calendar(original, history_sessions)
        exceptions_path = ROOT / "data" / "stock_history_exceptions.json"
        exceptions = json.loads(exceptions_path.read_text())
        cleaned, identity_trim = clip_identity_history(cleaned, exceptions)
        adds, excluded_additions = clip_identity_history(adds, exceptions)
        changed_symbols = sorted(s for s, row in comparison["symbols"].items() if row["different_rows"])
        refreshed_evidence = None
        if changed_symbols:
            full = destination / "full_history"
            hashes_path = destination / "full_history_hashes.json"
            if not hashes_path.exists():
                raise RepairError("adjustment vintage changed; run explicit refresh action before staging")
            expected_hashes = json.loads(hashes_path.read_text())
            actual_hashes = {p.name: sha256(p) for p in sorted(full.glob("*.parquet"))}
            if actual_hashes != expected_hashes or set(actual_hashes) != {s + ".parquet" for s in changed_symbols}:
                raise RepairError("full-history refresh hash/symbol set mismatch")
            fresh = pd.concat([pd.read_parquet(full / f"{s}.parquet") for s in changed_symbols])
            cleaned, refreshed_evidence = replace_vintage(cleaned, fresh, refs, changed_symbols, history_sessions)
            adds = adds[~adds.symbol.isin(changed_symbols)]
        repaired = merge_repairs(cleaned, adds, sessions, days, comparison)
        after = inventory(repaired, sessions, options)
        output_destination.mkdir(parents=True, exist_ok=True)
        (output_destination / "coverage_before.json").write_text(json.dumps(report, indent=2) + "\n")
        (output_destination / "coverage_after.json").write_text(json.dumps(after, indent=2) + "\n")
        if after["missing_underlying_days"] or after["missing_option_days"]:
            raise RepairError("calendar-wide missing sessions remain")
        remaining_target = {s: sorted(set(missing) & set(days))
                            for s, missing in after["missing_sessions_by_symbol"].items()
                            if set(missing) & set(days)}
        if remaining_target:
            raise RepairError("target repair sessions still missing for symbols: " + ",".join(sorted(remaining_target)))
        coverage_result = classify_coverage(after, exceptions)
        if not coverage_result["passed"]:
            raise RepairError("unexplained per-symbol/calendar coverage failures remain: " +
                              ",".join(coverage_result["unexpected_missing_sessions_by_symbol"]))
        manifest = dict(scope, created_at_utc=datetime.now(timezone.utc).isoformat(),
                        added_rows=len(adds), download_sha256=hashes,
                        reference_comparison=comparison,
                        calendar_trim=removed, full_history_refresh=refreshed_evidence,
                        full_history_sha256=expected_hashes if changed_symbols else {},
                        identity_trim=identity_trim, excluded_pre_identity_additions=excluded_additions,
                        exceptions_sha256=sha256(exceptions_path), coverage_result=coverage_result,
                        context_status="requires_daily_and_surface_refresh",
                        coverage=after, status="calendar_and_symbol_session_checks_passed")
        stage_cache(source, output_destination / "cache", repaired, manifest)
        shutil.copy2(exceptions_path, output_destination / "cache" / "stock_history_exceptions.json")
        (output_destination / "cache" / "exchange_calendar.json").write_text(json.dumps(
            {"provider": "alpaca_calendar", "timezone": "America/New_York",
             "source_sha256": scope["calendar_sha256"],
             "sessions": [r for r in records if history_start <= r["date"] <= args.end]}, indent=2) + "\n")
        print(f"Staged {len(adds):,} added bars at {output_destination / 'cache'}; original cache preserved.", flush=True)
        return 0
    except (RepairError, OSError, KeyError) as exc:
        print(f"Repair stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
