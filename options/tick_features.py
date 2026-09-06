"""Causal, descriptive option microstructure features for historical/live replay.

No fills, Greeks or true aggressor labels are inferred. Signed volume is an
explicit quote-test estimate, only for caller-approved trade condition codes.
Coverage must describe a continuous capture; an open socket alone is insufficient.
Historical SIP ordering does not establish parity with local live receipt latency.
"""
from __future__ import annotations

import math

from options.data.massive_ticks import TickDataError, integer_ns, verify_capture


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _valid_quote(q):
    values = [q.get(k) for k in ("bid_price", "ask_price", "bid_size", "ask_size")]
    return all(_number(v) and v > 0 for v in values) and values[0] <= values[1]


def _timeline(rows, end_ns, availability, *, trades=False):
    result = []
    identities = {}
    quote_sequences = {}
    observation_fields = {"available_at_ns", "received_at_ns", "received_monotonic_ns",
                          "capture_id", "journal_sequence", "receipt_precedes_event"}
    for row in rows:
        if not isinstance(row, dict):
            raise TickDataError("tick must be an object")
        available = integer_ns(row.get("sip_timestamp") if availability == "sip" else row.get("available_at_ns"))
        if available >= end_ns:
            continue
        event = integer_ns(row.get("sip_timestamp"))
        if available < event:
            raise TickDataError("receipt precedes event timestamp")
        sequence = row.get("sequence_number")
        sequence = 0 if sequence is None else integer_ns(sequence)
        if not trades:
            seen = quote_sequences.setdefault(event, set())
            seen.add(sequence)
            if 0 in seen and len(seen) > 1:
                raise TickDataError("ambiguous quote ordering with unreliable sequence")
        identity = (event, sequence)
        identifiable = sequence > 0
        # Repeated delivery of the same vendor identity is not a conflict just
        # because its local receipt/capture metadata differs. Keep the earliest
        # actual availability, regardless of caller input order.
        content = {k: v for k, v in row.items() if k not in observation_fields}
        item = (available, event, sequence, row)
        if (identifiable or not trades) and identity in identities:
            previous_content, position = identities[identity]
            if previous_content != content:
                raise TickDataError("ambiguous tick ordering or conflicting duplicate")
            if available < result[position][0]:
                result[position] = item
            continue
        if identifiable or not trades:
            identities[identity] = content, len(result)
        result.append(item)
    return sorted(result, key=lambda x: x[:3])


def _validate_declared_scope(rows):
    """Raw provider pages rely on their capture manifest; journal rows self-label."""
    for key in ("contract", "provider", "condition_namespace", "event_timestamp_basis"):
        values = set()
        for _, _, _, row in rows:
            value = row.get(key)
            if value is not None:
                if not isinstance(value, str):
                    raise TickDataError(f"invalid tick {key}")
                values.add(value.upper().removeprefix("O:") if key == "contract" else value)
        if len(values) > 1:
            raise TickDataError(f"mixed tick {key} values require a separate adapter")


