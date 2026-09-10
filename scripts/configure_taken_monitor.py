"""Preview/install the taken-trade exit watcher, preserving the previous cron."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess


def updated_cron(original, repo):
    if 'scripts/run_taken_monitor.py' in original:
        return original
    return original.rstrip() + ('\n\n# User-confirmed trades: closed-bar exit watch\n'
        f'4,19,34,49 * * * * cd {repo} && ./venv/bin/python scripts/run_taken_monitor.py >> logs/taken_monitor.log 2>&1\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    old=subprocess.check_output(['crontab','-l'],text=True)
    new=updated_cron(old,repo)
    if not args.run:
        print(new)
        return
    root=repo/'logs/ops'/('taken-monitor-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    root.mkdir(parents=True)
    (root/'crontab-before.txt').write_text(old)
    (root/'crontab-after.txt').write_text(new)
    subprocess.run(['crontab','-'],input=new,text=True,check=True)
    assert subprocess.check_output(['crontab','-l'],text=True)==new
    print(f'Exit watcher installed; rollback: {root}/crontab-before.txt')


if __name__=='__main__':main()
