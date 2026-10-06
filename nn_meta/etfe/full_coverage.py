"""Full-range transport census and explicit historical-terms rejection evidence."""
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import full_discovery as f
from nn_meta.etfe import acquisition as old
from nn_meta.etfe.demand_frontier import load as load_frontier
from nn_meta.etfe.demand import load_inventory
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.normalization import typed_row, schema_for, session_map

SOURCES = ('nn_meta/etfe/full_coverage.py', 'scripts/audit_etfe_full_coverage.py',
           'nn_meta/etfe/full_discovery.py', 'nn_meta/etfe/normalization.py',
           'docs/specs/ETFE_FULL_COVERAGE_20261005.md')


def dated_reasons(raw):
    reasons = ['current_snapshot_not_dated_contract_terms']
    # A price/OI date does not supply either of the missing terms clocks.
    if not raw.get('effective_at'): reasons.append('terms_effective_at_absent')
    if not raw.get('available_at'): reasons.append('terms_available_at_absent')
    try:
        multiplier = Decimal(str(raw.get('multiplier')))
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError()
    except (ValueError, InvalidOperation):
        reasons.append('nonpositive_or_invalid_raw_multiplier')
    if raw['expiration_date'] < '2024-05-28' and any(
            d.get('settlement_type') == 'T+1' for d in raw.get('deliverables', [])):
        reasons.append('current_T1_delivery_on_pre_transition_expiry')
    if not raw.get('deliverables'): reasons.append('deliverables_absent')
    return reasons


def identity(raw):
    return {k:raw.get(k) for k in ('symbol','underlying_symbol','expiration_date','type',
                                   'strike_price','id','underlying_asset_id')}


def publish_table(path, records, schema):
    buf = BytesIO()
    pq.write_table(pa.Table.from_pylist(records, schema=schema), buf, compression='zstd')
    payload = buf.getvalue()
    if path.exists():
        if f.sha(path.read_bytes()) != f.sha(payload):
            raise ValueError('Normalized full-discovery payload changed')
    else:
        f.write_new(path, payload)
    return f.sha(payload)


def prepare(root, raw_root, frontier_root):
    root, raw_root, frontier_root = map(lambda p:Path(p).resolve(), (root,raw_root,frontier_root))
    raw_plan = f.load_plan(raw_root)
    if raw_plan['jobs'] != f.full_jobs():
        raise ValueError('Full six-query scope required')
    prior = load_frontier(frontier_root)
    parent = load_inventory(prior['inventory_root'])
    report = dict(schema='etfe-full-coverage-audit-v1', raw_root=str(raw_root),
        raw_plan_sha256=raw_plan['sha256'], frontier_root=str(frontier_root),
        frontier_sha256=prior['sha256'], calendar_root=parent['calendar_root'],
        calendar_sha256=parent['calendar_sha256'], inventory_root=prior['inventory_root'],
        inventory_sha256=parent['sha256'],
        sources={n:f.sha((f.ROOT/n).read_bytes()) for n in SOURCES},
        historical_terms_admitted=False, ready_for_build=False, ready_for_training=False)
    report['sha256'] = f.digest(report)
    root.mkdir(parents=True, exist_ok=False)
    f.save(root/'PLAN.json', report)
    for name in SOURCES:
        target = root/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        f.write_new(target, (f.ROOT/name).read_bytes())
    return report


def load(root):
    root = Path(root)
    p = json.loads((root/'PLAN.json').read_text())
    if f.digest({k:v for k,v in p.items() if k!='sha256'}) != p['sha256']:
        raise ValueError('Full coverage plan changed')
    for name, h in p['sources'].items():
        if f.sha((root/'source'/name).read_bytes()) != h or f.sha((f.ROOT/name).read_bytes()) != h:
            raise ValueError('Coverage source changed; successor required')
    if f.load_plan(p['raw_root'])['sha256'] != p['raw_plan_sha256']:
        raise ValueError('Full discovery plan changed')
    if load_frontier(p['frontier_root'])['sha256'] != p['frontier_sha256']:
        raise ValueError('Prior frontier changed')
    if load_inventory(p['inventory_root'])['sha256'] != p['inventory_sha256']:
        raise ValueError('Calendar inventory changed')
    return p


