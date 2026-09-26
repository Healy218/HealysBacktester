#!/usr/bin/env python3
"""Read-only progress for one explicitly named capture-sample status file."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--follow', action='store_true')
    args = parser.parse_args()
    while True:
        if not args.status.exists():
            line = f'Waiting for status: {args.status}'
            finished = False
        else:
            doc = json.loads(args.status.read_text())
            total, done = doc['total'], doc['completed']
            fraction = done/total if total else 0
            age = (datetime.now(timezone.utc)-datetime.fromisoformat(doc['updated_at'])).total_seconds()
            bar = '='*int(30*fraction)+' '*(30-int(30*fraction))
            line = (f"[{bar}] {done}/{total} | {doc['state']} | failures {doc.get('failed', 0)} | "
                    f"{doc.get('captured_bytes', 0)/1e6:.1f} MB | update {age:.0f}s ago")
            if age > 120 and doc['state'] not in ('complete', 'failed_or_capacity_paused', 'failed'):
                line += ' (stale; process state unknown)'
            finished = doc['state'] in ('complete', 'failed_or_capacity_paused', 'failed')
        print('\r'+line+' '*15, end='\n' if finished or not args.follow else '', flush=True)
        if finished or not args.follow:
            break
        time.sleep(2)


if __name__ == '__main__':
    main()