def window_features(quotes, trades, *, start_ns, end_ns, coverage_start_ns,
                    coverage_end_ns, complete=False, availability="sip",
                    max_quote_age_ns=30_000_000_000, allowed_trade_conditions=(),
                    allow_unconditioned_trades=False):
    """Compute one contract's [start,end) features; stale/missing values are None.

    Prices are premium per share, sizes are contracts. Trade volume/VWAP describe
    uncorrected reported ticks, including multi-leg conditions; quote-test signing
    additionally excludes any condition outside the explicit allowlist. Time-
    weighted NBBO statistics use valid, fresh quote durations only and report the
    valid fraction, so sparse coverage is never silently forward-filled.
    """
    start_ns, end_ns = integer_ns(start_ns), integer_ns(end_ns)
    coverage_start_ns, coverage_end_ns = integer_ns(coverage_start_ns), integer_ns(coverage_end_ns)
    max_quote_age_ns = integer_ns(max_quote_age_ns)
    if complete is not True or not coverage_start_ns <= start_ns < end_ns <= coverage_end_ns:
        raise TickDataError("complete capture coverage required for feature window")
    if availability not in ("sip", "receipt") or max_quote_age_ns <= 0:
        raise TickDataError("invalid availability or quote age policy")
    if not isinstance(allow_unconditioned_trades, bool):
        raise TickDataError("allow_unconditioned_trades must be an explicit boolean")
    qt, tt = _timeline(quotes, end_ns, availability), _timeline(trades, end_ns, availability, trades=True)
    _validate_declared_scope(qt + tt)
    # A late old quote must not replace newer market state.
    effective, newest = [], (-1, -1)
    for item in qt:
        if item[1:3] >= newest:
            effective.append(item)
            newest = item[1:3]
    weighted_spread = weighted_imbalance = valid_ns = 0.0
    for i, (available, event, _, q) in enumerate(effective):
        stop = effective[i + 1][0] if i + 1 < len(effective) else end_ns
        duration = max(0, min(stop, event + max_quote_age_ns, end_ns) - max(available, start_ns))
        if duration and _valid_quote(q):
            mid = (q["bid_price"] + q["ask_price"]) / 2
            weighted_spread += duration * (q["ask_price"] - q["bid_price"]) / mid * 1e4
            weighted_imbalance += duration * (q["bid_size"] - q["ask_size"]) / (q["bid_size"] + q["ask_size"])
            valid_ns += duration
    last = effective[-1] if effective else None
    fresh = last is not None and _valid_quote(last[3]) and end_ns - last[1] <= max_quote_age_ns
    count = volume = premium_volume = signed_volume = signable_volume = rejected = 0
    try:
        allowed = set(allowed_trade_conditions)
    except TypeError as exc:
        raise TickDataError("invalid trade condition allowlist") from exc
    if any(isinstance(c, bool) or not isinstance(c, (str, int)) for c in allowed) or len({type(c) for c in allowed}) > 1:
        raise TickDataError("condition allowlist must use one provider's string or integer codes")
    quote_cursor, prior = 0, None
    for available, event, _, trade in tt:
        # Match by observation ordering AND require a strictly earlier quote event.
        while quote_cursor < len(effective) and effective[quote_cursor][0] < available:
            prior = effective[quote_cursor]
            quote_cursor += 1
        if not start_ns <= available < end_ns:
            continue
        price, size = trade.get("price"), trade.get("size")
        if not (_number(price) and price > 0 and _number(size) and size > 0) or trade.get("correction", 0) != 0:
            rejected += 1
            continue
        count += 1
        volume += size
        premium_volume += price * size
        conditions = trade.get("conditions")
        if conditions is None or conditions == []:
            if not allow_unconditioned_trades:
                continue
            conditions = []
        if not isinstance(conditions, list) or any(c not in allowed for c in conditions):
            continue
        # No order between quote and trade messages at identical availability
        # has been established. Falling back to the older quote would silently
        # classify through a potentially intervening book update.
        if quote_cursor < len(effective) and effective[quote_cursor][0] == available:
            continue
        if (prior is None or not _valid_quote(prior[3]) or event <= prior[1]
                or available - prior[1] > max_quote_age_ns):
            continue
        q = prior[3]
        if q["bid_price"] == q["ask_price"]:
            continue
        direction = 1 if price >= q["ask_price"] else (-1 if price <= q["bid_price"] else 0)
        if direction:
            signable_volume += size
            signed_volume += direction * size
    return {
        "schema": "option-tick-features-v1", "availability_basis": availability,
        "quote_updates": sum(start_ns <= item[0] < end_ns for item in qt),
        "valid_quote_time_fraction": valid_ns / (end_ns - start_ns),
        "time_weighted_spread_bps": weighted_spread / valid_ns if valid_ns else None,
        "time_weighted_size_imbalance": weighted_imbalance / valid_ns if valid_ns else None,
        "last_quote_age_seconds": (end_ns - last[1]) / 1e9 if last else None,
        "last_bid": last[3]["bid_price"] if fresh else None,
        "last_ask": last[3]["ask_price"] if fresh else None,
        "reported_trade_count": count, "reported_contract_volume": volume,
        "reported_trade_vwap": premium_volume / volume if volume else None,
        "excluded_invalid_or_corrected_trades": rejected,
        "quote_test_signed_volume": signed_volume,
        "quote_test_classified_volume_fraction": signable_volume / volume if volume else None,
        "allowed_trade_conditions": sorted(allowed),
        "allow_unconditioned_trades": allow_unconditioned_trades,
        "model_admission": False,
    }


def verified_window_features(quotes, trades, *, quote_manifest, trade_manifest,
                             contract, start_ns, end_ns,
                             max_quote_age_ns=30_000_000_000, allowed_trade_conditions=(),
                             allow_unconditioned_trades=False):
    """Historical SIP features from hash-verified, complete capture manifests.

    Manifests attest what the bounded provider retrieval returned. They do not
    prove exchange-feed completeness or historical local receipt availability.
    Raw ``window_features`` remains a low-level function whose caller must
    establish capture coverage; production artifact consumers should use this
    manifest-bound entry point instead of manufacturing ``complete=True``.
    """
    for rows, manifest, kind in ((quotes, quote_manifest, "quotes"), (trades, trade_manifest, "trades")):
        verify_capture(rows, manifest, contract=contract, kind=kind,
                       start_ns=start_ns, end_ns=end_ns)
    return window_features(quotes, trades, start_ns=start_ns, end_ns=end_ns,
        coverage_start_ns=max(quote_manifest["start_ns"], trade_manifest["start_ns"]),
        coverage_end_ns=min(quote_manifest["end_ns"], trade_manifest["end_ns"]),
        complete=True, max_quote_age_ns=max_quote_age_ns,
        allowed_trade_conditions=allowed_trade_conditions,
        allow_unconditioned_trades=allow_unconditioned_trades)
