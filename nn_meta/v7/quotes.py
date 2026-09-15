"""Union overlapping capture windows while preserving every original request."""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256

from options.data.massive_ticks import canonical_bytes, integer_ns
from options.data.provider import parse_occ_symbol


def capture_union(requests, *, max_span_ns=900_000_000_000):
    max_span_ns = integer_ns(max_span_ns)
    if not 0 < max_span_ns <= 86_400_000_000_000:
        raise ValueError('Capture span must be positive and at most one day')
    grouped, originals = defaultdict(list), {}
    for request in requests:
        name = request['request_id']
        if not isinstance(name, str) or not name:
            raise ValueError('Each request needs a stable identity')
        contract = request['contract'].removeprefix('O:').upper()
        parse_occ_symbol(contract)
        kind = request['kind']
        start, end = integer_ns(request['start_ns']), integer_ns(request['end_ns'])
        if start >= end or kind not in ('quotes', 'trades'):
            raise ValueError('Invalid quote/trade request')
        record = {'request_id': name, 'contract': contract, 'kind': kind, 'start_ns': start, 'end_ns': end}
        if name in originals and originals[name] != record:
            raise ValueError('Conflicting request identity')
        if name not in originals:
            grouped[contract, kind].append(record); originals[name] = record
    captures, links = [], defaultdict(list)
    for (contract, kind), records in sorted(grouped.items()):
        # Fixed cells ensure union never crosses a calendar-day boundary and is
        # deterministic under batching/order. Only requested subranges are kept.
        cells = defaultdict(list)
        for row in records:
            cursor = row['start_ns']
            while cursor < row['end_ns']:
                day_start = cursor // 86_400_000_000_000 * 86_400_000_000_000
                cell = day_start + (cursor - day_start) // max_span_ns * max_span_ns
                stop = min(row['end_ns'], cell + max_span_ns, day_start + 86_400_000_000_000)
                cells[cell].append((cursor, stop, row['request_id'])); cursor = stop
        for cell, parts in sorted(cells.items()):
            current = None
            groups = []
            for lo, hi, rid in sorted(parts):
                if current is None or lo > current[1]:
                    current = [lo, hi, {rid}]; groups.append(current)
                else:
                    current[1] = max(current[1], hi); current[2].add(rid)
            for lo, hi, members in groups:
                capture = {'contract': contract, 'kind': kind, 'start_ns': lo, 'end_ns': hi}
                cid = sha256(canonical_bytes(capture)).hexdigest()
                captures.append({**capture, 'capture_id': cid})
                for rid in sorted(members):
                    links[rid].append(cid)
    return {'schema': 'v7-shared-capture-requests-v1', 'captures': captures,
            'requests': [originals[k] for k in sorted(originals)],
            'request_captures': dict(sorted(links.items()))}
