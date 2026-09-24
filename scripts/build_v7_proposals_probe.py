"""Build all four full-catalog causal feature/proposal stores from captured inputs.

One security per invocation, all configured dates and all 8,451 variants across
the active 5/15/30-minute signal scope. The
same checkpointed worker supports full-universe scheduling. No data downloads.
Unresolved action or identity inputs stop construction instead of being ignored.
This stage does not create option labels or admit a security for model training.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_inputs(args):
    import pandas as pd
    from nn_meta.v7.storage import verify, sha
    from nn_meta.v7.scope import require_active_inputs, require_research_window
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.ordinary_actions import price_action
    from nn_meta.v7.admitted_history import bind_history_coverage
    from nn_meta.v7.entry_eligibility import EntryEligibility
    require_active_inputs(args['source'])
    require_research_window(args['start'], args['end'])
    source, history, actions = (Path(args[name]) for name in ('source', 'history', 'actions'))
    inputs = {str(Path(__file__)): sha(__file__)}
    active_path = Path(args.get('active',ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json'))
    active = json.loads(active_path.read_text())
    if source.resolve()!=(ROOT/active['working_inputs']).resolve():
        raise ValueError('Proposal source differs from the active raw data scope')
    coverage = ROOT/active['coverage_inventory']
    verify(coverage)
    if sha(coverage/'complete.json')!=active['coverage_receipt_sha256']:
        raise ValueError('Entry membership coverage receipt changed')
    membership_sources = {str(coverage/'complete.json'):sha(coverage/'complete.json'),
                          str(coverage/'sessions.parquet'):sha(coverage/'sessions.parquet')}
    inputs.update(membership_sources)
    inputs[str(active_path)] = sha(active_path)
    for path in (history, actions):
        doc = verify(path)
        dependencies = json.loads((path/'inputs.json').read_text())
        for filename, digest in dependencies.items():
            # These are transitive lineage entries from the historical action
            # compiler, not consumers of the proposal builder. The current
            # coverage receipt binds the active coverage implementation; the
            # portfolio module is consumed later by execution, not here.
            if Path(filename).resolve() in {
                    (ROOT / 'nn_meta/v7/action_coverage.py').resolve(),
                    (ROOT / 'nn_meta/v7/portfolio.py').resolve()}:
                continue
            if sha(filename) != digest:
                raise ValueError('Captured history/action parent changed: '+filename)
            if filename in inputs and inputs[filename] != digest:
                raise ValueError('Conflicting captured parent bindings')
            inputs[filename] = digest
        inputs.update({str(path/name): digest for name, digest in doc['files'].items()})
        inputs[str(path/'complete.json')] = sha(path/'complete.json')
    calendar_path = source/'calendar.json'
    inputs[str(calendar_path)] = sha(calendar_path)
    calendar = json.loads(calendar_path.read_text())
    membership = pd.read_parquet(coverage/'sessions.parquet',filters=[('security_id','=',args['security_id'])])
    membership = membership[membership.date.between(args['start'],args['end'])]
    eligibility = EntryEligibility(membership,calendar,security_id=args['security_id'],sources=membership_sources)
    frame = pd.read_parquet(history/'history.parquet', filters=[('security_id', '=', args['security_id'])])
    frame = frame[frame.source_date.between(args['start'], args['end'])].copy()
    observed = frame[frame.source_status.eq('observed')]
    if observed.empty:
        raise ValueError('Security has no observed history in requested dates')
    middle = frame[frame.source_date.between(observed.source_date.min(), observed.source_date.max())]
    eligible = pd.read_parquet(history/'eligible_sources.parquet', filters=[('security_id', '=', args['security_id'])])
    eligible = eligible[eligible.source_date.between(args['start'], args['end'])]
    events = [r for r in json.loads((actions/'actions.json').read_text())
              if r['security_id']==args['security_id']]
    # Explicit 7-1 boundary exclusions are safe only before the boundary. Keep
    # the exclusion visible in the parent coverage receipt, but do not ask the
    # causal builder to fabricate a factor or identity across it.
    coverage_path = Path(args['action_coverage'])
    coverage = pd.read_parquet(coverage_path / 'coverage.parquet',
                               filters=[('security_id', '=', args['security_id'])])
    selected = coverage[coverage.source_date.isin(middle.source_date)]
    if set(selected.source_date) != set(middle.source_date):
        raise ValueError('Action coverage does not cover selected history dates')
    admitted = selected.loc[selected.history_admitted.astype(bool), 'source_date']
    excluded = sorted(set(middle.source_date) - set(admitted))
    if excluded:
        middle = middle[middle.source_date.isin(admitted)].copy()
        frame = frame[frame.source_date.isin(admitted)].copy()
        observed = frame[frame.source_status.eq('observed')]
        if observed.empty:
            raise ValueError('Security has no admitted observed history in requested dates')
    if middle.identity_span.isna().any() or middle.identity_span.nunique()!=1:
        raise ValueError('Unresolved security continuity inside admitted history')
    bad_eligible = eligible[~eligible.source_matches]
    if not bad_eligible.empty:
        blocked = coverage[coverage.source_date.isin(bad_eligible.source_date)]
        if (len(blocked) != len(bad_eligible)
                or blocked.history_admitted.astype(bool).any()
                or bad_eligible.source_date.isin(middle.source_date).any()):
            raise ValueError('Unresolved eligible source identity inside admitted history')
    coverage_declaration = bind_history_coverage(args['action_coverage'], middle, events,
        security_id=args['security_id'], inputs=inputs)
    typed_actions = [price_action(r) for r in events]
    # Daily declarations are immutable parents of the selected history. Expand
    # their raw bindings before choosing a capture; a supplementary path alone
    # never authorizes replacing the original prices.
    needed = set(zip(observed.stock_ticker, observed.source_date.str[:4].astype(int)))
    daily_inputs = {}
    for filename in inputs:
        if Path(filename).name != 'declaration.json':
            continue
        declaration = json.loads(Path(filename).read_text())
        if (declaration.get('schema') == 'v7-raw-session-daily-v1'
                and (declaration.get('stock_ticker'), declaration.get('year')) in needed):
            for name, digest in {**declaration['inputs'], **declaration['sources']}.items():
                if sha(name) != digest or (name in inputs and inputs[name] != digest):
                    raise ValueError('Selected raw daily parent changed')
                if name in daily_inputs and daily_inputs[name] != digest:
                    raise ValueError('Conflicting raw daily parents')
                daily_inputs[name] = digest
    inputs.update(daily_inputs)
    raw_parts = []
    for (ticker, year), rows in observed.assign(year=observed.source_date.str[:4]).groupby(['stock_ticker','year']):
        roots = [source, *[Path(p) for p in args.get('raw_supplement', [])]]
        candidates = [(root, root/f'stock_1m/raw/{ticker}/{year}/complete.json') for root in roots
                      if (root/f'stock_1m/raw/{ticker}/{year}/complete.json').exists()]
        if len(candidates) != 1:
            raise ValueError('Exactly one bound raw capture for each selected ticker/year required')
        raw_root, receipt_path = candidates[0]
        if str(receipt_path.resolve()) not in {str(Path(p).resolve()) for p in inputs}:
            raise ValueError('Raw supplement is not bound to the selected history')
        doc, raw = receipt_frame(raw_root, receipt_path)
        if doc['task']['adjustment']!='raw' or doc['task']['symbol']!=ticker:
            raise ValueError('Wrong raw Alpaca capture')
        inputs[str(receipt_path)] = sha(receipt_path)
        inputs.update({str(receipt_path.parent/name):digest for name,digest in doc['files'].items()})
        days = raw.timestamp.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
        raw = raw.assign(source_date=days).merge(rows[['source_date','session_open_ns','available_ns',
            'observed_minutes']], on='source_date', how='inner', validate='many_to_one')
        ns = raw.timestamp.astype('int64')
        raw = raw[(ns>=raw.session_open_ns) & (ns+60_000_000_000<=raw.available_ns)]
        counts = raw.groupby('source_date').size().reindex(rows.source_date, fill_value=0)
        if counts.tolist()!=rows.observed_minutes.tolist():
            raise ValueError('Raw minutes differ from selected daily history')
        raw_parts.append(raw[['timestamp','Open','High','Low','Close','Volume']])
    raw = pd.concat(raw_parts, ignore_index=True).sort_values('timestamp').set_index('timestamp')
    raw['available_at'] = raw.index+pd.Timedelta(minutes=1)
    routing = dict(zip(middle.source_date, middle.stock_ticker))
    return raw, typed_actions, calendar, inputs, routing, eligibility, coverage_declaration


def work(payload):
    args, minutes = payload
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import resource
    import time
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.v7.causal_features import CausalFeatures
    from nn_meta.v7.proposal_store import (build_features, build_proposals, StoredFeatures,
                                            compact_feature_store)
    started = time.perf_counter()
    raw, actions, calendar, inputs, routing, eligibility, coverage_declaration = load_inputs(args)
    chart = CausalFeatures(raw, actions, calendar, security_id=args['security_id'], minutes=minutes,
        start=args['start'], end=args['end'])
    chart.coverage_declaration = coverage_declaration
    variants = [v for v in registered_catalog(['_build'])['records'] if v['signal_minutes']==minutes]
    output = Path(args['output'])/args['security_id']/str(minutes)
    features = build_features(output/'features', chart, variants, inputs=inputs,
                              reserve_bytes=args['reserve_bytes'],
                              batch_columns=args.get('batch_columns', 16),
                              working_bytes=args.get('working_bytes', 128*1024**2))
    print(json.dumps(dict(stage='features_complete', minutes=minutes, observations=features['observations'],
                          variants=features['variants'])), flush=True)
    store = StoredFeatures(output/'features')
    proposals = build_proposals(output/'proposals', store, symbol=args['security_id'],
        symbols_by_date=routing, start=args['start'], end=args['end'], reserve_bytes=args['reserve_bytes'],
        eligibility=eligibility, batch_columns=args.get('batch_columns', 16),
        working_bytes=args.get('working_bytes', 128*1024**2))
    compact_report = None
    if args.get('compact_final'):
        # Validate the sealed proposal store before removing build-only signal
        # matrices.  The compact store remains usable by downstream row joins.
        from nn_meta.v7.proposal_store import StoredProposals
        StoredProposals(output/'proposals', features=store)
        compact_report = compact_feature_store(output/'features', proposal_path=output/'proposals')
    report = dict(minutes=minutes, variants=proposals['variants'], proposals=proposals['proposals'],
        feature_observations=features['observations'], generated=proposals['generated'],
        excluded_not_member=proposals['excluded_not_member'],seconds=time.perf_counter()-started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, research_ready=False)
    if compact_report is not None:
        report['storage_mode'] = compact_report.get('storage_mode')
    print(json.dumps(report), flush=True)
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.scope import HISTORY_START, HISTORY_END
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active',type=Path,default=ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json')
    for name in ('source','history','actions','action-coverage','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--raw-supplement', type=Path, action='append', default=[])
    parser.add_argument('--security-id', required=True)
    parser.add_argument('--start', default=HISTORY_START)
    parser.add_argument('--end', default=HISTORY_END)
    parser.add_argument('--workers', type=int, required=True)
    parser.add_argument('--minutes', type=int, choices=(1, 5, 15, 30), action='append',
                        help='Build only these signal timeframes; repeat for multiple paths')
    parser.add_argument('--batch-columns', type=int, default=16,
                        help='Maximum signal/proposal variant columns held per batch')
    parser.add_argument('--working-bytes', type=int, default=128*1024**2,
                        help='Bounded in-memory signal workspace per worker')
    parser.add_argument('--compact-final', action='store_true',
                        help='After proposals seal, remove build-only feature matrices')
    args = vars(parser.parse_args())
    if args['batch_columns'] < 1 or args['working_bytes'] < 1:
        raise ValueError('Positive signal batch and workspace budgets required')
    args['reserve_bytes'] = 100*1024**3
    if not args['output'].resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Build outputs must use repository artifact disk')
    with worker_pool(args.pop('workers'), threads=1) as pool:
        minutes = args.pop('minutes') or [1, 5, 15, 30]
        reports = list(pool.map(work, [(args, m) for m in minutes]))
    print(json.dumps(dict(security_id=args['security_id'], reports=reports, research_ready=False)), flush=True)


if __name__=='__main__':
    main()
