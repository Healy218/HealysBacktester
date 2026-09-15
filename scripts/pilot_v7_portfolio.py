"""Replay the preselected SPY family/timeframe sample through one shared ledger."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.portfolio import portfolio_replay
    from nn_meta.v7.quote_archive import QuoteArchive
    from nn_meta.v7.storage import verify, receipt, transaction
    from nn_meta.v7.provenance import RunBinding
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('pilot', 'quotes', 'calendar', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    args = ap.parse_args()
    inputs = [args.calendar, args.quotes / 'requests.json']
    candidates = []
    for minutes in (1, 5, 15, 30):
        path = args.pilot / str(minutes)
        verify(path)
        inputs.append(path / 'complete.json')
        for sample in json.loads((path / 'samples.json').read_text()):
            if 'replay' not in sample:
                raise ValueError('All preselected samples need observed paths; no success-only selection')
            p = sample['proposal']
            candidates.append({**p, 'score': 0., 'score_available_ns': p['decision_ns'], 'path': sample['replay']})
    declaration = {'scope': 'fixed SPY plumbing sample, all 72 paths including censored outcomes',
                   'score': 'constant zero; stable proposal-id tie order', 'research_ready': False}
    binding = RunBinding(ROOT, inputs=inputs, declaration=declaration)
    calendar = SessionCalendar(json.loads(args.calendar.read_text()))
    clocks = [t.value for day, (opening, closing) in sorted(calendar.sessions.items())
              if '2022-03-07' <= day <= '2022-03-11'
              for t in pd.date_range(opening.tz_localize('UTC') + pd.Timedelta(minutes=1),
                  closing.tz_localize('UTC') + pd.Timedelta(minutes=14), freq='min')]
    with transaction(args.output) as temp:
        result = portfolio_replay(candidates, clocks, QuoteArchive(args.quotes))
        (temp / 'portfolio.json').write_text(json.dumps(result, indent=2) + '\n')
        manifest = binding.finish()
        (temp / 'binding.json').write_text(json.dumps(manifest, indent=2) + '\n')
        receipt(temp, {'identity': manifest['identity'], 'research_ready': False})
    print(json.dumps({k: v for k, v in result.items() if k not in ('fills', 'decisions', 'marks')}, indent=2))


if __name__ == '__main__':
    main()
