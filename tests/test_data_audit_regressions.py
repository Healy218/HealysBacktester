"""Adversarial regressions for the 2026-09-05 data audit."""
import json
from pathlib import Path
import pandas as pd
import pytest

from nn_meta import config, build_meta_dataset as builder
from nn_meta.feature_contract import CONTRACT_VERSION


def test_compaction_preserves_disjoint_dates_and_newest_corrections(tmp_path, monkeypatch):
    from nn_meta.download_universe import compact_bars_daily
    bars = tmp_path / 'bars'; bars.mkdir()
    pd.DataFrame({'ticker':['A','A'], 'date':pd.to_datetime(['2025-01-02','2025-01-03']),
                  'close':[1.,2.]}).to_parquet(bars/'bars_part_0.parquet')
    pd.DataFrame({'ticker':['A','A'], 'date':pd.to_datetime(['2025-01-03','2025-01-06']),
                  'close':[3.,4.]}).to_parquet(bars/'bars_part_1.parquet')
    monkeypatch.setattr(config,'BARS_DAILY_DIR',bars)
    compact_bars_daily()
    out=pd.concat([pd.read_parquet(p) for p in bars.glob('*.parquet')]).sort_values('date')
    assert out.close.tolist()==[1.,3.,4.]


def test_dte_sweep_order_does_not_change_fills():
    from tests.test_execution import SyntheticProvider,DAYS,_underlying
    from options.execution import Execution,execute_trade_returns
    provider=SyntheticProvider(DAYS,['2025-06-06','2025-06-13'])
    close,idx=_underlying()
    trades=[(idx[0],idx[51],0),(idx[130],idx[181],0)]
    def ex(): return Execution('SPY','15m','2025-06-30',provider,{})
    shared=ex()
    execute_trade_returns(shared,trades,close,idx,1)
    actual,_=execute_trade_returns(shared,trades,close,idx,10)
    expected,_=execute_trade_returns(ex(),trades,close,idx,10)
    assert actual==expected
    assert actual[0]['executed']


def test_intraday_missing_bars_do_not_fall_back_to_daily():
    from options.execution import Execution
    from datetime import date
    class Provider:
        calls=[]
        def get_contract_bars(self,occ,start,end,interval):
            self.calls.append(interval)
            return pd.DataFrame()
    p=Provider()
    assert Execution('SPY','15m','2025-01-03',p,{}).bars('A',date(2025,1,2),date(2025,1,3)).empty
    assert p.calls==['15m']


@pytest.mark.parametrize('pool',['v5','v6'])
def test_pit_default_for_both_pools(monkeypatch,pool):
    seen=[]
    monkeypatch.setattr(config,'POOL',pool)
    monkeypatch.setattr(config,'ensure_dirs',lambda:None)
    monkeypatch.setattr(builder,'assemble',lambda **kw:seen.append(kw))
    monkeypatch.setattr('sys.argv',['builder','--assemble'])
    builder.main()
    assert seen==[{'membership':True}]


def _reuse_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'ROOT',tmp_path)
    old=tmp_path/'artifacts_v5'; (old/'meta_rows').mkdir(parents=True)
    entry={'strategies':{'ma':{'params':{'fast_window':2,'slow_window':4},'dte':5}}}
    (old/'baseline_spec.json').write_text(json.dumps({'symbols':{'SPY':entry}}))
    rows=pd.DataFrame({'symbol':['SPY']*5,'strategy':['ma']*5,'trade_idx':[0]*5,
                       'entry_ts':pd.to_datetime(['2025-01-02']*5),
                       'dte':[1,5,10,30,45],'executed':[True]*5})
    rp=old/'meta_rows'/'SPY.parquet'; rows.to_parquet(rp)
    builder._write_provenance(rp,builder._provenance(entry,rows.dte.tolist()))
    return entry,rp,rows


def test_weekly_same_winner_requires_all_new_variants(tmp_path,monkeypatch):
    entry,_,_= _reuse_fixture(tmp_path,monkeypatch)
    assert builder._reusable_rows('SPY',entry,'v5',False) is not None
    assert builder._reusable_rows('SPY',entry,'v5',False,[1,2,4,5,7,10,30,45]) is None


