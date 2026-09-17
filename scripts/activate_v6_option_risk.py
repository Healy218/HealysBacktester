"""Amend V6 activation for arithmetic midpoint, premium stops and ITM expiry.

The frozen model and entry-feature code retain their prior bindings. Only the
reviewed exit/pricing/runtime modules may change. This transition requires an
empty open-position book; completed records, cash and alert history stay intact.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

CHANGED = ('nn_meta/live/v6_market.py', 'nn_meta/live/v6_portfolio.py',
           'nn_meta/live/v6_forward_inputs.py', 'options/paper_pricing.py',
           'scripts/run_v6_forward.py', 'scripts/install_v6_forward.py')
ADDED = ('options/paper_risk.py', 'nn_meta/live/v6_option_risk.py',
         'scripts/run_v6_option_risk.py', 'scripts/activate_v6_option_risk.py')
POLICY = 'option-arithmetic-midpoint-paper-v2'
RISK = dict(generation='v6', premium_stop_fraction=.075,
            expiry_exit_before_close_minutes=15, price_basis='arithmetic_bid_ask_midpoint')
CHECKS = ('empty_open_book', 'closed_records_unchanged', 'realized_equity_unchanged',
          'outbox_unchanged', 'frozen_entry_calculation_unchanged', 'risk_monitor_validated')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def amendment(root, previous, report, tests):
    root, previous, report, tests = map(Path, (root,previous,report,tests))
    prior = json.loads(previous.read_text())
    if (prior.get('status') != 'passed' or prior.get('schema') != 'v6-forward-activation-v1'
            or prior.get('pricing_policy') != 'option-midpoint-paper-v1'
            or prior.get('option_risk_policy') is not None):
        raise ValueError('Verified previous midpoint-only activation required')
    if any(name in prior['runtime_sha256'] for name in ADDED):
        raise ValueError('Option-risk amendment was already applied')
    runtime, changed = {}, []
    for name, digest in prior['runtime_sha256'].items():
        actual = sha(root/name)
        if actual != digest:
            if name not in CHANGED:raise ValueError('Unreviewed runtime change: '+name)
            changed.append(name)
        runtime[name] = actual
    if set(changed) != set(CHANGED):
        raise ValueError('Expected exactly the reviewed option-risk module changes')
    for name in ADDED:runtime[name] = sha(root/name)
    evidence = json.loads(report.read_text())
    if (evidence.get('status') != 'passed' or evidence.get('pricing_policy') != POLICY
            or evidence.get('option_risk_policy') != RISK
            or evidence.get('previous_activation_sha256') != sha(previous)
            or evidence.get('candidate_sources') != {n:runtime[n] for n in (*CHANGED,*ADDED)}
            or not all(evidence.get(k) is True for k in CHECKS) or not evidence.get('inputs')):
        raise ValueError('Copied-ledger option-risk validation is incomplete')
    for filename,digest in evidence['inputs'].items():
        if sha(filename) != digest:raise ValueError('Option-risk evidence input changed')
    suites = ET.parse(tests).getroot()
    count = 0
    for suite in suites.iter('testsuite'):
        if any(int(suite.get(k,'0')) for k in ('failures','errors','skipped')):
            raise ValueError('Candidate runtime tests must pass without skips')
        count += int(suite.get('tests','0'))
    cases = list(suites.iter('testcase'))
    for name, minimum in (('test_v6_option_risk', 10), ('test_option_paper_risk', 8),
                          ('test_v6_midpoint_pricing', 2)):
        if sum(name in c.get('classname','') for c in cases) < minimum:
            raise ValueError('Missing required option-risk regressions: '+name)
    if count < 1574:raise ValueError('Full candidate regression suite required')
    for filename,digest in prior['evidence_sha256'].items():
        if sha(filename) != digest:raise ValueError('Prior frozen-feature evidence changed')
    return {**prior, 'runtime_sha256':runtime, 'pricing_policy':POLICY, 'option_risk_policy':RISK,
        'activated_at':datetime.now(timezone.utc).isoformat(), 'tests':count,
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'evidence_sha256':{**prior['evidence_sha256'],str(report.resolve()):sha(report),str(tests.resolve()):sha(tests)},
        'option_risk_amendment':dict(previous_activation_sha256=sha(previous),
            changed_modules=list(CHANGED), added_modules=list(ADDED),
            prior_evidence_scope='Frozen model, entry features and signal generators retained; held exits and pricing superseded.',
            open_leg_transition='Require zero open positions under deployment lock; preserve completed history and realized cash.',
            reason='User-directed option midpoint stops and ITM expiry exits; no broker orders')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','previous','report','tests','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=amendment(args.root,args.previous,args.report,args.tests)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=result['status'],tests=result['tests'],pricing_policy=POLICY,output=str(args.output))))


if __name__=='__main__':main()
