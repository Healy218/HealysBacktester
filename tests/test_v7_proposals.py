import pandas as pd

import nn_meta.v7.proposals as module
from nn_meta.multitimeframe_catalog import registered_catalog


def test_underlying_timeline_keeps_open_proposals_censored_and_decisions_at_close(monkeypatch):
    index = pd.date_range('2022-03-07T14:30Z', periods=6, freq='5min')
    bars = pd.DataFrame({'Open': 100., 'High': 100.1, 'Low': 99.9, 'Close': 100., 'Volume': 100.}, index=index)
    variant = next(r for r in registered_catalog(['SPY'])['records'] if r['signal_minutes'] == 5)
    def signals(*args, **kwargs):
        channels = [pd.DataFrame(False, index=index, columns=[variant['variant_id']]) for _ in range(4)]
        channels[0].iloc[0, 0] = True
        channels[1].iloc[2, 0] = True
        channels[0].iloc[4, 0] = True
        yield [variant], channels
    monkeypatch.setattr(module, 'signal_batches', signals)
    records, proposals = next(module.proposal_batches('SPY', bars, [variant], start='2022-03-07', end='2022-03-07'))
    assert len(records) == 1 and len(proposals) == 2
    assert proposals[0]['decision_at'] == index[0] + pd.Timedelta(minutes=5)
    assert proposals[0]['exit_decision_at'] == index[2] + pd.Timedelta(minutes=5)
    assert proposals[0]['proposal_closed']
    assert not proposals[1]['proposal_closed'] and pd.isna(proposals[1]['exit_decision_at'])
    assert proposals[1]['censored_at'] == index[-1] + pd.Timedelta(minutes=5)
