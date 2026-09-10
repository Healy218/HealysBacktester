"""Synthetic full-session integration: real stores, loader, strategy and ledger.

Only external market-data/Telegram transports are replaced. Never uses live state.
"""
import json

import pandas as pd
import pytest

from nn_meta.live import taken_monitor as mon, run_live
from nn_meta.live.scanner import closed_bars
from nn_meta.live.alert_batches import Batches
from nn_meta.live.alert_replies import poll_replies
from nn_meta.live.feeds.barstore import BarStore, aggregate_15m
from nn_meta.live.taken_trades import handle, trade_id
from nn_meta.live.trade_accounting import summary, reconcile
from tests.test_alert_batches import API
from tests.test_taken_trades import message, queued, callback, rows
from tests.test_taken_monitor import bars, NOW


def test_full_session_stream_rest_restart_partial_sales_and_final_bar(tmp_path, monkeypatch):
    from nn_meta import config, proposals
    from nn_meta.live.feeds import stock_stream
    calendar = tmp_path/'session-calendar.json'
    calendar.write_text(json.dumps(dict(coverage_start='2026-09-09', coverage_end='2026-09-09',
                                       sessions=[dict(date='2026-09-09',open='09:30',close='16:00')])))
    monkeypatch.setenv('NN_META_SESSION_CALENDAR', str(calendar))
    # A real MA crossover, then an exit only on the final session bar.
    prices = [100, 99, 98, 99, 100] + [101 + i*.1 for i in range(20)] + [99]
    minute_index = pd.date_range('2026-09-09 13:30', periods=390, freq='min')
    raw = [dict(timestamp=ts, open=prices[i//15], high=prices[i//15]+.01,
                low=prices[i//15]-.01, close=prices[i//15], volume=10.)
           for i, ts in enumerate(minute_index)]
    store = BarStore(tmp_path/'feed')
    monkeypatch.setattr('nn_meta.live.feeds.barstore.BarStore', lambda: BarStoreOriginal(tmp_path/'feed'))
    heartbeat = tmp_path/'heartbeat.json'
    monkeypatch.setattr(stock_stream, 'HEARTBEAT', heartbeat)
    params = dict(fast_window=2, slow_window=3)
    full = pd.DataFrame({k.title():[b[k] for b in raw] for k in ('open','high','low','close','volume')}, index=minute_index)
    # One quiet minute is absent from both the symbol's stream and REST history.
    full = full.drop(minute_index[157])
    twin = aggregate_15m(full, now=pd.Timestamp('2026-09-09 20:00Z'), alive_minutes=set(minute_index))
    entries = proposals.single_signals('ma', twin, params)[0]
    entry = entries.index[entries.iloc[:,0]][0]
    assert entry == pd.Timestamp('2026-09-09 14:30')
    q = Batches(tmp_path/'queue.sqlite3')
    ctx = dict(symbol='MARA', strategy='ma', params=params, direction=0,
               spot=float(twin.loc[entry,'Close']), entry_ts=str(entry), sim_start=str(twin.index[0]),
               sim_config=dict(config.SIM_CONFIG, TREND_FILTER_WINDOW=0, USE_STOP_LOSS=False))
    q.enqueue(dict(title='[v31] MARA BUY CALL', message='synthetic replay', probability=.6,
                   expert='v31', alert_cycle=900, contract='MARA351009C00011500', trade_context=ctx), 'session', now=1000)
    ident = trade_id('session')
    assert 'Taken' in handle(q, message(f'/taken {ident} 3 @ 1.00', 1), '123')
    handle(q, message(f'/entryfees {ident} .09', 2), '123')
    rest_calls = []
    current = None
    def market_loader(symbol, start, end, interval, **kw):
        if not kw.get('force_download'):
            return twin.iloc[:0]
        rest_calls.append(current)
        # REST may return the forming bar; consumers must trim it.
        return twin.loc[:pd.Timestamp(current).tz_localize(None)]
    monkeypatch.setattr(run_live.vbt_data_loader, 'load_price_data_smart', market_loader)
    api = API()
    for bucket in range(26):
        current = pd.Timestamp('2026-09-09 13:45Z') + pd.Timedelta(minutes=15*bucket)
        chunk = raw[bucket*15:(bucket+1)*15]
        # A disconnected bucket loses both target and reference bars.
        if bucket != 12:
            store.append_1m('SPY', chunk)
            store.append_1m('MARA', [b for b in chunk if b['timestamp'] != minute_index[157]])
        heartbeat.write_text(json.dumps(dict(ts=current.isoformat(), state='reconnecting' if bucket==12 else 'streaming')))
        if bucket == 13:
            # Restart + idempotent replay of the missed range repairs coverage.
            store = BarStoreOriginal(tmp_path/'feed')
            store.append_1m('SPY', raw[180:195])
            store.append_1m('MARA', raw[180:195])
            store.append_1m('MARA', raw[180:195])
            q = Batches(q.path)
        actual = run_live._bar_loader('MARA', now=current.to_pydatetime())
        expected = twin.loc[:current.tz_localize(None)-pd.Timedelta(minutes=15)]
        pd.testing.assert_frame_equal(closed_bars(actual,current), expected, check_names=False, check_freq=False)
        if bucket < 4:
            continue
        if bucket == 16:
            # Sale is committed even if confirmation transport fails. Restart retries once.
            class Fails(API):
                def call(self, method, **kw):
                    if method == 'sendMessage':
                        raise RuntimeError('transport unavailable')
                    return super().call(method, **kw)
            update = message(f'/sold {ident} 1 @ 1.20 fees .04 ref partial', 3)
            fail = Fails(); fail.updates = [update]
            with pytest.raises(RuntimeError):
                poll_replies(q, fail)
            q = Batches(q.path)
            api.updates = [update]
            poll_replies(q, api); poll_replies(q, api)
            with q.connect() as db:
                assert summary(db, rows(q)[0])['remaining'] == 2
        assert mon.scan(q,'v31',lambda c,n:run_live._bar_loader('MARA',now=n),current.to_pydatetime(),
                        quote_loader=lambda occ:dict(ts='2026-09-09T13:30:00+00:00', bid=2, ask=2.1)) == 1
        assert rows(q)[0]['status'] == ('exit_due' if bucket==25 else 'open')
    assert rest_calls == [pd.Timestamp('2026-09-09 16:45Z')]*2
    assert '2026-09-09 19:45:00' in rows(q)[0]['exit_notice']
    assert 'Estimated net P/L' not in rows(q)[0]['exit_notice']
    q = Batches(q.path)
    mon.send_pending(q,api); mon.send_pending(q,api)
    assert sum('SELL WATCH' in p.get('text','') for m,p in api.calls if m=='sendMessage') == 1
    handle(q,message(f'/sold {ident} 2 @ .80 fees .08 ref final',4),'123')
    assert rows(q)[0]['status']=='closed'
    assert mon.scan(q,'v31',lambda *a:pytest.fail('closed trade loaded'),current.to_pydatetime()) == 0
    record = dict(trade_id=ident, contract='MARA351009C00011500',entry_quantity=3,entry_price='1',entry_fees='.09',remaining_quantity=0,
                  sales=[dict(quantity=1,premium='1.2',fees='.04',broker_ref='partial'),dict(quantity=2,premium='.8',fees='.08',broker_ref='final')])
    with q.connect() as db:
        assert reconcile(db,[record])[0]['matched']
        assert str(summary(db,rows(q)[0])['net']) == '-20.21'


BarStoreOriginal = BarStore


def test_error_recovers_on_same_bar_and_can_alert_on_next_failure(tmp_path):
    q, ident = queued(tmp_path);handle(q,callback(ident),'123')
    evaluate = lambda c,b,n:(None,str(b.index[-1]))
    mon.scan(q,'v31',lambda c,n:bars(),NOW,evaluate)
    def disconnected(*a):
        raise OSError('disconnected')
    mon.scan(q,'v31',disconnected,NOW,evaluate)
    api = API();mon.send_pending(q,api)
    q = Batches(q.path)
    mon.scan(q,'v31',lambda c,n:bars(),NOW,evaluate)
    assert rows(q)[0]['monitor_error'] is None
    mon.scan(q,'v31',disconnected,NOW,evaluate);mon.send_pending(q,api)
    assert len(api.calls)==2


def test_quote_disconnect_does_not_suppress_verified_exit(tmp_path):
    q, ident=queued(tmp_path);handle(q,callback(ident),'123')
    def quote_down(*a):
        raise OSError('quote disconnect')
    evaluator=lambda c,b,n:(dict(reason='strategy exit',bar=str(b.index[-1]),stock_close=12),str(b.index[-1]))
    mon.scan(q,'v31',lambda c,n:bars(),NOW,evaluator,quote_down)
    assert rows(q)[0]['status']=='exit_due'
    assert 'Estimated net P/L' not in rows(q)[0]['exit_notice']


def test_stale_bars_and_forming_exit_rejected_then_backfill_recovers(tmp_path):
    q, ident=queued(tmp_path);handle(q,callback(ident),'123')
    called=[]
    evaluate=lambda c,b,n:(called.append(b.index[-1]) or None,str(b.index[-1]))
    mon.scan(q,'v31',lambda c,n:bars().iloc[:3],NOW,evaluate)
    assert not called and rows(q)[0]['monitor_error']
    recovered=bars()
    recovered.loc[pd.Timestamp('2026-09-09 17:00')]=[1,1,1,1,1]
    mon.scan(Batches(q.path),'v31',lambda c,n:recovered,NOW,evaluate)
    assert called==[pd.Timestamp('2026-09-09 16:30')]
    assert rows(q)[0]['monitor_error'] is None
