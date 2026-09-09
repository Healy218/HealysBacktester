"""Read-only campaign observer. Run once from a persistent 30-minute timer."""
import argparse
import csv
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def campaign_processes(campaign, proc=Path('/proc')):
    """Bind by exact campaign/pool environment or explicit launcher arguments."""
    found = []
    modules = {'scripts.run_v6_request_inventory': 'inventory',
               'scripts.run_v6_full_freeze': 'preparation supervisor',
               'scripts.run_v6_parallel_freeze': 'parallel preparation supervisor',
               'scripts.run_v6_freeze_trial': 'freeze trial supervisor',
               'nn_meta.freeze_baseline': 'freeze',
               'nn_meta.build_meta_dataset': 'build/assemble',
               'nn_meta.train_meta': 'training',
               'nn_meta.v4_evaluate': 'evaluation/training',
               'nn_meta.v4_finalize': 'final training',
               'nn_meta.walkforward_meta': 'walk-forward training',
               'scripts.research_local': 'stage launcher'}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = entry.joinpath('cmdline').read_bytes().decode().split('\0')
            environment = entry.joinpath('environ').read_bytes().split(b'\0')
            bound = (f'NN_META_CAMPAIGN={campaign}'.encode() in environment
                     and b'NN_META_POOL=v6' in environment)
            if '-m' not in args:
                continue
            module = args[args.index('-m') + 1]
            if module == 'scripts.research_local':
                bound = bound or ('--campaign' in args and args[args.index('--campaign') + 1] == campaign
                                  and '--pool' in args and args[args.index('--pool') + 1] == 'v6')
            if not bound or module not in modules:
                continue
            stat = entry.joinpath('stat').read_text().rsplit(')', 1)[1].split()
            if stat[0] == 'Z':
                continue
            stage = modules[module]
            if module == 'scripts.research_local' and '--stage' in args and args[args.index('--stage') + 1] == 'build':
                stage = 'build/assembly launcher'
            if module == 'nn_meta.build_meta_dataset' and '--assemble' in args:
                stage = 'assembly'
            if module == 'scripts.run_v6_parallel_freeze' and '--symbol' in args:
                stage = 'tick store ' + args[args.index('--symbol') + 1]
            found.append({'pid': int(entry.name), 'start_ticks': stat[19], 'stage': stage})
        except (OSError, UnicodeError, IndexError):
            continue
    return sorted(found, key=lambda p: p['pid'])


