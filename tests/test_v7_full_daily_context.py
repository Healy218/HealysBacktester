import numpy as np
import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.causal_daily import context, returns, timeline
from scripts.build_v7_full_daily_context import prepare_stock, align_surfaces, audit_values


def inputs():
    days = pd.bdate_range('2022-03-15', periods=91).strftime('%Y-%m-%d').tolist()
    calendar = SessionCalendar(dict(coverage_start=days[0], coverage_end=days[-1],
        sessions=[dict(date=d, open='09:30', close='16:00') for d in days]))
    clock = timeline(calendar, days[0], days[-2])
    history = pd.DataFrame(dict(source_date=days[:-1], security_id='s', stock_ticker='X',
        raw_close=100*np.exp(np.cumsum(.003*np.sin(np.arange(90)))), observed_minutes=390,
        available_ns=clock.stock_available_ns, identity_span='legal-s'))
    surface = history[['source_date','stock_ticker','raw_close','observed_minutes']].copy()
    surface['capture_complete'] = True
    surface['atm_iv_near'], surface['atm_iv_far'], surface['pc_ratio'] = .3, .4, 1.
    surface['available_ns'] = clock.available_ns
    surface['surface_status'] = 'observed_options'
    return history, surface.set_index(['source_date','stock_ticker']), calendar, clock


def test_excluded_interval_cannot_supply_returns_or_carry_surface():
    h,s,c,clock = inputs()
    routing = dict.fromkeys(h.source_date, 'X')
    del routing[h.source_date.iloc[12]]
    stock = prepare_stock(h,routing,clock)
    surf = align_surfaces(stock,s,clock,'s')
    daily = context(returns(stock,[],c,security_id='s',start=h.source_date.iloc[0],
                           end=h.source_date.iloc[-1],action_evidence_identity='evidence'),surf,is_market=True)
    assert stock.identity_span.iloc[11] != stock.identity_span.iloc[13]
    assert daily.simple_return.iloc[12:14].isna().all()
    assert daily.rvol_5.iloc[12:18].isna().all()
    assert np.isnan(daily.atm_iv_near.iloc[12])
    audit_values(daily,stock,surf,clock,None)
    changed = daily.copy()
    changed.iloc[20,changed.columns.get_loc('simple_return')] = .99
    with pytest.raises(AssertionError):
        audit_values(changed,stock,surf,clock,None)


def test_wrong_ticker_surface_spot_or_availability_blocks():
    h,s,c,clock = inputs()
    routing = dict.fromkeys(h.source_date,'X')
    wrong = dict(routing)
    wrong[h.source_date.iloc[3]]='FOREIGN'
    with pytest.raises(ValueError,match='routing'):
        prepare_stock(h,wrong,clock)
    stock = prepare_stock(h,routing,clock)
    s.iloc[5,s.columns.get_loc('raw_close')] *= 2
    with pytest.raises(ValueError,match='spot or clocks'):
        align_surfaces(stock,s,clock,'s')
