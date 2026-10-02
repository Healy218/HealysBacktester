"""Read-only current option-data probe. Never submits orders or edits paper state."""
import json
import sqlite3
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv
from scripts.v6_alpaca_market_v1 import AlpacaOptionQuotes
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'nn_meta/validation/v6-alpaca-provider-20261002-r0'
STATE=Path('/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper')
def main():
    load_dotenv(ROOT/'.env')
    with sqlite3.connect('file:'+str(STATE/'portfolio.sqlite3')+'?mode=ro',uri=True) as db:
        positions=[json.loads(r[0]) for r in db.execute("SELECT payload FROM positions WHERE state IN ('open','exit_due','roll_due')")]
    m=AlpacaOptionQuotes(OUT/'observations');now=pd.Timestamp.now(tz='UTC')
    report=dict(observed_at=now.isoformat(),paper_only=True,orders_submitted=False,quotes=[])
    for p in positions:
        try:
            quote=m.execution_quote(p['contract'],after=now-pd.Timedelta(seconds=30))
            report['quotes'].append(dict(contract=p['contract'],status='passed',quote=quote))
        except Exception as exc:
            report['quotes'].append(dict(contract=p['contract'],status='blocked',error=str(exc)))
    if positions:
        contract=positions[0]['contract']
        for name,path,params in [
            ('historical_quotes','/v1beta1/options/quotes',dict(symbols=contract,feed='opra',start=(now-pd.Timedelta(minutes=15)).isoformat(),end=now.isoformat(),limit=1)),
            ('historical_trades','/v1beta1/options/trades',dict(symbols=contract,feed='opra',start=(now-pd.Timedelta(minutes=15)).isoformat(),end=now.isoformat(),limit=1))]:
            try:
                response=m.session.get('https://data.alpaca.markets'+path,params=params,timeout=15)
                report[name]=dict(status_code=response.status_code,endpoint=path)
            except requests.RequestException:
                report[name]=dict(error='transport failed')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