def run(root):
    root = Path(root)
    plan = load(root)
    raw_root = Path(plan['raw_root'])
    raw_plan = f.load_plan(raw_root)
    calendar = read_calendar(plan['calendar_root'])
    sessions = session_map(calendar)
    output = root/'partitions'
    output.mkdir(exist_ok=True)
    symbols, duplicate_symbols, counts, reasons = {}, Counter(), Counter(), Counter()
    dated_examples, page_receipts, route_queries = {}, {}, []
    for item in raw_plan['jobs']:
        history, _, complete = f.committed(raw_root, item)
        if not complete:
            raise ValueError('Full discovery transport incomplete')
        route_queries.append(dict(job_id=item['id'], params=item['params'], complete=True,
                                  pages=len(history), rows=0))
        for page, (receipt, body, _) in enumerate(history):
            f.guard(root, dict(max_page_bytes=32*2**20, max_root_bytes=2**30))
            records = []
            for ordinal, (symbol, raw) in enumerate(f.rows(body, item)):
                if symbol in symbols:
                    duplicate_symbols[symbol] += 1
                    if symbols[symbol] != identity(raw):
                        raise ValueError('Conflicting symbol identities in full discovery')
                symbols[symbol] = identity(raw)
                counts[raw['underlying_symbol'],raw['expiration_date'],raw['status']] += 1
                flags = dated_reasons(raw)
                reasons.update(flags)
                for flag in flags:
                    dated_examples.setdefault(flag, dict(symbol=symbol, raw=raw,
                        source=dict(job_id=item['id'],page=page,ordinal=ordinal,
                                    body_sha256=receipt['body_sha256'])))
                records.append(typed_row(symbol,raw,route='contracts',plan_sha=raw_plan['sha256'],
                    job_id=item['id'],page=page,ordinal=ordinal,receipt=receipt,sessions=sessions))
            key = f'{item["id"]}-{page:06d}'
            data_path = output/(key+'.parquet')
            h = publish_table(data_path, records, schema_for('contracts'))
            metadata = dict(data=str(data_path.relative_to(root)), data_sha256=h, rows=len(records),
                body_sha256=receipt['body_sha256'], job_id=item['id'], page=page)
            pointer = output/(key+'.json')
            if pointer.exists():
                if json.loads(pointer.read_text()) != metadata:
                    raise ValueError('Full discovery partition receipt changed')
            else:
                f.save(pointer, metadata)
            page_receipts[key] = f.sha(pointer.read_bytes())
            route_queries[-1]['rows'] += len(records)
    # Prior exact-query captures are an independent symbol-set control, not merged vintages.
    previous = json.loads((Path(plan['frontier_root'])/'FRONTIER.json').read_text())
    prior_symbols = {}
    for source in previous['inputs']:
        p = old.load_plan(source['root'])
        for item in p['jobs']:
            if item['route'] != 'contracts': continue
            for row in old.iter_records(source['root'], item):
                if f.START_EXPIRY <= row['raw']['expiration_date'] <= f.END_EXPIRY:
                    prior_symbols[row['symbol']] = identity(row['raw'])
    missing = sorted(set(prior_symbols)-set(symbols))
    conflicts = sorted(s for s in set(prior_symbols)&set(symbols) if prior_symbols[s] != symbols[s])
    required = load_inventory(plan['inventory_root'])['queries']
    exact = []
    for key, entry in sorted(required.items()):
        params = entry['item']['params']
        matches = [q for q in route_queries if q['params']['underlying_symbols']==params['underlying_symbols']
                   and q['params']['status']==params['status']
                   and q['params']['expiration_date_gte']<=params['expiration_date']<=q['params']['expiration_date_lte']]
        if len(matches)!=1:
            raise ValueError('Calendar expiry query lacks unique complete range transport')
        exact.append(dict(query_key=key, range_job_id=matches[0]['job_id'],
            underlying=params['underlying_symbols'], expiry=params['expiration_date'], status=params['status'],
            returned_occurrences=counts[params['underlying_symbols'],params['expiration_date'],params['status']],
            transport_complete=True, historical_listing_complete=False))
    surface_counts = Counter((r['underlying_symbol'],r['expiration_date']) for r in symbols.values())
    surfaces = []
    for session in calendar:
        day = date.fromisoformat(session['date'])
        minutes = (sessions[session['date']][1]-sessions[session['date']][0])//60_000_000_000
        for ticker in f.SYMBOLS:
            sizes = [surface_counts[ticker,(day+timedelta(days=i)).isoformat()] for i in range(46)]
            surfaces.append(dict(ticker=ticker,session=session['date'],returned_symbols=sum(sizes),
                purchase_symbols=sum(sizes[:6]),gross_bar_queries=(sum(sizes)+99)//100,
                regular_minute_scenario_rows=sum(sizes)*int(minutes)))
    report = dict(schema='etfe-full-discovery-census-v1', plan_sha256=plan['sha256'],
        page_receipts=page_receipts, route_queries=route_queries, exact_queries=exact, surfaces=surfaces,
        summary=dict(returned_occurrences=sum(counts.values()), unique_symbols=len(symbols),
            duplicate_symbols=len(duplicate_symbols), prior_symbols=len(prior_symbols),
            prior_missing_symbols=len(missing), prior_identity_conflicts=len(conflicts),
            calendar_queries=len(exact), calendar_transport_complete=sum(x['transport_complete'] for x in exact),
            historical_complete_queries=0, ticker_sessions=len(surfaces),
            symbol_session_edges=sum(s['returned_symbols'] for s in surfaces),
            purchase_symbol_session_edges=sum(s['purchase_symbols'] for s in surfaces),
            gross_bar_queries=sum(s['gross_bar_queries'] for s in surfaces),
            regular_minute_scenario_rows=sum(s['regular_minute_scenario_rows'] for s in surfaces)),
        duplicate_symbol_counts=dict(duplicate_symbols), prior_missing_symbols=missing, prior_identity_conflicts=conflicts,
        dated_reason_counts=dict(reasons), dated_examples=dated_examples,
        dated_terms_admitted=0, full_market_coverage_complete=False,
        ready_for_build=False, ready_for_training=False)
    seal = root/'CENSUS.json'
    if seal.exists():
        if json.loads(seal.read_text()) != report:
            raise ValueError('Full census changed')
    else:
        f.save(seal,report)
    return report