def test_marks_required_and_unversioned_reuse_rejected(tmp_path,monkeypatch):
    entry,rp,_=_reuse_fixture(tmp_path,monkeypatch)
    assert builder._reusable_rows('SPY',entry,'v5',True) is None
    builder._provenance_path(rp).unlink()
    assert builder._reusable_rows('SPY',entry,'v5',False) is None


def test_cached_symbol_without_marks_rebuilds(tmp_path,monkeypatch):
    entry,_,rows=_reuse_fixture(tmp_path,monkeypatch)
    rd=tmp_path/'rows'; rd.mkdir(); rp=rd/'SPY.parquet'; rows.to_parquet(rp)
    builder._write_provenance(rp,builder._provenance(entry,config.DTE_GRID))
    calls=[]
    def build(*args,**kw):
        calls.append(True)
        return pd.DataFrame()
    monkeypatch.setattr(builder,'build_symbol_rows',build)
    builder.build_rows(['SPY'],{'symbols':{'SPY':entry}},None,rows_dir=rd,
                       marks=True,marks_dir=tmp_path/'marks')
    assert calls==[True]
    assert (tmp_path/'marks'/'SPY.parquet').exists()


def test_assembly_rejects_pre_causal_rows(tmp_path):
    pd.DataFrame({'symbol':['SPY']}).to_parquet(tmp_path/'SPY.parquet')
    with pytest.raises(SystemExit,match='stale or unversioned'):
        builder.assemble(rows_dir=tmp_path)


def test_pit_second_run_ignores_derived_view(tmp_path):
    from nn_meta.universe_pit import load_daily_rows,monthly_membership,write_membership_parquet
    pd.DataFrame({'root':['SPY']*3,'date':pd.to_datetime(['2025-01-29','2025-01-30','2025-01-31']),
                  'opt_dollar_vol':[100]*3}).to_parquet(tmp_path/'2025-01.parquet')
    def run(): return monthly_membership(load_daily_rows(tmp_path),window_days=2,min_active_days=1)
    first=run(); write_membership_parquet(first,tmp_path)
    pd.testing.assert_frame_equal(run(),first)


def test_spx_wing_prefix_invariance():
    from nn_meta.spx0.contracts import pick_wing,parse_occ
    at=pd.Timestamp('2025-06-10 14:00')
    def row(k,t): return {'occ':f'SPXW250610P{int(k*1000):08d}','index':'SPX',
                          'right':'P','strike':k,'timestamp':t}
    past=pd.DataFrame([row(k,at-pd.Timedelta(minutes=1)) for k in [5970,5980,5990,6000,6010]])
    future=pd.DataFrame([row(k,at+pd.Timedelta(hours=1)) for k in [5975,5985,5995,6005]])
    def pick(df): return pick_wing(df,short_leg=parse_occ('SPXW250610P06000000'),
                                   mapped_spot=6000,wing_strikes=2,at=at)
    assert pick(past)==pick(pd.concat([past,future],ignore_index=True))
    assert pick(past).strike==5980


def test_stop_waits_until_trigger_close_is_known():
    from nn_meta.spx0.build_dataset import _stop_target_ts
    from nn_meta.spx0.fills import exit_fill,DepthPolicy
    from nn_meta.spx0.config import TradeVariant
    b=pd.DataFrame({'timestamp':pd.to_datetime(['2025-06-10 14:01','2025-06-10 14:02','2025-06-10 14:03']),
                    'Close':[1,.4,.2],'Low':[.8,.3,.1],'High':[1.1,.7,.3],'Volume':[10]*3})
    st=_stop_target_ts(b,b.timestamp[0],1.,TradeVariant(0,False,.5))
    assert st==pd.Timestamp('2025-06-10 14:03')
    ts,price,_,_=exit_fill(b,st,DepthPolicy(),session_floor_ts=b.timestamp.iloc[-1],intrinsic_at_floor=0)
    assert ts==st + pd.Timedelta(minutes=1) and price==.1


