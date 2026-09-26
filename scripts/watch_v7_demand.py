#!/usr/bin/env python3
"""Read-only terminal progress for the V7-3 demand/recovery service."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'nn_meta/validation/v7-3-scheduler-20260925'
DEFAULT_SERVICE = 'healys-v7-entry-demand-recovery-20260925.service'


def snapshot(output, service_state='unknown', now=None):
    output = Path(output)
    declaration = json.loads((output / 'declaration/plan.json').read_text())
    ids = set(declaration['securities'])
    saved = {p.parent.name for p in (output / 'checkpoints').glob('*/complete.json')
             if p.parent.name in ids}
    progress_path = output / 'kernel-recovery/progress.json'
    if not progress_path.exists():
        progress_path = output / 'progress.json'
    progress = json.loads(progress_path.read_text())
    if progress['selected'] != len(ids):
        raise ValueError('Progress scope differs from the declared universe')
    now = now or datetime.now(timezone.utc)
    updated = datetime.fromisoformat(progress['updated_at'])
    age = max(0.0, (now - updated).total_seconds())
    state = progress['state']
    stale = age > 90
    if state == 'running' and service_state in ('inactive', 'failed', 'not-found'):
        state = 'stopped (saved progress says running)'
    return dict(stage=progress['stage'], state=state, service_state=service_state,
                total=len(ids), saved=len(saved), remaining=len(ids)-len(saved),
                verified_this_run=progress['completed'], running=progress['running'],
                failed=progress['failed'], bytes=progress['output_bytes'],
                cap=progress['max_output_bytes'], free=shutil.disk_usage(output).free,
                age_seconds=age, stale=stale, progress_path=str(progress_path),
                full_scope_complete=progress.get('full_scope_complete', False))


def bar(done, total, width=34):
    fraction = min(1.0, max(0.0, done / total)) if total else 0.0
    filled = int(width * fraction)
    return '[' + '#' * filled + '-' * (width-filled) + f'] {done}/{total} ({fraction:.1%})'


def render(s):
    gib = lambda n: n / 1024**3
    workers = ', '.join(s['running']) or 'none'
    lines = ['V7-3 | Preparing option capture',
             f"Service: {s['service_state']} | Controller: {s['state']}", '',
             'Saved demand checkpoints (receipt presence):', bar(s['saved'], s['total']),
             f"Still to generate: {s['remaining']} securities", '',
             'Verified/reused or built by this invocation:', bar(s['verified_this_run'], s['total']),
             f'Active workers: {workers}', f"Failures: {len(s['failed'])}", '',
             f"Demand storage: {gib(s['bytes']):.2f} / {gib(s['cap']):.0f} GiB",
             f"Disk free: {gib(s['free']):.1f} GiB | required reserve: 100 GiB",
             f"Progress age: {s['age_seconds']:.0f}s" + (' — STALE; inspect service/logs' if s['stale'] else ''), '',
             'Next: full request union and capture storage forecast.',
             'Training requires captured paths, outcomes, assembled rows and readiness.',
             'Read-only viewer. Ctrl-C closes this window; the job continues.',
             f"Source: {s['progress_path']}"]
    if s['failed']:
        lines.extend(['', json.dumps(s['failed'], indent=2)])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--service', default=DEFAULT_SERVICE)
    parser.add_argument('--interval', type=float, default=5)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--follow', action='store_true', help='Refresh continuously (the default)')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('Use an interval of at least one second')
    try:
        while True:
            result = subprocess.run(['systemctl', '--user', 'show', args.service, '-p', 'ActiveState', '--value'],
                                    capture_output=True, text=True, timeout=5, check=False)
            state = result.stdout.strip() if result.returncode == 0 else 'unknown'
            s = snapshot(args.output, state)
            if sys.stdout.isatty() and not args.once:
                print('\033[2J\033[H', end='')
            print(json.dumps(s, indent=2) if args.json else render(s), flush=True)
            if args.once or args.json or s['full_scope_complete'] or s['failed']:
                return 1 if s['failed'] else 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
