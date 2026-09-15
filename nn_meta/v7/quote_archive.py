"""Bounded reads across immutable, adjacent V7 tick shards; gaps fail closed."""
from collections import OrderedDict
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from nn_meta.v7.execution import QuoteTape, QuotePolicy, QuoteUnavailable
from nn_meta.v7.storage import verify
from options.data.massive_ticks import canonical_bytes, verify_capture, integer_ns


class QuoteArchive:
    def __init__(self, root, *, cache_shards=8, policy=QuotePolicy()):
        self.root = Path(root)
        self.plan = json.loads((self.root / 'requests.json').read_text())
        if self.plan.get('schema') != 'v7-shared-capture-requests-v1':
            raise ValueError('Verified shared-capture plan required')
        if type(cache_shards) is not int or cache_shards < 1:
            raise ValueError('Positive bounded cache required')
        self.cache_shards, self.policy = cache_shards, policy
        self.cache, self.groups = OrderedDict(), {}
        seen = set()
        for capture in self.plan['captures']:
            scope = {k: capture[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')}
            cid = hashlib.sha256(canonical_bytes(scope)).hexdigest()
            if cid != capture['capture_id'] or cid in seen:
                raise ValueError('Invalid or duplicate capture identity')
            seen.add(cid)
            self.groups.setdefault((capture['contract'], capture['kind']), []).append(capture)
        for group in self.groups.values():
            group.sort(key=lambda c: c['start_ns'])
            if any(a['end_ns'] > b['start_ns'] for a, b in zip(group, group[1:])):
                raise ValueError('Overlapping capture shards require explicit reconciliation')

    def _read(self, capture):
        cid = capture['capture_id']
        if cid not in self.cache:
            path = self.root / cid
            if not path.exists():
                raise QuoteUnavailable('Requested quote shard has not been captured')
            receipt = verify(path, expected_identity=cid)
            if receipt.get('capture') != capture:
                raise ValueError('Capture receipt scope changed')
            records = json.loads(gzip.decompress((path / 'records.json.gz').read_bytes()))
            manifest = json.loads((path / 'capture.json').read_text())
            verify_capture(records, manifest, **{k: capture[k] for k in
                                                ('contract', 'kind', 'start_ns', 'end_ns')})
            if any(a['sip_timestamp'] > b['sip_timestamp'] for a, b in zip(records, records[1:])):
                raise ValueError('Unordered immutable capture')
            self.cache[cid] = records, manifest
            while len(self.cache) > self.cache_shards:
                self.cache.popitem(last=False)
        self.cache.move_to_end(cid)
        return self.cache[cid]

    def window(self, contract, kind, start_ns, end_ns):
        start_ns, end_ns = integer_ns(start_ns), integer_ns(end_ns)
        if not start_ns < end_ns or end_ns - start_ns > 86_400_000_000_000:
            raise ValueError('A bounded positive capture window is required')
        contract = contract.removeprefix('O:')
        cursor, rows, sources = start_ns, [], []
        for capture in self.groups.get((contract, kind), []):
            if capture['end_ns'] <= start_ns or capture['start_ns'] >= end_ns:
                continue
            if capture['start_ns'] > cursor:
                raise QuoteUnavailable('Gap in required capture interval')
            records, manifest = self._read(capture)
            rows.extend(deepcopy(r) for r in records if start_ns <= r['sip_timestamp'] < end_ns)
            sources.append({'capture_id': capture['capture_id'], 'records_sha256': manifest['records_sha256']})
            cursor = min(end_ns, capture['end_ns'])
        if cursor != end_ns:
            raise QuoteUnavailable('Capture does not reach required window end')
        manifest = {'schema': 'massive-option-ticks-v1', 'provider': 'massive', 'contract': 'O:' + contract,
                    'kind': kind, 'start_ns': start_ns, 'end_ns': end_ns, 'complete': True,
                    'records': len(rows), 'records_sha256': hashlib.sha256(canonical_bytes(rows)).hexdigest(),
                    'derived_from_captures': sources}
        return rows, manifest

    def first_fill(self, contract, decision_ns, *, side, deadline_ns=None):
        end = decision_ns + self.policy.entry_deadline_ns if deadline_ns is None else deadline_ns
        rows, manifest = self.window(contract, 'quotes', decision_ns + self.policy.latency_ns, end + 1)
        return QuoteTape(rows, manifest, contract=contract, policy=self.policy).first_fill(
            decision_ns, side=side, deadline_ns=deadline_ns)

    def mark(self, contract, clock_ns):
        rows, manifest = self.window(contract, 'quotes', max(0, clock_ns - self.policy.max_mark_age_ns), clock_ns + 1)
        return QuoteTape(rows, manifest, contract=contract, policy=self.policy).mark(clock_ns)
