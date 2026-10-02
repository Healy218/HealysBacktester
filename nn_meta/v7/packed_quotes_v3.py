"""Version 2 immutable indexed option tick packs with lossless columns and bounded reads.

A pack is a sealed SQLite file, never an appendable global database. Scope,
record bytes, provider manifests and per-payload hashes are checked on reads.
Historical directory archives and frozen producers are left untouched.
"""
from collections import OrderedDict
from bisect import bisect_left
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pyarrow as pa

from nn_meta.v7.execution import CaptureUnavailable, QuotePolicy
from nn_meta.v7.quote_archive import QuoteArchive
from nn_meta.v7.storage import identity, receipt, transaction, verify
from options.data.massive_ticks import canonical_bytes, integer_ns, verify_capture

FORMAT = 'v7-packed-option-captures-v2'
MAX_RAW_BYTES = 256 * 1024**2
MAX_PACK_BYTES = 512 * 1024**2
MAX_CAPTURES = 256


def columns(rows):
    """Lossless integer deltas / byte-shuffled IEEE doubles; mixed types stay JSON."""
    import base64
    import struct
    from nn_meta.v7.packed_quotes import columns as plain_columns
    doc = plain_columns(rows)
    transforms = []
    for index, values in enumerate(doc['values']):
        nonnull = [v for v in values if v is not None]
        nulls = [i for i, v in enumerate(values) if v is None]
        if nonnull and all(type(v) is int for v in nonnull):
            previous = 0
            encoded = []
            for value in values:
                if value is None:
                    encoded.append(0)
                else:
                    encoded.append(value-previous)
                    previous = value
            doc['values'][index] = encoded
            transforms.append(dict(kind='integer-delta', nulls=nulls))
        elif nonnull and all(type(v) is float for v in nonnull):
            raw = b''.join(struct.pack('<d', v if v is not None else 0.) for v in values)
            shuffled = b''.join(raw[byte::8] for byte in range(8))
            doc['values'][index] = base64.b64encode(shuffled).decode('ascii')
            transforms.append(dict(kind='float64-shuffle', nulls=nulls))
        else:
            transforms.append(dict(kind='json'))
    doc['transforms'] = transforms
    return doc


def records(doc):
    import base64
    import struct
    from nn_meta.v7.packed_quotes import records as plain_records
    count = doc['count']
    if type(count) is not int or not 0 <= count <= 1000000:
        raise ValueError('Invalid packed record count')
    values = []
    for encoded, transform in zip(doc['values'], doc['transforms'], strict=True):
        kind = transform['kind']
        nulls = set(transform.get('nulls', []))
        if any(type(i) is not int or not 0 <= i < count for i in nulls):
            raise ValueError('Invalid null locations')
        if kind == 'integer-delta':
            previous = 0
            decoded = []
            for i, delta in enumerate(encoded):
                if type(delta) is not int:
                    raise ValueError('Invalid integer delta')
                if i in nulls:
                    decoded.append(None)
                else:
                    previous += delta
                    decoded.append(previous)
        elif kind == 'float64-shuffle':
            shuffled = base64.b64decode(encoded, validate=True)
            if len(shuffled) != count*8:
                raise ValueError('Invalid float column shape')
            raw = bytearray(count*8)
            for byte in range(8):
                raw[byte::8] = shuffled[byte*count:(byte+1)*count]
            decoded = [None if i in nulls else struct.unpack_from('<d', raw, i*8)[0] for i in range(count)]
        elif kind == 'json':
            decoded = encoded
        else:
            raise ValueError('Unknown packed transform')
        values.append(decoded)
    return plain_records(dict(doc, values=values))


