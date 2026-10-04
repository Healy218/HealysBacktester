import pandas as pd
from nn_meta.etfe.expansion import discovery_jobs,stock_jobs
from scripts.acquire_etfe_alpaca import bootstrap_jobs


def test_stock_expansion_has_no_overlap_or_gap_with_bootstrap():
    jobs=stock_jobs()
    assert len(jobs)==96
    for ticker in ('SPY','QQQ','VOO'):
        parts=sorted([j for j in jobs+bootstrap_jobs() if j['route']=='stock_bars' and j['params']['symbols']==ticker],
            key=lambda j:j['params']['start'])
        assert len(parts)==34
        for a,b in zip(parts[:-1],parts[1:]):
            assert pd.Timestamp(a['params']['end']).value+1==pd.Timestamp(b['params']['start']).value
        assert pd.Timestamp(parts[-1]['params']['end'])<pd.Timestamp('2026-10-03T04:00:00Z')


def test_discovery_includes_same_day_and_never_exceeds_five():
    dates=['2024-11-29','2024-12-02','2024-12-03','2024-12-04','2024-12-05',
           '2025-04-04','2025-04-07','2025-04-08','2025-04-09','2025-04-10']
    jobs=discovery_jobs([dict(date=d) for d in dates])
    assert len(jobs)==48
    expiries={j['params']['expiration_date'] for j in jobs}
    assert '2024-11-29' in expiries and '2025-04-04' in expiries
    assert '2024-12-05' not in expiries and '2025-04-10' not in expiries
