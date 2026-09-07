"""Parallel symbol orchestration around the unchanged, pinned v6 tick pipeline.

Uses the existing capture scope, prepared tasks, raw bundles and stores in place.
Only scheduling changes. Final full-universe sealing and freeze launch retain
all existing gates. One process per symbol bounds materialization memory.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from nn_meta import config
from nn_meta import option_tick_dataset as d
from nn_meta.v6_expansion import from_environment, sha256
from options.data.massive_ticks import TickDataError, canonical_bytes
from scripts import run_v6_tick_capture as pinned
from scripts import materialize_v6_tick_store as streaming
from scripts.run_v6_full_freeze import seal
from scripts.plan_v6_option_requests import _require_expanded, _config_record, _source_hashes


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f'.tmp.{os.getpid()}')
    temporary.write_bytes(canonical_bytes(document) + b'\n')
    temporary.replace(path)


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def check_scope(inventory, policy, output):
    scope = json.loads((inventory / 'scope.json').read_bytes())
    if scope['config'] != _config_record() or scope['source_sha256'] != _source_hashes():
        raise TickDataError('inventory source/config changed')
    if set(scope['symbols']) != set(config.UNDERLYINGS):
        raise TickDataError('parallel full freeze requires exact full universe')
    expected = {'inventory_scope_sha256': sha256(inventory / 'scope.json'),
                'policy_sha256': sha256(policy), 'symbols': scope['symbols'],
                'capture_source_sha256': sha256(Path(pinned.__file__))}
    if json.loads((output / 'scope.json').read_bytes()) != expected:
        raise TickDataError('retained capture scope changed')
    return scope['symbols']


def symbol_order(symbols, output):
    # Work still requiring downloads comes first. Completed stores are fully
    # reverified later, and cannot be omitted from the final seal.
    return sorted(symbols, key=lambda s: ((output / 'stores' / s / 'manifest.json').exists(), s))


def available_bytes():
    return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                    if line.startswith('MemAvailable:'))) * 1024



def cpu_snapshot():
    result = {}
    for line in Path('/proc/stat').read_text().splitlines():
        fields = line.split()
        if fields[0].startswith('cpu') and fields[0][3:].isdigit():
            values = list(map(int, fields[1:9]))
            result[int(fields[0][3:])] = (sum(values), values[3] + values[4])
    return result


def resource_plan(available, cores, utilization, requested=4, per_worker_gib=3):
    # Leave two physical cores (including both SMT siblings) out of job affinity.
    ranked = sorted(cores, key=lambda core: sum(utilization.get(cpu, 0) for cpu in cores[core]))
    usable = ranked[:-2] if len(ranked) > 2 else []
    cpus = sorted(cpu for core in usable for cpu in cores[core])
    idle_threads = sum(1 - utilization.get(cpu, 0) for cpu in cpus)
    ram_slots = max(0, (available - 4*1024**3) // (per_worker_gib*1024**3))
    cpu_slots = int(idle_threads // 2)
    workers = min(requested, ram_slots, cpu_slots, len(usable))
    if workers < 2:
        raise TickDataError('insufficient safe headroom for at least two symbol processes')
    groups = [[] for _ in range(workers)]
    for index, core in enumerate(usable):
        groups[index % workers].extend(cores[core])
    return {'symbol_workers': workers, 'worker_cpu_groups': [sorted(g) for g in groups],
            'reserved_cpus': sorted(set(cpu for values in cores.values() for cpu in values) - set(cpus)),
            'physical_cores': len(cores), 'logical_cpus': sum(map(len, cores.values())),
            'available_ram_gib': round(available / 1024**3, 2), 'ram_reserve_gib': 4,
            'estimated_ram_per_symbol_gib': per_worker_gib, 'planned_symbol_ram_gib': workers*per_worker_gib,
            'sampled_idle_job_threads': round(idle_threads, 2)}


def measure_resources(requested, per_worker_gib=3):
    first = cpu_snapshot()
    time.sleep(1)
    second = cpu_snapshot()
    allowed = os.sched_getaffinity(0)
    cores, usage = {}, {}
    for cpu in allowed:
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        identity = (int((topology/'physical_package_id').read_text()),
                    int((topology/'core_id').read_text()))
        cores.setdefault(identity, []).append(cpu)
        total = second[cpu][0] - first[cpu][0]
        idle = second[cpu][1] - first[cpu][1]
        usage[cpu] = max(0., min(1., 1-idle/total)) if total else 0.
    return resource_plan(available_bytes(), cores, usage, requested, per_worker_gib)

def one_symbol(symbol, inventory, policy, output, workers):
    with lock(output / 'parallel' / 'locks' / f'{symbol}.lock'):
        status = output / 'parallel' / 'symbols' / f'{symbol}.json'
        def update(phase, **extra):
            write_json(status, {'symbol': symbol, 'pid': os.getpid(), 'phase': phase,
                                'time_utc': datetime.now(timezone.utc).isoformat(), **extra})
        update('verifying_task')
        task, plan = pinned.prepare_symbol(inventory / symbol, policy, output / 'prepared' / symbol)
        store = output / 'stores' / symbol
        reused = (store / 'manifest.json').exists()
        if store.exists() and not reused:
            # A killed materializer can leave files before writing its completion
            # marker. Preserve them; never accept or overwrite an incomplete store.
            preserved = output / 'parallel' / 'incomplete_stores' / f'{symbol}-{time.time_ns()}'
            preserved.parent.mkdir(parents=True, exist_ok=True)
            store.rename(preserved)
        if reused:
            update('verifying_completed_store')
            manifest = json.loads((store / 'manifest.json').read_bytes())
        else:
            raw = output / 'captures' / symbol
            raw.mkdir(parents=True, exist_ok=True)
            total = len(plan['capture_batches'])
            update('capturing', captured_batches=0, total_batches=total)
            captures = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(pinned.capture_one, batch, raw) for batch in plan['capture_batches']]
                try:
                    for future in as_completed(futures):
                        captures.append(future.result())
                        if len(captures) % 100 == 0:
                            update('capturing', captured_batches=len(captures), total_batches=total)
                            print(json.dumps({'symbol': symbol, 'captured_batches': len(captures),
                                              'total_batches': total}), flush=True)
                except BaseException:
                    for future in futures:
                        future.cancel()
                    raise
            update('materializing', captured_batches=total, total_batches=total)
            manifest = streaming.materialize(task, sorted(captures), store)
        d.load_feature_store(store, expected_task_sha256=task['task_sha256'],
                             expected_store_sha256=manifest['store_sha256'])
        reference = {'directory': str(store), 'task_sha256': task['task_sha256'],
                     'store_sha256': manifest['store_sha256']}
        update('complete', rows=manifest['row_count'], reused=reused, reference=reference)
        print(json.dumps({'symbol': symbol, 'store_complete': True, 'rows': manifest['row_count'],
                          'reused': reused}), flush=True)
        return reference


def stop_children(active):
    for process, _ in active.values():
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
    deadline = time.monotonic() + 120
    for process, log in active.values():
        try:
            process.wait(timeout=max(1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait()
        log.close()


def run_parallel(args, symbols):
    output = args.output
    snapshot = output / 'parallel' / 'scheduler-source.txt'
    source = Path(__file__).read_bytes()
    if snapshot.exists() and snapshot.read_bytes() != source:
        raise TickDataError('parallel scheduler changed; review before resuming')
    if not snapshot.exists():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source)
    resources = measure_resources(args.symbol_workers)
    count = resources['symbol_workers']
    write_json(output / 'parallel' / 'resource-plan.json', resources)
    print(json.dumps({'symbol_workers': count, 'download_workers_per_symbol': args.workers,
                      'maximum_download_workers': count*args.workers, 'resources': resources, 'freeze_started': False}), flush=True)
    queue = iter(symbol_order(symbols, output))
    active, results = {}, {}
    exhausted = False
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
    try:
        while active or not exhausted:
            if available_bytes() < 4*1024**3:
                raise TickDataError('parallel capture stopped at 4 GiB available RAM reserve')
            while len(active) < count and not exhausted:
                if active and available_bytes() < 7*1024**3:
                    break
                symbol = next(queue, None)
                if symbol is None:
                    exhausted = True
                    break
                assigned = {getattr(p, '_slot', -1) for p, _ in active.values()}
                slot = next(n for n in range(count) if n not in assigned)
                affinity = ','.join(map(str, resources['worker_cpu_groups'][slot]))
                command = ['taskset', '--cpu-list', affinity, sys.executable, '-m', 'scripts.run_v6_parallel_freeze',
                           '--inventory', str(args.inventory), '--policy', str(args.policy),
                           '--output', str(output), '--workers', str(args.workers), '--symbol', symbol, '--run']
                log = (output / 'parallel' / f'{symbol}.log').open('ab')
                process = subprocess.Popen(command, cwd=config.ROOT.parent, env=env,
                                           stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
                process._slot = slot
                active[symbol] = process, log
            write_json(output / 'parallel' / 'status.json', {
                'time_utc': datetime.now(timezone.utc).isoformat(), 'supervisor_pid': os.getpid(),
                'active': {s: p.pid for s, (p, _) in active.items()},
                'symbol_workers': count, 'download_workers_per_symbol': args.workers,
                'verified_symbols': len(results), 'total_symbols': len(symbols),
                'available_ram_gib': round(available_bytes()/1024**3, 2), 'freeze_started': False})
            for symbol, (process, log) in list(active.items()):
                code = process.poll()
                if code is None:
                    continue
                log.close()
                del active[symbol]
                if code:
                    raise TickDataError(f'{symbol} worker failed ({code}); see parallel/{symbol}.log')
                state = json.loads((output / 'parallel' / 'symbols' / f'{symbol}.json').read_bytes())
                if state.get('phase') != 'complete' or state.get('pid') != process.pid:
                    raise TickDataError('worker exited without matching verified completion')
                results[symbol] = state['reference']
                print(json.dumps({'symbol': symbol, 'verified_symbols': len(results),
                                  'total_symbols': len(symbols)}), flush=True)
            if active or not exhausted:
                time.sleep(2)
    finally:
        stop_children(active)
    if Path(__file__).read_bytes() != source:
        raise TickDataError('parallel scheduler changed during execution')
    check_scope(args.inventory, args.policy, output)
    if set(results) != set(symbols):
        raise TickDataError('incomplete parallel results')
    target = output / 'manifest.json'
    report = {'complete': True, 'stores': results, 'freeze_started': False}
    if target.exists() and json.loads(target.read_bytes()) != report:
        raise TickDataError('completed capture manifest changed')
    if not target.exists():
        write_json(target, report)
    write_json(output / 'parallel' / 'result.json', {'complete': True, 'symbols': len(results),
                                                   'scheduler_sha256': sha256(snapshot)})



def assert_no_other_supervisor(output):
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            args = (entry/'cmdline').read_bytes().decode().split('\0')
            if '-m' not in args or '--output' not in args or '--symbol' in args:
                continue
            module = args[args.index('-m')+1]
            if module not in ('scripts.run_v6_full_freeze', 'scripts.run_v6_tick_capture',
                              'scripts.run_v6_parallel_freeze'):
                continue
            target = Path(args[args.index('--output')+1])
            if not target.is_absolute():
                target = (entry/'cwd').resolve() / target
            if target.resolve() == output.resolve():
                raise TickDataError(f'another capture supervisor owns this output: PID {entry.name}')
        except (OSError, UnicodeError, IndexError):
            continue

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--symbol-workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--workers', type=int, choices=range(1, 33), default=16)
    parser.add_argument('--symbol')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    args.inventory, args.policy, args.output = (p.absolute() for p in (args.inventory, args.policy, args.output))
    _require_expanded()
    if not config.DATA_CANDIDATE:
        raise TickDataError('repaired candidate required')
    from dotenv import load_dotenv
    load_dotenv()
    if args.symbol:
        scope = json.loads((args.inventory / 'scope.json').read_bytes())
        if args.symbol not in scope['symbols']:
            raise TickDataError('symbol is outside sealed scope')
        if args.run:
            one_symbol(args.symbol, args.inventory, args.policy, args.output, args.workers)
        return
    symbols = check_scope(args.inventory, args.policy, args.output)
    planning = from_environment()
    if not args.run:
        print(json.dumps({'symbols': len(symbols), 'symbol_workers': args.symbol_workers,
                          'download_workers_per_symbol': args.workers, 'run': False}))
        return
    with lock(args.output / 'parallel' / 'supervisor.lock'):
        assert_no_other_supervisor(args.output)
        try:
            run_parallel(args, symbols)
            final, digest = seal(planning, args.inventory, args.output)
            freeze_resources = measure_resources(args.symbol_workers, per_worker_gib=5)
            write_json(args.output / 'parallel' / 'freeze-resource-plan.json', freeze_resources)
            freeze_cpus = sorted(cpu for group in freeze_resources['worker_cpu_groups'] for cpu in group)
            environment = dict(os.environ, NN_META_V6_INPUTS=str(final), NN_META_V6_INPUTS_SHA256=digest,
                               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
            print(json.dumps({'stage': 'launching_full_freeze', 'inputs': str(final), 'sha256': digest}), flush=True)
            result = subprocess.run(['taskset', '--cpu-list', ','.join(map(str, freeze_cpus)),
                                     'bash', 'scripts/run_freeze_v6_local.sh', '--workers',
                                     str(freeze_resources['symbol_workers']), '--run'], env=environment)
            write_json(args.output / 'freeze-launcher-result.json',
                       {'returncode': result.returncode, 'freeze_completed': result.returncode == 0})
            raise SystemExit(result.returncode)
        except BaseException as exc:
            if not isinstance(exc, SystemExit) or exc.code:
                write_json(args.output / 'parallel' / 'failure.json',
                           {'time_utc': datetime.now(timezone.utc).isoformat(),
                            'error_type': type(exc).__name__, 'message': str(exc)})
            raise


if __name__ == '__main__':
    main()
