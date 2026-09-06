"""Capture official Alpaca exchange sessions for all deployed experts."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from nn_meta.session_calendar import SessionCalendar
from nn_meta.live.state import atomic_write_json


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--start',default='2024-01-01');ap.add_argument('--end',default='2027-12-31')
    args=ap.parse_args();load_dotenv()
    headers={'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'],'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET']}
    data=None
    for host in ('https://paper-api.alpaca.markets','https://api.alpaca.markets'):
        try:
            r=requests.get(host+'/v2/calendar',params={'start':args.start,'end':args.end},headers=headers,timeout=30)
        except requests.RequestException:
            raise SystemExit('calendar transport failed; retained calendar unchanged') from None
        if r.status_code==200:data=r.json();break
        if r.status_code not in (401,403):raise SystemExit(f'calendar HTTP {r.status_code}; retained calendar unchanged')
    if not isinstance(data,list) or not data:raise SystemExit('calendar access unavailable')
    doc={'coverage_start':args.start,'coverage_end':args.end,
         'captured_at':dt.datetime.now(dt.timezone.utc).isoformat(),'source':host+'/v2/calendar',
         'sessions':[{k:row[k] for k in ('date','open','close')} for row in data]}
    SessionCalendar(doc)
    atomic_write_json(args.output,doc)
    print(json.dumps({'sessions':len(data),'coverage_start':args.start,'coverage_end':args.end}))
if __name__=='__main__':main()
