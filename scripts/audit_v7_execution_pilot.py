#!/usr/bin/env python3
"""Verify immutable pilot restart prefixes and report remaining exact frontiers."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--discoveries',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    inputs={str(Path(__file__).resolve()):sha(__file__)};previous={};rounds=[];prefix_checks=0;label_checks=0
    for directory in a.discoveries:
        directory=directory.resolve();header=verify(directory)
        bound=json.loads((directory/'binding.json').read_text())['inputs']
        bound.update({str(directory/n):h for n,h in header['files'].items()})
        bound[str(directory/'complete.json')]=sha(directory/'complete.json')
        for name,digest in bound.items():
            if name in inputs and inputs[name]!=digest:raise ValueError('Pilot source changed between resumes')
            inputs[name]=digest
        doc=json.loads((directory/'report.json').read_text());current={r['proposal_id']:r for r in doc['cases']}
        if previous and set(previous)!=set(current):raise ValueError('Pilot dropped or added original paths')
        for pid,new in current.items():
            if pid not in previous:continue
            old=previous[pid]
            if old['source_proposal']!=new['source_proposal'] or old['target_dte']!=new['target_dte']:
                raise ValueError('Pilot reranked or replaced a frozen proposal')
            before,after=old['replay'],new['replay']
            if before['fills']!=after['fills'][:len(before['fills'])]:raise ValueError('Earlier replay fills changed')
            known={identity(m) for m in after['marks'] if m['status']!='uncaptured'}
            if any(identity(m) not in known for m in before['marks'] if m['status']!='uncaptured'):
                raise ValueError('Earlier captured mark changed')
            prefix_checks+=1
            if before['label_complete']:
                if before!=after:raise ValueError('Completed replay changed after new capture')
                label_checks+=1
        rounds.append(dict(path=str(directory),receipt_sha256=sha(directory/'complete.json'),
            complete_labels=doc['complete_labels'],pending=len(doc['pending'])))
        previous=current
    if any(sha(f)!=h for f,h in inputs.items()):raise ValueError('Pilot bound input drift')
    latest=[dict(symbol=c['source_proposal']['symbol'],proposal_id=c['proposal_id'],target_dte=c['target_dte'],
        status=c['replay']['status'],label_complete=c['replay']['label_complete'],fills=len(c['replay']['fills']),
        observed_marks=sum(m['status']=='observed' for m in c['replay']['marks']),pending=c['pending'])
        for c in previous.values()]
    report=dict(schema='v7-execution-pilot-restart-audit-v1',rounds=rounds,paths=len(latest),
        retained_prefix_checks=prefix_checks,completed_label_checks=label_checks,cases=latest,
        complete_labels=sum(c['label_complete'] for c in latest),
        caveat='Purposive five-path execution/restart proof, not a representative storage sample or performance result.',
        full_execution_coverage=False,physical_fallback_complete=False,research_ready=False)
    binding=dict(inputs=inputs)
    output=a.output.resolve()
    if not output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use a new validation output')
    if output.exists():verify(output,expected_identity=identity(binding))
    else:
        with transaction(output) as temp:
            for name,doc in [('binding.json',binding),('report.json',report)]:
                (temp/name).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('rounds','cases')}))


if __name__=='__main__':main()
