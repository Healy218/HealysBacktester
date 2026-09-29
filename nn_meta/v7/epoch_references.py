"""Read original dated detail rows plus separately admitted exact list responses."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
from types import MappingProxyType

from nn_meta.v7.indexed_references import IndexedContractReferences
from nn_meta.v7.packed_references import check_standard
from nn_meta.v7.storage import sha, verify
from options.data.provider import parse_occ_symbol


def list_terms(contract, day, expired, raw, encoded, missing_anchor):
    """An alternate query must retain its real list provenance and exact ticker."""
    root, expiry, right, strike = parse_occ_symbol(contract)
    metadata, body = json.loads(encoded), json.loads(raw)
    query = dict(path='/v3/reference/options/contracts', params=dict(
        underlying_ticker=root, expiration_date=expiry.isoformat(), strike_price=strike,
        contract_type='call' if right == 'C' else 'put', as_of=day, expired=expired, limit=1000))
    if (expired not in ('false', 'true') or metadata['query'] != query
            or metadata['missing_row_receipt_sha256'] != missing_anchor
            or metadata['response_sha256'] != hashlib.sha256(raw).hexdigest()
            or metadata['http_status'] != 200 or metadata['pagination_complete'] is not True
            or body.get('status') != 'OK' or body.get('next_url')
            or not isinstance(body.get('results', []), list)):
        raise ValueError('Alternate reference scope/integrity differs')
    matches = [r for r in body.get('results', []) if r.get('ticker') == 'O:' + contract]
    if metadata['exact_matches'] != len(matches) or len(matches) > 1:
        raise ValueError('Ambiguous alternate reference match')
    if not matches:
        return None
    # Validate the selected unmodified row, never write a synthetic detail response.
    anchor = hashlib.sha256(encoded.encode()).hexdigest()
    terms = dict(check_standard(contract, day, dict(status='OK', results=matches[0]), 200, anchor))
    terms['reference_source'] = 'exact_dated_contract_list'
    terms['missing_detail_receipt_sha256'] = missing_anchor
    return terms


class EpochContractReferences:
    def __init__(self, audit, *, security_id, cache_packs=2):
        self.base = IndexedContractReferences(audit, security_id=security_id, cache_packs=cache_packs)
        self.root = self.base.root
        self.inputs = dict(self.base.inputs)
        binding = json.loads((self.root / 'binding.json').read_text())
        review = Path(binding['alternate_review'])
        if sha(review / 'complete.json') != binding['inputs'][str(review / 'complete.json')]:
            raise ValueError('Alternate admission review changed')
        verify(review)
        review_inputs = json.loads((review / 'binding.json').read_text())['inputs']
        if any(sha(p) != h for p, h in review_inputs.items()):
            raise ValueError('Alternate review evidence changed')
        self.inputs.update(review_inputs)
        self.inputs[str(review / 'complete.json')] = sha(review / 'complete.json')
        entries = json.loads((review / 'entries.json').read_text())
        self.entries = {(r['contract'], r['date']): r for r in entries if r['security_id'] == security_id}
        if len(self.entries) != sum(r['security_id'] == security_id for r in entries):
            raise ValueError('Duplicate alternate admission')

    @lru_cache(maxsize=4096)
    def standard(self, contract, day):
        contract = contract.removeprefix('O:')
        entry = self.entries.get((contract, day))
        if entry is None:
            result = self.base.standard(contract, day)
            self.inputs.update(self.base.inputs)
            return result
        pack = Path(entry['alternate_pack'])
        if sha(pack / 'complete.json') != entry['alternate_pack_sha256']:
            raise ValueError('Alternate reference pack changed')
        verify(pack)
        self.inputs[str(pack / 'complete.json')] = entry['alternate_pack_sha256']
        with sqlite3.connect((pack / 'responses.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            row = db.execute('SELECT body,receipt_json FROM responses WHERE contract=? AND date=? AND expired=?',
                             (contract, day, entry['expired'])).fetchone()
        if row is None or hashlib.sha256(row[1].encode()).hexdigest() != entry['alternate_row_sha256']:
            raise ValueError('Admitted alternate row changed')
        terms = list_terms(contract, day, entry['expired'], *row, entry['provider_receipt_sha256'])
        if terms is None:
            raise ValueError('Admitted exact match disappeared')
        return MappingProxyType(terms)

    def close(self):
        self.standard.cache_clear()
        self.base.close()
