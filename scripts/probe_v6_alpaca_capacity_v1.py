"""One bounded read-only OPRA capacity request; no bypass, reconnect or orders."""
import asyncio
import json
import os
from pathlib import Path
import time
import msgpack
import websockets
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'nn_meta/validation/v6-alpaca-provider-20261002-r0'
async def probe():
    census=json.loads((OUT/'stream-census.json').read_text())
    contracts=census['contracts']
    report=dict(observed_at_ns=time.time_ns(),requested_quotes=len(contracts),
        status='unverified',orders_submitted=False,provider='alpaca',feed='opra')
    try:
        async with websockets.connect('wss://stream.data.alpaca.markets/v1beta1/opra',
            additional_headers={'Content-Type':'application/msgpack'},max_queue=16) as socket:
            await socket.send(msgpack.packb(dict(action='auth',key=os.environ['ALPACA_PAPER_API_KEY'],secret=os.environ['ALPACA_PAPER_API_SECRET'])))
            async with asyncio.timeout(20):
                while True:
                    messages=msgpack.unpackb(await socket.recv(),raw=False,timestamp=0)
                    for m in messages:
                        if m.get('T')=='error':
                            report.update(status='rejected',error_code=m.get('code'),error_message=m.get('msg'))
                            return report
                        if m.get('T')=='success' and m.get('msg')=='authenticated':
                            await socket.send(msgpack.packb(dict(action='subscribe',quotes=contracts)))
                        if m.get('T')=='subscription':
                            acknowledged=set(m.get('quotes',[]))
                            report.update(status='accepted' if acknowledged==set(contracts) else 'partial',acknowledged_quotes=len(acknowledged))
                            return report
    except Exception as exc:report.update(status='unverified',error_type=type(exc).__name__)
    return report
if __name__=='__main__':
    load_dotenv(ROOT/'.env');r=asyncio.run(probe());(OUT/'capacity-probe.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
