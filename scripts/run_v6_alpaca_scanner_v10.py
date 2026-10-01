"""Versioned scanner adapter: reconcile expired projections before frozen scans."""
import argparse
from datetime import datetime, timezone
import fcntl
import subprocess
import sys
from pathlib import Path

from scripts.run_v6_alpaca_runtime_v5 import ROOT,validate,clients,save,read
from integrations.alpaca_paper.v6_bridge import Journal,reconcile
from integrations.alpaca_paper.v6_source_reconcile_v3 import POLICY,retire_unfilled_sources


def scan(state, m, index, frozen, env, workers):
    release = frozen/'deploy/v6/releases/v6-cash-repair-20260913'
    command = [sys.executable, str(ROOT/'scripts/run_v6_forward_resilient_v1.py'),
        '--release', str(release), '--anchor', m['release_sha256'],
        '--data-index', str(state/'data-index.json'), '--state', str(state),
        '--env', str(env), '--workers', str(workers)]
    subprocess.run(command, cwd=frozen, check=True, timeout=570)
    return read(state/'status.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--env',type=Path,default=ROOT/'.env')
    p.add_argument('--workers',type=int,required=True)
    a=p.parse_args();state=a.state.resolve()
    if not 1<=a.workers<=16:p.error('workers must be 1..16')
    with (state/'scanner-dispatch.lock').open('a+') as dispatch:
        try:fcntl.flock(dispatch,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 0
        report=dict(checked_at=datetime.now(timezone.utc).isoformat(),action='scan',scanner_book_policy=POLICY)
        try:
            m,index,frozen=validate(state,require_fresh=True)
            required=['integrations/alpaca_paper/v6_source_reconcile_v3.py',
                      'scripts/run_v6_alpaca_scanner_v10.py','scripts/run_v6_alpaca_scanner_v10.sh',
                      'scripts/run_v6_forward_resilient_v1.py']
            if (m.get('scanner_monitor_policy') != 'concurrent-quote-retry-v1' or
                    m.get('scanner_book_policy')!=POLICY) or any(r not in m['bridge_runtime_sha256'] for r in required):
                raise ValueError('Broker-aware scanner policy is not admitted')
            # Broker and frozen scanner cannot mutate their books during this check.
            with (state/'bridge.lock').open('a+') as bridge, (state/'.forward.lock').open('a+') as forward:
                fcntl.flock(bridge,fcntl.LOCK_EX)
                fcntl.flock(forward,fcntl.LOCK_EX)
                trading,_=clients(a.env.resolve())
                journal=Journal(state/'broker-orders.sqlite3')
                account,positions,orders=reconcile(journal,trading,expected_fingerprint=m['account_fingerprint'],allow_pending=True)
                report['retired_unfilled_sources']=retire_unfilled_sources(
                    state/'portfolio.sqlite3',journal,positions,orders,now=datetime.now(timezone.utc))
                save(state/'scanner-source-reconciliation.json',dict(report,status='reconciled'))
            report.update(scan(state,m,index,frozen,a.env.resolve(),a.workers))
        except Exception as exc:
            report.update(status='blocked',error=type(exc).__name__+': '+str(exc))
            save(state/'scanner-dispatch-status.json',report)
            raise
        save(state/'scanner-dispatch-status.json',report)
    return 0


if __name__=='__main__':raise SystemExit(main())