def snapshot(root, campaign, processes):
    prep = root / 'nn_meta/expanded_inputs' / campaign
    base = root / 'nn_meta/campaigns' / campaign / 'v6'
    scope = read_json(prep / 'inventory-r4/scope.json', {})
    symbols = scope.get('symbols', [])
    captures = prep / 'full-run'
    inventory = sum((prep / 'inventory-r4' / s / 'manifest.json').exists() for s in symbols)
    stores = sum((captures / 'stores' / s / 'manifest.json').exists() for s in symbols)
    batches = sum(1 for _ in (captures / 'captures').glob('*/*/*/manifest.json'))
    plans = list((captures / 'prepared').glob('*/capture_plan.json'))
    planned = sum(len(read_json(p, {}).get('capture_batches', [])) for p in plans)
    artifacts = base / 'artifacts'
    result = read_json(captures / 'freeze-launcher-result.json')
    trial = read_json(captures / 'worker-trial/status.json')
    trial_result = read_json(captures / 'worker-trial/result.json')
    trial_live = any(p['stage'] == 'freeze trial supervisor' for p in processes)
    if trial_result is not None:
        result = trial_result
    elif trial_live:
        result = None  # Original launcher drained intentionally for the trial.
    registry = base / 'runs/runs.csv'
    runs = 0
    if registry.exists():
        with registry.open() as f:
            runs = sum(1 for _ in csv.DictReader(f))
    baseline = read_json(artifacts / 'baseline_spec.json')
    build_total = len(baseline['symbols']) if baseline is not None else len(symbols)
    counts = {'inventory_symbols': inventory, 'tick_stores': stores, 'capture_batches': batches,
              'prepared_capture_batches': planned, 'prepared_symbols': len(plans),
              'freeze_shards': sum((artifacts / 'freeze_shards' / f'{s}.json').exists() for s in symbols),
              'build_symbols': sum((artifacts / 'meta_rows' / f'{s}.parquet').exists() for s in symbols),
              'training_registry_rows': runs,
              'model_files': sum(1 for p in base.rglob('*')
                                 if p.is_file() and p.suffix in ('.keras', '.joblib'))}
    evidence = {'sealed_inputs': (captures / 'final-inputs.json').exists(),
                'baseline_spec': (artifacts / 'baseline_spec.json').exists(),
                'assembled_dataset': (artifacts / 'meta_dataset.parquet').exists(),
                'evaluation_manifest': (base / 'reports/evaluate.manifest.json').exists(),
                'final_model_manifest': (base / 'model_final/manifest.json').exists()}
    # File presence is progress evidence, never proof of a passing or deployable model.
    logs = list((base / 'runs/logs').glob('*/*.log'))
    logs += list(prep.glob('*-resume-*.log'))
    logs += list((base / 'runs/next-stage').glob('*.log'))
    latest = max((p.stat().st_mtime for p in logs), default=0)
    return {'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'campaign': campaign,
            'total_symbols': len(symbols), 'counts': counts, 'evidence_present': evidence,
            'launchers_prepared': bool((read_json(prep / 'post-freeze-launchers.json') or {}).get('prepared')),
            'processes': processes, 'freeze_launcher_result': result,
            'build_total_symbols': build_total,
            'build_plan': read_json(base / 'runs/next-stage/build-plan.json'),
            'build_result': read_json(base / 'runs/next-stage/build-result.json'),
            'worker_trial': trial if trial_live or trial_result else None,
            'parallel': read_json(captures / 'parallel/status.json'),
            'parallel_result': read_json(captures / 'parallel/result.json'),
            'freeze_resource_plan': read_json(captures / 'parallel/freeze-resource-plan.json'),
            'resource_plan': read_json(captures / 'parallel/resource-plan.json'),
            'latest_log_mtime': latest, 'free_gib': round(shutil.disk_usage(root).free / 1024**3, 1)}


def active_metric(s):
    stages = {p['stage'] for p in s['processes']}
    if any('training' in stage for stage in stages):
        return 'training_registry_rows'
    if 'build/assemble' in stages:
        return 'build_symbols'
    if 'freeze' in stages:
        return 'freeze_shards'
    if any(stage.startswith('tick store ') for stage in stages):
        return 'tick_stores'
    if 'inventory' in stages:
        return 'inventory_symbols'
    return None


def pace_line(s, history):
    metric = active_metric(s)
    if metric is None:
        return None
    now = dt.datetime.fromisoformat(s['time_utc'])
    # Average over the current observed stage, up to six hours. Stop at a
    # stage gap or counter reset rather than mixing unrelated work/resumes.
    baseline = None
    last_count = s['counts'][metric]
    for record in reversed(history):
        when = dt.datetime.fromisoformat(record['time_utc'])
        if when >= now or record.get('campaign') != s['campaign']:
            continue
        if active_metric(record) != metric or now - when > dt.timedelta(hours=6):
            break
        count = record['counts'][metric]
        if count > last_count:
            break
        baseline = record
        last_count = count
    if baseline is None:
        return 'Average/hour: collecting progress; ETA: calculating ⏲️'
    hours = (now - dt.datetime.fromisoformat(baseline['time_utc'])).total_seconds() / 3600
    completed = s['counts'][metric] - baseline['counts'][metric]
    if hours < 1/12:
        return 'Average/hour: collecting progress; ETA: calculating ⏲️'
    rate = completed / hours
    label = f'Average: {rate:.1f}/hour'
    if rate <= 0:
        return label + '; ETA: waiting for completions ⏲️'
    # Training registry rows have no declared total; never assume symbols
    # equal training jobs. A training launcher can supply its total later.
    total = s.get('training_total') if metric == 'training_registry_rows' else s['total_symbols']
    if metric == 'build_symbols':
        total = s.get('build_total_symbols', total)
    if not total:
        return label + '; ETA: awaiting total job count ⏲️'
    remaining = max(0, total - s['counts'][metric])
    if not remaining:
        return label + '; ETA: stage count complete ⏲️'
    finish = now + dt.timedelta(hours=remaining / rate)
    return label + f"; ETA: ~{finish:%b %d %H:%M} UTC ⏲️"


