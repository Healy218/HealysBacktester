"""Extend captured trade/settlement clocks through the last reviewed dividend pay date."""
from pathlib import Path
import argparse
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import requests
    from scripts.download_v7_data import get_json, quota_update, disk_guard, tree_bytes
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.settlement_schedule import normalize_reported_settlements, ReportedSettlementSchedule
    from nn_meta.v7.storage import receipt, transaction, verify, sha, identity
    from nn_meta.v7.dividend_producer_versions import historical_input_bindings
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('calendar', 'settlement', 'output', 'budget-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--end', required=True)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(args.budget_root.resolve())
            or not args.budget_root.resolve().is_relative_to(ROOT/'nn_meta')
            or not '2026-11-01' <= args.end <= '2027-01-31'):
        raise ValueError('Finite dividend payment horizon and shared repository quota required')
    inputs = {}
    for directory in (args.calendar.parent, args.settlement.parent):
        doc = verify(directory)
        inputs[str(directory/'complete.json')] = sha(directory/'complete.json')
        inputs.update({str(directory/n): d for n,d in doc['files'].items()})
        if (directory/'inputs.json').exists(): inputs.update(historical_input_bindings(json.loads((directory/'inputs.json').read_text())))
    for path in [Path(__file__), ROOT/'scripts/download_v7_data.py', ROOT/'nn_meta/session_calendar.py',
                 ROOT/'nn_meta/v7/settlement_schedule.py', ROOT/'nn_meta/v7/storage.py']:
        inputs[str(path)] = sha(path)
    old = json.loads(args.calendar.read_text()); old_schedule = json.loads(args.settlement.read_text())
    params = dict(start=old['coverage_start'], end=args.end)
    disk_guard(args.budget_root,100); key = uuid.uuid4().hex
    quota_update(args.budget_root,reserve=key)
    before = tree_bytes(args.output)
    try:
        with requests.Session() as session:
            raw, rows = get_json(session,'https://paper-api.alpaca.markets/v2/calendar',params)
        if [r for r in rows if r['date'] <= old['coverage_end']] != old['sessions']:
            raise ValueError('Original calendar or reported settlement bytes differ')
        document = dict(provider='alpaca_calendar', timezone=old['timezone'],
                        coverage_start=params['start'], coverage_end=params['end'], sessions=rows)
        calendar = SessionCalendar(document)
        schedule = normalize_reported_settlements(rows, document, start=old_schedule['coverage_start'],
            end=args.end, source_identity=identity(dict(calendar=document, inputs=inputs)))
        if [r for r in schedule['trade_settlements'] if r['trade_date'] <= old_schedule['coverage_end']] != old_schedule['trade_settlements']:
            raise ValueError('Previously verified settlement mappings changed')
        ReportedSettlementSchedule(schedule,calendar)
        if any(sha(p)!=d for p,d in inputs.items()): raise ValueError('Calendar extension input changed')
        with transaction(args.output) as temp:
            (temp/'calendar.raw.json').write_bytes(raw)
            for name,value in [('calendar',document),('settlement_calendar',schedule),('inputs',inputs),('request',params)]:
                (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
            receipt(temp,dict(identity=identity(inputs), research_ready=False))
        print(json.dumps(dict(sessions=len(rows),coverage_end=args.end,output=str(args.output))))
    finally:
        quota_update(args.budget_root,finish=(key,max(0,tree_bytes(args.output)-before)))


if __name__ == '__main__':
    main()
