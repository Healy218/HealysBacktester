#!/usr/bin/env python3
"""Independently reconcile all alternate responses and prepare exact review scope."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['audit','recovery','review','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
    from options.data.provider import parse_occ_symbol
    for name,path in vars(a).items():setattr(a,name,path.resolve())
    verify(a.audit);verify(a.review)
    declaration=json.loads((a.recovery/'declaration.json').read_text())
    if declaration['audit_sha256']!=sha(a.audit/'complete.json'):raise ValueError('Wrong recovery parent')
    inputs={str(a.audit/'complete.json'):sha(a.audit/'complete.json'),str(a.review/'complete.json'):sha(a.review/'complete.json'),
            str(a.recovery/'declaration.json'):sha(a.recovery/'declaration.json'),str(Path(__file__).resolve()):sha(__file__)}
    with sqlite3.connect((a.audit/'coverage.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        wanted={(c,d):(sid,anchor,pack) for sid,c,d,anchor,pack in db.execute('SELECT security_id,contract,date,receipt_sha256,pack FROM observed WHERE admission="unavailable_404"')}
        reviewed={(e['contract'],e['date']) for e in json.loads((a.review/'entries.json').read_text())}
        adjusted=[dict(security_id=sid,contract=c,date=d,provider_receipt_sha256=anchor,pack=pack,reason='unsupported_cash_deliverable')
                  for sid,c,d,anchor,pack in db.execute('SELECT security_id,contract,date,receipt_sha256,pack FROM observed WHERE admission="nonstandard"') if (c,d) not in reviewed]
    seen={};recovered=[]
    for head in sorted(Path(declaration['output']).glob('*/complete.json')):
        pack=head.parent;header=verify(pack);binding=json.loads((pack/'binding.json').read_text())
        if header['identity']!=identity(binding) or binding['campaign_identity']!=identity(declaration):raise ValueError('Foreign alternate response pack')
        inputs[str(head)]=sha(head)
        expected={(c,d,e) for c,d,anchor in binding['pairs'] for e in ['false','true']};actual=set()
        with sqlite3.connect((pack/'responses.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            for c,d,expired,raw,encoded in db.execute('SELECT * FROM responses'):
                key=c,d,expired
                if key in seen or (c,d) not in wanted:raise ValueError('Duplicate or foreign recovery response')
                root,expiry,right,strike=parse_occ_symbol(c)
                query=dict(path='/v3/reference/options/contracts',params=dict(underlying_ticker=root,
                    expiration_date=expiry.isoformat(),strike_price=strike,contract_type='call' if right=='C' else 'put',
                    as_of=d,expired=expired,limit=1000))
                metadata=json.loads(encoded);body=json.loads(raw)
                if (metadata['query']!=query or metadata['missing_row_receipt_sha256']!=wanted[c,d][1]
                        or metadata['response_sha256']!=hashlib.sha256(raw).hexdigest()
                        or metadata['http_status']!=200 or metadata['pagination_complete'] is not True
                        or body.get('status')!='OK' or body.get('next_url') or not isinstance(body.get('results',[]),list)):
                    raise ValueError('Recovery raw response scope/integrity differs')
                matches=[r for r in body.get('results',[]) if r.get('ticker')=='O:'+c]
                if metadata['exact_matches']!=len(matches):raise ValueError('Recovery match census differs')
                if matches:recovered.append(dict(contract=c,date=d,expired=expired,pack=str(pack)))
                seen[key]=str(head);actual.add(key)
        if actual!=expected:raise ValueError('Recovery batch incomplete')
    if set(seen)!={(c,d,e) for c,d in wanted for e in ['false','true']}:raise ValueError('Full alternate recovery scope incomplete')
    if recovered:raise ValueError('Matching rows require admission review before preparing exclusions')
    exclusions=[dict(security_id=sid,contract=c,date=d,provider_receipt_sha256=anchor,pack=pack,
        reason='missing_from_detail_and_both_exact_lists',alternate_receipts={e:seen[c,d,e] for e in ['false','true']})
        for (c,d),(sid,anchor,pack) in sorted(wanted.items())]
    # Cash scope is established by the actual raw terms; no synthetic terms are used.
    for row in adjusted:
        pack=Path(row['pack']);verify(pack);inputs[str(pack/'complete.json')]=sha(pack/'complete.json')
        with sqlite3.connect((pack/'references.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            status,raw,anchor=db.execute('SELECT http_status,body,receipt_sha256 FROM responses WHERE contract=? AND date=?',(row['contract'],row['date'])).fetchone()
        body=json.loads(raw);legs=body.get('results',{}).get('additional_underlyings',[])
        if status!=200 or anchor!=row['provider_receipt_sha256'] or not any(l.get('underlying')=='USD' for l in legs):
            raise ValueError('Unreviewed nonstandard disposition')
        row['cash_legs']=legs
    exclusions.extend(adjusted)
    report=dict(missing_pairs=len(wanted),alternate_queries=len(seen),exact_matches=len(recovered),
                cash_deliverable_pairs=len(adjusted),proposed_exact_exclusions=len(exclusions),
                full_alternate_recovery_capture=True,authorization_pending=True,exclusions_active=False,
                reference_admission_complete=False,research_ready=False)
    proposal=dict(schema='v7-reference-exclusion-review-v1',authorization=None,scope='exact_contract_date',
        treatment='exclude_affected_research_path',automatic_extension=False,changes_exchange_calendar=False,
        rerank_or_replace_contract=False,creates_terms_or_outcomes=False,historically_known_eligibility=False,
        exclusions=exclusions)
    binding=dict(inputs=inputs)
    if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Recovery audit inputs changed')
    with transaction(a.output) as temp:
        for name,doc in [('binding.json',binding),('report.json',report),('proposed-exclusions.json',proposal)]:
            (temp/name).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
        receipt(temp,dict(identity=identity(binding),exclusions_active=False))
    print(json.dumps(report))


if __name__=='__main__':main()
