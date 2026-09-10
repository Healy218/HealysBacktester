"""Run one scheduled job under a lock and retain status plus per-run logs."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.job_receipts import record, stamp


def run(name,state_dir,command,*,timeout=14400):
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',name):raise ValueError('Invalid job name')
    folder=Path(state_dir)/name;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'run.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 75
        started=stamp()
        logfile=folder/('run-'+started.replace(':','-')+'.log')
        record(state_dir,name,'running',started=started,details=dict(log=str(logfile)))
        try:
            with logfile.open('w') as log:
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    code=process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    # Kill surviving descendants even when the shell exited on TERM.
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait()
                    code=124
        except OSError:
            code=127
        record(state_dir,name,'success' if code==0 else 'failed',started=started,returncode=code,details=dict(log=str(logfile)))
        return code


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--state-dir',type=Path,default=ROOT/'logs/job-health')
    p.add_argument('--timeout',type=int,default=14400)
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();command=a.command[1:] if a.command[:1]==['--'] else a.command
    if not command or a.timeout<=0:p.error('A command and positive timeout are required')
    return run(a.name,a.state_dir,command,timeout=a.timeout)


if __name__=='__main__':raise SystemExit(main())
