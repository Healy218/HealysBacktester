"""Exercise the real proposal loader for deferred V7 catalog securities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.scope import HISTORY_START, HISTORY_END
    from scripts.build_v7_proposals import load_inputs

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--actions', type=Path, required=True)
    parser.add_argument('--action-coverage', type=Path, required=True)
    parser.add_argument('--raw-supplement', type=Path, action='append', default=[])
    parser.add_argument('--security-id', action='append')
    parser.add_argument('--security-ids-from-report', type=Path,
                        help='Use exact security IDs from a prior loader audit')
    parser.add_argument('--deferred-only', action='store_true',
                        help='Select observed securities with zero admitted observed dates')
    parser.add_argument('--start', default=HISTORY_START)
    parser.add_argument('--end', default=HISTORY_END)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    frame = pd.read_parquet(args.history / 'history.parquet',
                            columns=['security_id', 'source_date', 'source_status'])
    if args.security_id and args.security_ids_from_report:
        raise ValueError('Choose explicit IDs or a prior audit, not both')
    prior_ids = None
    if args.security_ids_from_report:
        prior = json.loads(args.security_ids_from_report.read_text())
        if prior.get('schema') != 'v7-deferred-real-loader-preflight-v1':
            raise ValueError('Expected prior real-loader preflight report')
        prior_ids = [row['security_id'] for row in prior['results']]
        if len(prior_ids) != prior['total'] or len(prior_ids) != len(set(prior_ids)):
            raise ValueError('Prior loader audit has incomplete or duplicate IDs')
    ids = sorted(set(args.security_id or prior_ids or frame.security_id.unique()))
    if set(ids) - set(frame.security_id.unique()):
        raise ValueError('Unknown security ID in preflight scope')
    if args.deferred_only:
        coverage = pd.read_parquet(args.action_coverage / 'coverage.parquet',
                                   columns=['security_id', 'source_date', 'history_admitted'])
        observed = frame[frame.source_status.eq('observed')].merge(
            coverage, on=['security_id', 'source_date'], how='left', validate='one_to_one')
        if observed.history_admitted.isna().any():
            raise ValueError('Coverage omits observed security history')
        admitted_ids = set(observed.loc[observed.history_admitted.astype(bool), 'security_id'])
        ids = [sid for sid in ids if sid not in admitted_ids]
    payload = dict(source=args.source, history=args.history, actions=args.actions,
                   action_coverage=args.action_coverage, raw_supplement=args.raw_supplement,
                   start=args.start, end=args.end)
    results = []
    for sid in ids:
        try:
            raw, actions, _, inputs, routing, _, coverage = load_inputs(
                {**payload, 'security_id': sid})
            result = dict(security_id=sid, status='passed', raw_minutes=len(raw),
                          events=len(actions), routed_days=len(routing),
                          bound_inputs=len(inputs), coverage_receipt=coverage['receipt_sha256'])
        except Exception as exc:
            result = dict(security_id=sid, status='failed', error_type=type(exc).__name__,
                          reason=str(exc))
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    report = dict(schema='v7-deferred-real-loader-preflight-v1', total=len(results),
                  passed=sum(row['status'] == 'passed' for row in results),
                  results=results, research_ready=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    return int(report['passed'] != report['total'])


if __name__ == '__main__':
    raise SystemExit(main())
