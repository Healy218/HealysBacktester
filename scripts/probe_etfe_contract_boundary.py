"""Bounded VWAP-bound history/reference controls, never global-history admission."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nn_meta.etfe.alpaca_probe import ReadOnlyProbe
from nn_meta.etfe.preparation import file_sha, save_new
from nn_meta.etfe.vwap_setup import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    setup, output = args.setup.resolve(), args.output.resolve()
    if output.parent != ROOT/'nn_meta/validation' or not output.name.startswith('etfe-'):
        parser.error('Use a fresh direct ETFE validation root')
    verified = verify(setup)
    from dotenv import dotenv_values
    values = dotenv_values(ROOT/'.env')
    credentials = {role: (values.get(key), values.get(secret)) for role, key, secret in (
        ('data', 'ALPACA_API_KEY', 'ALPACA_API_SECRET'),
        ('metadata', 'ALPACA_PAPER_API_KEY', 'ALPACA_PAPER_API_SECRET'))}
    if not all(all(pair) for pair in credentials.values()):
        parser.error('Required credential pairs missing')
    client = ReadOnlyProbe(output, credentials, max_requests=10)
    observations = []
    # Symbols come from the retained October 3 sample, not constructed chains.
    for symbol in ('SPY240119C00475000', 'QQQ240119C00409780', 'VOO240119C00435000'):
        for route, field in (('option_trades', 'trades'), ('option_bars', 'bars')):
            params = dict(symbols=symbol, start='1970-01-01T00:00:00Z',
                          end='2024-01-18T14:29:59.999999999Z', sort='asc', limit=1)
            if route == 'option_bars':
                params['timeframe'] = '1Min'
            receipt, body = client.get(route, params)
            rows = (body.get(field) or {}).get(symbol, []) if isinstance(body, dict) else []
            observations.append(dict(contract=symbol, route=route,
                status_code=receipt['status_code'], first_returned=rows[0] if rows else None,
                next_page_available=receipt.get('next_page_available'),
                scope='named contract only; no global absence inference'))
        ticker = symbol[:-15]
        receipt, body = client.get('contracts', dict(underlying_symbols=ticker,
            status='inactive', expiration_date='2024-01-19', type='call',
            strike_price_gte=int(symbol[-8:])/1000, strike_price_lte=int(symbol[-8:])/1000,
            show_deliverables='true', limit=100))
        observations.append(dict(contract=symbol, route='contracts',
            status_code=receipt['status_code'],
            matches=[r for r in (body.get('option_contracts') or []) if r.get('symbol') == symbol]
                    if isinstance(body, dict) else [],
            scope='current metadata only; no historical availability assertion'))
    receipt, body = client.get('calendar', dict(start='2026-10-02', end='2026-10-02'))
    observations.append(dict(route='calendar', status_code=receipt['status_code'], sessions=body))
    report = dict(schema='etfe-contract-boundary-controls-v1',
        observed_at=datetime.now(timezone.utc).isoformat(),
        setup_plan_sha256=verified['plan_sha256'],
        source_bindings={name:file_sha(ROOT/name) for name in (
            'scripts/probe_etfe_contract_boundary.py', 'nn_meta/etfe/alpaca_probe.py')},
        requests=len(client.receipts), transport_failures=sum(bool(r['transport_error']) for r in client.receipts),
        observations=observations, provider_global_start_verified=False,
        ready_for_build=False, ready_for_training=False,
        receipt_files={p.name:file_sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    save_new(output/'REPORT.json', report)
    print(json.dumps({k:report[k] for k in ('requests', 'transport_failures', 'provider_global_start_verified')}, indent=2))
    if report['transport_failures']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
