"""Check existing V6 paper option stops each minute without rebuilding features."""
from pathlib import Path
import argparse
from dataclasses import asdict
import fcntl
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def run(args):
    from dotenv import load_dotenv
    import pandas as pd
    from nn_meta.live.v6_market import MassiveMarket, read, save, utcnow
    from nn_meta.live.v6_release import sha
    from nn_meta.live.v6_portfolio import ForwardPortfolio
    from nn_meta.live.v6_option_risk import monitor_option_position
    from nn_meta.live.v6_option_sessions import LATE_CLOSE, expiry_cutoff
    from nn_meta.session_calendar import SessionCalendar
    from options.data.provider import parse_occ_symbol
    from options.paper_pricing import MIDPOINT_POLICY
    from options.paper_risk import V6_OPTION_RISK
    state=Path(args.state)
    with (state/'.option-risk.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        activation=read(args.activation)
        if (activation.get('status')!='passed' or activation.get('pricing_policy')!=MIDPOINT_POLICY
                or activation.get('option_risk_policy')!=asdict(V6_OPTION_RISK)):
            raise ValueError('Option risk runtime has not passed activation validation')
        for name,digest in activation['runtime_sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Option risk runtime changed since activation')
        index=read(state/'data-index.json')
        data=Path(index['path'])
        if (index['release_sha256']!=activation['release_sha256']
                or sha(data/'manifest.json')!=index['sha256']):
            raise ValueError('Option risk calendar belongs to a changed data manifest')
        manifest=read(data/'manifest.json')
        if sha(data/'calendar.json')!=manifest['files']['calendar.json']:
            raise ValueError('Option risk calendar changed')
        calendar=SessionCalendar(read(data/'calendar.json'))
        with sqlite3.connect(f'file:{state}/portfolio.sqlite3?mode=ro',uri=True) as db:
            scope=json.loads(db.execute("SELECT value FROM metadata WHERE key='scope'").fetchone()[0])
        if scope['release_sha256']!=activation['release_sha256']:
            raise ValueError('Option risk portfolio belongs to another model release')
        book=ForwardPortfolio(state/'portfolio.sqlite3',scope=scope)
        load_dotenv(args.env)
        now=utcnow(); day=now.tz_convert('America/New_York').date().isoformat()
        results=[]; errors=[]; market=None
        for position in book.open_positions():
            try:
                bounds=calendar.bounds(day)
                if bounds is None:continue
                opening,closing=(p.tz_localize('UTC') for p in bounds)
                root=parse_occ_symbol(position['contract'])[0]
                if root in LATE_CLOSE:closing+=pd.Timedelta(minutes=15)
                if not opening<=now<closing:continue
                if market is None:market=MassiveMarket(state/'market')
                result=monitor_option_position(book,position,market,clock=utcnow,alerts=args.enable_alerts,
                    calendar=calendar,underlying_mark=market.underlying_mark)
                if result['status']=='otm_expiry':
                    book.trigger(position['key'],kind='roll',reason='OTM option expiry cutoff',
                        at=expiry_cutoff(position['contract'],calendar),alerts=args.enable_alerts,
                        expected_leg=position)
                    book.settle(position['key'],quote_loader=market.execution_quote,clock=utcnow,alerts=args.enable_alerts)
                results.append(result)
            except Exception as exc:
                errors.append(dict(key=position['key'],error=f'{type(exc).__name__}: {exc}'))
        if args.enable_alerts:book.export(state/'alert-spool')
        report=dict(schema='v6-option-risk-status-v1',checked_at=utcnow().isoformat(),
            status='failed' if errors else 'complete',results=results,errors=errors,
            option_risk_policy=asdict(V6_OPTION_RISK),pricing_policy=MIDPOINT_POLICY,
            broker_orders=False,portfolio=book.summary())
        save(state/'option-risk-status.json',report)
        if errors:raise RuntimeError('One or more option risk checks failed; positions retained for retry')
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('state','activation','env'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--enable-alerts',action='store_true')
    print(json.dumps(run(parser.parse_args()),allow_nan=False))


if __name__=='__main__':main()
