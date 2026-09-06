"""Bounded, completely paginated historical option ticks; no silent truncation.

Raw SIP nanoseconds and trade conditions/corrections survive JSON serialization.
This captures a specified contract; it does not choose one using future outcomes.
Historical retrieval time is provenance, not historical feature availability.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from numbers import Integral
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from options.data.provider import parse_occ_symbol


class TickDataError(ValueError):
    pass


def integer_ns(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise TickDataError("timestamps must be nonnegative integer nanoseconds")
    return int(value)


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def verify_capture(records, manifest, *, contract, kind, start_ns, end_ns):
    """Bind immutable raw rows to a complete provider capture and requested scope."""
    if not isinstance(manifest, dict) or not isinstance(records, list):
        raise TickDataError("capture rows and manifest have invalid types")
    contract = contract.upper().removeprefix("O:")
    parse_occ_symbol(contract)
    start_ns, end_ns = integer_ns(start_ns), integer_ns(end_ns)
    if (manifest.get("schema") != "massive-option-ticks-v1" or manifest.get("provider") != "massive"
            or manifest.get("complete") is not True or manifest.get("kind") != kind
            or manifest.get("contract") != f"O:{contract}" or kind not in ("quotes", "trades")):
        raise TickDataError("capture manifest completeness, provider, or contract scope mismatch")
    captured_start, captured_end = integer_ns(manifest.get("start_ns")), integer_ns(manifest.get("end_ns"))
    if not captured_start <= start_ns < end_ns <= captured_end:
        raise TickDataError("capture does not completely cover the requested window")
    if (isinstance(manifest.get("records"), bool) or manifest.get("records") != len(records)
            or manifest.get("records_sha256") != hashlib.sha256(canonical_bytes(records)).hexdigest()):
        raise TickDataError("capture record count or SHA256 mismatch")
    for row in records:
        if not isinstance(row, dict) or not captured_start <= integer_ns(row.get("sip_timestamp")) < captured_end:
            raise TickDataError("capture row is malformed or outside manifest bounds")


class MassiveTicks:
    def __init__(self, api_key=None, *, session=None, base_url="https://api.massive.com"):
        self._key = api_key or os.environ.get("MASSIVE_API_KEY")
        if not self._key:
            raise TickDataError("MASSIVE_API_KEY is missing")
        base = urlsplit(base_url)
        if base.scheme != "https" or base.netloc not in ("api.massive.com", "api.polygon.io") or base.path not in ("", "/"):
            raise TickDataError("unsupported Massive API origin")
        self.base = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _next(self, url, path):
        parsed, origin = urlsplit(url), urlsplit(self.base)
        if (parsed.scheme, parsed.netloc, parsed.path) != (origin.scheme, origin.netloc, path) or parsed.fragment:
            raise TickDataError("pagination left the requested endpoint")
        query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() != "apikey"]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))

    def capture(self, contract, kind, start_ns, end_ns, *, max_pages=20, page_size=50000):
        """Return (records, manifest) for [start,end); raise if incomplete."""
        contract = contract.upper().removeprefix("O:")
        parse_occ_symbol(contract)
        if kind not in ("quotes", "trades"):
            raise TickDataError("kind must be quotes or trades")
        start_ns, end_ns = integer_ns(start_ns), integer_ns(end_ns)
        if start_ns >= end_ns or end_ns - start_ns > 86_400_000_000_000:
            raise TickDataError("capture window must be positive and at most one day")
        if (isinstance(max_pages, bool) or not isinstance(max_pages, int)
                or isinstance(page_size, bool) or not isinstance(page_size, int)
                or not 1 <= max_pages <= 1000 or not 1 <= page_size <= 50000):
            raise TickDataError("invalid page bounds")
        path = f"/v3/{kind}/O:{contract}"
        url = self.base + path
        params = {"timestamp.gte": start_ns, "timestamp.lt": end_ns,
                  "order": "asc", "sort": "timestamp", "limit": page_size}
        records, hashes, seen_pages, identities = [], [], set(), {}
        duplicates = unidentified = 0
        for _ in range(max_pages):
            if url in seen_pages:
                raise TickDataError("pagination repeated a page")
            seen_pages.add(url)
            try:
                response = self.session.get(url, params=params,
                    headers={"Authorization": f"Bearer {self._key}"}, timeout=45,
                    allow_redirects=False)
            except requests.RequestException:
                raise TickDataError("Massive tick transport failed") from None
            if response.status_code != 200:
                raise TickDataError(f"Massive ticks HTTP {response.status_code}")
            try:
                body = response.json()
            except ValueError:
                raise TickDataError("Massive returned invalid JSON") from None
            if not isinstance(body, dict) or body.get("status") != "OK":
                raise TickDataError("Massive tick response is not OK")
            page = body.get("results", [])
            if not isinstance(page, list):
                raise TickDataError("invalid tick result list")
            if "results_count" in body:
                count = body["results_count"]
                if isinstance(count, bool) or not isinstance(count, int) or count != len(page):
                    raise TickDataError("provider result count mismatch; capture incomplete")
            hashes.append(hashlib.sha256(canonical_bytes(page)).hexdigest())
            for record in page:
                if not isinstance(record, dict):
                    raise TickDataError("provider tick is not an object")
                stamp = integer_ns(record.get("sip_timestamp"))
                if not start_ns <= stamp < end_ns:
                    raise TickDataError("provider returned a tick outside the capture window")
                sequence = record.get("sequence_number")
                if sequence is not None:
                    sequence = integer_ns(sequence)
                # The API can return sequence=0 and id="" for option trades.
                # Identical prints then may be distinct executions: preserve their
                # multiplicity rather than silently deleting reported volume.
                identity = (stamp, sequence) if sequence else None
                encoded = canonical_bytes(record)
                if identity is not None and identity in identities:
                    if identities[identity] != encoded:
                        raise TickDataError("conflicting duplicate tick identity")
                    duplicates += 1
                    continue
                if identity is None:
                    unidentified += 1
                else:
                    identities[identity] = encoded
                records.append(record)
            if not body.get("next_url"):
                break
            url, params = self._next(body["next_url"], path), None
        else:
            raise TickDataError("page budget exhausted; capture incomplete")
        records.sort(key=lambda r: (r["sip_timestamp"], r.get("sequence_number") or 0))
        return records, {"schema": "massive-option-ticks-v1", "provider": "massive",
            "contract": f"O:{contract}", "kind": kind, "start_ns": start_ns, "end_ns": end_ns,
            "complete": True, "pages": len(hashes), "page_result_sha256": hashes,
            "duplicates_removed": duplicates, "records": len(records),
            "records_without_reliable_sequence": unidentified,
            "deduplication_policy": "positive sequence plus SIP timestamp; unidentified prints preserved",
            "records_sha256": hashlib.sha256(canonical_bytes(records)).hexdigest(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "availability_basis": "historical_sip_timestamp; local receipt latency unknown"}
