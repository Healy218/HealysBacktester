import json
from pathlib import Path

import pandas as pd

from nn_meta.v7.scope import HISTORY_START, data_day_allowed
from nn_meta.v7.storage import receipt, sha, verify
from scripts.download_v7_data import quota_update
from scripts.rescope_v7_inputs import stock


def test_deleted_local_dates_are_removed_across_dst_and_source_is_preserved(tmp_path):
    root = tmp_path/'quota'; root.mkdir()
    source = root/'original/stock_1m/raw/SPY/2022'; source.mkdir(parents=True)
    times = pd.to_datetime(['2022-03-08T04:59Z', '2022-03-08T05:00Z',
                            '2022-03-15T03:59Z', '2022-03-15T04:00Z'])
    frame = pd.DataFrame({'timestamp':times,'Open':1.,'High':1.,'Low':1.,'Close':1.,'Volume':1.})
    frame.to_parquet(source/'bars.parquet',index=False)
    receipt(source, {'task':{'kind':'stock','key':'stock_1m/raw/SPY/2022',
                            'symbol':'SPY','adjustment':'raw'},'rows':4})
    original = sha(source/'bars.parquet')
    quota_update(root, initialize=250_000_000_000)
    result = stock((str(source/'complete.json'),str(root/'working'),str(root)))
    destination=root/'working/stock_1m/raw/SPY/2022'
    assert result['rows']==2 and result['removed_rows']==2
    assert pd.read_parquet(destination/'bars.parquet').timestamp.tolist()==[times[0],times[3]]
    assert sha(source/'bars.parquet')==original
    assert verify(destination)['task']['derived_scope']
    assert not json.loads((root/'quota.json').read_text())['reservations']
    assert stock((str(source/'complete.json'),str(root/'working'),str(root)))==result


def test_scope_removes_entire_requested_interval_but_retains_separate_warmup():
    assert HISTORY_START=='2022-03-15'
    assert data_day_allowed('2021-12-31') and data_day_allowed('2022-03-07')
    assert not any(data_day_allowed(f'2022-03-{day:02d}') for day in range(8,15))
    assert data_day_allowed('2022-03-15')
    assert not data_day_allowed('2026-09-15')


def test_current_evaluation_rejects_old_start_and_purges_prestart_labels():
    import pytest
    from types import SimpleNamespace
    from nn_meta.v7.evaluation import evaluation_plan, fold_masks
    from nn_meta.v7.scope import require_research_window
    policy=evaluation_plan()
    assert policy['history_start']=='2022-03-15'
    assert policy['expiry']['policy']=='funded-physical-exercise-observed-stock-liquidation-v1'
    with pytest.raises(ValueError,match='current V7'):
        require_research_window('2022-03-07','2022-03-18')
    rows=pd.DataFrame({'decision_at':pd.to_datetime(['2022-03-14T14:00Z','2022-03-15T14:00Z']),
                       'label_end':pd.to_datetime(['2022-03-14T15:00Z','2022-03-15T15:00Z']),
                       'label_complete':[True,True]})
    train,validation=fold_masks(rows,policy['folds'][0],SimpleNamespace(sessions={}),embargo_sessions=0)
    assert train.tolist()==[False,True] and not validation.any()
