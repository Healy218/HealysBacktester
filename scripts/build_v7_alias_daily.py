"""Aggregate a finite alias capture into bound raw daily shards."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.stock_daily import build_shard
    from nn_meta.v7.storage import sha

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    scope = json.loads((args.capture / 'acquisition.json').read_text())
    status = json.loads((args.capture / 'status.json').read_text())
    if (scope.get('schema') != 'v7-reviewed-alias-span-capture-v1'
            or status['failed'] or status['completed'] != status['total']):
        raise ValueError('Complete reviewed alias capture required')
    source_calendar = args.source / 'calendar.json'
    capture_calendar = args.capture / 'calendar.json'
    if sha(source_calendar) != scope['calendar_sha256']:
        raise ValueError('Captured calendar parent changed')
    if capture_calendar.exists():
        if sha(capture_calendar) != sha(source_calendar):
            raise ValueError('Alias capture calendar differs from active source')
    else:
        shutil.copyfile(source_calendar, capture_calendar)
    pairs = sorted({(row['symbol'], year) for row in scope['requests']
                    for year in range(int(row['start'][:4]), int(row['end'][:4]) + 1)})
    for symbol, year in pairs:
        result = build_shard(args.capture, symbol, year,
                             args.output / 'shards' / symbol / str(year))
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
