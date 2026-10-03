"""Create a separate, immutable ETFE planning catalog. No data/model campaign."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('NN_META_POOL', 'etfe') != 'etfe':
        parser.error('Inherited NN_META_POOL is not etfe; use an ETFE-only environment')
    for key in ('NN_META_CAMPAIGN', 'NN_META_RESEARCH_ROOT', 'NN_META_DATA_CANDIDATE', 'NN_META_V6_INPUTS'):
        if os.environ.get(key):
            parser.error(f'Clear unrelated runtime selector {key}')
    for key in ('NN_META_SHORT_DTE', 'NN_META_V6_EXPANDED'):
        if os.environ.get(key, '0') != '0':
            parser.error(f'Clear unrelated runtime selector {key}')
    os.environ['NN_META_POOL'] = 'etfe'
    from nn_meta.etfe.preparation import prepare
    print(json.dumps(prepare(args.output), indent=2))


if __name__ == '__main__':
    main()
