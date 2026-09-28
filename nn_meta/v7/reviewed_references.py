"""Finite reviewed underlying-name corrections over immutable provider responses."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
from types import MappingProxyType

from nn_meta.v7.packed_references import check_standard, query
from nn_meta.v7.storage import sha, verify
from options.data.provider import parse_occ_symbol


def corrected_terms(contract, day, body, status, anchor, review):
    root, _, _, _ = parse_occ_symbol(contract)
    if (review['contract'] != contract or review['date'] != day
            or root != review['new_symbol']
            or not review['published_date'] < review['effective_date'] <= day
            or body.get('results', {}).get('underlying_ticker') != review['old_symbol']):
        raise ValueError('Reference is outside the exact reviewed rename scope')
    corrected = deepcopy(body)
    corrected['results']['underlying_ticker'] = root
    # All other standard-deliverable checks remain mandatory, including cash legs.
    terms = dict(check_standard(contract, day, corrected, status, anchor))
    terms['provider_underlying'] = review['old_symbol']
    return terms


def read_original(entry):
    pack = Path(entry['pack'])
    with sqlite3.connect((pack/'references.sqlite3').resolve().as_uri()+'?mode=ro', uri=True) as db:
        row = db.execute('SELECT http_status,body,body_sha256,receipt_json,receipt_sha256 FROM responses '
                         'WHERE contract=? AND date=?',(entry['contract'],entry['date'])).fetchone()
    if row is None:raise ValueError('Reviewed provider row is missing')
    status, raw, digest, encoded, anchor = row
    metadata = json.loads(encoded)
    if (hashlib.sha256(raw).hexdigest()!=digest or hashlib.sha256(encoded.encode()).hexdigest()!=anchor
            or metadata['query']!=query(entry['contract'],entry['date'])
            or metadata['response_sha256']!=digest or metadata['http_status']!=status
            or anchor!=entry['provider_receipt_sha256']):
        raise ValueError('Reviewed provider evidence changed')
    return json.loads(raw), status, anchor


class ReviewedContractReferences:
    """Wrap a selected reader; only sealed exact pairs receive normalization."""
    def __init__(self, base, review):
        self.base = base
        self.root = base.root
        self.review = Path(review).resolve()
        verify(self.review)
        binding = json.loads((self.review/'binding.json').read_text())
        for path,digest in binding['inputs'].items():
            if sha(path)!=digest:raise ValueError('Reference review input changed')
        self.inputs = dict(base.inputs)
        self.inputs.update(binding['inputs'])
        self.inputs[str(self.review/'complete.json')] = sha(self.review/'complete.json')
        entries = json.loads((self.review/'entries.json').read_text())
        self.entries = {(e['contract'],e['date']):e for e in entries}
        if len(self.entries)!=len(entries):raise ValueError('Duplicate review pair')

    @lru_cache(maxsize=4096)
    def standard(self, contract, day):
        contract=contract.removeprefix('O:')
        entry=self.entries.get((contract,day))
        if entry is None:
            result=self.base.standard(contract,day)
            self.inputs.update(self.base.inputs)
            return result
        body,status,anchor=read_original(entry)
        terms=corrected_terms(contract,day,body,status,anchor,entry)
        terms['reference_review_sha256']=self.inputs[str(self.review/'complete.json')]
        return MappingProxyType(terms)
