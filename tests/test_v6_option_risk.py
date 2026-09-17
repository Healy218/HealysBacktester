from types import SimpleNamespace
import pandas as pd
import pytest

from tests import test_v6_forward_portfolio as fixtures
from nn_meta.live.v6_option_risk import monitor_option_position
from nn_meta.session_calendar import SessionCalendar


@pytest.fixture
def fixture():
    value=fixtures.ForwardPortfolioTests();value.setUp()
    yield value
    value.tearDown()


def test_unchanged_wide_spread_is_not_an_option_stop(fixture):
    f=fixture
    f.quote=lambda c,**k:dict(contract=c,bid=3.15,ask=3.9,bid_size=10,ask_size=10,
        sip_timestamp_ns=(f.now-pd.Timedelta(seconds=1)).value,received_at=f.now.isoformat())
    f.allocate();f.now+=pd.Timedelta(minutes=1)
    result=monitor_option_position(f.book,f.book.open_positions()[0],SimpleNamespace(execution_quote=f.quote),
                                   clock=lambda:f.now,alerts=False)
    assert result['status']=='holding' and result['assessment']['premium_return']==0.
    assert len(f.book.open_positions())==1


@pytest.mark.parametrize('right',['C','P'])
def test_calls_and_puts_exit_on_option_midpoint_loss_with_separate_costs(fixture,right):
    f=fixture;f.contract=f.contract.replace('C','P') if right=='P' else f.contract
    f.allocate();f.now+=pd.Timedelta(minutes=1)
    before=f.book.open_positions()[0]
    def loss(contract,**kwargs):return {**f.quote(contract,**kwargs),'bid':1.8,'ask':1.9}
    result=monitor_option_position(f.book,before,SimpleNamespace(execution_quote=loss),clock=lambda:f.now,alerts=False)
    assert result['status']=='exit_triggered' and not f.book.open_positions()
    assert result['assessment']['premium_return']==pytest.approx(1.85/2.05-1)
    expected=1+.1*(1.85*.9985/(2.05*1.0015)-1)
    assert f.book.summary()['equity']==pytest.approx(expected)


def test_stop_sells_using_its_valid_trigger_quote_without_second_request(fixture):
    f=fixture;f.allocate();f.now+=pd.Timedelta(minutes=1)
    calls=[]
    def quote(contract,**kwargs):
        calls.append(1)
        if len(calls)==2:raise ValueError('quote unavailable at exit')
        return {**f.quote(contract,**kwargs),'bid':1.8,'ask':1.9}
    monitor_option_position(f.book,f.book.open_positions()[0],SimpleNamespace(execution_quote=quote),
                            clock=lambda:f.now,alerts=False)
    assert len(calls)==1 and not f.book.open_positions()


@pytest.mark.parametrize('spot,status',[(761.,'exit_triggered'),(760.,'otm_expiry'),(759.,'otm_expiry')])
def test_itm_expiry_closes_at_confirmed_late_class_cutoff(fixture,spot,status):
    f=fixture;f.contract='SPY260914C00760000';f.allocate()
    calendar=SessionCalendar(dict(timezone='America/New_York',coverage_start='2026-09-14',coverage_end='2026-09-14',
        sessions=[dict(date='2026-09-14',open='09:30',close='16:00')]))
    market=SimpleNamespace(execution_quote=f.quote)
    f.now=pd.Timestamp('2026-09-14T19:59:59Z')
    assert monitor_option_position(f.book,f.book.open_positions()[0],market,clock=lambda:f.now,alerts=False,
        calendar=calendar,underlying_mark=lambda *a:pytest.fail('Before expiry cutoff'))['status']=='holding'
    f.now+=pd.Timedelta(seconds=1)
    result=monitor_option_position(f.book,f.book.open_positions()[0],market,clock=lambda:f.now,alerts=False,
        calendar=calendar,underlying_mark=lambda *a:dict(price=spot,sip_timestamp=f.now.value))
    assert result['status']==status
    assert bool(f.book.open_positions())==(status=='otm_expiry')


