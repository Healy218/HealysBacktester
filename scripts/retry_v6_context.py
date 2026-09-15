"""Retry frozen V6 refresh when delayed prior-session MASSIVE files appear.

This operational helper does not change the activated inference runtime or
publish data. Only the existing refresh service can validate/publish inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botocore.exceptions import ClientError
from nn_meta.session_calendar import SessionCalendar


def availability(calendar, index, now, client):
    """Require all sessions after the current pointer, not just the latest."""
    import pandas as pd
    now = pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError('availability time requires timezone')
    calendar.bounds(now.tz_convert('America/New_York').date().isoformat())
    through = max(day for day in calendar.sessions
                  if calendar.bounds(day)[1].tz_localize('UTC') < now)
    current = index['through']
    if current not in calendar.sessions or current > through:
        raise ValueError('invalid current context session')
    result = {'required_through': through, 'current_through': current,
              'checked_at': now.isoformat()}
    if current == through:
        return {**result, 'status': 'current'}
    missing = []
    for day in sorted(calendar.sessions):
        if not current < day <= through:
            continue
        key = f'us_options_opra/minute_aggs_v1/{day[:4]}/{day[5:7]}/{day}.csv.gz'
        try:
            response = client.head_object(Bucket='flatfiles', Key=key)
        except ClientError as exc:
            if str(exc.response['Error']['Code']) not in ('404', 'NoSuchKey', 'NotFound'):
                raise
            missing.append(key)
        else:
            if response['ContentLength'] <= 0:
                raise ValueError('empty MASSIVE context object')
    return {**result, 'status': 'waiting_for_provider' if missing else 'available',
            'missing_keys': missing}


def retry(result, *, run, command=subprocess.run):
    if result['status'] != 'available' or not run:
        return result
    for unit in ('healys-v6-forward.service', 'healys-v6-data.service'):
        state = command(['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '--value'],
                        check=True, text=True, capture_output=True, timeout=15).stdout.strip()
        if state in ('active', 'activating', 'deactivating', 'reloading'):
            return {**result, 'status': 'deferred_busy', 'unit': unit}
        if state not in ('inactive', 'failed'):
            raise ValueError(f'unexpected service state: {unit}: {state}')
    command(['systemctl', '--user', 'start', '--no-block', 'healys-v6-data.service'],
            check=True, timeout=15)
    return {**result, 'status': 'refresh_requested'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--calendar', type=Path, required=True)
    ap.add_argument('--data-index', type=Path, required=True)
    ap.add_argument('--env', type=Path, default=ROOT / '.env')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()
    from dotenv import load_dotenv
    import boto3
    from botocore.config import Config
    load_dotenv(args.env)
    client = boto3.client('s3', endpoint_url='https://files.massive.com',
                         aws_access_key_id=os.environ['MASSIVE_FLAT_FILES_API_KEY'],
                         aws_secret_access_key=os.environ['MASSIVE_FLAT_FILES_API_SECRET'],
                         config=Config(signature_version='s3v4', connect_timeout=10,
                                       read_timeout=15, retries={'max_attempts': 2}))
    result = availability(SessionCalendar(json.loads(args.calendar.read_text())),
                          json.loads(args.data_index.read_text()), datetime.now(timezone.utc), client)
    print(json.dumps(retry(result, run=args.run), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
