"""Bound original full-market dated listing records for finite reviews."""
import gzip
import json
from pathlib import Path

from nn_meta.v7.daily_identities import EXCHANGES, page_records, query
from nn_meta.v7.storage import sha, verify


class ListedEvidence:
    def __init__(self, root):
        self.root = Path(root)
        self.inputs, self.cache = {}, {}

    def record(self, symbol, day):
        if day not in self.cache:
            rows = {}
            for exchange in EXCHANGES:
                path = self.root / day / exchange
                doc = verify(path)
                if doc['query'] != query(day, exchange):
                    raise ValueError('Exact full-market dated listed query required')
                self.inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
                self.inputs.update({str(path / n): h for n, h in doc['files'].items()})
                count, seen = 0, set()
                for name in sorted(n for n in doc['files'] if n.startswith('page-') and n.endswith('.json.gz')):
                    records = page_records(json.loads(gzip.decompress((path / name).read_bytes())), exchange, seen)
                    count += len(records)
                    for row in records:
                        if row['ticker'] in rows:
                            raise ValueError('Duplicate listing across exchanges')
                        rows[row['ticker']] = row
                if count != doc['records']:
                    raise ValueError('Dated listing capture count differs')
            self.cache[day] = rows
        return self.cache[day].get(symbol)
