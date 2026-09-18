"""Measure lossless compact proposal storage on an existing real V7 pilot.

The input pilot is never modified. Rows are streamed through the same compact
Parquet writer used by the V7 proposal store, then read back and counted. This
is a storage/design benchmark, not a readiness or training gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def rows(path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                source = json.loads(line)
                decision = pd.Timestamp(source['decision_ns'], unit='ns', tz='UTC')
                closed = bool(source['proposal_closed'])
                exit_at = (pd.Timestamp(source['exit_decision_ns'], unit='ns', tz='UTC')
                           if closed else pd.NaT)
                censored_at = (pd.Timestamp(source['censored_ns'], unit='ns', tz='UTC')
                               if not closed else pd.NaT)
                yield {key: value for key, value in {
                    **source, 'decision_at': decision, 'exit_decision_at': exit_at,
                    'censored_at': censored_at}.items()
                    if key not in ('exit_decision_ns', 'censored_ns')}


def main():
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.v7.compact_proposals import read_proposals, write_proposals
    from nn_meta.v7.storage import sha

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--minutes', type=int, required=True, choices=(1, 5, 15, 30))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    catalog = [v for v in registered_catalog(['_store'])['records']
               if v['signal_minutes'] == args.minutes]
    first = next(rows(args.input), None)
    if first is None:
        raise ValueError('Input pilot is empty')
    declaration = dict(schema='v7-compact-proposals-v2', variants=catalog,
                       symbols_by_date=None, simulator_policy=first['simulator_policy'],
                       timezone='UTC', security_id='pilot')
    # Re-open after peeking so the writer consumes the complete source.
    args.output.mkdir(parents=True)
    target = args.output/'proposals.parquet'
    started = time.perf_counter()
    counts = write_proposals(target, rows(args.input), declaration, row_batch_size=16384)
    compact_bytes = target.stat().st_size
    original_bytes = args.input.stat().st_size
    decoded = sum(1 for _ in read_proposals(target, declaration, batch_size=16384))
    if decoded != counts['proposals']:
        raise ValueError('Compact round-trip row count differs')
    report = dict(schema='v7-proposal-compaction-benchmark-v1', input=str(args.input),
                  input_sha256=sha(args.input), minutes=args.minutes,
                  original_bytes=original_bytes, compact_bytes=compact_bytes,
                  reduction_ratio=compact_bytes/original_bytes,
                  counts=counts, decoded_rows=decoded,
                  seconds=time.perf_counter()-started,
                  limitations=['Existing pilot rows only; no new signals generated',
                               'Storage reduction does not establish full-build peak space',
                               'No option labels or training readiness claimed'])
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
