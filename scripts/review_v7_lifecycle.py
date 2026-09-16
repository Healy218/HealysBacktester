"""Bind reviewed lifecycle explanations to every unresolved coverage session."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.v7.lifecycle import classify_gaps
    from nn_meta.v7.storage import verify, sha, transaction, receipt, identity
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('coverage', 'review', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    verify(args.coverage)
    inputs = {str(p): sha(p) for p in (args.coverage/'complete.json', args.review,
              ROOT/'nn_meta/v7/lifecycle.py', Path(__file__))}
    review = json.loads(args.review.read_text())
    for name, digest in review.get('captured_sources', {}).items():
        source = ROOT/name
        verify(source)
        if sha(source/'complete.json') != digest:
            raise ValueError('Captured lifecycle source receipt differs')
        inputs[str(source/'complete.json')] = digest
    gaps = pd.read_csv(args.coverage/'missing-sessions.csv')
    rows = pd.DataFrame(classify_gaps(gaps, review))
    report = dict(schema='v7-lifecycle-explanations-v1', inputs=inputs, sessions=len(rows),
                  explanations=rows.explanation.value_counts().to_dict(),
                  point_in_time_admitted=False, held_positions_resolved=False, research_ready=False)
    with transaction(args.output) as temp:
        rows.to_csv(temp/'sessions.csv', index=False)
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        if any(sha(p) != digest for p, digest in inputs.items()):
            raise ValueError('Lifecycle evidence changed during review')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
