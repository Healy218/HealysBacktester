#!/usr/bin/env python3
"""Union immutable reference inventories without rewriting provider responses."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
from incubator.continual.storage import write


def combine(audits, alternate_review, output):
    audits=[Path(p).resolve() for p in audits];alternate_review=Path(alternate_review).resolve()
    if len(audits)<2 or len(set(audits))!=len(audits):raise ValueError('Distinct complete inventories required')
    verify(alternate_review);inputs={str(alternate_review/'complete.json'):sha(alternate_review/'complete.json'),str(Path(__file__).resolve()):sha(__file__)}
    expected=0
    for p in audits:
        verify(p);r=json.loads((p/'report.json').read_text())
        if not r['full_planned_reference_capture']:raise ValueError('Incomplete reference inventory')
        inputs[str(p/'complete.json')]=sha(p/'complete.json')
        for k,v in json.loads((p/'binding.json').read_text())['inputs'].items():
            if k in inputs and inputs[k]!=v:raise ValueError('Conflicting reference provenance')
            inputs[k]=v
        expected+=r['observed_contract_dates']
    binding=dict(schema='v7-union-reference-epochs-v1',inputs=inputs,parents=list(map(str,audits)),alternate_review=str(alternate_review))
    with transaction(output) as t:
        shutil.copyfile(audits[0]/'coverage.sqlite3',t/'coverage.sqlite3')
        with sqlite3.connect(t/'coverage.sqlite3') as db:
            for p in audits[1:]:
                db.execute('ATTACH DATABASE ? AS incoming',(str(p/'coverage.sqlite3'),))
                if db.execute('SELECT 1 FROM observed a JOIN incoming.observed b USING(security_id,contract,date) LIMIT 1').fetchone():
                    raise ValueError('Overlapping reference inventories need explicit reconciliation')
                db.execute('INSERT INTO observed SELECT * FROM incoming.observed');db.commit();db.execute('DETACH DATABASE incoming')
            count=db.execute('SELECT count(*) FROM observed').fetchone()[0]
            if count!=expected:raise ValueError('Union reference census differs')
            db.execute('DELETE FROM security_coverage')
            db.execute('INSERT INTO security_coverage SELECT security_id,count(*),count(*),0 FROM observed GROUP BY security_id')
            counts=dict(db.execute('SELECT admission,count(*) FROM observed GROUP BY admission'))
        report=dict(schema='v7-union-reference-epochs-v1',expected_contract_dates=count,observed_contract_dates=count,
            missing_contract_dates=0,full_planned_reference_capture=True,counts=counts,
            raw_responses_unchanged=True,full_execution_coverage=False,
            separately_admitted_exact_list_pairs=len(json.loads((alternate_review/'entries.json').read_text())))
        write(t/'binding.json',binding);write(t/'report.json',report)
        receipt(t,dict(identity=identity(binding),research_ready=False))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,action='append',required=True)
    p.add_argument('--alternate-review',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(combine(a.audit,a.alternate_review,a.output),indent=2))