def test_missing_terminal_marks_are_incomplete():
    rows=pd.DataFrame({'symbol':['SPY'],'strategy':['ma'],'trade_idx':[0],'dte':[5],
                       'entry_ts':pd.to_datetime(['2025-01-02 14:30']), 'executed':[True],
                       'fill_entry_ts':pd.to_datetime(['2025-01-02 14:45']),
                       'fill_exit_ts':pd.to_datetime(['2025-01-02 15:30'])})
    from nn_meta.mark_stream import stable_trade_id
    marks=pd.DataFrame({'trade_id':[stable_trade_id(rows).iloc[0]],
                        'mark_ts':rows.fill_entry_ts,'gross_return':[0.],
                        'cost_entries':[1], 'cost_exits':[0]})
    assert not builder._marks_cover(rows,marks)


def test_empty_partial_resumes_only_with_matching_provenance(tmp_path,monkeypatch):
    bars=pd.DataFrame({'Close':[100.], 'Open':[100.], 'High':[100.], 'Low':[100.], 'Volume':[1.]},
                       index=pd.to_datetime(['2025-01-02 14:30']))
    monkeypatch.setattr(builder,'load_underlying_15m',lambda sym:bars)
    calls=[]
    monkeypatch.setattr(builder,'propose_trades',lambda *args:calls.append(True) or [])
    entry={'strategies':{'ma':{'params':{'fast_window':2,'slow_window':4},'dte':5}}}
    def run(e): return builder.build_symbol_rows('SPY',e,None,marks_sink=[],partial_dir=tmp_path)
    run(entry); run(entry)
    assert len(calls)==1
    assert (tmp_path/'SPY.ma.marks.parquet').exists()
    changed={'strategies':{'ma':{'params':{'fast_window':3,'slow_window':4},'dte':5}}}
    run(changed)
    assert len(calls)==2


@pytest.mark.parametrize('target', [0., 0.02])
def test_target_moneyness_is_independent_of_selected_strike(monkeypatch, target):
    import numpy as np
    monkeypatch.setitem(config.EXEC_CONFIG, 'MONEYNESS', target)
    from tests.test_execution import SyntheticProvider,DAYS,_underlying
    close,idx=_underlying()
    bars=pd.DataFrame({c:102. for c in ['Open','High','Low','Close']},index=idx)
    bars['Volume']=100.
    from nn_meta import price_basis
    raw_close = bars.Close.copy()
    raw_close.attrs = dict(price_basis.raw_spot_provenance('15m', provider='test', feed='synthetic'), symbol='SPY')
    monkeypatch.setattr(price_basis, 'load_raw_close_15m', lambda symbol, *, index: raw_close)
    monkeypatch.setattr(builder,'load_underlying_15m',lambda sym:bars)
    monkeypatch.setattr(builder,'propose_trades',lambda *args:[(idx[0],idx[51],0)])
    entry={'strategies':{'ma':{'params':{'fast_window':2,'slow_window':4},'dte':5}}}
    out=builder.build_symbol_rows('SPY',entry,SyntheticProvider(DAYS,['2025-06-13'],strike=100.),dte_grid=[5])
    assert out.strike.iloc[0]==100.
    assert out.moneyness.iloc[0]==pytest.approx(np.log1p(target))


def test_assembly_rejects_missing_symbol_marks(tmp_path, monkeypatch):
    rd=tmp_path/'rows'; rd.mkdir()
    md=tmp_path/'marks'; md.mkdir()
    rows=pd.DataFrame({'symbol':['SPY'],'strategy':['ma'],'trade_idx':[0],'dte':[5],
                       'entry_ts':pd.to_datetime(['2025-01-02']), 'executed':[True]})
    rp=rd/'SPY.parquet'; rows.to_parquet(rp)
    builder._write_provenance(rp,builder._provenance({},config.DTE_GRID))
    pd.DataFrame().to_parquet(md/'OTHER.parquet')
    with pytest.raises(SystemExit,match='incomplete marks'):
        builder.assemble(rows_dir=rd,marks_dir=md)


