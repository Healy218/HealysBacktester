"""Narrow activation amendment for the user-selected V6 paper price convention.

Accepts only two changed runtime modules and the new shared pricing helper.
All frozen model, strategy, feature, timing and access code must still match
its previous activation. Requires regression and copied-ledger evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

CHANGED = ('nn_meta/live/v6_market.py', 'nn_meta/live/v6_portfolio.py')
ADDED = ('options/paper_pricing.py',)
POLICY = 'option-midpoint-paper-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def amendment(root, previous, report, tests):
    prior = json.loads(previous.read_text())
    if prior.get('status') != 'passed' or prior.get('schema') != 'v6-forward-activation-v1':
        raise ValueError('Verified previous activation required')
    if any(name in prior['runtime_sha256'] for name in ADDED):
        raise ValueError('This one-time amendment requires the original ask/bid activation')
    runtime = {}
    changed = []
    for name, digest in prior['runtime_sha256'].items():
        actual = sha(root/name)
        if actual != digest:
            if name not in CHANGED:
                raise ValueError(f'Unreviewed runtime change: {name}')
            changed.append(name)
        runtime[name] = actual
    if set(changed) != set(CHANGED):
        raise ValueError('Expected both reviewed quote/pricing module changes')
    for name in ADDED:runtime[name] = sha(root/name)
    evidence = json.loads(report.read_text())
    if (evidence.get('status') != 'passed' or evidence.get('pricing_policy') != POLICY
            or evidence.get('candidate_sources') != {n: runtime[n] for n in (*CHANGED, *ADDED)}
            or not all(evidence.get(key) is True for key in
                       ('closed_records_unchanged','realized_equity_unchanged','idempotent','same_quote_cost_only'))):
        raise ValueError('Copied-ledger midpoint transition evidence is incomplete')
    for filename, digest in evidence['inputs'].items():
        if sha(filename) != digest:raise ValueError('Copied-ledger evidence changed')
    test_count = 0; midpoint_tests = 0
    suites = ET.parse(tests).getroot()
    for suite in suites.iter('testsuite'):
        if any(int(suite.get(k, '0')) for k in ('failures','errors','skipped')):
            raise ValueError('Candidate runtime tests must pass without skips')
        test_count += int(suite.get('tests', '0'))
    for case in suites.iter('testcase'):
        midpoint_tests += 'test_v6_midpoint_pricing' in case.get('classname', '')
    if test_count < 180 or midpoint_tests < 2:
        raise ValueError('Required runtime and midpoint regressions missing')
    for filename, digest in prior['evidence_sha256'].items():
        if sha(filename) != digest:raise ValueError('Prior unchanged-feature evidence changed')
    return {**prior, 'runtime_sha256': runtime,
            'activated_at': datetime.now(timezone.utc).isoformat(),
            'git_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'tests':test_count,
            'evidence_sha256':{**prior['evidence_sha256'],str(report.resolve()):sha(report),str(tests.resolve()):sha(tests)},
            'pricing_policy': POLICY,
            'pricing_amendment':dict(previous_activation_sha256=sha(previous),
                changed_modules=list(CHANGED), added_modules=list(ADDED),
                reason='User explicitly requested midpoint for paper option entries/exits/marks',
                prior_evidence_scope='Unchanged model/features/signals/timing only; old ask/bid execution prices are superseded',
                open_leg_transition='Audited retained-entry-quote midpoint; completed legacy history preserved')}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('root','previous','report','tests','output'):ap.add_argument('--'+name,type=Path,required=True)
    args = ap.parse_args()
    result = amendment(args.root,args.previous,args.report,args.tests)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=result['status'],tests=result['tests'],pricing_policy=POLICY,output=str(args.output))))


if __name__ == '__main__':main()
