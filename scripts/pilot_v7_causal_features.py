"""Real AAPL dividend-boundary pilot of every V7 strategy and four timeframes.

This validates causal price/feature/proposal integration only. Quotes, full
model rows, option outcomes and full-universe action admission are separate.
"""
from pathlib import Path
import argparse
import gzip
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def action_input(source, dividends, splits, alpaca, issuer, reference):
    import pandas as pd
    from html.parser import HTMLParser
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.storage import verify, sha, identity
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.causal_prices import cash_distribution_action
    from nn_meta.v7.scope import require_active_inputs
    require_active_inputs(source)
    for path in (dividends, splits, alpaca, issuer, reference):
        verify(path)
    ref = json.loads((reference/'response.json').read_text())['results']
    ref_doc = json.loads((reference/'complete.json').read_text())
    if (ref_doc['query'] != {'path':'/v3/reference/tickers/AAPL', 'params':{'date':'2022-05-05'}}
            or ref.get('ticker') != 'AAPL' or ref.get('composite_figi') != 'BBG000B9XRY4'
            or ref.get('cik') != '0000320193'):
        raise ValueError('AAPL dated security reference differs')
    issuer_doc = json.loads((issuer/'complete.json').read_text())
    url = 'https://www.apple.com/newsroom/2022/04/apple-reports-second-quarter-results/'
    if issuer_doc['query']['url'] != url or issuer_doc['final_url'] != url:
        raise ValueError('Original issuer publication URL differs')
    class Text(HTMLParser):
        def __init__(self): super().__init__(); self.parts = []
        def handle_data(self, data): self.parts.append(data)
    parsed = Text(); parsed.feed((issuer/'response.bin').read_text())
    text = ' '.join(' '.join(parsed.parts).split())
    for phrase in ('April 28, 2022', 'cash dividend of $0.23 per share', 'May 12, 2022', 'May 9, 2022'):
        if phrase not in text:
            raise ValueError('Reviewed original amount/date evidence is absent')
    candidates = []
    for page in sorted(dividends.glob('*.gz')):
        candidates += [r for r in json.loads(gzip.decompress(page.read_bytes()))['results']
                       if r['ticker']=='AAPL' and '2022-03-15'<=r['ex_dividend_date']<='2022-05-10']
    if len(candidates) != 1:
        raise ValueError('Pilot cash action inventory changed')
    event = candidates[0]
    expected = dict(id='E6a8bb996a7b4db68fb8b9cac903ea5d69e6d5fcf4a8a3ff45e94c327b268d770',
        currency='USD', cash_amount=.23, ex_dividend_date='2022-05-06',
        pay_date='2022-05-12', record_date='2022-05-09')
    if any(event.get(k) != v for k,v in expected.items()):
        raise ValueError('Original cash amount/effective-date inventory differs')
    for page in sorted(splits.glob('*.gz')):
        if any(r['ticker']=='AAPL' and '2022-03-15'<=r['execution_date']<='2022-05-10'
               for r in json.loads(gzip.decompress(page.read_bytes()))['results']):
            raise ValueError('Pilot has an unreviewed combined/split action')
    corroborating = []
    for page in sorted(alpaca.glob('*.gz')):
        for kind, records in json.loads(gzip.decompress(page.read_bytes()))['corporate_actions'].items():
            for row in records:
                if 'AAPL' not in row.values():
                    continue
                dates = [v for k,v in row.items() if k.endswith('_date') and isinstance(v,str)]
                if not any('2022-03-15'<=v<='2022-05-10' for v in dates):
                    continue
                if kind != 'cash_dividends':
                    raise ValueError('Unreviewed AAPL lifecycle/action during pilot')
                corroborating.append(row)
    if (len(corroborating) != 1 or any(corroborating[0].get(k) != v for k,v in
            dict(ex_date='2022-05-06', rate=.23, record_date='2022-05-09', payable_date='2022-05-12').items())):
        raise ValueError('Independent action amount/effective-date reconciliation failed')
    stock_receipt = source/'stock_1m/raw/AAPL/2022/complete.json'
    _, raw = receipt_frame(source, stock_receipt)
    raw = raw.set_index('timestamp')
    raw['available_at'] = raw.index+pd.Timedelta(minutes=1)
    calendar_doc = json.loads((source/'calendar.json').read_text())
    calendar = SessionCalendar(calendar_doc)
    closing = calendar.bounds('2022-05-05')[1].tz_localize('UTC')
    prior = raw.loc[closing-pd.Timedelta(minutes=1)]
    inputs = {str(p/'complete.json'): sha(p/'complete.json') for p in (dividends, splits, alpaca, issuer, reference)}
    inputs.update({str(stock_receipt):sha(stock_receipt), str(source/'calendar.json'):sha(source/'calendar.json')})
    action = cash_distribution_action(cash_per_share=.23, prior_raw_close=float(prior.Close),
        prior_close_at=closing, event_id=event['id'],
        effective_at=calendar.bounds('2022-05-06')[0].tz_localize('UTC'),
        available_at=pd.Timestamp('2022-04-29', tz='America/New_York'), source_identity=identity(inputs))
    facts = dict(symbol='AAPL', security_id=ref['composite_figi'], amount=.23, prior_raw_close=float(prior.Close),
        prior_close_available_at=closing.isoformat(), effective_at=action.effective_at.isoformat(),
        factor_available_at=action.available_at.isoformat(), factor=action.price_factor,
        original_publication_date='2022-04-28', source_identity=action.source_identity,
        effective_date_basis='same ex-date in both captured corporate-action sources',
        issuer_available_clock='conservative midnight after published calendar date', research_ready=False)
    return raw, action, calendar_doc, inputs, facts


