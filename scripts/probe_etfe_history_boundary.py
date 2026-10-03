"""Bounded near-money contract history samples; never declares a global start."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nn_meta.etfe.alpaca_probe import ReadOnlyProbe, select_contract
from nn_meta.etfe.preparation import SYMBOLS, file_sha, save_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    setup, output = args.setup.resolve(), args.output.resolve()
    if (setup.parent != ROOT/'nn_meta/validation' or not setup.name.startswith('etfe-')
            or output.parent != setup or not output.name.startswith('probe-')):
        parser.error('Expected an ETFE setup root and fresh probe-* child')
    from dotenv import dotenv_values
    values = dotenv_values(ROOT/'.env')
    credentials = {role:(values.get(key),values.get(secret)) for role,key,secret in (
        ('data','ALPACA_API_KEY','ALPACA_API_SECRET'),
        ('metadata','ALPACA_PAPER_API_KEY','ALPACA_PAPER_API_SECRET'))}
    if not all(all(pair) for pair in credentials.values()):
        parser.error('Alpaca credential pairs missing')
    plan=json.loads((setup/'plan.json').read_text())
    from nn_meta.etfe.preparation import digest, validate_scope
    validate_scope(plan['scope'])
    if digest({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan['plan_sha256']:
        parser.error('Setup plan digest mismatch')
    for name,expected in plan['source_bindings'].items():
        if file_sha(ROOT/name)!=expected:
            parser.error('Frozen setup source differs; use a versioned consumer')
    client=ReadOnlyProbe(output,credentials)
    examples=[]
    for ticker in SYMBOLS:
        receipt,body=client.get('stock_bars',dict(symbols=ticker,timeframe='1Day',
            start='2024-01-16T05:00:00Z',end='2024-01-17T04:59:59Z',
            feed='sip',adjustment='raw',limit=1,sort='asc'))
        rows=(body.get('bars') or {}).get(ticker,[]) if isinstance(body,dict) else []
        if receipt['status_code']!=200 or not rows:
            continue
        reference=float(rows[0]['c'])
        for expiry in ('2024-01-19','2024-02-16'):
            receipt,body=client.get('contracts',dict(underlying_symbols=ticker,status='inactive',
                expiration_date=expiry,type='call',strike_price_gte=round(reference*.98,2),
                strike_price_lte=round(reference*1.02,2),limit=100))
            contracts=body.get('option_contracts') or [] if isinstance(body,dict) else []
            valid=[c for c in contracts if select_contract({'option_contracts':[c]},ticker)]
            if receipt['status_code']!=200 or not valid:
                examples.append(dict(ticker=ticker,expiry=expiry,status='no_contract_example',
                    status_code=receipt['status_code']))
                continue
            row=min(valid,key=lambda c:abs(float(c['strike_price'])-reference))
            contract=row['symbol']
            end=(date.fromisoformat(expiry)+timedelta(days=1)).isoformat()+'T04:59:59Z'
            for route,field in [('option_bars','bars'),('option_trades','trades')]:
                params=dict(symbols=contract,start='2023-01-01T00:00:00Z',end=end,limit=1,sort='asc')
                if route=='option_bars':params['timeframe']='1Min'
                receipt,body=client.get(route,params)
                rows=(body.get(field) or {}).get(contract,[]) if isinstance(body,dict) else []
                examples.append(dict(ticker=ticker,contract=contract,kind=route,
                    reference_stock_close=reference,status_code=receipt['status_code'],
                    first_returned_timestamp=rows[0]['t'] if rows else None,
                    next_page_available=receipt.get('next_page_available',False)))
    result=dict(schema='etfe-history-boundary-sample-v1',expert='etfe',
        observed_at=datetime.now(timezone.utc).isoformat(),
        script_sha256=file_sha(__file__),client_sha256=file_sha(ROOT/'nn_meta/etfe/alpaca_probe.py'),
        setup_plan_sha256=plan['plan_sha256'],requests=len(client.receipts),examples=examples,
        provider_global_start_verified=False,history_coverage_complete=False,ready_for_build=False,
        selection='Near the captured January 16 stock close, one returned call per ticker/expiry. Diagnostic examples only; not PIT candidate selection or a complete historical contract census.',
        receipt_files={p.name:file_sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    save_new(output/'BOUNDARY.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='receipt_files'},indent=2))
    if any(r['transport_error'] for r in client.receipts):raise SystemExit(2)


if __name__=='__main__':main()
