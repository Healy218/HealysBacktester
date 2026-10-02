"""Bounded V6 OPRA transport recorder; raw data only, never model admission.

A subscription acknowledgement, heartbeat or ping is NOT proof of complete
exchange coverage. Connection epochs, failures and durable rows stay explicit.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import msgpack
import websockets
from dotenv import load_dotenv
from nn_meta.live.feeds.tick_journal import canonical_contract
from scripts.v6_opra_journal_v1 import V6OpraJournal as TickJournal

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n');tmp.replace(path)


def load_plan(path):
    raw=Path(path).read_bytes();doc=json.loads(raw)
    contracts=sorted({canonical_contract(x) for x in doc['contracts']})
    if not contracts or len(contracts)>1000:
        raise ValueError('Explicit recording plan must contain 1..1000 contracts; never truncate')
    if doc.get('scope')!='transport_validation_only' or doc.get('model_admission') is not False:
        raise ValueError('This recorder has not been admitted for model inputs')
    return contracts,hashlib.sha256(raw).hexdigest()


async def capture(plan,root,seconds=None):
    contracts,plan_sha=load_plan(plan)
    key,secret=os.environ.get('ALPACA_PAPER_API_KEY'),os.environ.get('ALPACA_PAPER_API_SECRET')
    if not key or not secret:raise ValueError('Dedicated paper credentials missing')
    epoch=uuid.uuid4().hex;output=Path(root)/epoch;output.mkdir(parents=True)
    state=dict(schema='v6-alpaca-recorder-v1',epoch=epoch,plan_sha256=plan_sha,
        contracts=contracts,scope='transport_validation_only',model_admission=False,
        coverage_complete=False,provider='alpaca',feed='opra',status='connecting',
        started_at_ns=time.time_ns(),subscription_ack_ns=None)
    def report(**changes):
        state.update(changes,observed_at_ns=time.time_ns());save(output/'status.json',state);save(Path(root)/'status.json',state)
    began=time.monotonic()
    with TickJournal(output/'journal',max_contracts=len(contracts)) as journal:
        journal.set_contracts(contracts)
        try:
            async with websockets.connect('wss://stream.data.alpaca.markets/v1beta1/opra',
                additional_headers={'Content-Type':'application/msgpack'},ping_interval=10,
                ping_timeout=10,max_queue=1024) as socket:
                await socket.send(msgpack.packb(dict(action='auth',key=key,secret=secret)))
                authenticated=False;last_flush=time.monotonic()
                while seconds is None or time.monotonic()-began<seconds:
                    try:packet=await asyncio.wait_for(socket.recv(),timeout=5)
                    except asyncio.TimeoutError:
                        # No tick does not establish a gap or healthy coverage.
                        journal.flush();report(journal=journal.status());continue
                    messages=msgpack.unpackb(packet,raw=False,timestamp=0)
                    received,mono=time.time_ns(),time.monotonic_ns()
                    if not isinstance(messages,list):raise ValueError('Unexpected OPRA packet')
                    for message in messages:
                        kind=message.get('T')
                        if kind=='error':raise RuntimeError('Alpaca stream error code '+str(message.get('code')))
                        if kind=='success' and message.get('msg')=='authenticated':
                            authenticated=True
                            await socket.send(msgpack.packb(dict(action='subscribe',quotes=contracts,trades=contracts)))
                            report(status='awaiting_subscription')
                        elif kind=='subscription':
                            if not authenticated or set(message.get('quotes',[]))!=set(contracts) or set(message.get('trades',[]))!=set(contracts):
                                raise ValueError('OPRA subscription acknowledgement does not match plan')
                            journal.control('subscription_acknowledged',received_at_ns=received,
                                quotes=contracts,trades=contracts,coverage_complete=False)
                            journal.flush();report(status='recording',subscription_ack_ns=received,journal=journal.status())
                        elif kind in ('q','t'):
                            if state['subscription_ack_ns'] is None:raise ValueError('Tick before subscription acknowledgement')
                            if not journal.record(message,received_at_ns=received,received_monotonic_ns=mono):
                                raise ValueError('Unplanned contract tick')
                            if journal.normalization_errors:raise ValueError('OPRA tick normalization error')
                    if time.monotonic()-last_flush>=2:
                        journal.flush();last_flush=time.monotonic();report(journal=journal.status())
                journal.control('bounded_capture_finished',coverage_complete=False);journal.flush()
                report(status='finished',journal=journal.status())
        except BaseException as exc:
            # Do not log provider payloads or authentication fields.
            journal.control('capture_interrupted',exception_type=type(exc).__name__,coverage_complete=False)
            journal.flush();report(status='interrupted',error_type=type(exc).__name__,
                error=str(exc) if isinstance(exc,ValueError) or str(exc).startswith('Alpaca stream error code') else type(exc).__name__,journal=journal.status())
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--seconds',type=float)
    a=p.parse_args();load_dotenv(ROOT/'.env');asyncio.run(capture(a.plan,a.root,a.seconds))
if __name__=='__main__':main()
