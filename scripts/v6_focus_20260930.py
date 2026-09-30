#!/usr/bin/env python3
"""One-time September 30 compute handover, retaining all research checkpoints."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import identity, sha, verify, write
from scripts.v6_continual_resume_v3 import resume_config, unfinished_session

STATE = ROOT / 'nn_meta/validation/v6-focus-20260930'
CONFIG = ROOT / 'deploy/incubator-continual-v6-r3.json'
UNIT = 'healys-v6-focus-20260930.service'
WHEN = datetime(2026, 9, 30, 15, 1, tzinfo=ZoneInfo('America/Chicago'))
MEMORY_MIB = 26 * 1024
SUPERVISORS = ['healys-v7-required-discovery-20260930.service',
               'healys-v7-required-frontier-20260930.service']
INITIAL = ['healys-v7-discovery-20260930.service', 'healys-v7-frontier-20260930.service']
KEEP = {'healys-v7-hourly-updates.timer'}


def ctl(*args, check=True):
    return subprocess.run(['systemctl', '--user', *args], capture_output=True,
                          text=True, check=check, timeout=600)


def selected_timer(name):
    return name not in KEEP and (name.startswith(('healys-v7-', 'healys-fa-')) or name in {
        'healys-v6-continual.timer', 'healys-v6-data.timer',
        'healys-v6-context-retry.timer', 'healys-v6-alpaca-scanner.timer',
        'healys-archive-pull.timer', 'healys-stocktwits-push.timer',
        'healys-cache-backup.timer'})


def properties(unit):
    result = ctl('show', unit, '-p', 'Id', '-p', 'ActiveState', '-p', 'SubState',
                 '-p', 'UnitFileState', '-p', 'Result', '-p', 'ExecMainStatus')
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def report(phase, **details):
    path = STATE / 'progress.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    write(path, previous | details | dict(phase=phase, updated_at=datetime.now(timezone.utc).isoformat()))


def clock_allowed(now, closing):
    local = now.astimezone(WHEN.tzinfo)
    return local.date() == WHEN.date() and now >= WHEN and now >= closing


def preflight():
    from scripts.run_v6_continual_v3 import runtime_sources
    from scripts.check_v7_entry_complete import complete
    from nn_meta.session_calendar import SessionCalendar
    config = json.loads(CONFIG.read_text())
    root = Path(config['root'])
    through = unfinished_session(root)
    if through != '2026-09-28':
        raise ValueError('Expected unfinished September 28 catch-up; inspect before selecting another run')
    contract = json.loads((root / 'contract.json').read_text())
    if contract['sources'] != runtime_sources():
        raise ValueError('Frozen V6 source hashes changed')
    resumed = resume_config(config, through)
    snapshot = resumed['bootstrap_snapshot']
    if sha(Path(snapshot['path']) / 'manifest.json') != snapshot['sha256']:
        raise ValueError('Pinned snapshot changed')
    if not complete(ROOT / 'nn_meta/validation/v7-entry-campaign-v7-20260927/progress.json',
                    '8ea809659f0647dbbfef9682321a6828dc182ccac1bbbe9d3e2d5bfb4e99f568'):
        raise ValueError('Required V7 entry completion is not established')
    index = json.loads(Path(config['data_index']).read_text())
    calendar = SessionCalendar(json.loads((Path(index['path']) / 'calendar.json').read_text()))
    bounds = calendar.bounds('2026-09-30')
    if bounds is None:
        raise ValueError('Requested trading date is not in selected calendar')
    closing = bounds[1].tz_localize('UTC').to_pydatetime()
    return resumed, through, closing


def resource_plan(available_workers=None, cpus=None):
    if available_workers is None:
        available_workers = int(subprocess.check_output(
            ['bash', '-c', 'source scripts/lib/autosize.sh; autosize_workers 4500 4096'],
            cwd=ROOT, text=True).strip())
    cpus = cpus or len(os.sched_getaffinity(0))
    # Include parent/assembly overhead in the service's 26-GiB hard ceiling.
    workers = min(available_workers, cpus, (MEMORY_MIB - 2048) // 4500)
    if workers < 1:
        raise ValueError('Insufficient worker capacity')
    fields = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(fields['MemAvailable'].split()[0]) // 1024
    if available < 4500 + 4096:
        raise ValueError('Insufficient available memory after pausing other workloads')
    return dict(workers=workers, training_threads=cpus, memory_max_mib=MEMORY_MIB,
                worker_mib=4500, host_reserve_mib=4096, available_mib=available)


def inventory():
    timers = {}
    for line in ctl('list-unit-files', '--type=timer', '--no-legend', '--plain').stdout.splitlines():
        name = line.split()[0]
        if selected_timer(name):
            timers[name] = properties(name)
    services = set(name.replace('.timer', '.service') for name in timers)
    for line in ctl('list-units', 'healys-v7-*.service', '--all', '--no-legend', '--plain').stdout.splitlines():
        name = line.split()[0]
        if name.endswith('.service') and name != 'healys-v7-hourly-updates.service':
            services.add(name)
    active = {name: properties(name) for name in sorted(services)}
    active = {name: value for name, value in active.items()
              if value['ActiveState'] in {'active', 'activating', 'deactivating'}}
    # Save exact launch definitions before transient units disappear on stop.
    for name in active:
        target = STATE / 'units' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(ctl('cat', name).stdout)
    return dict(timers=timers, active_services=active)


def pause(plan):
    report('pausing', pause_plan=str(STATE / 'pause-plan.json'))
    for name, values in plan['timers'].items():
        if values.get('UnitFileState') in {'enabled', 'enabled-runtime'}:
            ctl('disable', '--now', name)
        else:
            ctl('stop', name)
    supervisors = [name for name in SUPERVISORS if name in plan['active_services']]
    if supervisors:
        ctl('stop', *supervisors)
    other = [name for name in plan['active_services'] if name not in SUPERVISORS]
    research = [name for name in other if name.startswith('healys-v7-')]
    # Let capture seal its current pack/index and migration finish its atomic
    # move without the transient units' short stop timeout killing that work.
    for name in research:
        if properties(name)['ActiveState'] in {'active', 'activating'}:
            ctl('kill', '--kill-whom=main', '--signal=SIGTERM', name)
    ordinary = [name for name in other if name not in research]
    if ordinary:
        ctl('stop', *ordinary)
    end = time.monotonic() + 900
    while any(properties(name)['ActiveState'] in {'active', 'activating', 'deactivating'} for name in research):
        if time.monotonic() >= end:
            raise RuntimeError('Research is still draining; preserve checkpoints and inspect before starting V6')
        time.sleep(5)
    after = {name: properties(name) for name in plan['active_services']}
    write(STATE / 'paused-services.json', after)
    if any(v['ActiveState'] in {'active', 'activating', 'deactivating'} for v in after.values()):
        raise RuntimeError('A competing workload has not stopped')
    report('paused', paused_services=list(after))


def restore(plan):
    # Initial V7 capture/discovery units are superseded on resume. The saved
    # supervisors reuse their checkpoints and produce fresh sealed quote indexes.
    research = [name for name in plan['active_services']
                if name.startswith('healys-v7-') and name not in INITIAL]
    for name in research:
        if ctl('show', name, '-p', 'LoadState', '--value').stdout.strip() == 'not-found':
            ctl('link', '--runtime', str(STATE / 'units' / name))
    # Install resource-only overrides after the old bound supervisors stop.
    # Original producer files and checkpoint bindings remain unchanged.
    for name, mode, memory in [(SUPERVISORS[0], 'discovery', 8), (SUPERVISORS[1], 'frontier', 6)]:
        if name not in research:
            continue
        override = Path(os.environ['XDG_RUNTIME_DIR']) / 'systemd/user' / (name + '.d') / '90-focus-resume.conf'
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text('[Service]\nExecStart=\nExecStart=' + str(ROOT / 'venv/bin/python') +
            ' -u ' + str(ROOT / 'scripts/resume_v7_compute_20260930.py') + ' ' + mode +
            f'\nCPUQuota=\nMemoryHigh={memory-1}G\nMemoryMax={memory}G\nTasksMax=256\n')
    ctl('daemon-reload')
    for name, values in plan['timers'].items():
        enabled = values.get('UnitFileState')
        if enabled in {'enabled', 'enabled-runtime'}:
            ctl('enable', *(['--runtime'] if enabled == 'enabled-runtime' else []), name)
        if values['ActiveState'] == 'active':
            ctl('start', name)
    if research:
        ctl('start', '--no-block', *research)
    observed = {name: properties(name) for name in research}
    write(STATE / 'restored-services.json', observed)
    if any(value.get('ActiveState') == 'failed' for value in observed.values()):
        raise RuntimeError('A resumed research service failed; inspect restored-services.json')
    report('restored', restored_at=datetime.now(timezone.utc).isoformat(),
           restoration_scope='Timers restored and research starts requested; ongoing health requires live receipts')


def run(auto_restore=False):
    config, through, closing = preflight()
    if not clock_allowed(datetime.now(timezone.utc), closing):
        raise ValueError('One-time handover is only authorized September 30 at/after 15:01 Central and market close')
    prior = STATE / 'pause-plan.json'
    if prior.exists():
        raise ValueError('Handover already attempted; inspect retained plan rather than overwriting it')
    plan = inventory()
    write(prior, plan)
    pause(plan)
    resources = resource_plan()
    root = Path(config['root'])
    path = root / 'invocations' / (identity(config) + '.json')
    if path.exists() and json.loads(path.read_text()) != config:
        raise ValueError('Invocation configuration differs')
    if not path.exists():
        write(path, config)
    command = ['bash', str(ROOT / 'scripts/run_v6_continual_v3.sh'), '--config', str(path),
               '--through', through, '--max-seconds', '86400',
               '--workers', str(resources['workers']), '--threads', str(resources['training_threads'])]
    report('incubator_running', resources=resources, through=through, auto_restore=auto_restore,
           command=command, candidate_complete=False)
    result = subprocess.run(command, cwd=ROOT, check=False)
    latest = json.loads((root / 'latest-run.json').read_text())
    write(STATE / 'incubator-result.json', latest)
    if (result.returncode or latest.get('status') not in {'candidate_frozen', 'candidate_already_frozen'}
            or latest.get('scope') != 'full_universe' or latest.get('through') != through):
        report('needs_review', returncode=result.returncode, incubator_status=latest.get('status'))
        raise RuntimeError('Incubator has not frozen a full candidate; competing jobs remain paused')
    candidate = root / 'runs' / through / 'candidate'
    verify(candidate)
    report('candidate_complete', candidate_complete=True, candidate=str(candidate),
           candidate_sha256=sha(candidate / 'complete.json'), verdict=latest.get('verdict'))
    if auto_restore:
        restore(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--record-exit', action='store_true')
    parser.add_argument('--auto-restore', action='store_true')
    args = parser.parse_args()
    if args.check:
        config, through, closing = preflight()
        print(json.dumps(dict(preflight='passed', through=through, snapshot=config['bootstrap_snapshot'],
                              closing=closing.isoformat(), scheduled_at=WHEN.isoformat(),
                              resources_now=resource_plan())))
        return
    STATE.mkdir(parents=True, exist_ok=True)
    if args.record_exit:
        write(STATE / 'service-exit.json', dict(observed_at=datetime.now(timezone.utc).isoformat(),
              result=os.environ.get('SERVICE_RESULT'), code=os.environ.get('EXIT_CODE'),
              status=os.environ.get('EXIT_STATUS')))
        return
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.restore:
                restore(json.loads((STATE / 'pause-plan.json').read_text()))
            else:
                run(args.auto_restore)
        except Exception as exc:
            report('failed', error=f'{type(exc).__name__}: {exc}')
            raise


if __name__ == '__main__':
    main()
