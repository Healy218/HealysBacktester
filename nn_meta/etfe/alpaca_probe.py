"""Bounded, receipt-backed Alpaca-only GET probes; never a coverage admission."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import requests

from nn_meta.etfe.preparation import SYMBOLS, file_sha, save_new

DATA = 'https://data.alpaca.markets'
PAPER = 'https://paper-api.alpaca.markets'
ROUTES = {
    'calendar': (PAPER, '/v2/calendar', 'metadata'),
    'contracts': (PAPER, '/v2/options/contracts', 'metadata'),
    'stock_bars': (DATA, '/v2/stocks/bars', 'data'),
    'option_bars': (DATA, '/v1beta1/options/bars', 'data'),
    'option_trades': (DATA, '/v1beta1/options/trades', 'data'),
    # A diagnostic request only; 404 must not be recorded as empty quote history.
    'historical_quotes': (DATA, '/v1beta1/options/quotes', 'data'),
}


class ReadOnlyProbe:
    def __init__(self, output, credentials, *, session=None, max_requests=32, max_response_bytes=2**21):
        self.output = Path(output)
        self.output.mkdir(exist_ok=False)
        self.session = session or requests.Session()
        self.credentials = credentials
        self.max_requests = max_requests
        self.max_response_bytes = max_response_bytes
        self.receipts = []

    def get(self, route, params):
        if route not in ROUTES:
            raise ValueError('Only allowlisted Alpaca metadata/data GET routes are permitted')
        if len(self.receipts) >= self.max_requests:
            raise ValueError('ETFE probe request budget reached')
        base, path, role = ROUTES[route]
        key, secret = self.credentials[role]
        if not key or not secret:
            raise ValueError('Required Alpaca credential pair missing')
        index = len(self.receipts)
        receipt = dict(route=route, method='GET', url=base+path, params=params,
            credential_role=role, observed_at=datetime.now(timezone.utc).isoformat(),
            status_code=None, transport_error=None, complete_history=False)
        self.receipts.append(receipt)
        body = None
        try:
            with self.session.get(base+path, params=params,
                    headers={'APCA-API-KEY-ID':key, 'APCA-API-SECRET-KEY':secret},
                    timeout=(10,20), allow_redirects=False, stream=True) as response:
                receipt['status_code'] = response.status_code
                raw = bytearray()
                for block in response.iter_content(65536):
                    raw.extend(block)
                    if len(raw) > self.max_response_bytes:
                        raise ValueError('Alpaca probe response exceeded byte budget')
                # Never persist credentials even if an unexpected response echoes them.
                if any(v.encode() in raw for pair in self.credentials.values() for v in pair if v):
                    raise ValueError('Provider response contains credential material; not saved')
                raw_path = self.output/f'{index:03d}-{route}.body'
                with raw_path.open('xb') as stream:
                    stream.write(raw)
                receipt.update(body_path=raw_path.name, body_bytes=len(raw),
                    body_sha256=hashlib.sha256(raw).hexdigest())
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    receipt['response_format'] = 'non_json'
                if isinstance(body, dict):
                    receipt['next_page_available'] = bool(body.get('next_page_token'))
        except requests.RequestException:
            # Exception strings may include request internals; retain only classification.
            receipt['transport_error'] = 'request_failed'
        finally:
            save_new(self.output/f'{index:03d}-{route}.json', receipt)
        return receipt, body


def select_contract(body, underlying):
    """A returned example is a probe target, never a PIT eligible-chain claim."""
    if not isinstance(body, dict):
        return None
    for row in body.get('option_contracts') or []:
        symbol = row.get('symbol', '')
        if (row.get('underlying_symbol') == underlying
                and re.fullmatch(re.escape(underlying)+r'\d{6}[CP]\d{8}', symbol)):
            return symbol
    return None


def run_probe(client, plan_path):
    plan = json.loads(Path(plan_path).read_text())
    if plan.get('expert') != 'etfe' or plan['runtime']['provider'] != 'alpaca':
        raise ValueError('Expected ETFE Alpaca setup plan')
    from nn_meta.etfe.preparation import digest, validate_scope
    validate_scope(plan['scope'])
    if digest({k:v for k,v in plan.items() if k != 'plan_sha256'}) != plan['plan_sha256']:
        raise ValueError('ETFE plan digest mismatch')
    observations = []
    calendar_receipt, calendar = client.get('calendar',
        dict(start='2024-02-01', end='2026-10-02'))
    final_session = None
    if calendar_receipt['status_code'] == 200 and isinstance(calendar, list):
        matches = [x for x in calendar if x.get('date') == '2026-10-02']
        if len(matches) == 1:
            final_session = matches[0]
    # Probe each symbol separately: a multi-symbol page limit can conceal later symbols.
    for ticker in SYMBOLS:
        r, b = client.get('stock_bars', dict(symbols=ticker, timeframe='1Min',
            start='2024-02-01T00:00:00Z', end='2024-02-02T00:00:00Z',
            feed='sip', adjustment='raw', limit=1, sort='asc'))
        rows = (b.get('bars') or {}).get(ticker, []) if isinstance(b, dict) else []
        observations.append(dict(ticker=ticker, kind='stock_minute_sample',
            status_code=r['status_code'], first_sample=rows[0].get('t') if rows else None))
        # Expired contracts require status=inactive; this is today's reference
        # response about old contracts, not a historical as-of chain snapshot.
        r, body = client.get('contracts', dict(underlying_symbols=ticker,
            status='inactive', expiration_date_gte='2024-02-01',
            expiration_date_lte='2024-02-29', type='call', limit=5))
        contract = select_contract(body, ticker) if r['status_code'] == 200 else None
        observations.append(dict(ticker=ticker, kind='historical_contract_example',
            status_code=r['status_code'], contract=contract, point_in_time_chain_verified=False))
        if contract is None:
            continue
        for route in ('option_bars', 'option_trades'):
            for start in ('2024-01-01T00:00:00Z', '2024-02-01T00:00:00Z'):
                params = dict(symbols=contract, start=start, end='2024-03-01T00:00:00Z',
                    limit=1, sort='asc')
                if route == 'option_bars':
                    params['timeframe'] = '1Min'
                # Historical option endpoints do not document a feed parameter;
                # preserve provider response, and never infer OPRA provenance merely
                # from the request being accepted. Feed proof remains an admission task.
                receipt, response = client.get(route, params)
                field = 'bars' if route == 'option_bars' else 'trades'
                rows = (response.get(field) or {}).get(contract, []) if isinstance(response, dict) else []
                observations.append(dict(ticker=ticker, contract=contract, kind=route,
                    requested_start=start, status_code=receipt['status_code'],
                    first_sample=rows[0].get('t') if rows else None,
                    coverage_complete=False, feed_verified=False))
        r, _ = client.get('historical_quotes', dict(symbols=contract,
            start='2024-02-01T14:30:00Z', end='2024-02-01T14:31:00Z', limit=1, feed='opra'))
        observations.append(dict(ticker=ticker, kind='historical_quote_endpoint',
            status_code=r['status_code'], coverage_complete=False))
    result = dict(schema='etfe-alpaca-capability-probe-v1', expert='etfe',
        observed_at=datetime.now(timezone.utc).isoformat(),
        setup_plan_file_sha256=file_sha(plan_path), setup_plan_sha256=plan['plan_sha256'],
        status='bounded_probe_complete_not_admitted', requests=len(client.receipts),
        transport_failures=sum(bool(r['transport_error']) for r in client.receipts),
        observations=observations, final_stock_session=final_session,
        first_history_timestamp_verified=False, historical_quote_coverage_verified=False,
        dated_contract_coverage_verified=False, ready_for_build=False,
        feed_admission='OPRA required; historical response feed provenance still requires verification',
        boundary='Sample responses only. Empty pages/errors are not no-trade evidence; first samples do not prove provider-global earliest coverage.',
        receipt_files={p.name:file_sha(p) for p in sorted(client.output.iterdir()) if p.is_file()})
    if result['transport_failures']:
        result['status'] = 'transport_blocked'
    save_new(client.output/'PROBE.json', result)
    return result