def render(s, previous, history=None):
    c, n = s['counts'], s['total_symbols']
    stages = sorted({p['stage'] for p in s['processes']})
    status = ', '.join(stages) if stages else 'IDLE/STOPPED: no campaign worker detected; watcher remains active'
    trial = s.get('worker_trial')
    transitioning = (trial or {}).get('phase') in ('draining_four_workers', 'preflight')
    if transitioning:
        status += '; ' + ('verifying inputs before five-worker trial' if trial['phase'] == 'preflight'
                          else 'finishing current symbols before five-worker trial')
    result = s['freeze_launcher_result']
    if result and result.get('returncode') != 0:
        status += f"; freeze launcher failed (exit {result.get('returncode')})"
    build_active = 'build/assembly launcher' in stages or 'build/assemble' in stages or 'assembly' in stages
    build_workers = sum(p['stage'] == 'build/assemble' for p in s['processes'])
    if s.get('build_result') and s['build_result'].get('returncode') != 0:
        status += f"; build/assembly failed (exit {s['build_result'].get('returncode')})"
    lines = [f"🧪🔬HealyLabs v6 - {s['time_utc'][:16].replace('T', ' ')} UTC💻📲", f'Active: {status}',
             f"Inventory {c['inventory_symbols']}/{n}" + (" ✅" if n and c['inventory_symbols'] == n else ""),
             f"Tick stores {c['tick_stores']}/{n}" + (" ✅" if n and c['tick_stores'] == n else ""),
             f"Freeze shards {c['freeze_shards']}/{n} 🧊",
             f"Built symbols {c['build_symbols']}/{s.get('build_total_symbols', n)} 🛠️",
             f"Trained: {c['training_registry_rows']}🎮",
             f"Model files: {c['model_files']} 🗂️",
             f"Free disk: {s['free_gib']} GiB 💾"]
    pace = pace_line(s, history if history is not None else ([previous] if previous else []))
    if transitioning:
        rate = trial['baseline']['average_per_hour']
        lines.insert(5, f'Previous four-worker average: {rate:.1f}/hour; ETA: recalculates after restart ⏲️')
    elif pace:
        stage_index = {'inventory_symbols': 2, 'tick_stores': 3, 'freeze_shards': 4,
                       'build_symbols': 5, 'training_registry_rows': 6}[active_metric(s)]
        lines.insert(stage_index + 1, pace)
    if build_active:
        target = (s.get('build_plan') or {}).get('resources', {}).get('symbol_workers', '?')
        lines.append(f'Build workers: {build_workers}/{target}')
        if not build_workers:
            phase = 'assembling/verifying dataset' if 'assembly' in stages or c['build_symbols'] >= s.get('build_total_symbols', n) else 'verifying inputs before worker startup'
            lines.append('Build phase: ' + phase)
            lines.insert(6, 'Average/hour: awaiting build completions; ETA: calculating ⏲️')
    freeze_workers = sum(p['stage'] == 'freeze' for p in s['processes'])
    if freeze_workers or transitioning:
        plan = s.get('freeze_resource_plan') or {}
        trial = s.get('worker_trial')
        target = trial.get('target_workers', '?') if trial else plan.get('symbol_workers', '?')
        lines.append(f"Freeze workers: {freeze_workers}/{target}")
        if transitioning:
            lines.append('Worker trial: input verification in progress; two-hour clock has not started'
                         if trial['phase'] == 'preflight' else
                         'Worker trial: draining current symbols; two-hour clock has not started')
        if trial:
            decision = trial.get('decision')
            if decision:
                lines.append('Worker trial: ' + decision.replace('_', ' '))
            elif trial.get('started_utc'):
                review = dt.datetime.fromisoformat(trial['started_utc']) + dt.timedelta(seconds=trial['trial_seconds'])
                lines.append(f"Worker trial: review {review:%b %d %H:%M} UTC ⏲️")
        if plan and not trial:
            lines.append(f"Freeze launch budget: {plan['planned_symbol_ram_gib']} GiB for workers + {plan['ram_reserve_gib']} GiB system headroom; {len(plan['reserved_cpus'])} logical CPUs excluded")
    elif s.get('parallel') and not (s.get('parallel_result') or {}).get('complete'):
        parallel = s['parallel']
        live = sum(p['stage'].startswith('tick store ') for p in s['processes'])
        lines.append(f"Symbol workers: {live}/{parallel['symbol_workers']}; download threads per symbol: {parallel['download_workers_per_symbol']}")
        if s.get('resource_plan'):
            plan = s['resource_plan']
            lines.append(f"System headroom: {len(plan['reserved_cpus'])} logical CPUs excluded from job affinity; {plan['ram_reserve_gib']} GiB available-RAM reserve")
    if previous:
        if c == previous['counts'] and s['latest_log_mtime'] == previous['latest_log_mtime']:
            lines.append('No observed count/log progress since previous report; stage may be computing or stopped.')
    if n and c['freeze_shards'] >= (n + 1) // 2 and not s['evidence_present'].get('baseline_spec'):
        lines.append('Post-freeze launchers ready; waiting for freeze completion 🛠️' if s.get('launchers_prepared') else
                     'HALFWAY FREEZE CHECKPOINT: prepare build/evaluation launchers; keep compute reserved for freeze until it completes.')
    return '\n'.join(lines)


