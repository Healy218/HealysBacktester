"""Measured fresh acquisition frontier; never a signal or admission census."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import fcntl
import json
import math
from pathlib import Path

from nn_meta.etfe import acquisition as a
from nn_meta.etfe.demand import load_inventory, query_key
from nn_meta.etfe.expansion import read_calendar

SOURCES = ('nn_meta/etfe/demand_frontier.py', 'scripts/etfe_demand_frontier.py',
           'docs/specs/ETFE_DEMAND_FRONTIER_20261005.md')


def inspect_inputs(roots):
    """Measure verified payloads once; reject implicit selection of vintages."""
    inputs, queries, contracts, measurements = [], {}, {}, defaultdict(Counter)
    for root in roots:
        root = Path(root).resolve()
        plan = a.load_plan(root)
        if any(x['root'] == str(root) for x in inputs):
            raise ValueError('Duplicate input root')
        inputs.append(dict(root=str(root), sha256=plan['sha256']))
        for item in plan['jobs']:
            key = query_key(item)
            if key in queries:
                raise ValueError('Overlapping query vintages require explicit selection')
            history, _, complete = a.committed(root, item)
            if not complete:
                raise ValueError('Complete captures required for frontier')
            queries[key] = dict(root=str(root), job_id=item['id'])
            m = measurements[item['route']]
            m['queries'] += 1
            query_bytes = query_rows = 0
            for receipt, body, attempt in history:
                payload_bytes = (root/attempt/'body.json').stat().st_size
                m['pages'] += 1
                m['payload_bytes'] += payload_bytes
                query_bytes += payload_bytes
                for symbol, row in a.rows(body, item):
                    m['rows'] += 1
                    query_rows += 1
                    if item['route'] == 'contracts':
                        p = item['params']
                        if row['expiration_date'] != p['expiration_date']:
                            raise ValueError('Discovery expiry mismatch')
                        identity = dict(ticker=p['underlying_symbols'], expiry=row['expiration_date'])
                        if symbol in contracts:
                            raise ValueError('Multiple discovery observations for one symbol')
                        contracts[symbol] = identity
            m['empty_queries'] += int(query_rows == 0)
            m['max_query_payload_bytes'] = max(m['max_query_payload_bytes'], query_bytes)
            m['max_query_pages'] = max(m['max_query_pages'], len(history))
        inputs[-1]['total_files_bytes'] = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    return inputs, queries, contracts, dict(measurements)


def surface_envelope(calendar, contracts, queries, required):
    """Count returned symbols only, with unresolved expiry queries kept separate."""
    counts = Counter((v['ticker'], v['expiry']) for v in contracts.values())
    by_expiry = defaultdict(list)
    for key, entry in required.items():
        p = entry['item']['params']
        by_expiry[p['underlying_symbols'], p['expiration_date']].append(key)
    result = []
    for session in calendar:
        day = date.fromisoformat(session['date'])
        opening = datetime.fromisoformat(session['date']+'T'+session['open'])
        closing = datetime.fromisoformat(session['date']+'T'+session['close'])
        minutes = int((closing-opening).total_seconds()/60)
        for ticker in a.SYMBOLS:
            surface = purchase = unresolved = 0
            for (underlying, expiry), keys in by_expiry.items():
                dte = (date.fromisoformat(expiry)-day).days
                if underlying != ticker or not 0 <= dte <= 45:
                    continue
                surface += counts[underlying, expiry]
                if dte <= 5:
                    purchase += counts[underlying, expiry]
                unresolved += sum(k not in queries for k in keys)
            result.append(dict(ticker=ticker, session=session['date'], regular_minutes=minutes,
                returned_symbol_surface=surface, returned_purchase_symbols=purchase,
                unresolved_discovery_queries=unresolved,
                gross_surface_requests=math.ceil(surface/100),
                one_bar_per_regular_minute_scenario=surface*minutes))
    return result


def select_batch(required, captured, size=126):
    if not 1 <= size <= 126:
        raise ValueError('Batch size must be 1..126')
    missing = [entry['item'] for key, entry in required.items() if key not in captured]
    missing.sort(key=lambda j: (j['params']['expiration_date'],
                                j['params']['underlying_symbols'], j['params']['status']))
    return missing[:size], len(missing)


def build(root, inventory_root, input_roots):
    inventory = load_inventory(inventory_root)
    calendar = read_calendar(inventory['calendar_root'])
    inputs, queries, contracts, measures = inspect_inputs(input_roots)
    surfaces = surface_envelope(calendar, contracts, queries, inventory['queries'])
    batch, missing = select_batch(inventory['queries'], queries)
    discovery = measures['contracts']
    budget = dict(minimum_remaining_discovery_gets=missing,
        empirical_mean_payload_scenario_bytes=math.ceil(missing*discovery['payload_bytes']/discovery['queries']),
        observed_max_query_payload_scenario_bytes=missing*discovery['max_query_payload_bytes'],
        observed_max_query_page_scenario_gets=missing*discovery['max_query_pages'],
        scenario_is_not_a_bound=True, full_phase_B_C_request_budget=None,
        full_phase_B_C_storage_budget=None, normalization_and_temporary_bytes_not_in_payload=True)
    requirements = [
        dict(path='entry_features_context', inputs=['option_bars_0_45_DTE', 'option_trades_feature_windows'],
             status='known_symbol_envelope_only; exact full-window signals and eligibility unresolved'),
        dict(path='hold_exit_roll_retry', inputs=['option_bars_until_exit_or_expiry',
             'fresh_underlying_quotes_at_each_roll_retry', 'new_contract_0_5_DTE', 'dated_contract_terms'],
             status='path-conditioned clocks unresolved; retry cannot reuse stale quote'),
        dict(path='exercise_delivery_liquidation', inputs=['official_exercise_reference',
             'dated_deliverables', 'settlement_calendar', 'SIP_stock_quotes_with_size'],
             status='source/admission and quote transport density unresolved'),
        dict(path='terminal', inputs=['cash_settlement_calendar_after_final_market_observation'],
             status='market data ends at fixed cutoff; unresolved liabilities stay censored'),
    ]
    report = dict(schema='etfe-demand-frontier-v1', observed_at=datetime.now(timezone.utc).isoformat(),
        sources={n:a.sha((a.ROOT/n).read_bytes()) for n in SOURCES},
        inventory_root=str(Path(inventory_root).resolve()), inventory_sha256=inventory['sha256'],
        inputs=inputs, measurements=measures, budget=budget, phase_C_requirements=requirements,
        end_exclusive_utc=a.END, surfaces=surfaces, next_discovery_jobs=batch,
        summary=dict(required_discovery_queries=len(inventory['queries']),
            captured_discovery_queries=len(inventory['queries'])-missing,
            missing_discovery_queries=missing, discovered_symbols=len(contracts),
            ticker_sessions=len(surfaces),
            returned_symbol_session_edges=sum(s['returned_symbol_surface'] for s in surfaces),
            returned_purchase_symbol_session_edges=sum(s['returned_purchase_symbols'] for s in surfaces),
            gross_surface_requests=sum(s['gross_surface_requests'] for s in surfaces),
            regular_bar_scenario_rows=sum(s['one_bar_per_regular_minute_scenario'] for s in surfaces),
            possible_stock_quote_session_windows=len(surfaces),
            possible_stock_quote_regular_minutes=sum(s['regular_minutes'] for s in surfaces)),
        resources=a.resources(a.ROOT), legacy_data_inputs=[], full_demand_complete=False,
        ready_for_build=False, ready_for_training=False)
    report['sha256'] = a.digest(report)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    a.save(root/'FRONTIER.json', report)
    for name in SOURCES:
        target = root/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        a.write_new(target, (a.ROOT/name).read_bytes())
    return report


def load(root):
    root = Path(root)
    report = json.loads((root/'FRONTIER.json').read_text())
    if a.digest({k:v for k,v in report.items() if k != 'sha256'}) != report['sha256']:
        raise ValueError('Frontier checksum changed')
    for name, expected in report['sources'].items():
        if a.sha((root/'source'/name).read_bytes()) != expected or a.sha((a.ROOT/name).read_bytes()) != expected:
            raise ValueError('Frontier source changed; successor required')
    if load_inventory(report['inventory_root'])['sha256'] != report['inventory_sha256']:
        raise ValueError('Calendar inventory changed')
    for entry in report['inputs']:
        if a.load_plan(entry['root'])['sha256'] != entry['sha256']:
            raise ValueError('Input plan changed')
        # Also verify payload chains, not only their immutable plan.
        for item in a.load_plan(entry['root'])['jobs']:
            if not a.committed(entry['root'], item)[2]:
                raise ValueError('Input capture incomplete')
    return report


def prepare(root, frontier_root):
    report = load(frontier_root)
    return a.prepare(root, report['next_discovery_jobs'], parent=dict(
        kind='etfe-demand-frontier-discovery', frontier_root=str(Path(frontier_root).resolve()),
        frontier_sha256=report['sha256'], max_total_requests=256))


def run(root, http, request_budget=128, **kwargs):
    root = Path(root)
    plan = a.load_plan(root)
    parent = plan['parent']
    if parent['kind'] != 'etfe-demand-frontier-discovery' or parent['max_total_requests'] != 256:
        raise ValueError('Bounded frontier capture required')
    frontier = load(parent['frontier_root'])
    if frontier['sha256'] != parent['frontier_sha256'] or plan['jobs'] != frontier['next_discovery_jobs']:
        raise ValueError('Frontier binding changed')
    if not 1 <= request_budget <= 128:
        raise ValueError('Request budget must be 1..128')
    with (root/'study.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reservations = root/'request_reservations'
        reservations.mkdir(exist_ok=True)
        # Reserve BEFORE networking, including a process death inside HTTP.get.
        spent = len(list(reservations.glob('*.json')))
        if spent >= 256:
            raise ValueError('Study request budget exhausted; explicit successor required')
        class ReservedHTTP:
            def get(self, route, params, max_bytes):
                nonlocal spent
                if spent >= 256:
                    raise RuntimeError('Study request budget exhausted')
                a.save(reservations/f'{spent:06d}.json', dict(route=route, params=params))
                spent += 1
                return http.get(route, params, max_bytes)
        return a.capture(root, ReservedHTTP(), request_budget=min(request_budget, 256-spent), **kwargs)
