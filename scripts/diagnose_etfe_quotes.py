"""Bounded GET controls for the unsupported historical option-quotes route.

An independent diagnostic consumer; never changes frozen setup producers.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe.preparation import file_sha, save_new
from nn_meta.etfe.verification import verify_setup

BASE = 'https://data.alpaca.markets'
PATHS = {'/v1beta1/options/quotes', '/v1beta1/options/quotes/latest',
         '/v1beta1/options/trades'} | {
             f'/v1beta1/options/snapshots/{s}' for s in ('SPY', 'QQQ', 'VOO')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    setup, output = args.setup.resolve(), args.output.resolve()
    if (setup.parent != ROOT/'nn_meta/validation' or not setup.name.startswith('etfe-')
            or output.parent != setup or not output.name.startswith('probe-')):
        parser.error('Expected an ETFE setup root and fresh probe-* child')
    verification = verify_setup(setup)
    from dotenv import dotenv_values
    values = dotenv_values(ROOT/'.env')
    credentials = (values.get('ALPACA_API_KEY'), values.get('ALPACA_API_SECRET'))
    if not all(credentials):
        parser.error('Alpaca data credential pair missing')
    output.mkdir(exist_ok=False)
    receipts = []
    session = requests.Session()

    def get(label, path, params):
        if path not in PATHS or len(receipts) >= 13:
            raise ValueError('Diagnostic route/request budget exceeded')
        receipt = dict(label=label, method='GET', url=BASE+path, params=params,
            observed_at=datetime.now(timezone.utc).isoformat(), credential_role='data',
            status_code=None, transport_error=None, coverage_complete=False)
        prefix = f'{len(receipts):03d}-{label}'
        receipts.append(receipt)
        body = None
        try:
            with session.get(BASE+path, params=params, headers={
                    'APCA-API-KEY-ID': credentials[0],
                    'APCA-API-SECRET-KEY': credentials[1]},
                    timeout=(10, 20), allow_redirects=False, stream=True) as response:
                receipt['status_code'] = response.status_code
                raw = bytearray()
                for block in response.iter_content(65536):
                    raw.extend(block)
                    if len(raw) > 2**21:
                        raise ValueError('Response byte budget exceeded')
                if any(value.encode() in raw for value in credentials):
                    raise ValueError('Credential echo; response not saved')
                body_path = output/f'{prefix}.body'
                with body_path.open('xb') as stream:
                    stream.write(raw)
                receipt.update(body_path=body_path.name, body_bytes=len(raw),
                               body_sha256=file_sha(body_path))
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    receipt['response_format'] = 'non_json'
        except requests.RequestException:
            receipt['transport_error'] = 'request_failed'
        finally:
            save_new(output/f'{prefix}.json', receipt)
        return receipt, body

    # Removing all parameters distinguishes a missing route from empty history.
    get('history-no-params', '/v1beta1/options/quotes', {})
    get('known-historical-trade', '/v1beta1/options/trades', dict(
        symbols='SPY240119C00475000', start='2024-01-18T14:30:00Z',
        end='2024-01-18T14:31:00Z', limit=1, sort='asc'))
    examples = {}
    for ticker in ('SPY', 'QQQ', 'VOO'):
        receipt, body = get(f'{ticker}-chain', f'/v1beta1/options/snapshots/{ticker}',
            dict(feed='opra', type='call', expiration_date_gte='2026-10-05',
                 expiration_date_lte='2026-10-16', limit=1))
        snapshots = body.get('snapshots') or {} if isinstance(body, dict) else {}
        contracts = [s for s in snapshots if re.fullmatch(ticker+r'\d{6}C\d{8}', s)]
        if receipt['status_code'] != 200 or not contracts:
            continue
        contract = contracts[0]
        examples[ticker] = contract
        get(f'{ticker}-latest', '/v1beta1/options/quotes/latest',
            dict(symbols=contract, feed='opra'))
        get(f'{ticker}-history-opra', '/v1beta1/options/quotes', dict(
            symbols=contract, feed='opra', start='2026-10-02T13:30:00Z',
            end='2026-10-02T20:00:00Z', limit=1))
    if 'SPY' in examples:
        for feed in (None, 'indicative'):
            params = dict(symbols=examples['SPY'], start='2026-10-02T13:30:00Z',
                          end='2026-10-02T20:00:00Z', limit=1)
            if feed:
                params['feed'] = feed
            get(f'history-{feed or "no-feed"}', '/v1beta1/options/quotes', params)
    session.close()
    result = dict(schema='etfe-quote-route-diagnostic-v1',
        observed_at=datetime.now(timezone.utc).isoformat(),
        script_sha256=file_sha(__file__), setup_verification=verification,
        requests=len(receipts), transport_failures=sum(bool(r['transport_error']) for r in receipts),
        examples=examples, observations=receipts, ready_for_build=False,
        historical_quote_coverage_verified=False,
        boundary='Latest snapshots/quotes are endpoint controls, never historical input admission.',
        receipt_files={p.name:file_sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    save_new(output/'DIAGNOSTIC.json', result)
    print(json.dumps(dict(requests=result['requests'], transport_failures=result['transport_failures'],
        examples=examples, statuses={r['label']:r['status_code'] for r in receipts}), indent=2))
    if result['transport_failures']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
