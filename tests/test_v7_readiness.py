import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from nn_meta.v7.context import chart_context


def sample(minutes=1):
    dates=['2022-03-07','2022-03-08']
    calendar={'timezone':'America/New_York','coverage_start':dates[0], 'coverage_end':dates[-1],
              'sessions':[{'date':d,'open':'09:30','close':'16:00'} for d in dates]}
    idx=pd.date_range('2022-03-07 14:30Z',periods=390,freq='min').append(pd.date_range('2022-03-08 14:30Z',periods=390,freq='min'))
    c=100+np.sin(np.arange(len(idx))/9)*3+np.arange(len(idx))*.01
    raw=pd.DataFrame({'Open':c-.1,'High':c+.4,'Low':c-.5,'Close':c,'Volume':100.},index=idx)
    if minutes==1:return raw,raw,calendar
    bars=raw.resample(f'{minutes}min',origin='start').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    return bars,raw,calendar


@pytest.mark.parametrize('minutes',[1,5,15,30])
def test_context_prefix_and_exact_minute_opening_range(minutes):
    bars,raw,calendar=sample(minutes);ctx=chart_context(bars,raw,calendar,minutes)
    cut=len(bars)//2-2
    prefix=chart_context(bars.iloc[:cut],raw[raw.index<ctx['available_at'][cut-1]],calendar,minutes)
    pd.testing.assert_frame_equal(ctx['opening'].iloc[:cut],prefix['opening'])
    pd.testing.assert_frame_equal(ctx['vwap'].iloc[:cut],prefix['vwap'])
    row=ctx['opening'][ctx['opening'].or_done].iloc[0]
    assert row.or_high==raw.High.iloc[:15].max()
    assert row.or_low==raw.Low.iloc[:15].min()
    assert ctx['htf_period']==('240' if minutes==1 else '720' if minutes==5 else '2D')


def test_missing_opening_minute_is_not_filled():
    bars,raw,calendar=sample(30)
    ctx=chart_context(bars,raw.drop(raw.index[3]),calendar,30)
    assert not ctx['opening'].or_done.iloc[:13].any()
    assert ctx['opening'].or_done.iloc[13:].all()


@pytest.mark.parametrize('minutes',[1,5,15,30])
def test_all_source_features_and_registered_families(minutes):
    from nn_meta.v7.features import source_frames,project,technical
    from nn_meta.v7.signals import signal_batches
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.tradingview_features import FEATURE_NAMES
    bars,raw,calendar=sample(minutes);ctx=chart_context(bars,raw,calendar,minutes)
    sources=source_frames(bars,ctx)
    matrix=project(bars,sources,ctx)
    assert tuple(matrix.columns)==FEATURE_NAMES
    features=technical(bars,ctx)
    assert features.tod.iloc[0]==0
    records=registered_catalog(['SPY'])['records']; selected={}
    for row in records:
        if row['signal_minutes']==minutes:selected.setdefault(row['strategy'],row)
    batches=list(signal_batches(bars,list(selected.values()),sources=sources,batch_columns=3))
    assert sum(len(b[0]) for b in batches)==20
    for records,frames in batches:
        assert len(frames)==4
        assert all(f.index.equals(bars.index) for f in frames)


@pytest.mark.parametrize('minutes',[1,5,15,30])
def test_all_source_projections_preserve_history_prefix(minutes):
    from nn_meta.v7.features import source_frames,project
    bars,raw,calendar=sample(minutes)
    context=chart_context(bars,raw,calendar,minutes)
    full=project(bars,source_frames(bars,context),context)
    cut=len(bars)-max(5,len(bars)//4)
    prefix=bars.iloc[:cut]
    limited=raw[raw.index<prefix.index[-1]+pd.Timedelta(minutes=minutes)]
    ctx=chart_context(prefix,limited,calendar,minutes)
    part=project(prefix,source_frames(prefix,ctx),ctx)
    pd.testing.assert_frame_equal(full.iloc[:cut],part,check_exact=False,rtol=1e-10,atol=1e-10)


def test_legacy_full_parameter_batches_match_single_and_batch_width():
    from nn_meta.v7.signals import signal_batches
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.proposals import single_signals
    bars,_,_=sample(1)
    variants=[r for r in registered_catalog(['SPY'])['records'] if r['signal_minutes']==1
              and r['strategy'] in ('ma','rsi','macd','bbands','stoch','volume','elliott','supertrend','tv_rating','squeeze','keltner','bbw_squeeze')]
    # Full 2,804 legacy grid, not one representative per family.
    def collect(width):
        frames=[[] for _ in range(4)]
        for rows,batch in signal_batches(bars,variants,batch_columns=width):
            for values,frame in zip(frames,batch):values.append(frame)
        return [pd.concat(values,axis=1) for values in frames]
    a,b=collect(7),collect(31)
    for left,right in zip(a,b):pd.testing.assert_frame_equal(left,right)
    for variant in variants[::137]:
        expected=single_signals(variant['strategy'],bars,variant['params'])
        for actual,wanted in zip(a,expected):
            if wanted is not None:np.testing.assert_array_equal(actual[variant['variant_id']],wanted.iloc[:,0])
