#!/usr/bin/env python3
"""Seal exact provider-name corrections supported by reviewed exchange notices."""
import argparse,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','declaration','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    from nn_meta.v7.storage import sha,verify,transaction,identity,receipt
    from nn_meta.v7.reviewed_references import corrected_terms,read_original
    a.audit=a.audit.resolve();a.declaration=a.declaration.resolve();a.output=a.output.resolve()
    if not a.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use a new validation output')
    verify(a.audit)
    doc=json.loads(a.declaration.read_text());summary=json.loads((a.audit/'report.json').read_text())
    if doc['schema']!='v7-exact-reference-rename-review-v1' or doc['automatic_extension'] is not False:
        raise ValueError('Finite reviewed corrections required')
    inputs={str(f):sha(f) for f in [a.declaration,a.audit/'complete.json',Path(__file__).resolve(),
        ROOT/'nn_meta/v7/reviewed_references.py',ROOT/'nn_meta/v7/packed_references.py']}
    entries=[];counts={}
    with sqlite3.connect((a.audit/'coverage.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        for group in doc['groups']:
            evidence=(ROOT/group['evidence']).resolve();head=verify(evidence)
            if sha(evidence/'response.bin')!=group['evidence_sha256'] or head['query']['url']!=group['url']:
                raise ValueError('Reviewed notice identity changed')
            for f in ['complete.json','response.bin']:inputs[str(evidence/f)]=sha(evidence/f)
            if group['terms_unchanged'] is not True or group['deliverable_shares']!=100:
                raise ValueError('Unchanged 100-share deliverable required')
            matches=db.execute("SELECT contract,date,pack,receipt_sha256 FROM observed WHERE admission='nonstandard' AND contract LIKE ? AND date=?",(group['new_symbol']+'%',group['reference_date'])).fetchall()
            if len(matches)!=group['expected_pairs']:raise ValueError('Reviewed exception census changed')
            for contract,day,pack,anchor in matches:
                verify(Path(pack));head_path=Path(pack)/'complete.json';inputs[str(head_path)]=sha(head_path)
                e=dict(group,contract=contract,date=day,pack=pack,provider_receipt_sha256=anchor)
                body,status,anchor=read_original(e)
                corrected_terms(contract,day,body,status,anchor,e)
                entries.append(e)
            counts[group['new_symbol']]=len(matches)
    if len({(e['contract'],e['date']) for e in entries})!=len(entries):raise ValueError('Duplicate corrections')
    report=dict(reviewed_pairs=len(entries),by_symbol=counts,
        raw_responses_unchanged=True,blackouts_changed=False,
        unresolved_404=summary['counts'].get('unavailable_404',0),
        remaining_nonstandard=summary['counts'].get('nonstandard',0)-len(entries),
        full_reference_admission=False,full_execution_coverage=False,research_ready=False)
    binding=dict(inputs=inputs,schema=doc['schema'])
    if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Review inputs changed')
    with transaction(a.output) as t:
        for name,value in [('entries',entries),('report',report),('binding',binding)]:
            (t/(name+'.json')).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
        receipt(t,dict(identity=identity(binding),research_ready=False))
    print(json.dumps(report))


if __name__=='__main__':main()
