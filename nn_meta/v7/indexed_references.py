"""Bounded reader over the independently reconciled full reference inventory."""
from collections import OrderedDict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3

from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.packed_references import check_standard, query
from nn_meta.v7.storage import sha, verify


class ReferenceAdmissionPending(CaptureUnavailable):
    """Captured missing/nonstandard metadata still needs explicit adjudication."""


class IndexedContractReferences:
    def __init__(self, audit, *, security_id, cache_packs=2):
        self.root = Path(audit).resolve()
        verify(self.root)
        report = json.loads((self.root / 'report.json').read_text())
        if not report['full_planned_reference_capture']:
            raise ValueError('Full reconciled reference inventory required')
        if type(cache_packs) is not int or cache_packs < 1:
            raise ValueError('Positive bounded pack cache required')
        self.security_id, self.cache_packs = security_id, cache_packs
        self.inputs = {str(self.root / 'complete.json'): sha(self.root / 'complete.json')}
        self.anchors = json.loads((self.root / 'binding.json').read_text())['inputs']
        self.db = sqlite3.connect((self.root / 'coverage.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True)
        self.db.execute('PRAGMA cache_size=-2048')
        self.cache = OrderedDict()

    def _pack(self, path):
        path = Path(path)
        if path not in self.cache:
            anchor = str(path / 'complete.json')
            if anchor not in self.anchors or sha(anchor) != self.anchors[anchor]:
                raise ValueError('Reconciled reference pack changed')
            verify(path)
            self.inputs[anchor] = self.anchors[anchor]
            self.cache[path] = sqlite3.connect((path / 'references.sqlite3').resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
            while len(self.cache) > self.cache_packs:
                self.cache.popitem(last=False)[1].close()
        self.cache.move_to_end(path)
        return self.cache[path]

    def disposition(self, contract, day):
        row = self.db.execute('SELECT admission FROM observed WHERE security_id=? AND contract=? AND date=?',
                              (self.security_id, contract.removeprefix('O:'), day)).fetchone()
        return row[0] if row else 'uncaptured'

    @lru_cache(maxsize=4096)
    def standard(self, contract, day):
        contract = contract.removeprefix('O:')
        row = self.db.execute('SELECT pack,receipt_sha256 FROM observed WHERE security_id=? AND contract=? AND date=?',
                             (self.security_id, contract, day)).fetchone()
        if row is None:
            raise FileNotFoundError('Uncaptured dated contract reference: ' + contract + '/' + day)
        path, expected = row
        record = self._pack(path).execute('SELECT http_status,body,body_sha256,receipt_json,receipt_sha256 '
                                         'FROM responses WHERE contract=? AND date=?', (contract, day)).fetchone()
        if record is None:
            raise ValueError('Reconciled reference row disappeared')
        status, raw, digest, encoded, anchor = record
        metadata = json.loads(encoded)
        if (anchor != expected or hashlib.sha256(raw).hexdigest() != digest
                or hashlib.sha256(encoded.encode()).hexdigest() != anchor
                or metadata['query'] != query(contract, day)
                or metadata['response_sha256'] != digest or metadata['http_status'] != status):
            raise ValueError('Reference row integrity or scope changed')
        try:
            return check_standard(contract, day, json.loads(raw), status, anchor)
        except ValueError as exc:
            raise ReferenceAdmissionPending('Captured reference awaiting admission: ' + contract + '/' + day) from exc

    def close(self):
        self.standard.cache_clear()
        for db in self.cache.values():
            db.close()
        self.cache.clear()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
