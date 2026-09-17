from itertools import chain

import numpy as np
import pandas as pd
import pytest

from nn_meta.v7.proposal_store import build_features,build_proposals,StoredFeatures,StoredProposals
from nn_meta.v7.stored_rows import StoredFeatureRows
from nn_meta.v7.rows import DAILY,NUMERIC_FEATURES,schema
from nn_meta.v7.sectors import DatedSectors
from nn_meta.v7.storage import sha,identity
from tests.test_v7_proposal_store import chart_fixture


def test_full_stored_row_join_matches_causal_epochs_including_split_warmup_and_raw_spot(tmp_path):
    chart,variants=chart_fixture()
    source=tmp_path/'source';source.write_text('fixture raw and actions')
    build_features(tmp_path/'features',chart,variants,inputs={str(source):sha(source)},reserve_bytes=0)
    features=StoredFeatures(tmp_path/'features')
    build_proposals(tmp_path/'proposals',features,symbol='TEST',start='2022-03-15',end='2022-03-16',reserve_bytes=0)
    proposals=StoredProposals(tmp_path/'proposals',features=features)
    daily=pd.DataFrame([dict(**dict.fromkeys(DAILY,.2),source_date='2022-03-15',security_id='fixture')],
                       index=pd.DatetimeIndex(['2022-03-16T13:30Z']))
    sectors=DatedSectors(pd.DataFrame([dict(date=d,security_id='fixture',sector=sector,
        available_ns=pd.Timestamp(d+'T13:30Z').value,reference_date=prior,reason='fixture',
        source_receipt='fixture',source_sha256='fixture') for d,prior,sector in
        [('2022-03-15','2022-03-14','tech'),('2022-03-16','2022-03-15','fin')]]),security_id='fixture')
    context=tmp_path/'context';context.write_text('retained daily/sector inputs')
    join=StoredFeatureRows(proposals,daily,sectors=sectors,inputs={str(context):sha(context)})
    epochs=list(chart.epochs())
    direct=[epoch.rows(daily=daily,symbol='TEST',sectors=sectors) for epoch in epochs]
    by_variant={v['variant_id']:v for v in variants}
    # The first registered MA variant need not signal in this short fixture.
    # Separately probe its features at the first post-split observation, where
    # recomputing an average from only the saved epoch would lose its warmup.
    ma=next(v for v in variants if v['strategy']=='ma')
    decision=epochs[1].observed[0]+pd.Timedelta(minutes=1)
    key=dict(symbol='TEST',variant_id=ma['variant_id'],decision_ns=decision.value,right='C')
    probe=dict(**key,proposal_id=identity(dict(schema='v7-proposal-v1',**key)),
        security_id='fixture',decision_at=decision.isoformat(),strategy='ma',bars_since_previous_signal=0)
    checked=set();post_action_ma=False;warmup=False
    for proposal in chain([probe],proposals.rows(batch_size=7)):
        stamp=pd.Timestamp(proposal['decision_at'])
        ordinal=0 if stamp<epochs[1].start else 1
        # The explicit MA observation plus actual trades for the other
        # available family/epoch pairs exercise the same feature join.
        key=proposal['variant_id'],ordinal
        if key in checked:continue
        checked.add(key)
        bar=stamp-pd.Timedelta(minutes=1)
        right=proposal['right']
        ticks=dict(**dict.fromkeys(NUMERIC_FEATURES,.3),option_tick_status='covered',symbol='TEST',
            contract=f'TEST220318{right}00100000',window_start_ns=bar.value,
            window_end_ns=stamp.value,decision_close_ns=stamp.value,request_id='fixture')
        actual=join.row(proposal,ticks=ticks,target_dte=2)
        raw=chart.history.raw.loc[bar]
        expected=direct[ordinal].row(variant=by_variant[proposal['variant_id']],bar_at=bar,right=right,
            target_dte=2,bars_since_previous_signal=proposal['bars_since_previous_signal'],ticks=ticks,
            raw_spot=float(raw.Close),raw_spot_available_ns=stamp.value)
        pd.testing.assert_series_equal(actual,expected,check_exact=True)
        assert len(actual)==len(schema())==222
        assert actual.attrs['raw_spot']==float(raw.Close)
        assert actual.attrs['action_ids']==([] if ordinal==0 else ['split'])
        assert actual.sec_tech==float(ordinal==0) and actual.sec_fin==float(ordinal==1)
        if ordinal==0:
            warmup=True;assert actual[list(DAILY)].isna().all()
        elif proposal['strategy']=='ma':
            post_action_ma=True
            assert np.isfinite(actual.ma_gap)
            assert bar<epochs[1].observed[by_variant[proposal['variant_id']]['params']['slow_window']]
    assert len(checked)>10 and post_action_ma and warmup
    join.verify_bindings()
    context.write_text('changed context')
    with pytest.raises(ValueError,match='context inputs changed'):join.verify_bindings()
