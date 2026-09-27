#!/usr/bin/env python3
"""Seal the five authorized contract/date blackouts and audit frozen entry impact."""
import argparse
from collections import Counter
from datetime import datetime, time, timedelta
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--declaration', type=Path, default=ROOT/'docs/specs/V7_CONTRACT_REFERENCE_BLACKOUTS_20260927.json')
    parser.add_argument('--references', type=Path, default=ROOT/'nn_meta/data_v7/entry-joined-sample-references-20260926')
    parser.add_argument('--probes', type=Path, default=ROOT/'nn_meta/data_v7/missing-contract-probes-20260927')
    parser.add_argument('--audit', type=Path, default=ROOT/'nn_meta/validation/v7-3-entry-union-20260926')
    parser.add_argument('--reference-plan', type=Path, default=ROOT/'nn_meta/validation/v7-dated-reference-demand-20260927')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--impact-output', type=Path, required=True)
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.contract_blackouts import compile_blackouts, BlackoutReferences, ReferenceBlackout
    from nn_meta.v7.contracts import ContractReferences
    from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
    from scripts.download_v7_data import save
    from options.data.provider import parse_occ_symbol
    for key in vars(args):
        setattr(args, key, getattr(args, key).resolve())
    if any(not p.is_relative_to(ROOT/'nn_meta/validation') for p in (args.output, args.impact_output)):
        parser.error('Use new validation artifact directories')
    policy = compile_blackouts(args.declaration, args.references, args.probes, args.output)
    for path in (args.audit, args.reference_plan):
        verify(path)
    audit = json.loads((args.audit/'report.json').read_text())
    audit_binding = json.loads((args.audit/'binding.json').read_text())
    reference_plan = json.loads((args.reference_plan/'report.json').read_text())
    demand = Path(audit_binding['demand_root'])/'demand'
    inputs = dict(policy.inputs)
    for path in (args.audit, args.reference_plan):
        inputs[str(path/'complete.json')] = sha(path/'complete.json')
    inputs[str(Path(__file__).resolve())] = sha(__file__)
    scopes = {}
    for contract, day in policy.treatments:
        scopes.setdefault(parse_occ_symbol(contract)[0], []).append((contract, day))
    cases = []
    for sid, expected in sorted(reference_plan['checkpoints'].items()):
        checkpoint = args.reference_plan.with_suffix('.checkpoints')/sid
        if sha(checkpoint/'complete.json') != expected:
            raise ValueError('Reference-plan checkpoint drift')
        # Verify the small report before using its root routing to omit a store.
        header = json.loads((checkpoint/'complete.json').read_text())
        if sha(checkpoint/'report.json') != header['files']['report.json']:
            raise ValueError('Reference-plan routing report drift')
        report = json.loads((checkpoint/'report.json').read_text())
        roots = set(report['roots']) & scopes.keys()
        if not roots:
            continue
        source = demand/sid
        digest = audit['inputs'][str(source/'complete.json')]
        if sha(source/'complete.json') != digest:
            raise ValueError('Demand parent changed since full union audit')
        doc = verify(source)
        inputs[str(source/'complete.json')] = digest
        inputs.update({str(source/name):h for name,h in doc['files'].items()})
        with sqlite3.connect((source/'demand.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
            for root in sorted(roots):
                for contract, day in scopes[root]:
                    date = datetime.fromisoformat(day).date()
                    start = int(datetime.combine(date, time(), ZoneInfo('America/New_York')).timestamp())*10**9
                    end = int(datetime.combine(date+timedelta(days=1), time(), ZoneInfo('America/New_York')).timestamp())*10**9
                    selected = db.execute('SELECT COUNT(*),COUNT(DISTINCT decision_ns) FROM selections WHERE '
                        'contract=? AND status=? AND decision_ns>=? AND decision_ns<?',
                        (contract,'selected',start,end)).fetchone()
                    if selected[0] == 0:
                        continue
                    requests = db.execute('SELECT kind,COUNT(*) FROM requests WHERE contract=? AND date=? GROUP BY kind',
                        (contract,day)).fetchall()
                    groups = db.execute('SELECT s.target_dte,d.minutes,COUNT(*),SUM(d.proposals) '
                        'FROM selections s JOIN decisions d ON s.symbol=d.symbol AND s.decision_ns=d.decision_ns AND s.right=d.right '
                        'WHERE s.contract=? AND s.status=? AND s.decision_ns>=? AND s.decision_ns<? '
                        'GROUP BY s.target_dte,d.minutes ORDER BY s.target_dte,d.minutes',
                        (contract,'selected',start,end)).fetchall()
                    cases.append(dict(contract=contract,date=day,security_id=sid,selection_outcomes=selected[0],
                        decision_clocks=selected[1],original_requests_by_kind=dict(requests),
                        proposal_target_outcomes=sum(r[3] for r in groups),
                        groups=[dict(target_dte=t,minutes=m,decision_rows=n,proposal_target_outcomes=c) for t,m,n,c in groups],
                        treatment_id=policy.treatments[contract,day]['treatment_id']))
    if {(c['contract'],c['date']) for c in cases} != set(policy.treatments) or len(cases) != len(policy.treatments):
        raise ValueError('Each finite blackout must route to exactly one frozen security/date scope')
    guard = BlackoutReferences(ContractReferences(args.references), policy)
    for contract, day in policy.treatments:
        try:
            guard.standard(contract, day)
        except ReferenceBlackout:
            pass
        else:
            raise ValueError('Real missing reference was not excluded by the consumer')
    samples = ROOT/'nn_meta/validation/v7-joined-sample-reference-requests-20260926.json'
    inputs[str(samples)] = sha(samples)
    statuses = Counter()
    for item in json.loads(samples.read_text()):
        try:
            guard.standard(item['contract'], item['date'])
            statuses['verified_standard'] += 1
        except ReferenceBlackout:
            statuses['explicit_contract_date_blackout'] += 1
        ref = args.references/item['contract']/item['date']
        header = verify(ref)
        inputs[str(ref/'complete.json')] = sha(ref/'complete.json')
        inputs.update({str(ref/name):digest for name,digest in header['files'].items()})
    binding = dict(inputs=inputs,policy_identity=policy.fingerprint)
    if args.impact_output.exists():
        verify(args.impact_output, expected_identity=identity(binding))
        print('Verified existing blackout policy and frozen impact audit')
        return
    policy.verify_bindings()
    if any(sha(path) != digest for path,digest in inputs.items()):
        raise ValueError('Blackout input drift during impact audit')
    report = dict(schema='v7-contract-blackout-impact-v1', cases=cases, exclusions=len(cases),
        selection_outcomes=sum(c['selection_outcomes'] for c in cases),
        proposal_target_outcomes=sum(c['proposal_target_outcomes'] for c in cases),
        original_requests=sum(sum(c['original_requests_by_kind'].values()) for c in cases),
        sampled_reference_treatments=dict(statuses),originals_preserved=True,calendar_changed=False,
        new_downloads=0,full_held_path_impact_counted=False,full_execution_coverage=False,research_ready=False)
    with transaction(args.impact_output) as temp:
        save(temp/'binding.json',binding); save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))


if __name__ == '__main__':
    main()
