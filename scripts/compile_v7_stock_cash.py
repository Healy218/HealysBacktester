"""Seal finite authorized cash entitlements and modeled release clocks."""
from pathlib import Path
import argparse
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.stock_cash import compile_cash_entitlements
    from nn_meta.v7.storage import identity,sha,verify,receipt,transaction
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('actions','inventory','calendar','policy','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free<100*1024**3):
        raise ValueError('Repository artifact disk and reserve required')
    inputs={}
    def merge(values):
        for p,d in values.items():
            if p in inputs and inputs[p]!=d:raise ValueError('Conflicting source bindings')
            inputs[p]=d
    for path in (args.actions,args.inventory):
        doc=verify(path);merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):d for n,d in doc['files'].items()})
    merge(json.loads((args.actions/'inputs.json').read_text()))
    inventory=json.loads((args.inventory/'declaration.json').read_text());merge(inventory['sources']);merge(inventory['inputs'])
    policy=json.loads(args.policy.read_text());proposal_path=Path(policy['proposal_path'])
    if sha(proposal_path)!=policy['proposal_sha256']:raise ValueError('Authorized proposal changed')
    for name,digest in policy['sources'].items():
        if name not in inputs or inputs[name]!=digest:raise ValueError('Cash inputs differ from authorized proposal')
    for path in [Path(__file__),args.policy,proposal_path,args.calendar,ROOT/'nn_meta/session_calendar.py',
                 *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('stock_cash','action_inventory','cash_actions','storage','runtime')]]:
        merge({str(path):sha(path)})
    calendar_doc=json.loads(args.calendar.read_text())
    # Bind the retained exchange-calendar capture as well as its normalized file.
    capture=verify(args.calendar.parent)
    if args.calendar.name not in capture['files']:raise ValueError('Captured calendar required')
    merge({str(args.calendar.parent/'complete.json'):sha(args.calendar.parent/'complete.json')})
    merge({str(args.calendar.parent/n):d for n,d in capture['files'].items()})
    events,pending=compile_cash_entitlements(json.loads((args.actions/'actions.json').read_text()),
        json.loads((args.inventory/'candidates.json').read_text()),SessionCalendar(calendar_doc),policy,
        json.loads(proposal_path.read_text()))
    report=dict(compiled_cash_entitlements=len(events),unresolved_cash_events=len(pending),
        securities=len({e['security_id'] for e in events}),policy_identity=identity(policy),
        broker_posting_verified=False,withholding_fraction=0,held_history_admitted=False,research_ready=False)
    if any(sha(p)!=d for p,d in inputs.items()):raise ValueError('Cash source changed')
    with transaction(args.output) as temp:
        for name,value in [('inputs',inputs),('report',report),('events',events),('unresolved',pending),('policy',policy)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
