"""Narrow activation amendment for validated recent V6 minute-risk evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

CHANGED = frozenset(('nn_meta/live/v6_option_risk.py', 'scripts/run_v6_forward.py'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def amendment(root, previous, tests, report):
    root, previous, tests, report = map(Path, (root, previous, tests, report))
    prior = json.loads(previous.read_text())
    if prior.get('schema') != 'v6-forward-activation-v1' or prior.get('status') != 'passed':
        raise ValueError('Prior passed V6 activation required')
    runtime, changed = {}, set()
    for name, digest in prior['runtime_sha256'].items():
        actual = sha(root / name)
        if actual != digest:
            if name not in CHANGED:
                raise ValueError('Unreviewed frozen source changed: ' + name)
            changed.add(name)
        runtime[name] = actual
    if changed != CHANGED:
        raise ValueError('Expected exactly the two reviewed runtime changes')
    for filename, digest in prior['evidence_sha256'].items():
        if sha(filename) != digest:
            raise ValueError('Prior activation evidence changed: ' + filename)
    suites = ET.parse(tests).getroot()
    cases = list(suites.iter('testcase'))
    if len(cases) < 1610 or any(int(suite.get(k, '0')) for suite in suites.iter('testsuite')
                               for k in ('failures', 'errors', 'skipped')):
        raise ValueError('Full candidate suite must pass without failures or skips')
    if not any('test_forward_accepts_only_same_leg_recent_post_close_risk_evidence' in
               case.get('name', '') for case in cases):
        raise ValueError('Recent-risk regression is absent')
    evidence = json.loads(report.read_text())
    if (evidence.get('status') != 'passed' or
            evidence.get('previous_activation_sha256') != sha(previous) or
            evidence.get('changed_modules') != {name: runtime[name] for name in sorted(CHANGED)} or
            evidence.get('quote_age_seconds') != 30 or
            evidence.get('max_observation_age_seconds') != 60 or
            evidence.get('same_leg_required') is not True or
            evidence.get('no_quote_still_blocks') is not True):
        raise ValueError('Bounded risk-evidence review is incomplete')
    return {**prior, 'runtime_sha256': runtime,
        'activated_at': datetime.now(timezone.utc).isoformat(),
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'tests': len(cases),
        'evidence_sha256': {**prior['evidence_sha256'],
                            str(tests.resolve()): sha(tests), str(report.resolve()): sha(report)},
        'quote_evidence_amendment': {
            'previous_activation_sha256': sha(previous),
            'changed_modules': sorted(CHANGED),
            'reason': 'Accept a same-leg post-close minute-risk observation when the scanner poll misses a quote',
            'execution_policy': 'Each observation retains the existing 30-second SIP quote age; missing evidence blocks new entries',
            'portfolio_transition': 'No ledger or model migration; preserve open and closed positions'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'previous', 'tests', 'report', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = amendment(args.root, args.previous, args.tests, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'tests': result['tests'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
