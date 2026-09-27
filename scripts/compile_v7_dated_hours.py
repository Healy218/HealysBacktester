#!/usr/bin/env python3
"""Seal compact dated option hours and reconcile every frozen entry root/date."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--declaration',type=Path,default=ROOT/'docs/specs/V7_DATED_OPTION_HOURS_20260927.json')
    p.add_argument('--reference-plan',type=Path,default=ROOT/'nn_meta/validation/v7-dated-reference-demand-20260927')
    p.add_argument('--calendar',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--audit-output',type=Path,required=True)
    args=p.parse_args()
    from nn_meta.v7.dated_hours import compile_hours,MINUTE
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    for key in vars(args):setattr(args,key,getattr(args,key).resolve())
    for output in (args.output,args.audit_output):
        if not output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Separate validation directories required')
    verify(args.reference_plan)
    plan=json.loads((args.reference_plan/'report.json').read_text())
    inputs={str(args.reference_plan/'complete.json'):sha(args.reference_plan/'complete.json'),
            str(Path(__file__).resolve()):sha(__file__)}
    calendar_header=verify(args.calendar.parent)
    calendar_doc=json.loads(args.calendar.read_text())
    if (calendar_doc.get('provider')!='alpaca_calendar' or calendar_doc['sessions']!=
            json.loads(args.calendar.with_name('calendar.raw.json').read_text())):
        raise ValueError('Captured Alpaca calendar required')
    inputs[str(args.calendar.parent/'complete.json')]=sha(args.calendar.parent/'complete.json')
    inputs.update({str(args.calendar.parent/n):h for n,h in calendar_header['files'].items()})
    hours=compile_hours(args.declaration,args.calendar,args.output,extra_inputs=inputs)
    inputs.update(hours.inputs)
    counts=Counter();byroot=Counter();early=Counter();checks=[]
    for sid,digest in plan['checkpoints'].items():
        source=args.reference_plan.with_suffix('.checkpoints')/sid
        if sha(source/'complete.json')!=digest:raise ValueError('Reference demand checkpoint drift')
        head=verify(source)
        inputs[str(source/'complete.json')]=digest
        inputs.update({str(source/n):h for n,h in head['files'].items()})
        with sqlite3.connect((source/'references.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            for symbol,day in db.execute('SELECT symbol,date FROM hours ORDER BY symbol,date'):
                session=hours.at(symbol,day)
                counts[str(session['extension_minutes'])]+=1;byroot[symbol]+=1
                o,c=hours.calendar.bounds(day)
                if (c-o).total_seconds()<6.5*3600:early[str(session['extension_minutes'])]+=1
    if sum(counts.values())!=plan['root_dates'] or set(byroot)!=set(plan['roots']):
        raise ValueError('Dated session census differs from frozen entry demand')
    for root,rows in hours.rules['exceptions'].items():
        for row in rows[1:]:
            day=row['start'];before=max(d for d in hours.days if d<day)
            after=hours.at(root,day);prior=hours.at(root,before)
            if prior['extension_minutes']==after['extension_minutes']:raise ValueError('Ineffective hours transition')
            checks.append(dict(root=root,before_date=before,effective=day,before_extension=prior['extension_minutes'],after_extension=after['extension_minutes']))
    hours.verify_bindings()
    if any(sha(f)!=h for f,h in inputs.items()):raise ValueError('Hours audit input changed')
    binding=dict(inputs=inputs,hours_identity=identity(hours.rules))
    report=dict(schema='v7-dated-hours-audit-v1',securities=len(plan['checkpoints']),roots=len(byroot),
                root_dates=sum(counts.values()),by_extension=dict(counts),early_closes=dict(early),
                boundary_checks=checks,all_entry_hours_resolved=True,
                methodology=hours.rules['methodology'],full_execution_coverage=False,research_ready=False)
    if args.audit_output.exists():verify(args.audit_output,expected_identity=identity(binding))
    else:
        with transaction(args.audit_output) as temp:
            for name,doc in [('binding.json',binding),('report.json',report)]:
                (temp/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('boundary_checks','methodology')},indent=2))


if __name__=='__main__':main()
