"""Preview/install the 2026-09-08 operations fixes in the production crontab,
preserving rollback (same shape as configure_top_alerts.py).

Idempotent rewrites:
  * every expert scan line gets ``TF_CPP_MIN_LOG_LEVEL=2 BACKTESTER_CONSOLE_QUIET=1``
    (no TensorFlow banners, no per-symbol engine chatter in the cron logs);
  * the Sunday ``--bars-and-surface-only … && build_surface`` lines become
    ``scripts/run_refresh.sh <pool>`` (recorded exit status, 6 download workers);
  * a daily ``scripts/rotate_logs.sh`` line is added;
  * the feed watchdogs' ``pgrep -f "[f]eeds.<x>"`` becomes ``pgrep -f "feeds\.<x>$"``
    — the old pattern matched the watchdog's own ``sh -c`` line (which also
    contains ``-m nn_meta.live.feeds.<x>``), so a dead daemon was never restarted;
  * ``--enable-option-feed`` restores the two option-stream lines if they were
    commented out (safe: the stream idles until the alert path registers contracts).

    ./venv/bin/python scripts/configure_cron.py            # preview
    ./venv/bin/python scripts/configure_cron.py --run      # install (backs up first)
"""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
import subprocess

SCAN_ENV = 'TF_CPP_MIN_LOG_LEVEL=2 BACKTESTER_CONSOLE_QUIET=1'
_SCAN_MODULES = ('-m nn_meta.live.run_live ', '-m nn_meta.live.v4_scan ')
_POOL_RE = re.compile(r'NN_META_POOL=(\w+)')
_SCHEDULE_RE = re.compile(r'^(\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(.*)$')
_DISABLED_MARK = '# DISABLED 2026-09-08 (option feed has no subscribers'
_WATCHDOG_RE = re.compile(r'pgrep -f "\[f\]eeds\.(\w+)"')


def updated_cron(original, repo, *, enable_option_feed=False):
    lines = []
    for line in original.splitlines():
        stripped = line.lstrip()
        if stripped.startswith('#'):
            body = stripped[1:]
            if enable_option_feed and 'feeds.option_stream' in body and \
                    (body.startswith('@reboot') or _SCHEDULE_RE.match(body)):
                lines.append(body)            # restore the disabled daemon/watchdog
                continue
            if enable_option_feed and stripped.startswith(_DISABLED_MARK):
                continue
            lines.append(line)
            continue
        line = _WATCHDOG_RE.sub(lambda m: f'pgrep -f "feeds\\.{m.group(1)}$"', line)
        if any(m in line for m in _SCAN_MODULES) and SCAN_ENV not in line:
            line = line.replace(' && ', f' && {SCAN_ENV} ', 1)
        if '--bars-and-surface-only' in line:
            pool = _POOL_RE.search(line)
            sched = _SCHEDULE_RE.match(line)
            if pool and sched:
                line = (f'{sched.group(1)} cd {repo} && ./scripts/run_refresh.sh {pool.group(1)} '
                        f'>> logs/surface_refresh_{pool.group(1)}.log 2>&1')
        lines.append(line)
    if not any('scripts/rotate_logs.sh' in ln for ln in lines):
        lines.extend(['', '# Daily log rotation as the service user (deploy/logrotate/healys.conf)',
                      f'7 4 * * * cd {repo} && ./scripts/rotate_logs.sh >> logs/logrotate.log 2>&1'])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--enable-option-feed', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    original = subprocess.check_output(['crontab', '-l'], text=True)
    updated = updated_cron(original, repo, enable_option_feed=args.enable_option_feed)
    if not args.run:
        print(updated)
        return
    if updated == original:
        print('crontab already up to date; nothing written')
        return
    root = repo / 'logs/ops' / ('ops-fixes-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    root.mkdir(parents=True)
    (root / 'crontab-before.txt').write_text(original)
    (root / 'crontab-after.txt').write_text(updated)
    subprocess.run(['crontab', '-'], input=updated, text=True, check=True)
    assert subprocess.check_output(['crontab', '-l'], text=True) == updated
    print(f'crontab updated; rollback copy: {root}/crontab-before.txt')


if __name__ == '__main__':
    main()
