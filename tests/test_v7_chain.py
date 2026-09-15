from datetime import date
from pathlib import Path
import subprocess
import sys

import pandas as pd

from nn_meta.v7.chain import ObservedChain
from nn_meta.v7.storage import receipt, verify


def test_disk_partitioned_chain_preserves_first_observation_and_past_selection(tmp_path):
    audit = tmp_path / 'audit'
    for day, contracts in [('2022-03-04', ['O:SPY220309C00432000']),
                           ('2022-03-07', ['O:SPY220309C00432000', 'O:SPY220308C00432000',
                                          'O:SPY1220309C00432000'])]:
        directory = audit / 'options' / day
        directory.mkdir(parents=True)
        pd.DataFrame({'ticker': contracts, 'window_start': pd.Timestamp(day, tz='UTC').value}).to_parquet(
            directory / 'contracts.parquet')
        receipt(directory, {'identity': day})
    output = tmp_path / 'chain'
    subprocess.run([sys.executable, 'scripts/build_v7_chain.py', '--audit', str(audit),
                    '--output', str(output), '--partitions', '16'],
                   cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True)
    verify(output)
    frame = pd.read_parquet(output / 'contracts.parquet')
    assert len(frame) == 2
    assert not (output / 'grouping-parts').exists()
    chain = ObservedChain(output / 'contracts.parquet', 'SPY')
    # UTC-midnight aggregate timestamp belongs to the prior NY date. Both
    # inputs deliberately exercise the timezone convention, not retrieval time.
    assert chain.select(date(2022, 3, 6), 432, 'C', 1)['ticker'] == 'O:SPY220309C00432000'
    assert chain.select(date(2022, 3, 7), 432, 'C', 1)['ticker'] == 'O:SPY220308C00432000'


def test_vectorized_selector_matches_exhaustive_expiry_and_strike_order(tmp_path):
    import numpy as np
    from datetime import timedelta
    rng = np.random.default_rng(8)
    day = date(2022, 3, 7)
    rows = []
    for dte in (0, 1, 3, 5, 9, 10):
        for right in ('C', 'P'):
            for strike in (80., 95., 100., 105., 110., 125.):
                rows.append({'root': 'BRKB', 'ticker': f'{dte}-{right}-{strike}', 'expiry': day+timedelta(days=dte),
                             'right': right, 'strike': strike,
                             'first_seen': day-timedelta(days=int(rng.integers(0, 3)))})
    path = tmp_path / 'chain.parquet'
    pd.DataFrame(rows).to_parquet(path)
    chain = ObservedChain(path, 'BRK.B')
    spots = np.r_[rng.uniform(60, 150, 300), 97.5, 102.5, 107.5]
    for right in ('C', 'P'):
        for target in (1, 2, 4, 5, 7, 9):
            expected = []
            for spot in spots:
                eligible = [r for r in rows if r['first_seen'] < day and r['right'] == right
                            and 1 <= (r['expiry']-day).days <= 9 and .85*spot <= r['strike'] <= 1.15*spot]
                expected.append(min(eligible, key=lambda r:(abs((r['expiry']-day).days-target),r['expiry'],
                                                           abs(r['strike']-spot),r['strike'],r['ticker'])) if eligible else None)
            assert chain.select_many(day, spots, right, target) == expected
