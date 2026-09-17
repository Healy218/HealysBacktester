"""Build all four full-catalog causal feature/proposal stores from captured inputs.

One security per invocation, all configured dates and all 11,268 variants. The
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
    from nn_meta.v7.causal_prices import PriceAction
    require_active_inputs(args['source'])
    require_research_window(args['start'], args['end'])
    source, history, actions = (Path(args[name]) for name in ('source', 'history', 'actions'))
    inputs = {str(Path(__file__)): sha(__file__)}
    for path in (history, actions):
        doc = verify(path)
        dependencies = json.loads((path/'inputs.json').read_text())
        for filename, digest in dependencies.items():
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
    frame = pd.read_parquet(history/'history.parquet', filters=[('security_id', '=', args['security_id'])])
    frame = frame[frame.source_date.between(args['start'], args['end'])].copy()
    observed = frame[frame.source_status.eq('observed')]
    if observed.empty:
        raise ValueError('Security has no observed history in requested dates')
    middle = frame[frame.source_date.between(observed.source_date.min(), observed.source_date.max())]
    if middle.identity_span.isna().any() or middle.identity_span.nunique()!=1:
        raise ValueError('Unresolved security continuity inside requested history')
    eligible = pd.read_parquet(history/'eligible_sources.parquet', filters=[('security_id', '=', args['security_id'])])
    eligible = eligible[eligible.source_date.between(args['start'], args['end'])]
    if not eligible.source_matches.all():
        raise ValueError('Unresolved eligible source identity; cannot substitute another security')
    symbols = set(middle.stock_ticker.dropna())
    pending = json.loads((actions/'unresolved.json').read_text())
    unresolved = [r for r in pending if symbols.intersection(r['scoped_symbols']) and
                  (not r['effective_date'] or args['start']<=r['effective_date']<=args['end'])]
    if unresolved:
        raise ValueError(f'{len(unresolved)} unresolved captured action records for selected history')
    events = [r for r in json.loads((actions/'actions.json').read_text())
              if r['security_id']==args['security_id']]
    typed_actions = [PriceAction(**r['action']) for r in events]
    raw_parts = []
    for (ticker, year), rows in observed.assign(year=observed.source_date.str[:4]).groupby(['stock_ticker','year']):
        receipt_path = source/f'stock_1m/raw/{ticker}/{year}/complete.json'
        doc, raw = receipt_frame(source, receipt_path)
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
    return raw, typed_actions, calendar, inputs, routing


def work(payload):
    args, minutes = payload
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import resource
    import time
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.v7.causal_features import CausalFeatures
    from nn_meta.v7.proposal_store import build_features, build_proposals, StoredFeatures
    started = time.perf_counter()
    raw, actions, calendar, inputs, routing = load_inputs(args)
    chart = CausalFeatures(raw, actions, calendar, security_id=args['security_id'], minutes=minutes,
        start=args['start'], end=args['end'])
    variants = [v for v in registered_catalog(['_build'])['records'] if v['signal_minutes']==minutes]
    output = Path(args['output'])/args['security_id']/str(minutes)
    features = build_features(output/'features', chart, variants, inputs=inputs,
                              reserve_bytes=args['reserve_bytes'])
    print(json.dumps(dict(stage='features_complete', minutes=minutes, observations=features['observations'],
                          variants=features['variants'])), flush=True)
    store = StoredFeatures(output/'features')
    proposals = build_proposals(output/'proposals', store, symbol=args['security_id'],
        symbols_by_date=routing, start=args['start'], end=args['end'], reserve_bytes=args['reserve_bytes'])
    report = dict(minutes=minutes, variants=proposals['variants'], proposals=proposals['proposals'],
        feature_observations=features['observations'], seconds=time.perf_counter()-started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, research_ready=False)
    print(json.dumps(report), flush=True)
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.scope import HISTORY_START, HISTORY_END
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','history','actions','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--security-id', required=True)
    parser.add_argument('--start', default=HISTORY_START)
    parser.add_argument('--end', default=HISTORY_END)
    parser.add_argument('--workers', type=int, required=True)
    args = vars(parser.parse_args())
    args['reserve_bytes'] = 100*1024**3
    if not args['output'].resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Build outputs must use repository artifact disk')
    with worker_pool(args.pop('workers'), threads=1) as pool:
        reports = list(pool.map(work, [(args, m) for m in (1,5,15,30)]))
    print(json.dumps(dict(security_id=args['security_id'], reports=reports, research_ready=False)), flush=True)


if __name__=='__main__':
    main()
