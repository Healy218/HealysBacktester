"""Check current V7 full-universe evidence; exit nonzero until every gate passes."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.readiness import assess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active', type=Path, default=ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = assess(ROOT, args.active)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'ready_for_training':report['ready_for_training'],
                      'failed_gates':[g['gate'] for g in report['gates'] if not g['passed']],
                      'report':str(args.output)}))
    return 0 if report['ready_for_training'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
