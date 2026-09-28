"""Immutable raw dated-contract responses with the original standard-contract checks."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from types import MappingProxyType

from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
from options.data.provider import parse_occ_symbol

MAX_RESPONSE = 65536


def query(contract, day):
    parse_occ_symbol(contract)
    return {'path': '/v3/reference/options/contracts/O:' + contract.removeprefix('O:'),
            'params': {'as_of': day}}


def check_standard(contract, day, body, status, receipt_sha256):
    contract = contract.removeprefix('O:')
    root, expiry, right, strike = parse_occ_symbol(contract)
    row = body.get('results', {})
    if status != 200:
        raise ValueError('Dated contract metadata is unavailable')
    if (body.get('status') != 'OK' or row.get('ticker') != 'O:' + contract
            or str(row.get('underlying_ticker', '')).replace('.', '') != root
            or row.get('expiration_date') != expiry.isoformat()
            or row.get('contract_type') != ('call' if right == 'C' else 'put')
            or row.get('strike_price') != strike or row.get('shares_per_contract') != 100
            or row.get('exercise_style') != 'american' or row.get('additional_underlyings')
            or not row.get('primary_exchange')):
        raise ValueError('Contract is not the verified standard 100-share American instrument')
    return MappingProxyType(dict(contract=contract, date=day, underlying=root, expiry=expiry,
        right=right, strike=strike, multiplier=100, metadata_receipt_sha256=receipt_sha256))


def write_pack(destination, rows, binding):
    counts = {'responses': 0, 'standard': 0, 'unavailable_404': 0, 'nonstandard': 0, 'reused': 0}
    with transaction(destination) as temp:
        (temp/'binding.json').write_text(json.dumps(binding, sort_keys=True, indent=2)+'\n')
        with sqlite3.connect(temp/'references.sqlite3') as db:
            db.execute('''CREATE TABLE responses(contract TEXT,date TEXT,http_status INTEGER,
                body BLOB,body_sha256 TEXT,receipt_json TEXT,receipt_sha256 TEXT,admission TEXT,
                PRIMARY KEY(contract,date)) WITHOUT ROWID''')
            for contract, day, status, body, metadata in rows:
                if len(body) > MAX_RESPONSE or status not in (200, 404):
                    raise ValueError('Unbounded or unsuccessful reference response')
                doc = json.loads(body)
                if not isinstance(doc, dict) or doc.get('next_url'):
                    raise ValueError('Malformed/paginated contract response')
                if metadata['query'] != query(contract, day):
                    raise ValueError('Reference scope differs from demand')
                digest = hashlib.sha256(body).hexdigest()
                original = metadata.get('original_receipt_sha256')
                entry = dict(metadata, http_status=status, response_sha256=digest)
                encoded = json.dumps(entry,sort_keys=True,separators=(',',':'))
                anchor = hashlib.sha256(encoded.encode()).hexdigest()
                admission = 'standard'
                try:check_standard(contract,day,doc,status,anchor)
                except ValueError:admission = 'unavailable_404' if status==404 else 'nonstandard'
                db.execute('INSERT INTO responses VALUES(?,?,?,?,?,?,?,?)',
                           (contract,day,status,body,digest,encoded,anchor,admission))
                counts['responses']+=1;counts[admission]+=1;counts['reused']+=bool(original)
        if counts['responses'] != binding['requests']:
            raise ValueError('Incomplete reference batch')
        (temp/'report.json').write_text(json.dumps(counts,sort_keys=True,indent=2)+'\n')
        receipt(temp,dict(identity=identity(binding),schema='v7-packed-contract-references-v1',
                          research_ready=False))
    return counts


class PackedContractReferences:
    """Reader over an explicit list of sealed batches, optionally legacy roots.

    No mutable campaign glob is treated as a frozen dataset input. Consumers must
    bind the returned inputs in their own declarations when selecting this reader.
    """
    def __init__(self, packs, legacy_roots=()):
        packs = [Path(p).resolve() for p in packs]
        if not packs and not legacy_roots:
            raise ValueError('Explicit reference packs or legacy roots required')
        self.root = Path(os.path.commonpath([str(p) for p in packs] or
                                          [str(Path(p).resolve()) for p in legacy_roots]))
        self.inputs = {}
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE routes(contract TEXT,date TEXT,pack TEXT,PRIMARY KEY(contract,date)) WITHOUT ROWID')
        self.legacy_roots = [Path(p) for p in legacy_roots]
        for pack in packs:
            header=verify(pack)
            if header.get('schema')!='v7-packed-contract-references-v1':
                raise ValueError('Unknown reference pack schema')
            self.inputs[str(pack/'complete.json')]=sha(pack/'complete.json')
            with sqlite3.connect((pack/'references.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as src:
                self.db.executemany('INSERT INTO routes VALUES(?,?,?)',
                    ((c,d,str(pack)) for c,d in src.execute('SELECT contract,date FROM responses')))

    @lru_cache(maxsize=4096)
    def standard(self, contract, day):
        contract=contract.removeprefix('O:')
        route=self.db.execute('SELECT pack FROM routes WHERE contract=? AND date=?',(contract,day)).fetchone()
        if route is None:
            from nn_meta.v7.contracts import ContractReferences
            for root in self.legacy_roots:
                path=root/contract/day
                if path.exists():
                    result=ContractReferences(root).standard(contract,day)
                    self.inputs[str(path/'complete.json')]=sha(path/'complete.json')
                    return result
            raise FileNotFoundError('Uncaptured dated contract reference: '+contract+'/'+day)
        path=Path(route[0])
        with sqlite3.connect((path/'references.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
            status,body,digest,encoded,anchor=db.execute(
                'SELECT http_status,body,body_sha256,receipt_json,receipt_sha256 FROM responses WHERE contract=? AND date=?',(contract,day)).fetchone()
        if hashlib.sha256(body).hexdigest()!=digest or hashlib.sha256(encoded.encode()).hexdigest()!=anchor:
            raise ValueError('Packed reference integrity failure')
        metadata=json.loads(encoded)
        if metadata['query']!=query(contract,day) or metadata['response_sha256']!=digest or metadata['http_status']!=status:
            raise ValueError('Packed reference receipt scope mismatch')
        return check_standard(contract,day,json.loads(body),status,anchor)

    def close(self):
        self.standard.cache_clear()
        self.db.close()