@pytest.mark.parametrize('direction',[0,1])
def test_held_strategy_exit_ignores_stock_loss_until_actual_exit_signal(direction):
    from nn_meta.live.v6_forward_inputs import held_signal_exit
    index=pd.date_range('2026-09-14T13:30',periods=6,freq='15min')
    price=pd.DataFrame({'Close':[100.,100.,90.,89.,88.,88.] if direction==0 else [100.,100.,110.,111.,112.,112.]},index=index)
    channels=[pd.DataFrame(False,index=index,columns=['one']) for _ in range(4)]
    position=dict(entry_ts=index[1].isoformat(),context={'direction':direction})
    assert held_signal_exit(price,channels,position,{'TREND_FILTER_WINDOW':50}) is None
    channels[3 if direction else 1].iloc[-1,0]=True
    assert held_signal_exit(price,channels,position,{'TREND_FILTER_WINDOW':50})==index[-1]


def test_held_opposite_entry_keeps_existing_trend_filter():
    from nn_meta.live.v6_forward_inputs import held_signal_exit
    index=pd.date_range('2026-09-14T13:30',periods=4,freq='15min')
    price=pd.DataFrame({'Close':[100.,101.,102.,90.]},index=index)
    channels=[pd.DataFrame(False,index=index,columns=['one']) for _ in range(4)]
    channels[2].iloc[2:,0]=True
    position=dict(entry_ts=index[1].isoformat(),context={'direction':0})
    assert held_signal_exit(price,channels,position,{'TREND_FILTER_WINDOW':50})==index[-1]


def test_quote_gap_keeps_position_open_and_recovered_quote_closes_at_midpoint(fixture):
    f=fixture;f.allocate();f.now+=pd.Timedelta(minutes=1)
    def unavailable(*a,**k):raise ValueError('No fresh observed quote')
    with pytest.raises(ValueError,match='fresh'):
        monitor_option_position(f.book,f.book.open_positions()[0],SimpleNamespace(execution_quote=unavailable),
                                clock=lambda:f.now,alerts=False)
    assert f.book.open_positions()[0]['state']=='open'
    f.now+=pd.Timedelta(minutes=1)
    loss=lambda c,**k:{**f.quote(c,**k),'bid':1.8,'ask':1.9}
    result=monitor_option_position(f.book,f.book.open_positions()[0],SimpleNamespace(execution_quote=loss),
                                  clock=lambda:f.now,alerts=False)
    assert result['status']=='exit_triggered' and not f.book.open_positions()


def test_expiry_stock_mark_uses_alpaca_sip_alias_and_retains_received_quote(tmp_path,monkeypatch):
    from nn_meta.live.v6_market import MassiveMarket
    from nn_meta import config
    from alpaca.data.enums import DataFeed
    import json
    now=pd.Timestamp('2026-09-14T19:45Z')
    calls=[]
    quote=SimpleNamespace(timestamp=now-pd.Timedelta(seconds=1),bid_price=99.,ask_price=101.)
    def latest(request):calls.append(request);return {'BRK.B':quote}
    monkeypatch.setitem(config.FETCH_ALIASES,'BRK','BRK.B')
    market=MassiveMarket(tmp_path,session=object(),tick_client=object(),clock=lambda:now)
    market._stock_client=SimpleNamespace(get_stock_latest_quote=latest)
    mark=market.underlying_mark('BRK',now)
    assert calls[0].symbol_or_symbols=='BRK.B' and calls[0].feed==DataFeed.SIP
    assert mark['price']==100. and mark['symbol']=='BRK' and mark['fetched_symbol']=='BRK.B'
    assert mark['sip_timestamp']==quote.timestamp.value and mark['provider']=='alpaca'
    assert json.loads(next((tmp_path/'underlying-quotes').glob('*.json')).read_text())==mark
    quote.timestamp=now-pd.Timedelta(seconds=31)
    with pytest.raises(ValueError,match='stale'):market.underlying_mark('BRK',now)
    quote.timestamp=now+pd.Timedelta(seconds=1)
    with pytest.raises(ValueError,match='future'):market.underlying_mark('BRK',now)


