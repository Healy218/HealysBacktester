"""Verify ETFE VWAP preparation; does not admit inputs or launch training."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe.vwap_setup import verify

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.setup), indent=2))
