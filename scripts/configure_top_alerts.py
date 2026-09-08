"""Preview/install the production top-five alert cron wiring, preserving rollback."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess


def updated_cron(original, repo):
    lines=[];count=0
    for line in original.splitlines():
        if not line.lstrip().startswith('#') and ('-m nn_meta.live.run_live ' in line or '-m nn_meta.live.v4_scan ' in line):
            if '--once' in line:count+=1
            if 'NN_META_ALERT_TOP_N=5' not in line:
                line=line.replace('&& NN_META_POOL=', '&& NN_META_ALERT_TOP_N=5 NN_META_POOL=',1)
        lines.append(line)
    if count!=4:
        raise ValueError(f'expected four expert scan crons, found {count}')
    if not any('-m nn_meta.live.alert_batches ' in line for line in lines):
        lines.extend(['','# Shared top-five entry alerts and opt-in remainder summaries',
                      f'* * * * * cd {repo} && NN_META_ALERT_TOP_N=5 ./venv/bin/python -m nn_meta.live.alert_batches >> logs/alert_batches.log 2>&1'])
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    original=subprocess.check_output(['crontab','-l'],text=True)
    updated=updated_cron(original,repo)
    if not args.run:
        print(updated);return
    root=repo/'logs/ops'/('top-five-alerts-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    root.mkdir(parents=True)
    (root/'crontab-before.txt').write_text(original)
    (root/'crontab-after.txt').write_text(updated)
    subprocess.run(['crontab','-'],input=updated,text=True,check=True)
    assert subprocess.check_output(['crontab','-l'],text=True)==updated
    print(f'Top-five alert routing enabled; rollback crontab: {root}/crontab-before.txt')


if __name__=='__main__':main()