def test_old_leg_quote_cannot_trigger_exit_after_concurrent_roll(fixture):
    f=fixture;f.allocate();f.now+=pd.Timedelta(minutes=1)
    before=f.book.open_positions()[0]
    replacement=before['contract'].replace('261016','261023')
    assert replacement!=before['contract']
    def quote(c,**kwargs):
        f.book.trigger(before['key'],kind='roll',reason='concurrent worker',at=f.now-pd.Timedelta(seconds=2))
        f.book.settle(before['key'],quote_loader=f.quote,clock=lambda:f.now,replacement=replacement)
        return {**f.quote(c,**kwargs),'bid':1.8,'ask':1.9}
    result=monitor_option_position(f.book,before,SimpleNamespace(execution_quote=quote),clock=lambda:f.now,alerts=False)
    assert result['status']=='position_changed'
    current=f.book.open_positions()[0]
    assert current['state']=='open' and current['contract']==replacement and current['rolls']==1


@pytest.mark.parametrize('direction',[0,1])
def test_held_signal_conflicts_match_vectorbt_simulator(direction):
    import itertools
    import vectorbt as vbt
    from nn_meta.live.v6_forward_inputs import held_signal_exit
    index=pd.date_range('2026-09-14T13:30',periods=3,freq='15min')
    price=pd.DataFrame({'Close':[100.,100.,100.]},index=index)
    for bits in itertools.product((False,True),repeat=4):
        channels=[pd.DataFrame(False,index=index,columns=['one']) for _ in range(4)]
        channels[2 if direction else 0].iloc[0,0]=True
        for n,bit in enumerate(bits):channels[n].iloc[1,0]=bit
        portfolio=vbt.Portfolio.from_signals(price.Close,entries=channels[0],exits=channels[1],
            short_entries=channels[2],short_exits=channels[3],upon_long_conflict='entry',
            upon_short_conflict='entry',upon_dir_conflict='opposite',upon_opposite_entry='reverse')
        original=portfolio.trades.records.iloc[0]
        expected=index[1] if original.status==1 else None
        actual=held_signal_exit(price,channels,{'entry_ts':index[0].isoformat(),
            'context':{'direction':direction}}, {'TREND_FILTER_WINDOW':50})
        assert actual==expected,(direction,bits,actual,expected)


def test_old_otm_classification_cannot_roll_a_concurrently_replaced_contract(fixture,monkeypatch):
    from scripts import run_v6_forward
    from nn_meta.live import v6_option_risk
    f=fixture;f.contract='SPY260914C00760000';f.allocate()
    f.now=pd.Timestamp('2026-09-14T20:00:02Z')
    before=f.book.open_positions()[0]
    replacement='SPY261016C00760000'
    calendar=SessionCalendar(dict(timezone='America/New_York',coverage_start='2026-09-14',coverage_end='2026-09-14',
        sessions=[dict(date='2026-09-14',open='09:30',close='16:00')]))
    def classified(*a,**k):
        f.book.trigger(before['key'],kind='roll',reason='other worker',at=f.now-pd.Timedelta(seconds=2))
        f.book.settle(before['key'],quote_loader=f.quote,clock=lambda:f.now,replacement=replacement)
        return {'status':'otm_expiry'}
    monkeypatch.setattr(v6_option_risk,'monitor_option_position',classified)
    monkeypatch.setattr(run_v6_forward,'utcnow',lambda:f.now)
    market=SimpleNamespace(execution_quote=f.quote,underlying_mark=None)
    assert run_v6_forward.close_expiring_without_bars(f.book,calendar,market,f.now,alerts=False)==[]
    current=f.book.open_positions()[0]
    assert current['state']=='open' and current['contract']==replacement and current['rolls']==1
