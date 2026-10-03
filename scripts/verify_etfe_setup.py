"""Read-only integrity check for a selected ETFE preparation directory."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    args = parser.parse_args()
    from nn_meta.etfe.verification import verify_setup
    print(json.dumps(verify_setup(args.setup), indent=2))
