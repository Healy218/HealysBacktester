"""Lossless float32 factorization of every real integrated-pilot feature row."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import numpy as np
    import pandas as pd
    from nn_meta.v7.storage import verify, sha
    from nn_meta.v7.factorized import write_shard, FactorizedRows
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pilot', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    frames, rows, inputs = [], [], {}
    for minutes in (1, 5, 15, 30):
        path = args.pilot / str(minutes)
        verify(path)
        inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
        frames.append(pd.read_parquet(path / 'feature_rows.parquet'))
        for sample in json.loads((path / 'samples.json').read_text()):
            p, label = sample['proposal'], sample['replay']
            rows.append({'row_id': p['proposal_id'], 'variant_id': p['variant_id'], 'symbol': p['symbol'],
                         'decision_ns': p['decision_ns'], 'label_complete': label['label_complete'],
                         'label_end_ns': label['label_end_ns'], 'net_return': label['net_return']})
    frame = pd.concat(frames)
    metadata = pd.DataFrame(rows).set_index('row_id').loc[frame.index].reset_index(names='row_id')
    write_shard(args.output, frame, metadata, input_identity={'source_receipts': inputs,
                'factorized_source': sha(ROOT / 'nn_meta/v7/factorized.py'), 'runner': sha(__file__)})
    store = FactorizedRows(args.output)
    np.testing.assert_array_equal(store.take(np.arange(len(frame))), frame.to_numpy(dtype=np.float32))
    print(json.dumps({k: v for k, v in store.receipt.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
