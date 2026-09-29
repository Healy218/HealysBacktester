#!/usr/bin/env python3
"""Separate exact alternate admissions from unresolved finite exclusion proposals."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
from nn_meta.v7.epoch_references import list_terms
from incubator.continual.storage import write


def review(audit, recovery, output):
    audit, recovery, output = [Path(p).resolve() for p in (audit, recovery, output)]
    verify(audit)
    declaration = json.loads((recovery / 'declaration.json').read_text())
    if declaration['audit_sha256'] != sha(audit / 'complete.json'):
        raise ValueError('Recovery audit changed')
    inputs = {str(p): sha(p) for p in (audit / 'complete.json', recovery / 'declaration.json',
              Path(__file__).resolve(), ROOT / 'nn_meta/v7/epoch_references.py')}
    with sqlite3.connect((audit / 'coverage.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        wanted = {(c, d): dict(security_id=s, contract=c, date=d, pack=p, provider_receipt_sha256=h)
                  for s, c, d, p, h in db.execute('SELECT security_id,contract,date,pack,receipt_sha256 FROM observed WHERE admission="unavailable_404"')}
    seen, entries, mismatched = {}, {}, []
    for head in sorted(Path(declaration['output']).glob('*/complete.json')):
        pack = head.parent; header = verify(pack)
        binding = json.loads((pack / 'binding.json').read_text())
        if header['identity'] != identity(binding) or binding['campaign_identity'] != identity(declaration):
            raise ValueError('Foreign alternate pack')
        inputs[str(head)] = sha(head)
        with sqlite3.connect((pack / 'responses.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            for c, d, expired, raw, encoded in db.execute('SELECT * FROM responses'):
                key = c, d, expired
                if key in seen or (c, d) not in wanted: raise ValueError('Foreign/duplicate alternate row')
                item = wanted[c, d]
                terms = list_terms(c, d, expired, raw, encoded, item['provider_receipt_sha256'])
                seen[key] = str(head)
                if terms is not None:
                    if (c, d) in entries: raise ValueError('Multiple matching alternate queries require separate review')
                    entries[c, d] = dict(item, expired=expired, alternate_pack=str(pack),
                        alternate_pack_sha256=sha(head), alternate_row_sha256=hashlib.sha256(encoded.encode()).hexdigest())
                elif json.loads(raw).get('results'):
                    mismatched.append(dict(contract=c, date=d, returned_tickers=[r['ticker'] for r in json.loads(raw)['results']]))
    if set(seen) != {(c, d, e) for c, d in wanted for e in ('false', 'true')}:
        raise ValueError('Incomplete alternate query coverage')
    for item in wanted.values():
        pack = Path(item['pack']); verify(pack); inputs[str(pack / 'complete.json')] = sha(pack / 'complete.json')
        with sqlite3.connect((pack / 'references.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            status, anchor = db.execute('SELECT http_status,receipt_sha256 FROM responses WHERE contract=? AND date=?',
                                       (item['contract'], item['date'])).fetchone()
        if status != 404 or anchor != item['provider_receipt_sha256']: raise ValueError('Original 404 differs')
    exclusions = [dict(v, reason='missing_from_detail_and_both_exact_lists',
                  alternate_receipts={e:seen[c,d,e] for e in ('false','true')})
                  for (c,d),v in sorted(wanted.items()) if (c,d) not in entries]
    report = dict(scope='Exact unresolved subset after separate exact-list admissions',
        missing_pairs=len(wanted), alternate_queries=len(seen), recovered_exact_pairs=len(entries),
        exact_matches=0, proposed_exact_exclusions=len(exclusions), full_alternate_recovery_capture=True,
        authorization_pending=bool(exclusions), exclusions_active=False, mismatched_tickers=mismatched,
        full_execution_coverage=False)
    proposal = dict(schema='v7-reference-exclusion-review-v1', authorization=None, scope='exact_contract_date',
        treatment='exclude_affected_research_path', automatic_extension=False, changes_exchange_calendar=False,
        rerank_or_replace_contract=False, creates_terms_or_outcomes=False, historically_known_eligibility=False,
        exclusions=exclusions)
    with transaction(output) as temp:
        for n,d in [('binding',dict(inputs=inputs)),('entries',list(entries.values())),('report',report),('proposed-exclusions',proposal)]:
            write(temp/(n+'.json'),d)
        receipt(temp,dict(identity=identity(inputs),exclusions_active=False))
    return report


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for n in ['audit','recovery','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(); print(json.dumps(review(a.audit,a.recovery,a.output),indent=2))
