"""Audit regressions using temporary state, archived fixtures and stub transports."""
from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd
import pytest

from fa import archive, config as fa_config
from fa.entities import resolve
from fa.ranker import load_mention_sources
from fa.scores import build_score_table
from fa.tracker import forward_returns
from fa.universe_loop import eligible_graduates, monthly_rank
from nn_meta.live.state import AlertState, Outbox, preview_state
from nn_meta.live.scanner import Scanner, is_rth, require_recent_bars
from nn_meta.live.watchlist import Watchlist


def test_stale_instances_merge_mutations_and_dedupe(tmp_path):
    a, b = AlertState(tmp_path/'state.json'), AlertState(tmp_path/'state.json')
    assert a.mark('a') and b.mark('b')
    assert not b.mark('a')
    latest = AlertState(tmp_path/'state.json')
    assert latest.seen('a') and latest.seen('b')
    first, second = Outbox(tmp_path/'out.json'), Outbox(tmp_path/'out.json')
    ident = first.enqueue({'message':'m'}, key='same')
    assert second.enqueue({'message':'m'}, key='same') == ident
    second.enqueue({'message':'other'}, key='other')
    first.acknowledge(ident)
    pending = Outbox(tmp_path/'out.json').unacked()
    assert len(pending) == 1 and pending[0]['key'] == 'other'


def test_preview_cannot_consume_pending_production_outbox(tmp_path):
    path = tmp_path/'.v4_outbox.json'
    ident = Outbox(path).enqueue({'message':'m'}, key='k')
    before = path.read_bytes()
    with preview_state(tmp_path) as copied:
        Outbox(copied/path.name).acknowledge(ident)
        AlertState(copied/'.v4_alert_state.json').mark('new')
    assert path.read_bytes() == before
    assert not (tmp_path/'.v4_alert_state.json').exists()


def test_legacy_failed_delivery_survives_restart(tmp_path, monkeypatch):
    from nn_meta.live import scanner as mod
    idx = pd.date_range('2026-09-04 10:00', periods=40, freq='15min')
    bars = pd.DataFrame({'Close':100.,'Open':100.,'High':101.,'Low':99.,'Volume':100},index=idx)
    monkeypatch.setattr(mod,'propose_trades',lambda *a,**k:[(idx[-1],None,0)])
    spec={'symbols':{'SPY':{'best_strategy':'rsi','strategies':{'rsi':{'params':{},'dte':5}}}}}
    def scanner():
        return Scanner(lambda _:bars,state_path=tmp_path/'state.json',spec=spec)
    class Transport:
        def __init__(self, ok): self.ok=ok; self.messages=[]
        def send(self,message,title): self.messages.append(message); return self.ok
    now=(idx[-1]+pd.Timedelta(minutes=15)).to_pydatetime()
    first=scanner(); assert len(first.scan_once(now=now))==1
    assert first.deliver_pending(Transport(False))==0
    restarted=scanner(); assert restarted.scan_once(now=now)==[]
    good=Transport(True); assert restarted.deliver_pending(good)==1
    assert restarted.deliver_pending(good)==0


def test_final_close_allowed_and_yesterdays_feed_refused():
    assert is_rth(datetime(2026,9,4,20,0,tzinfo=timezone.utc))
    bars=pd.DataFrame({'Close':[100]},index=[pd.Timestamp('2026-09-04 19:45')])
    assert require_recent_bars(bars,pd.Timestamp('2026-09-04 20:00')).equals(bars)
    with pytest.raises(ValueError,match='stale'):
        require_recent_bars(bars,pd.Timestamp('2026-09-07 13:30'))


def test_archive_cross_month_identity_and_failed_write(tmp_path, monkeypatch):
    monkeypatch.setattr(fa_config,'ARCHIVE',tmp_path)
    assert archive.append('reddit',pd.DataFrame([{'post_id':'p','ts_utc':'2026-01-31'}]),['post_id'])==1
    assert archive.append('reddit',pd.DataFrame([{'post_id':'p','ts_utc':'2026-02-01'}]),['post_id'])==0
    path=tmp_path/'reddit/2026-01.parquet'; before=path.read_bytes()
    def broken(self,path,*args,**kwargs):
        Path(path).write_bytes(b'partial')
        raise OSError('disk full')
    monkeypatch.setattr(pd.DataFrame,'to_parquet',broken)
    with pytest.raises(OSError):
        archive.append('reddit',pd.DataFrame([{'post_id':'new','ts_utc':'2026-01-31'}]),['post_id'])
    assert path.read_bytes()==before


