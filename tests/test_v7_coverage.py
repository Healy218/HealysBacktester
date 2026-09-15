import json
import pandas as pd
import pytest

from nn_meta.v7.coverage import receipt_frame
from nn_meta.v7.storage import sha


def stock_receipt(root, stamps):
    directory = root / 'stock_1m/raw/SPY/2022'
    directory.mkdir(parents=True)
    frame = pd.DataFrame({'timestamp': stamps, 'Open': 100., 'High': 101.,
                          'Low': 99., 'Close': 100., 'Volume': 10.})
    frame.to_parquet(directory / 'bars.parquet')
    doc = {'task': {'key': 'stock_1m/raw/SPY/2022'}, 'complete': True, 'rows': len(frame),
           'files': {'bars.parquet': sha(directory / 'bars.parquet')}}
    path = directory / 'complete.json'
    path.write_text(json.dumps(doc))
    return path, doc


def test_receipt_cannot_redirect_verification_to_another_task(tmp_path):
    path, doc = stock_receipt(tmp_path, pd.date_range('2022-03-07T14:30Z', periods=2, freq='min'))
    assert len(receipt_frame(tmp_path, path)[1]) == 2
    doc['task']['key'] = 'missing'
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='verified task path'):
        receipt_frame(tmp_path, path)


@pytest.mark.parametrize('stamps', [pd.DatetimeIndex(['2022-03-07 14:30', '2022-03-07 14:31']),
    pd.DatetimeIndex(['2022-03-07T14:30Z', '2022-03-07T14:30Z']),
    pd.DatetimeIndex(['2022-03-07T14:30:00.000000001Z', '2022-03-07T14:31Z'])])
def test_stock_time_quality_rejects_naive_duplicate_and_subminute_rows(tmp_path, stamps):
    path, _ = stock_receipt(tmp_path, stamps)
    with pytest.raises(ValueError):
        receipt_frame(tmp_path, path)
