"""Isolated end-of-day preview and confirmed-signal recap; no model admission.

Workers write provisional observations separately from live alert state. A panel
sender reads those observations at close minus five minutes. Missing/late worker
results remain visible; they never delay the recap or become normal alerts.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import pandas as pd
from nn_meta import config
from dotenv import load_dotenv
load_dotenv(config.ROOT.parent / ".env")
from nn_meta.live.state import atomic_write_json, Outbox, state_lock
from nn_meta.live.feeds.barstore import COLS
from nn_meta.session_calendar import configured_calendar, utc_naive

EXPERTS=('v3','v31','v4','v5')
ROOT=config.ROOT/'live/eod_preview'


def provisional_bar(history, minutes, cutoff):
    """Add the incomplete final bucket using only fully elapsed minute bars.

    Callers must capture minutes at/before their declared observation time.
    Never pass the resulting frame through normal scan/alert state.
    """
    cutoff=utc_naive(cutoff)
    bucket=cutoff.floor('15min')
    elapsed=int((cutoff.floor('min')-bucket)/pd.Timedelta(minutes=1))
    if not 0 < elapsed < 15:
        raise ValueError('preview needs an unfinished 15-minute interval')
    expected=pd.date_range(bucket,periods=elapsed,freq='min')
    sample=minutes.loc[(minutes.index>=bucket)&(minutes.index+pd.Timedelta(minutes=1)<=cutoff),COLS]
    if not sample.index.equals(expected):
        raise ValueError('partial preview has missing or malformed minute observations')
    prior=history[history.index<bucket]
    if prior.empty or prior.index[-1]!=bucket-pd.Timedelta(minutes=15):
        raise ValueError('preview history is stale or missing the preceding closed bar')
    row=pd.DataFrame({'Open':[sample.Open.iloc[0]],'High':[sample.High.max()],
        'Low':[sample.Low.min()],'Close':[sample.Close.iloc[-1]],'Volume':[sample.Volume.sum()]},index=[bucket])
    return pd.concat([prior,row]),elapsed


def recap(state_dir, day):
    result=[]
    for expert in EXPERTS:
        path=state_dir/f'.{expert}_watchlist.json'
        if not path.exists():continue
        for record in json.loads(path.read_text()).values():
            if record.get('date')==day and record.get('alerted'):
                result.append(dict(record,expert=expert))
    return result


def render_panel(day, confirmed, reports, now):
    lines=[f'End-of-day panel — {day}', 'CONFIRMED CLOSED-BAR RECAP',
           'Earlier threshold-qualified signals; not fresh entry recommendations.']
    for expert in EXPERTS:
        rows=[r for r in confirmed if r['expert']==expert]
        lines.append(f'{expert}: {len(rows)} qualifying signals today')
        for r in sorted(rows,key=lambda r:r['entry_ts'],reverse=True)[:2]:
            side='PUT' if r['direction'] else 'CALL'
            lines.append(f"  {r['symbol']} {side}, {r['strategy']}, bar {r['entry_ts']} UTC")
    lines+=['EXPERIMENTAL PARTIAL-BAR VIEW',
            'Unfinished bar. Model scores are unvalidated for partial bars; signals can disappear.']
    for expert in EXPERTS:
        r=reports.get(expert)
        if not r or r.get('day')!=day:
            lines.append(f'{expert}: preview unavailable');continue
        observed=pd.Timestamp(r['observed_at'])
        age=(pd.Timestamp(now)-observed).total_seconds()
        if not 0<=age<=180:
            lines.append(f'{expert}: preview stale/unavailable');continue
        lines.append(f"{expert}: {r['scored_symbols']}/{r['total_symbols']} symbols checked, {r['errors']} errors; as of {observed.strftime('%H:%M:%S')} UTC")
        if not r['candidates']:
            lines.append('  No provisional qualifiers observed in checked symbols.')
        for row in sorted(r['candidates'],key=lambda x:x['decision'],reverse=True)[:2]:
            side='PUT' if row['direction'] else 'CALL'
            lines.append(f"  {row['symbol']} {side}, {row['strategy']}, {row['minutes']}/15 minutes; experimental {row['mode']} score {row['decision']:.3f}")
    lines.append('Normal alerts and their deduplication state are separate.')
    return '\n'.join(lines)


def collect(expert, symbols=None, cutoff=None):
    import numpy as np
    from nn_meta.baseline import load_spec
    from nn_meta.live.run_live import _bar_loader
    from nn_meta.live.feeds.barstore import BarStore
    from nn_meta.live.scanner import detect_fresh_signal
    from nn_meta.build_meta_dataset import load_surface_features
    from nn_meta.live import v4_scan
    if config.POOL != ('v31' if expert=='v4' else expert):
        raise ValueError('expert/pool mismatch')
    spec=load_spec(); names=symbols or list(spec['symbols'])
    if set(names)-set(spec['symbols']):raise ValueError('symbols outside frozen spec')
    if expert in ('v4','v5'):
        bundle=v4_scan.load_trusted_bundle(config.ROOT/f'model_final_{expert}')
        surface=load_surface_features()
    else:
        from nn_meta.live.scorer import NNScorer
        scorer=NNScorer(spec=spec)
    # Preload before the observation window, without modifying live scan state.
    histories={};errors=0
    for symbol in names:
        try:histories[symbol]=_bar_loader(symbol)
        except Exception:errors+=1
    if cutoff:
        while datetime.now(timezone.utc)<cutoff:
            time.sleep(max(0,min(1,(cutoff-datetime.now(timezone.utc)).total_seconds())))
    observed=datetime.now(timezone.utc)
    report={'expert':expert,'day':observed.date().isoformat(),'observed_at':observed.isoformat(),
            'total_symbols':len(names),'scored_symbols':0,'errors':errors,'candidates':[],
            'experimental':True,'complete':False}
    out=ROOT/report['day']/f'{expert}.json';store=BarStore()
    # Capture all available minute observations before model calculation. The
    # actual capture-finish timestamp is recorded, rather than backdating receipt.
    captured={}
    for symbol in histories:
        try:captured[symbol]=store.read_1m(symbol,days=[report['day']])
        except Exception:report['errors']+=1
    observed=datetime.now(timezone.utc);report['observed_at']=observed.isoformat()
    atomic_write_json(out,report)
    deadline=observed.replace(second=0,microsecond=0)+__import__("datetime").timedelta(minutes=1)
    for symbol,minutes in captured.items():
        if datetime.now(timezone.utc)>=deadline:
            report["timed_out"]=True
            break
        try:
            bars,n=provisional_bar(histories[symbol],minutes,observed)
            rows=[]
            if expert in ('v4','v5'):
                fresh=v4_scan.fresh_proposals(symbol,bars,spec['symbols'][symbol],list(config.PROPOSAL_STRATEGIES))
                if fresh:
                    batch=v4_scan.build_candidate_batch(v4_scan.candidate_frame(fresh),{symbol:bars},surface,spec)
                    batch=v4_scan.fill_context(batch,surface)
                    probability=bundle.score(batch)
                    decision=bundle.ev(batch) if bundle.mode==config.EV_MODE else probability
                    winners=v4_scan.best_per_signal(batch,probability,decision)
                    by_strategy={r['strategy']:r for r in fresh}
                    rows=[{'symbol':symbol,'strategy':r.strategy,'direction':by_strategy[r.strategy]['direction'],
                           'decision':float(r.decision),'mode':bundle.mode,'minutes':n}
                          for r in winners.itertuples() if np.isfinite(r.decision) and r.decision>=bundle.threshold]
            else:
                sig=detect_fresh_signal(symbol,bars,spec['symbols'][symbol])
                if sig is not None:
                    probability=scorer(sig,bars)
                    if probability is not None and np.isfinite(probability) and probability>=scorer.threshold:
                        rows=[{'symbol':symbol,'strategy':sig.strategy,'direction':sig.direction,
                               'decision':float(probability),'mode':'probability','minutes':n}]
            report['candidates'].extend(rows);report['scored_symbols']+=1
        except Exception:
            report['errors']+=1
        atomic_write_json(out,report)
    report['complete']=True;atomic_write_json(out,report)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--expert',choices=EXPERTS)
    ap.add_argument('--symbols')
    ap.add_argument('--capture-at',help='UTC timestamp; preload then wait until this time')
    ap.add_argument('--send',action='store_true')
    args=ap.parse_args()
    if args.expert:
        if args.send:ap.error('workers cannot send alerts')
        cutoff=datetime.fromisoformat(args.capture_at) if args.capture_at else None
        if cutoff and cutoff.tzinfo is None:ap.error('capture-at requires timezone')
        print(json.dumps(collect(args.expert,args.symbols.split(',') if args.symbols else None,cutoff)))
        return
    now=datetime.now(timezone.utc);day=now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat()
    reports={}
    for expert in EXPERTS:
        p=ROOT/day/f'{expert}.json'
        if p.exists():reports[expert]=json.loads(p.read_text())
    message=render_panel(day,recap(config.ROOT/'live',day),reports,now)
    print(message)
    if args.send:
        cal=configured_calendar()
        if cal is None:raise ValueError('panel sending requires captured exchange calendar')
        bounds=cal.bounds(day)
        if bounds is None or not bounds[1]-pd.Timedelta(minutes=5)<=utc_naive(now)<bounds[1]-pd.Timedelta(minutes=4):
            raise ValueError('send only within close-minus-five-minute delivery window')
        from nn_meta.live.notifier import get_notifier,ConsoleNotifier
        notifier=get_notifier()
        if isinstance(notifier,ConsoleNotifier):raise ValueError('panel delivery transport is not configured')
        with state_lock(ROOT/'.panel.lock'):
            outbox=Outbox(ROOT/'panel_outbox.json')
            outbox.enqueue({'title':f'[EOD panel] {day}','message':message},key=day)
            for entry in outbox.unacked():
                if entry.get('key')!=day:continue
                delivered=False
                for attempt in range(3):
                    if notifier.send(entry['payload']['message'],title=entry['payload']['title']):
                        delivered=True
                        break
                    time.sleep(attempt+1)
                if not delivered:
                    raise RuntimeError('panel delivery failed after three attempts; pending message retained')
                outbox.acknowledge(entry['id'])

if __name__=='__main__':main()
