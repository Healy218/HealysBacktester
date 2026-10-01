#!/usr/bin/env python3
"""Read-only live terminal progress for the daily V6 r5 incubator."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / 'incubator/continual-v6/r5/latest-run.json'
DEFAULT_FOCUS = ROOT / 'incubator/continual-v6/r5/resources.json'
DEFAULT_SERVICE = 'healys-v6-continual.service'


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def service_info(service):
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'show', service, '-p', 'ActiveState',
             '-p', 'SubState', '-p', 'MemoryCurrent', '-p', 'MemoryMax'],
            capture_output=True, text=True, timeout=3, check=False)
        if result.returncode == 0:
            return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {'ActiveState': 'unknown'}


def snapshot(path=DEFAULT_RUN, focus_path=DEFAULT_FOCUS, service=None, now=None):
    now = now or datetime.now(timezone.utc)
    path = Path(path)
    run = read(path)
    focus = read(focus_path)
    service = service or {'ActiveState': 'unknown'}
    state = run.get('status', 'waiting for run receipt')
    if state == 'running' and service.get('ActiveState') in {'inactive', 'failed', 'not-found'}:
        state = 'stopped — saved receipt says running'
    recent = []
    run_dir = Path(run['run_dir']) if run.get('run_dir') else None
    if run_dir and run.get('stage') == 'candidates_and_labels':
        started = datetime.fromisoformat(run['started_at']).timestamp()
        for progress in (run_dir / 'progress').glob('*.json'):
            try:
                modified = progress.stat().st_mtime
                if modified < started or now.timestamp() - modified > 120:
                    continue
                item = read(progress)
                symbol = item.get('symbol', progress.stem)
                if not (run_dir / 'symbols' / symbol / 'complete.json').exists():
                    recent.append(symbol)
            except OSError:
                continue
    return {'observed_at': now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'),
            'run': run, 'state': state, 'service': service, 'focus': focus,
            'recent_symbols': sorted(recent), 'source': str(path)}


def bar(done, total):
    if not total:
        return 'Waiting for training plan'
    fraction = min(1, max(0, done / total))
    filled = int(34 * fraction)
    return '[' + '#' * filled + '-' * (34 - filled) + f'] {done}/{total} ({fraction:.1%})'


def render(s):
    r = s['run']
    resources = s['focus'].get('resources', {})
    stage = r.get('stage', 'unknown')
    finished = r.get('status') in {'candidate_frozen', 'candidate_already_frozen'}
    lines = [f"V6 INCUBATOR | {s['observed_at']}",
             f"Through: {r.get('through', '?')} | Stage: {stage}",
             f"Run: {s['state']} | Service: {s['service'].get('ActiveState', 'unknown')}", '',
             'Data preparation — completed symbols:',
             bar(r.get('symbols_complete', 0), r.get('symbols_required', 0)), '',
             'Training — completed ensemble members:']
    if finished:
        lines.append('Complete — candidate frozen (producer receipt)')
    elif r.get('training_started'):
        lines.append(bar(r.get('members_complete', 0), r.get('members_required', 0)))
    else:
        lines.append('Pending — starts automatically after data preparation and checks')
    lines.extend(['', 'Evaluation / final freeze: ' + ('complete' if finished else
                 'in progress' if stage == 'evaluation' else 'pending'),
                 f"Data workers selected: {resources.get('workers', '?')} | Training threads: {resources.get('training_threads', '?')}"])
    if stage == 'candidates_and_labels':
        lines.append('Recent symbol updates (last 120s): ' + (', '.join(s['recent_symbols']) or 'none observed'))
    memory = s['service'].get('MemoryCurrent', '')
    limit = s['service'].get('MemoryMax', '')
    if memory.isdigit() and limit.isdigit():
        lines.append(f'Service memory (includes cache): {int(memory)/1024**3:.2f} / {int(limit)/1024**3:.1f} GiB')
    if r.get('verdict'):
        lines.append('Evaluation verdict: ' + json.dumps(r['verdict']))
    if r.get('error') or r.get('errors'):
        lines.append('Errors: ' + json.dumps(r.get('error') or r['errors']))
    lines.extend([f"Handover: {s['focus'].get('phase', 'unknown')}", '',
                  'Counts update at completed checkpoints; no ETA is inferred.',
                  'Read-only. Ctrl-C closes the viewer; the incubator continues.',
                  f"Source: {s['source']}"])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--focus', type=Path, default=DEFAULT_FOCUS)
    parser.add_argument('--service', default=DEFAULT_SERVICE)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--follow', action='store_true', help='Refresh continuously (default)')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('Interval must be at least one second')
    try:
        while True:
            s = snapshot(args.run, args.focus, service_info(args.service))
            if sys.stdout.isatty() and not (args.once or args.json):
                print('\033[2J\033[H', end='')
            print(json.dumps(s, indent=2) if args.json else render(s), flush=True)
            if args.once or args.json:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