def worker(payload):
    args, minutes = payload
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import time
    import resource
    from nn_meta.v7.causal_features import CausalFeatures
    from nn_meta.v7.proposals import causal_proposal_batches
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.v7.provenance import RunBinding
    from nn_meta.v7.storage import transaction, receipt
    began = time.perf_counter()
    raw, action, calendar, inputs, facts = action_input(**{k:Path(args[k]) for k in
        ('source','dividends','splits','alpaca','issuer','reference')})
    variants = [v for v in registered_catalog(['AAPL'])['records'] if v['signal_minutes']==minutes]
    declaration = dict(symbol='AAPL', start='2022-03-15', end='2022-05-10', minutes=minutes,
                       variants=variants, action_facts=facts, minimum_tick=.01, research_ready=False)
    binding = RunBinding(ROOT, inputs=inputs, declaration=declaration)
    chart = CausalFeatures(raw, [action], calendar, security_id=facts['security_id'], minutes=minutes,
                           start=declaration['start'], end=declaration['end'])
    counts, proposals, censored, epochs = 0, 0, 0, []
    with transaction(Path(args['output'])/str(minutes)) as temp:
        for number, epoch in enumerate(chart.epochs()):
            epoch.tv.join(epoch.technical.loc[epoch.observed]).to_parquet(temp/f'epoch-{number}-features.parquet')
            epochs.append(dict(start=epoch.start.isoformat(), end=epoch.end.isoformat(),
                               observations=len(epoch.observed), action_ids=list(epoch.action_ids)))
        with (temp/'proposals.jsonl').open('w') as stream:
            for records, batch in causal_proposal_batches('AAPL', chart, variants, start=declaration['start'],
                                                          end=declaration['end']):
                counts += len(records)
                for row in batch:
                    row['exit_decision_ns'] = int(row['exit_decision_at'].value) if row['proposal_closed'] else None
                    row['censored_ns'] = None if row['proposal_closed'] else int(row['censored_at'].value)
                    for key in ('decision_at','exit_decision_at','censored_at'):
                        row.pop(key)
                    stream.write(json.dumps(row, default=str)+'\n')
                    proposals += 1
                    censored += not row['proposal_closed']
        if counts != len(variants):
            raise ValueError('Causal pilot omitted variants')
        report = dict(minutes=minutes, variants=counts, proposals=proposals, censored=censored,
            epochs=epochs, action_facts=facts, seconds=time.perf_counter()-began,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            research_ready=False, limits='Single issuer/action price-feature-proposal integration; no quote labels or model training')
        manifest = binding.finish()
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        (temp/'binding.json').write_text(json.dumps(manifest, indent=2)+'\n')
        receipt(temp, dict(identity=manifest['identity'], research_ready=False))
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source','dividends','splits','alpaca','issuer','reference','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = vars(parser.parse_args()); workers = args.pop('workers')
    args['output'].mkdir(parents=True, exist_ok=False)
    with worker_pool(workers, threads=1) as pool:
        reports = list(pool.map(worker, [(args, m) for m in (1,5,15,30)]))
    (args['output']/'report.json').write_text(json.dumps(reports, indent=2)+'\n')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__': main()