def scope(item):
    result = {k: item[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')}
    if item['capture_id'] != identity(result):
        raise ValueError('Packed capture identity mismatch')
    return result


def encode(item, rows, manifest):
    requested = scope(item)
    verify_capture(rows, manifest, **requested)
    if any(manifest[k] != v for k, v in requested.items() if k != 'contract') or manifest['contract'] != 'O:'+item['contract']:
        raise ValueError('Packed manifest must bind the exact capture scope')
    if any(a['sip_timestamp'] > b['sip_timestamp'] for a, b in zip(rows, rows[1:])):
        raise ValueError('Unordered capture records')
    raw = canonical_bytes(dict(columns=columns(rows), manifest=manifest))
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError('Packed capture exceeds decoded byte limit; split required')
    blob = bytes(pa.Codec('zstd', compression_level=9).compress(raw))
    # Validate the actual representation before publication, including raw types.
    restored, original_manifest = decode(item, blob, len(raw), hashlib.sha256(blob).hexdigest())
    if canonical_bytes(restored) != canonical_bytes(rows) or original_manifest != manifest:
        raise ValueError('Packed encoding failed exact raw roundtrip')
    return blob, len(raw), hashlib.sha256(blob).hexdigest()


def decode(item, blob, raw_size, digest):
    if type(raw_size) is not int or not 0 < raw_size <= MAX_RAW_BYTES:
        raise ValueError('Packed decoded byte limit exceeded')
    if len(blob) > MAX_PACK_BYTES or hashlib.sha256(blob).hexdigest() != digest:
        raise ValueError('Packed payload hash mismatch')
    raw = bytes(pa.Codec('zstd').decompress(blob, raw_size))
    if len(raw) != raw_size:
        raise ValueError('Packed decoded size mismatch')
    doc = json.loads(raw)
    rows, manifest = records(doc['columns']), doc['manifest']
    verify_capture(rows, manifest, **scope(item))
    return rows, manifest


def write_pack(destination, entries, *, binding):
    """Consume bounded (capture, rows, manifest) entries; publish atomically."""
    destination = Path(destination)
    sizes, count = {}, 0
    with transaction(destination) as temporary:
        with sqlite3.connect(temporary/'captures.sqlite3') as db:
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE captures (capture_id TEXT PRIMARY KEY, contract TEXT NOT NULL, '
                       'kind TEXT NOT NULL, start_ns INTEGER NOT NULL, end_ns INTEGER NOT NULL, '
                       'raw_size INTEGER NOT NULL, sha256 TEXT NOT NULL, payload BLOB NOT NULL)')
            db.execute('CREATE INDEX scope ON captures(contract,kind,start_ns,end_ns)')
            for item, rows, manifest in entries:
                if count >= MAX_CAPTURES:
                    raise ValueError('Too many captures in bounded pack')
                blob, raw_size, digest = encode(item, rows, manifest)
                overlap = db.execute('SELECT 1 FROM captures WHERE contract=? AND kind=? AND start_ns<? AND end_ns>?',
                                     (item['contract'], item['kind'], item['end_ns'], item['start_ns'])).fetchone()
                if overlap:
                    raise ValueError('Overlapping captures in pack')
                db.execute('INSERT INTO captures VALUES (?,?,?,?,?,?,?,?)',
                           (item['capture_id'], item['contract'], item['kind'], item['start_ns'], item['end_ns'],
                            raw_size, digest, blob))
                sizes[item['capture_id']] = len(blob)
                count += 1
                if db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0] > MAX_PACK_BYTES:
                    raise ValueError('Pack byte bound exceeded')
            if not count:
                raise ValueError('Empty pack is not a capture')
        (temporary/'binding.json').write_bytes(canonical_bytes(binding))
        receipt(temporary, dict(identity=identity(binding), format=FORMAT, captures=count,
                               payload_bytes=sizes, full_execution_coverage=False))
    return verify(destination, expected_identity=identity(binding))


class PackedQuoteArchive(QuoteArchive):
    """Same causal window/fill/mark API as QuoteArchive for one bounded pack."""
    def __init__(self, root, *, cache_shards=2, policy=QuotePolicy()):
        self.root = Path(root)
        self.receipt = verify(self.root)
        if self.receipt.get('format') != FORMAT:
            raise ValueError('Unsupported packed archive')
        if type(cache_shards) is not int or cache_shards < 1:
            raise ValueError('Positive bounded cache required')
        self.cache_shards, self.policy = cache_shards, policy
        self.cache = OrderedDict()
        self.db = sqlite3.connect((self.root/'captures.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1', uri=True)
        if self.db.execute('SELECT COUNT(*) FROM captures').fetchone()[0] != self.receipt['captures']:
            self.close()
            raise ValueError('Packed capture census drift')

    def close(self):
        self.db.close()
        self.cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def window(self, contract, kind, start_ns, end_ns):
        start_ns, end_ns = integer_ns(start_ns), integer_ns(end_ns)
        if not start_ns < end_ns or end_ns-start_ns > 86400*10**9 or kind not in ('quotes', 'trades'):
            raise ValueError('A bounded positive capture window is required')
        contract = contract.removeprefix('O:')
        captures = self.db.execute('SELECT capture_id,start_ns,end_ns,raw_size,sha256 FROM captures '
                                  'WHERE contract=? AND kind=? AND start_ns<? AND end_ns>? ORDER BY start_ns',
                                  (contract, kind, end_ns, start_ns)).fetchall()
        cursor, rows, sources = start_ns, [], []
        for cid, start, end, raw_size, digest in captures:
            if start > cursor:
                raise CaptureUnavailable('Gap in required packed interval')
            if cid not in self.cache:
                blob = self.db.execute('SELECT payload FROM captures WHERE capture_id=?', (cid,)).fetchone()[0]
                item = dict(capture_id=cid, contract=contract, kind=kind, start_ns=start, end_ns=end)
                data, manifest = decode(item, blob, raw_size, digest)
                self.cache[cid] = data, manifest, [r['sip_timestamp'] for r in data]
                while len(self.cache) > self.cache_shards:
                    self.cache.popitem(last=False)
            self.cache.move_to_end(cid)
            data, manifest, stamps = self.cache[cid]
            lo, hi = bisect_left(stamps, start_ns), bisect_left(stamps, end_ns)
            rows.extend(deepcopy(r) for r in data[lo:hi])
            sources.append(dict(capture_id=cid, records_sha256=manifest['records_sha256']))
            cursor = min(end_ns, end)
        if cursor != end_ns:
            raise CaptureUnavailable('Packed capture does not reach required window end')
        return rows, dict(schema='massive-option-ticks-v1', provider='massive', contract='O:'+contract,
                          kind=kind, start_ns=start_ns, end_ns=end_ns, complete=True, records=len(rows),
                          records_sha256=identity(rows), derived_from_captures=sources)
