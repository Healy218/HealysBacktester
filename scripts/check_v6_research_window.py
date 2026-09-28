"""Reject intraday research starts, including delayed persistent-timer events."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from nn_meta.session_calendar import SessionCalendar


def allowed(calendar, now):
    now = pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError('research clock must be timezone aware')
    bounds = calendar.bounds(now.tz_convert('America/New_York').date().isoformat())
    if bounds is None:
        return True
    opening, closing = (x.tz_localize('UTC') for x in bounds)
    return now < opening-pd.Timedelta(minutes=30) or now >= closing+pd.Timedelta(minutes=15)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-index', type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.data_index.read_text())
    calendar = SessionCalendar(json.loads((Path(index['path'])/'calendar.json').read_text()))
    if not allowed(calendar, pd.Timestamp.now(tz='UTC')):
        print('V6 research deferred: paper-session reserve window.')
        raise SystemExit(1)
