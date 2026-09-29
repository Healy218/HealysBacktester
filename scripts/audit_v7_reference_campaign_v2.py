#!/usr/bin/env python3
"""Reconcile packed references using the frozen demand plan's actual scope."""
import argparse,hashlib,json,sqlite3,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','blackouts','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--allow-incomplete',action='store_true');a=p.parse_args()
    from nn_meta.v7.storage import sha,identity,verify,transaction,receipt
    from nn_meta.v7.packed_references import check_standard,query
    from nn_meta.v7.contract_blackouts import BlackoutPolicy
    for key in ('campaign','blackouts','output'):setattr(a,key,getattr(a,key).resolve())
    if not a.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use new validation output')
    verify(a.campaign/'declaration');decl=json.loads((a.campaign/'declaration/declaration.json').read_text())
    campaign=identity(decl);plan=Path(decl['plan']);verify(plan)
    if sha(plan/'complete.json')!=decl['plan_sha256']:raise ValueError('Reference plan changed')
    if any(sha(path)!=digest for path,digest in decl['sources'].items()):raise ValueError('Reference acquisition source changed')
    policy=BlackoutPolicy(a.blackouts)
    source_doc=json.loads((plan/'report.json').read_text());expected=source_doc['contract_dates']
    inputs={str(a.campaign/'declaration/complete.json'):sha(a.campaign/'declaration/complete.json'),
            str(plan/'complete.json'):sha(plan/'complete.json'),str(Path(__file__).resolve()):sha(__file__),
            str(ROOT/'nn_meta/v7/packed_references.py'):sha(ROOT/'nn_meta/v7/packed_references.py'),**policy.inputs}
    counts=Counter();dates=Counter();pack_count=raw_bytes=0
    with transaction(a.output) as temp:
        with sqlite3.connect(temp/'coverage.sqlite3') as audit:
            audit.executescript('''CREATE TABLE observed(security_id,contract,date,admission,pack,receipt_sha256,
                PRIMARY KEY(security_id,contract,date)) WITHOUT ROWID;
                CREATE TABLE security_coverage(security_id PRIMARY KEY,expected,observed,missing);
                CREATE INDEX unresolved ON observed(admission,contract,date);''')
            for sid,parent_digest in sorted(source_doc['checkpoints'].items()):
                parent=plan.with_suffix('.checkpoints')/sid
                if sha(parent/'complete.json')!=parent_digest:raise ValueError('Reference demand checkpoint changed')
                verify(parent)
                with sqlite3.connect((parent/'references.sqlite3').as_uri()+'?mode=ro',uri=True) as demand:
                    wanted=set(demand.execute('SELECT contract,date FROM requests'));seen=set()
                    for head in sorted((Path(decl['output'])/sid).glob('*/complete.json')):
                        pack=head.parent;header=verify(pack);binding=json.loads((pack/'binding.json').read_text())
                        if header['identity']!=identity(binding) or binding['campaign_identity']!=campaign:
                            raise ValueError('Reference pack belongs to another campaign')
                        if binding['scope']['security_id']!=sid or binding['scope']['demand_receipt_sha256']!=parent_digest:
                            raise ValueError('Reference pack demand scope mismatch')
                        pairs=set(map(tuple,binding['scope']['pairs']))
                        if len(pairs)!=binding['requests'] or not pairs<=wanted or pairs & seen:
                            raise ValueError('Duplicate or foreign reference requests')
                        actual=set()
                        with sqlite3.connect((pack/'references.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
                            for c,d,status,body,digest,encoded,anchor,admission in db.execute('SELECT * FROM responses'):
                                if hashlib.sha256(body).hexdigest()!=digest or hashlib.sha256(encoded.encode()).hexdigest()!=anchor:
                                    raise ValueError('Reference row integrity mismatch')
                                metadata=json.loads(encoded)
                                if metadata['query']!=query(c,d) or metadata['response_sha256']!=digest or metadata['http_status']!=status:
                                    raise ValueError('Reference scope/response mismatch')
                                try:check_standard(c,d,json.loads(body),status,anchor);verified='standard'
                                except ValueError:verified='unavailable_404' if status==404 else 'nonstandard'
                                if verified!=admission:raise ValueError('Reference admission mismatch')
                                if policy.at(c,d) is not None:
                                    if status!=404:raise ValueError('Retained blackout evidence conflicts with new capture')
                                    verified='approved_blackout'
                                counts[verified]+=1
                                if verified not in ('standard','approved_blackout'):dates[d]+=1
                                actual.add((c,d))
                                audit.execute('INSERT INTO observed VALUES(?,?,?,?,?,?)',(sid,c,d,verified,str(pack),anchor))
                        if actual!=pairs:raise ValueError('Reference batch is incomplete')
                        seen.update(actual);inputs[str(head)]=sha(head);pack_count+=1
                        raw_bytes+=sum((pack/name).stat().st_size for name in header['files'])+head.stat().st_size
                audit.execute('INSERT INTO security_coverage VALUES(?,?,?,?)',(sid,len(wanted),len(seen),len(wanted-seen)))
                audit.commit()
                if not a.allow_incomplete and seen!=wanted:raise ValueError('Reference capture still incomplete')
            total=sum(counts.values())
            if total>expected:raise ValueError('Reference census exceeds frozen plan')
            report=dict(schema='v7-reference-capture-reconciliation-v1',expected_contract_dates=expected,
                observed_contract_dates=total,missing_contract_dates=expected-total,counts=dict(counts),
                unknown_failure_dates=dict(sorted(dates.items())),packs=pack_count,retained_bytes=raw_bytes,
                full_planned_reference_capture=total==expected,
                admitted_under_existing_exclusions=(total==expected and not dates),
                scope=source_doc.get('scope','Completed entry-reference plan only; actual held paths can add references'),
                full_execution_coverage=False,research_ready=False)
        binding=dict(inputs=inputs,campaign_identity=campaign,allow_incomplete=a.allow_incomplete)
        if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Reference audit inputs changed')
        for name,value in [('report',report),('binding',binding)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
