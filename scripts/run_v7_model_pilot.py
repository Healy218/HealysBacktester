"""Run one predeclared bounded V7 model pilot; does not launch full training."""
from pathlib import Path
import argparse
import json
import os
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.trials import run_pilot
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fold', type=Path, required=True)
    parser.add_argument('--preprocessing', type=Path, required=True)
    parser.add_argument('--plan', type=Path, default=ROOT/'docs/specs/V7_MODEL_TRIALS_20260916.json')
    parser.add_argument('--trial', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Model pilots must use repository artifacts, not tmpfs')
    print(json.dumps(run_pilot(args.fold, args.preprocessing, args.plan, args.trial, args.output), allow_nan=False))


if __name__ == '__main__':
    main()