def send_telegram(message):
    from dotenv import dotenv_values
    env = dotenv_values(ROOT / '.env')
    token, chat = env.get('TELEGRAM_BOT_TOKEN'), env.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        raise RuntimeError('Telegram credentials missing')
    request = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id': chat, 'text': message}).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.load(response)
        if result.get('ok') is not True:
            raise RuntimeError('Telegram rejected update')
    except Exception:
        # Never expose URLs containing bot credentials in tracebacks.
        raise RuntimeError('Telegram delivery failed; local report retained') from None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--campaign', required=True)
    ap.add_argument('--telegram', action='store_true')
    args = ap.parse_args()
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', args.campaign):
        ap.error('invalid campaign name')
    out = ROOT / 'logs/v6-progress' / args.campaign
    out.mkdir(parents=True, exist_ok=True)
    with (out / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior = read_json(out / 'latest.json')
        current = snapshot(ROOT, args.campaign, campaign_processes(args.campaign))
        history = []
        history_path = out / 'history.jsonl'
        if history_path.exists():
            for line in history_path.read_text().splitlines():
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # Retain useful history after an interrupted write.
        message = render(current, prior, history)
        temporary = out / 'latest.json.tmp'
        temporary.write_text(json.dumps(current, indent=2) + '\n')
        temporary.replace(out / 'latest.json')
        (out / 'progress.txt').write_text(message + '\n')
        with (out / 'history.jsonl').open('a') as f:
            f.write(json.dumps(current) + '\n')
        print(message, flush=True)
        if args.telegram:
            send_telegram(message)
            print('Telegram update delivered.', flush=True)


if __name__ == '__main__':
    main()
