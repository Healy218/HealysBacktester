"""Independently reconcile frontier counts from verified raw discovery bodies."""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe.acquisition import save, sha, SYMBOLS
from nn_meta.etfe.demand_frontier import load
from nn_meta.etfe.expansion import read_calendar


def audit(root):
    report = load(root)
    parent = json.loads((Path(report['inventory_root'])/'DEMAND.json').read_text())
    calendar = read_calendar(parent['calendar_root'])
    sessions = [date.fromisoformat(s['date']) for s in calendar]
    all_queries, symbols = set(), {}
    measured = {}
    for source in report['inputs']:
        raw = Path(source['root'])
        plan = json.loads((raw/'PLAN.json').read_text())
        for item in plan['jobs']:
            route = item['route']
            m = measured.setdefault(route, Counter())
            p = item['params']
            if route == 'contracts':
                key = (p['underlying_symbols'], p['expiration_date'], p['status'])
                assert key not in all_queries
                all_queries.add(key)
            pages = list((raw/'jobs'/item['id']).glob('page-*.json'))
            query_bytes = query_rows = 0
            for page in pages:
                pointer = json.loads(page.read_text())
                body_path = raw/pointer['attempt']/'body.json'
                body = json.loads(body_path.read_text())
                field = 'option_contracts' if route == 'contracts' else 'trades' if route == 'option_trades' else 'bars'
                values = body[field] or ([] if route == 'contracts' else {})
                query_rows += len(values) if route == 'contracts' else sum(map(len, values.values()))
                query_bytes += body_path.stat().st_size
                if route == 'contracts':
                    for row in values:
                        assert row['symbol'] not in symbols
                        symbols[row['symbol']] = (row['underlying_symbol'], date.fromisoformat(row['expiration_date']))
            m.update(queries=1, rows=query_rows, pages=len(pages), payload_bytes=query_bytes,
                     empty_queries=int(query_rows == 0))
            m['max_query_pages'] = max(m['max_query_pages'], len(pages))
            m['max_query_payload_bytes'] = max(m['max_query_payload_bytes'], query_bytes)
    assert measured == report['measurements']
    surface, purchases = Counter(), Counter()
    for ticker, expiry in symbols.values():
        for day in sessions[bisect_left(sessions, expiry-timedelta(days=45)):bisect_right(sessions, expiry)]:
            surface[ticker, day] += 1
            purchases[ticker, day] += int((expiry-day).days <= 5)
    required = {(ticker, (day+timedelta(days=i)).isoformat(), status)
                for day in sessions for ticker in SYMBOLS for i in range(46)
                for status in ('active', 'inactive')}
    missing = required-all_queries
    summary = report['summary']
    assert summary['required_discovery_queries'] == len(required)
    assert summary['missing_discovery_queries'] == len(missing)
    assert summary['captured_discovery_queries'] == len(required & all_queries)
    assert summary['discovered_symbols'] == len(symbols)
    assert summary['returned_symbol_session_edges'] == sum(surface.values())
    assert summary['returned_purchase_symbol_session_edges'] == sum(purchases.values())
    expected_batch = sorted(missing, key=lambda k:(k[1], k[0], k[2]))[:126]
    actual_batch = [(j['params']['underlying_symbols'], j['params']['expiration_date'],
                     j['params']['status']) for j in report['next_discovery_jobs']]
    assert actual_batch == expected_batch
    seen = set()
    for row in report['surfaces']:
        key = row['ticker'], date.fromisoformat(row['session'])
        assert key not in seen
        seen.add(key)
        assert row['returned_symbol_surface'] == surface[key]
        assert row['returned_purchase_symbols'] == purchases[key]
        assert row['unresolved_discovery_queries'] == sum(
            (key[0], (key[1]+timedelta(days=i)).isoformat(), status) in missing
            for i in range(46) for status in ('active', 'inactive'))
        session = calendar[sessions.index(key[1])]
        def minute(clock):
            hours, minutes = clock.split(':')[:2]
            return int(hours)*60+int(minutes)
        duration = minute(session['close'])-minute(session['open'])
        assert row['regular_minutes'] == duration
        assert row['one_bar_per_regular_minute_scenario'] == duration*surface[key]
        assert row['gross_surface_requests'] == (surface[key]+99)//100
    assert seen == {(ticker, day) for ticker in SYMBOLS for day in sessions}
    assert summary['ticker_sessions'] == len(seen)
    assert summary['gross_surface_requests'] == sum(r['gross_surface_requests'] for r in report['surfaces'])
    assert summary['regular_bar_scenario_rows'] == sum(r['one_bar_per_regular_minute_scenario'] for r in report['surfaces'])
    assert not report['full_demand_complete'] and not report['ready_for_training']
    return dict(frontier_sha256=report['sha256'], verified_ticker_sessions=len(seen),
        all_payload_measurements_match=True, all_surface_counts_match=True,
        next_batch_independently_reconciled=True, audit_source_sha256=sha(Path(__file__).read_bytes()))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.root)
    save(args.root/'INDEPENDENT_AUDIT.json', result)
    print(json.dumps(result))
