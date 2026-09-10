"""Run isolated synthetic session/recovery acceptance and save an evidence receipt."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ['tests/test_live_session_recovery.py', 'tests/test_trade_accounting.py',
         'tests/test_taken_monitor.py', 'tests/test_taken_trades.py',
         'tests/test_alert_batches.py', 'tests/test_feeds_barstore.py',
         'tests/test_feeds_quotestore.py', 'tests/test_ops_fixes_20260908.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New evidence directory; refuses reuse')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = TESTS + ['nn_meta/live/taken_monitor.py', 'nn_meta/live/taken_trades.py',
                      'nn_meta/live/trade_accounting.py', 'nn_meta/live/alert_replies.py',
                      'nn_meta/live/run_live.py', 'nn_meta/live/scanner.py',
                      'nn_meta/live/feeds/barstore.py', 'nn_meta/live/feeds/quotestore.py']
    receipt = dict(kind='synthetic-session-recovery', started=datetime.now(timezone.utc).isoformat(),
                   python=sys.version, live_session_verified=False, broker_records_verified=False,
                   source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    with (out/'pytest.log').open('w') as log:
        result = subprocess.run([sys.executable, '-m', 'pytest', *TESTS, '-q',
                                 '--junitxml='+str(out/'results.xml')], cwd=ROOT, env=env,
                                stdout=log, stderr=subprocess.STDOUT)
    receipt.update(returncode=result.returncode, finished=datetime.now(timezone.utc).isoformat())
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(returncode=result.returncode, evidence=str(out))))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
