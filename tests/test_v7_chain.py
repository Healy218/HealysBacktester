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
