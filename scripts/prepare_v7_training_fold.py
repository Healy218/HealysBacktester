"""Select a predeclared V7 fold and fit bounded train-only preprocessing."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.evaluation import evaluation_plan
    from nn_meta.v7.training_data import prepare_fold
    from nn_meta.v7.preprocessing import fit_preprocessing
    from nn_meta.session_calendar import SessionCalendar
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shards', type=Path, required=True, help='JSON list of ordered immutable factorized shard paths')
    parser.add_argument('--fold', required=True, choices=[f['name'] for f in evaluation_plan()['folds']])
    parser.add_argument('--calendar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Training selections must use the repository artifact disk, not tmpfs')
    shards = json.loads(args.shards.read_text())
    if not isinstance(shards, list) or not shards or not all(isinstance(p, str) for p in shards):
        raise ValueError('Ordered explicit source shard paths required')
    policy = evaluation_plan()
    fold = next(f for f in policy['folds'] if f['name'] == args.fold)
    calendar = SessionCalendar(json.loads(args.calendar.read_text()))
    selected = prepare_fold(shards, fold, calendar, args.output/'selection',
                            embargo_sessions=policy['embargo_sessions'])
    fitted = fit_preprocessing(args.output/'selection', args.output/'preprocessing')
    print(json.dumps(dict(counts=selected['counts'], training_rows=fitted['rows'], research_ready=False)))


if __name__ == '__main__': main()
