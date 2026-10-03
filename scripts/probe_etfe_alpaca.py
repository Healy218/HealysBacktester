"""Bounded read-only ETFE provider probes; no orders, streams or data campaign."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values
    from nn_meta.etfe.alpaca_probe import ReadOnlyProbe, run_probe
    # Read only known credentials; do not export the root .env into old runtime selectors.
    values = dotenv_values(ROOT/'.env')
    credentials = {role:(values.get(key), values.get(secret)) for role,key,secret in (
        ('data','ALPACA_API_KEY','ALPACA_API_SECRET'),
        ('metadata','ALPACA_PAPER_API_KEY','ALPACA_PAPER_API_SECRET'))}
    if not all(all(pair) for pair in credentials.values()):
        parser.error('Alpaca data/paper metadata credential pairs must be configured in root .env')
    plan = args.plan.resolve()
    output = args.output.resolve()
    base = ROOT/'nn_meta/validation'
    if (plan.parent.parent != base or not plan.parent.name.startswith('etfe-')
            or output.parent != plan.parent or not output.name.startswith('probe-')):
        parser.error('Use an ETFE setup plan and a fresh probe-* subdirectory beside it')
    result = run_probe(ReadOnlyProbe(output, credentials), plan)
    print(json.dumps(result, indent=2))
    if result['transport_failures']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
