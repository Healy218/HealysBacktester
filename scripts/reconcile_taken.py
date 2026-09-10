"""Read-only comparison with normalized broker JSON; no broker login required."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nn_meta.live.trade_accounting import reconcile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--broker-json', type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        results = reconcile(db, json.loads(args.broker_json.read_text(), parse_float=str))
    print(json.dumps(results, indent=2))
    return 0 if results and all(r['matched'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
