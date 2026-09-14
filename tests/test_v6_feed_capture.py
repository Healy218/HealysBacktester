import asyncio
import json
import msgpack
import time
import pytest
from types import SimpleNamespace
import pandas as pd
from nn_meta.live.feeds import option_stream as feed
from nn_meta.live.feeds.tick_journal import TickJournal


def test_raw_quotes_trades_and_running_subscription_refresh(tmp_path, monkeypatch):
    events, updates = [], []
    a, b = 'SPY260918C00650000', 'QQQ260918P00500000'
    class Stream:
        def __init__(self, *args, **kw):
            assert kw['raw_data'] is True
            self._running = False
            self._handlers = {'quotes': {}, 'trades': {}}
        def subscribe_quotes(self, handler, *symbols):
            assert not self._running
            self._handlers['quotes'].update(dict.fromkeys(symbols, handler))
        def subscribe_trades(self, handler, *symbols):
            assert not self._running
            self._handlers['trades'].update(dict.fromkeys(symbols, handler))
        async def _send_subscribe_msg(self):
            events.append({k: sorted(v) for k,v in self._handlers.items()})
        async def _send_unsubscribe_msg(self, channel, symbols):
            events.append((channel, symbols))
        async def _run_forever(self):
            self._running = True
            await self._handlers['quotes'][a]({'T':'q','S':a,'t':msgpack.Timestamp.from_unix_nano(time.time_ns()),
                'bp':1.,'ap':1.1,'bs':2,'as':3,'c':'R'})
            await self._handlers['trades'][a]({'T':'t','S':a,'t':msgpack.Timestamp.from_unix_nano(time.time_ns()),
                'p':1.1,'s':2,'c':'I'})
            (tmp_path/'watch.json').write_text(json.dumps({'contracts':[b]}))
            await asyncio.Event().wait()
        async def close(self):
            pass
    monkeypatch.setattr('alpaca.data.live.OptionDataStream', Stream)
    monkeypatch.setenv('ALPACA_API_KEY','test')
    monkeypatch.setenv('ALPACA_API_SECRET','test')
    monkeypatch.setattr(feed,'WATCH',tmp_path/'watch.json')
    monkeypatch.setattr(feed,'HEARTBEAT',tmp_path/'heartbeat.json')
    monkeypatch.setattr(feed,'FLUSH_S',.01)
    monkeypatch.setattr(feed,'REFRESH_S',.02)
    monkeypatch.setattr(feed,'LOOP_TICK_S',.005)
    monkeypatch.setattr(feed.shutil,'disk_usage',lambda p: SimpleNamespace(free=20*1024**3))
    (tmp_path/'watch.json').write_text(json.dumps({'contracts':[a]}))
    store=SimpleNamespace(update=lambda *a,**k: updates.append((a,k)),flush=lambda:None)
    with TickJournal(tmp_path/'ticks') as journal:
        asyncio.run(feed._serve(store,None,.08,journal))
        status=journal.status()
    assert len(updates)==1 and status['fsynced_rows']==2
    assert not status['coverage_complete']
    assert any(isinstance(e,dict) and b in e['trades'] for e in events)
    assert ('quotes',[a]) in events and ('trades',[a]) in events
    heartbeat=json.loads((tmp_path/'heartbeat.json').read_text())
    assert heartbeat['received_quotes']==1 and heartbeat['trades']==1
    assert heartbeat['journal_errors']==0 and heartbeat['tick_recording']
    assert heartbeat['state']=='stopped'


def test_main_keeps_reconnect_heartbeat_after_stream_error(tmp_path, monkeypatch):
    calls, heartbeats = [], []
    async def serve(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('test disconnect')
    monkeypatch.setattr(feed, '_serve', serve)
    monkeypatch.setattr(feed, '_stall_guard', lambda: None)
    monkeypatch.setattr(feed, 'write_heartbeat', lambda p, **k: heartbeats.append(k))
    monkeypatch.setattr(feed.time, 'sleep', lambda n: None)
    monkeypatch.setattr(feed, 'QuoteStore', lambda: None)
    monkeypatch.setenv('NN_META_OPTION_RECORD_TICKS', '0')
    monkeypatch.setattr('sys.argv', ['option_stream', '--run-seconds', '1'])
    feed.main()
    assert len(calls) == 2
    assert heartbeats[0]['state'] == 'reconnecting'
    assert heartbeats[0]['recording_suspended']


def test_additional_frozen_universe_and_missing_spec_fail_closed(tmp_path, monkeypatch):
    from nn_meta.live.feeds import stock_stream
    monkeypatch.setattr(stock_stream.config, 'ROOT', tmp_path)
    monkeypatch.setattr(stock_stream.config, 'CAMPAIGN', '', raising=False)
    spec = tmp_path / 'spec.json'
    spec.write_text(json.dumps({'symbols': {'SPY': {}, 'NEW': {}}}))
    monkeypatch.setenv('NN_META_ADDITIONAL_STOCK_SPECS', str(spec))
    assert stock_stream.union_universe() == ['NEW', 'SPY']
    spec.unlink()
    with pytest.raises(FileNotFoundError):
        stock_stream.union_universe()


def test_capture_configuration_preserves_other_environment_values():
    from scripts.configure_v6_capture import updated_env
    source = 'ALPACA_API_KEY="placeholder"\nNN_META_ALERT_TOP_N=5\n'
    values = {'NN_META_OPTION_RECORD_TICKS': '1'}
    result = updated_env(source, values)
    assert result.startswith(source)
    assert updated_env(result, values) == result
    with pytest.raises(ValueError, match='duplicate'):
        updated_env(result + 'NN_META_OPTION_RECORD_TICKS=0\n', values)