def test_rank_sources_use_capture_cutoff_and_expand_all_news_tickers(tmp_path):
    folder=tmp_path/'news'; folder.mkdir()
    raw=pd.DataFrame([{'tickers':'AAPL,MSFT,NVDA','published':'2026-01-01',
                       'ts_utc':d,'provider':'test','url':str(i)}
                      for i,d in enumerate(pd.date_range('2026-01-01',periods=15))])
    raw.loc[14,'ts_utc']='2026-02-01'
    raw.to_parquet(folder/'2026-01.parquet')
    sources=load_mention_sources(tmp_path,as_of='2026-01-31')
    assert len(sources[0][1])==14
    assert sources[0][2]['ts_col']=='ts_utc'
    table=build_score_table(sources,{},valid_tickers=['AAPL','MSFT','NVDA'])
    assert set(table.ticker)=={'AAPL','MSFT','NVDA'}
    assert table.observed_at.max()==pd.Timestamp('2026-01-14')


def test_score_not_available_at_midnight_and_rank_window_excludes_old_corroboration():
    raw=pd.DataFrame([{'text':'$AAPL','ts_utc':d} for d in pd.date_range('2026-01-01 18:00',periods=15)])
    scores=build_score_table([('social',raw,{'text_col':'text','ts_col':'ts_utc'})],{})
    assert scores.observed_at.iloc[-1]==pd.Timestamp('2026-01-15 18:00')
    assert (scores[scores.observed_at <= pd.Timestamp('2026-01-15')].observed_at.dt.day < 15).all()
    scores=pd.DataFrame([('A','2026-01-01','social',10.,'s'),('A','2026-03-01','news',10.,'n')],columns=['ticker','observed_at','source_family','score','evidence_ref'])
    assert monthly_rank(scores,as_of='2026-03-02').empty


def test_tracker_accepts_utc_cli_timestamp_and_graduation_preserves_cohort():
    ranks=pd.DataFrame([{'ticker':'AAA','ranking_date':'2026-01-01'}, {'ticker':'AAA','ranking_date':'2026-08-01'}])
    prices=pd.Series([100.,110.],index=pd.to_datetime(['2026-01-01','2026-09-01'],utc=True))
    assert not forward_returns(ranks,lambda _:prices,as_of=pd.Timestamp('2026-09-01',tz='UTC'),baseline=['SPY']).empty
    returns=pd.DataFrame([{'ticker':'AAA','ranking_date':'2026-01-01','as_of':'2026-08-31','excess_return':-.2},{'ticker':'AAA','ranking_date':'2026-08-01','as_of':'2026-08-31','excess_return':.1}])
    assert eligible_graduates(ranks,returns,as_of='2026-09-01').empty


def test_trending_cashtags_must_be_in_universe():
    from fa.trending import _tickers
    assert 'LOL' not in _tickers('$LOL $SPY')
    assert 'SPY' in _tickers('$LOL $SPY')


def test_hit_rate_window_uses_resolution_date(tmp_path,monkeypatch):
    from nn_meta.live import watchlist as mod
    monkeypatch.setattr(mod,'_utcnow',lambda:datetime(2026,9,5,tzinfo=timezone.utc))
    path=tmp_path/'watch.json'
    path.write_text(json.dumps({'k':{'date':'2026-08-25','alerted':True,'outcome':{'resolved_ts':'2026-09-01T15:00:00','hit':True}}}))
    assert Watchlist(path).hit_stats(days=7)['resolved']==1


def test_concurrent_alert_mutations_preserve_every_key(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "alerts.json"
    def mark(i):
        return AlertState(path).mark(str(i))
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(mark, range(40)))
    state = AlertState(path)
    assert all(state.seen(str(i)) for i in range(40))


def test_candidate_moneyness_uses_configured_decision_target(monkeypatch):
    from nn_meta import config
    from nn_meta.live.v4_scan import candidate_frame
    monkeypatch.setattr(config, "EXEC_CONFIG", {**config.EXEC_CONFIG, "MONEYNESS":.02})
    frame = candidate_frame([{"symbol":"SPY", "strategy":"rsi", "direction":0,
                              "spot":100., "entry_ts":pd.Timestamp("2026-09-04 15:00"),
                              "bars_since_signal":2}])
    assert (frame.strike == 102.).all()
