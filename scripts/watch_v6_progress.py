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
    registry = base / 'runs/runs.csv'
    runs = 0
    if registry.exists():
        with registry.open() as f:
            runs = sum(1 for _ in csv.DictReader(f))
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
    latest = max((p.stat().st_mtime for p in logs), default=0)
    return {'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'campaign': campaign,
            'total_symbols': len(symbols), 'counts': counts, 'evidence_present': evidence,
            'processes': processes, 'freeze_launcher_result': result,
            'parallel': read_json(captures / 'parallel/status.json'),
            'resource_plan': read_json(captures / 'parallel/resource-plan.json'),
            'latest_log_mtime': latest, 'free_gib': round(shutil.disk_usage(root).free / 1024**3, 1)}


def render(s, previous):
    c, n = s['counts'], s['total_symbols']
    stages = sorted({p['stage'] for p in s['processes']})
    status = ', '.join(stages) if stages else 'IDLE/STOPPED: no campaign worker detected; watcher remains active'
    result = s['freeze_launcher_result']
    if result and result.get('returncode') != 0:
        status += f"; freeze launcher failed (exit {result.get('returncode')})"
    lines = [f"v6 progress — {s['time_utc'][:16]} UTC", s['campaign'], f'Active: {status}',
             f"Inventory {c['inventory_symbols']}/{n}; tick stores {c['tick_stores']}/{n}",
             f"Raw batches {c['capture_batches']:,}/{c['prepared_capture_batches']:,} planned so far ({c['prepared_symbols']}/{n} symbols prepared)",
             f"Freeze shards {c['freeze_shards']}/{n}; built symbols {c['build_symbols']}/{n}",
             f"Training registry rows: {c['training_registry_rows']}; model files: {c['model_files']}; free disk {s['free_gib']} GiB"]
    if s.get('parallel'):
        parallel = s['parallel']
        lines.append(f"Symbol workers: {len(parallel['active'])}/{parallel['symbol_workers']}; download threads per symbol: {parallel['download_workers_per_symbol']}")
        if s.get('resource_plan'):
            plan = s['resource_plan']
            lines.append(f"System headroom: {len(plan['reserved_cpus'])} logical CPUs excluded from job affinity; {plan['ram_reserve_gib']} GiB available-RAM reserve")
    if previous:
        delta = c['capture_batches'] - previous['counts']['capture_batches']
        lines.append(f'Raw batch change since last report: {delta:+,}')
        if c == previous['counts'] and s['latest_log_mtime'] == previous['latest_log_mtime']:
            lines.append('No observed count/log progress since previous report; stage may be computing or stopped.')
    if n and c['freeze_shards'] >= (n + 1) // 2:
        lines.append('HALFWAY FREEZE CHECKPOINT: prepare build/evaluation launchers; keep compute reserved for freeze until it completes.')
    lines.append('Artifacts present: ' + (', '.join(k for k, v in s['evidence_present'].items() if v) or 'none yet'))
    lines.append('Artifact presence is not a validation or launch verdict. Monitoring continues through stage gaps.')
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
        message = render(current, prior)
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
