import pandas as pd
from v3._source_memo import memoized_source,reuse_identical_sources


def test_reuse_binds_all_history_parameters_and_returns_detached_nested_values():
    calls=[]
    @memoized_source
    def source(bars,scale=2):
        calls.append(True)
        return pd.DataFrame({'result':bars.x*scale,'nested':[[1] for _ in range(len(bars))]},index=bars.index)
    bars=pd.DataFrame({'x':[1.,2.]},index=pd.date_range('2026-09-14',periods=2,tz='UTC'))
    with reuse_identical_sources() as scope:
        a=source(bars);a.iloc[0,1].append(9)
        b=source(bars,scale=2)
        assert b.iloc[0,1]==[1] and scope['hits']==1
        changed=bars.copy();changed.iloc[0,0]=10
        assert source(changed).iloc[0,0]==20
        assert source(bars,3).iloc[0,0]==3
    source(bars)
    assert len(calls)==4


def test_a_new_symbol_scope_never_reuses_prior_scope_state():
    calls=[]
    @memoized_source
    def source(x): calls.append(x);return x
    for _ in range(2):
        with reuse_identical_sources(): source(1);source(1)
    assert calls==[1,1]


def test_proposals_and_features_reuse_all_eight_sources_without_value_changes():
    from tests.test_tradingview_proposals import data
    from nn_meta import tradingview_proposals as proposals
    from nn_meta.tradingview_features import tradingview_features
    bars,context=data(n=100)
    expected=tradingview_features(bars,**context)
    with reuse_identical_sources() as scope:
        for strategy in proposals.STRATEGIES:
            proposals.sweep_signals(strategy,bars,context=context)
        actual=tradingview_features(bars,**context)
        assert scope['hits']==8 and scope['misses']==8
    pd.testing.assert_frame_equal(actual.values,expected.values,check_exact=True)