def test_spx_package_cost_counters_are_accepted_by_ledger(tmp_path, monkeypatch):
    from tests.test_spx0_round3 import DAY, T_IN, T_OUT, VERT_1, _proxy, _options, _prepared
    from nn_meta.spx0 import build_dataset as spx
    from nn_meta.mark_stream import execution_frames, load_mark_stream
    from nn_meta.v4_accounting import validate_marks
    monkeypatch.setattr(spx.sc,'INDEXES',('SPX',))
    monkeypatch.setattr(spx,'load_proxy_1m',lambda index:_proxy())
    monkeypatch.setattr(spx,'load_session_options',lambda day:_options())
    monkeypatch.setattr(spx,'prepare_signals',lambda bars,entry,active:_prepared(bars,T_IN,T_OUT))
    ds,marks=spx.build([DAY],tmp_path,spec={'symbols':{'SPY':{'strategies':{}}}},variants=VERT_1)
    restored=pd.read_parquet(tmp_path/'meta_dataset.parquet')
    assert restored.attrs['feature_contract_version']==CONTRACT_VERSION
    assert ds.n_fills.tolist()==[1] and ds.n_legs.tolist()==[2]
    trades,stream=execution_frames(ds,load_mark_stream(tmp_path/'meta_dataset.marks.parquet'))
    assert not validate_marks(stream,trades).empty


def test_assembly_rejects_current_version_rows_from_replaced_spec(tmp_path, monkeypatch):
    old={'strategies':{'ma':{'params':{'fast_window':2,'slow_window':4},'dte':5}}}
    new={'strategies':{'ma':{'params':{'fast_window':3,'slow_window':4},'dte':5}}}
    rp=tmp_path/'SPY.parquet'
    pd.DataFrame({'symbol':['SPY']}).to_parquet(rp)
    builder._write_provenance(rp,builder._provenance(old,config.DTE_GRID))
    monkeypatch.setattr(builder,'load_spec',lambda:{'symbols':{'SPY':new}})
    with pytest.raises(SystemExit,match='current frozen spec/grid'):
        builder.assemble(rows_dir=tmp_path,marks_dir=tmp_path/'absent')


@pytest.mark.parametrize('short,wing',[(False,0),(True,1),(True,0)])
@pytest.mark.parametrize('stressed',[False,True])
@pytest.mark.parametrize('settled',[False,True])
def test_spx_dollar_friction_matches_isolated_ledger(tmp_path,monkeypatch,short,wing,stressed,settled):
    from tests.test_spx0_round3 import DAY,T_IN,T_OUT,_proxy,_options,_prepared
    from nn_meta.spx0 import build_dataset as spx
    from nn_meta.spx0.costs import BASE,STRESSED
    from nn_meta.mark_stream import execution_frames
    from nn_meta.v4_accounting import mark_to_market_portfolio,BASE_COSTS,STRESSED_COSTS
    variant=spx.sc.TradeVariant(-1001 if wing else -200 if short else 0,short,
                               float('inf') if wing else 2. if short else 0. if settled else .5,
                               wing_strikes=wing)
    monkeypatch.setattr(spx.sc,'INDEXES',('SPX',))
    monkeypatch.setattr(spx,'load_proxy_1m',lambda index:_proxy())
    monkeypatch.setattr(spx,'load_session_options',lambda day:_options(minutes=40 if settled else 390))
    monkeypatch.setattr(spx,'prepare_signals',lambda bars,entry,active:_prepared(bars,T_IN,T_OUT))
    ds,marks=spx.build([DAY],tmp_path,spec={'symbols':{'SPY':{'strategies':{}}}},
                       variants=(variant,),costs=STRESSED if stressed else BASE)
    assert len(ds)==1 and ds.executed.all()
    if settled:
        assert ds.exit_reason.iloc[0]=='settled_intrinsic'
    trades,stream=execution_frames(ds,marks)
    metrics,curve=mark_to_market_portfolio(trades,stream,max_concurrent=1,position_fraction=1.,
                                          costs=STRESSED_COSTS if stressed else BASE_COSTS)
    assert metrics['total_return']==pytest.approx(ds.net_return.iloc[0])
    assert metrics['total_return'] < ds.gross_return.iloc[0]
    assert metrics['cost_model']=='index_dollar'
    assert curve.equity.iloc[0]<1. # entry friction booked immediately
