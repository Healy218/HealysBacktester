#!/usr/bin/env python3
"""Explicit kernel-pair recovery; original V7 stores and scheduler stay immutable.

Validation writes new replay artifacts on the actual current runtime. Production
requires their sealed byte-parity proof. No global runtime override is installed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if __name__ == '__main__':
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
from scripts import run_v7_entry_demand as original
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
from nn_meta.v7.provenance import runtime_manifest
from nn_meta.v7.entry_demand import EntryDemand, build_entry_demand

OLD_PLATFORM = 'Linux-7.2.6-1-cachyos-x86_64-with-glibc2.44'
NEW_PLATFORM = 'Linux-7.2.7-1-cachyos-x86_64-with-glibc2.44'
CASES = ('BBG004FPTZB8', 'BBG010FXVQ98', 'BBG000B9YJ35', 'BBG000BF8TF5')
read, write = original.read, original.write


def runtime_allowed(saved, current):
    """Only the approved kernel pair; interpreter, libc and packages stay exact."""
    if identity(saved) == identity(current):
        return
    if (saved.get('platform') != OLD_PLATFORM or current.get('platform') != NEW_PLATFORM or
            identity({k: v for k, v in saved.items() if k != 'platform'}) !=
            identity({k: v for k, v in current.items() if k != 'platform'})):
        raise ValueError('Runtime drift exceeds the approved kernel pair')


class KernelCatalogProof(original.CatalogProof):
    def __init__(self, completion, evidence=None):
        super().__init__(completion)
        self.bindings[str(Path(__file__).resolve())] = sha(__file__)
        if evidence is not None:
            verify_kernel_proof(evidence, completion)
            self.bindings[str(Path(evidence).resolve() / 'complete.json')] = sha(Path(evidence) / 'complete.json')

    def current_bindings(self, path, declaration):
        current = runtime_manifest()
        runtime_allowed(declaration['runtime'], current)
        # Run all existing receipt/source/input checks after separately checking
        # the runtime exception. The saved declaration is never modified.
        return super().current_bindings(path, dict(declaration, runtime=current))


class KernelEntryDemand(EntryDemand):
    def verify_bindings(self):
        runtime_allowed(self.declaration['runtime'], runtime_manifest())
        if any(sha(p) != h for p, h in self.declaration['inputs'].items()):
            raise ValueError('Entry demand source or input changed')


def verify_kernel_proof(path, completion):
    path = Path(path)
    verify(path)
    report = read(path / 'report.json')
    if (report.get('schema') != 'v7-kernel-demand-equivalence-v1' or report.get('passed') is not True or
            report['recovery_source_sha256'] != sha(__file__) or
            report['completion_sha256'] != sha(Path(completion) / 'complete.json') or
            report['original_scheduler_sha256'] != sha(original.__file__) or
            identity(report['current_runtime']) != identity(runtime_manifest()) or
            report['old_platform'] != OLD_PLATFORM or report['new_platform'] != NEW_PLATFORM or
            {r['security_id'] for r in report['cases']} != set(CASES) or len(report['cases']) != len(CASES)):
        raise ValueError('Foreign or stale kernel equivalence proof')
    for row in report['cases']:
        if not row['sqlite_byte_equal'] or not row['report_equal'] or not row['exports_byte_equal']:
            raise ValueError('Kernel replay parity failed')
    if any(sha(p) != h for p, h in report['inputs'].items()):
        raise ValueError('Kernel equivalence evidence changed')
    return report


def validate_kernel(args):
    """Authorized experiment only; this does not admit production on its own."""
    proof = KernelCatalogProof(args.completion)
    stage = args.output
    destination = args.kernel_proof
    if destination.exists():
        verify_kernel_proof(destination, args.completion)
        return
    replay = destination.with_name(destination.name + '-replays')
    active = read(args.active)
    chain = ROOT / active['chain']
    if sha(chain / 'complete.json') != active['chain_receipt_sha256']:
        raise ValueError('Active chain changed')
    inputs = dict(proof.bindings)
    cases = []
    for sid in CASES:
        old = KernelEntryDemand(stage / 'demand' / sid)
        if old.declaration['runtime']['platform'] != OLD_PLATFORM:
            raise ValueError('Replay reference must use the exact old kernel')
        old.export_requests(stage / 'requests' / sid)
        stores = original.proven_stores(proof, sid)
        report = build_entry_demand(replay / 'demand' / sid, stores, chain, reserve_bytes=original.RESERVE)
        new = EntryDemand(replay / 'demand' / sid)  # Strict current-runtime reader.
        new.export_requests(replay / 'requests' / sid)
        old_sqlite = sha(old.path / 'demand.sqlite3')
        new_sqlite = sha(new.path / 'demand.sqlite3')
        old_export = read(stage / 'requests' / sid / 'report.json')
        new_export = read(replay / 'requests' / sid / 'report.json')
        result = dict(security_id=sid, proposals=report['proposals'], requests=report['requests'],
                      sqlite_sha256=old_sqlite, sqlite_byte_equal=old_sqlite == new_sqlite,
                      report_equal=old.report == report, exports_byte_equal=old_export == new_export)
        if not all(result[k] for k in ('sqlite_byte_equal', 'report_equal', 'exports_byte_equal')):
            raise ValueError(f'Kernel replay differs: {sid}')
        for root in (old.path, new.path, stage / 'requests' / sid, replay / 'requests' / sid):
            doc = verify(root)
            inputs[str((root / 'complete.json').resolve())] = sha(root / 'complete.json')
            inputs.update({str((root / name).resolve()): digest for name, digest in doc['files'].items()})
        inputs.update(old.declaration['inputs'])
        inputs.update(new.declaration['inputs'])
        cases.append(result)
        print(json.dumps(result), flush=True)
    report = dict(schema='v7-kernel-demand-equivalence-v1', passed=True,
                  checked_at=datetime.now(timezone.utc).isoformat(), cases=cases,
                  old_platform=OLD_PLATFORM, new_platform=NEW_PLATFORM,
                  current_runtime=runtime_manifest(), recovery_source_sha256=sha(__file__),
                  original_scheduler_sha256=sha(original.__file__),
                  completion_sha256=sha(args.completion / 'complete.json'), inputs=inputs,
                  scope='Frozen catalog consumption and entry demand only; no feature regeneration or training',
                  research_ready=False)
    if any(sha(p) != h for p, h in inputs.items()):
        raise ValueError('Kernel replay parents changed')
    with transaction(destination) as temp:
        write(temp / 'report.json', report)
        receipt(temp, dict(identity=identity(report), research_ready=False))


def run_security(args):
    sid, output = args.worker, args.output
    proof = KernelCatalogProof(args.completion, args.kernel_proof)
    if sid not in proof.security_ids:
        raise ValueError('Unknown security')
    legacy = dict(security_id=sid, completion_sha256=sha(args.completion / 'complete.json'),
                  active_sha256=sha(args.active), scheduler_sha256=sha(original.__file__))
    binding = dict(legacy, recovery_source_sha256=sha(__file__),
                   kernel_proof_sha256=sha(args.kernel_proof / 'complete.json'))
    checkpoint = output / 'checkpoints' / sid
    if checkpoint.exists():
        doc = verify(checkpoint)
        if doc['identity'] not in (identity(legacy), identity(binding)):
            raise ValueError('Foreign completed checkpoint')
        result = read(checkpoint / 'result.json')
        if result['security_id'] != sid or any(sha(p) != h for p, h in result['receipts'].items()):
            raise ValueError('Completed security receipt changed')
        demand = KernelEntryDemand(output / 'demand' / sid)
        demand.export_requests(output / 'requests' / sid)
        return
    stores = original.proven_stores(proof, sid)
    if any(s.features.declaration['inputs'].get(str(args.active)) != sha(args.active) for s in stores):
        raise ValueError('Active scope changed')
    active = read(args.active)
    chain = ROOT / active['chain']
    if sha(chain / 'complete.json') != active['chain_receipt_sha256']:
        raise ValueError('Chain changed')
    path = output / 'demand' / sid
    started = time.monotonic()
    if path.exists():
        # An interruption can occur after demand seals but before export/checkpoint.
        demand = KernelEntryDemand(path)
        if (demand.declaration['security_id'] != sid or
                demand.declaration['proposal_stores'] != [str(s.path.resolve()) for s in stores]):
            raise ValueError('Foreign uncheckpointed demand')
        report = demand.report
    else:
        report = build_entry_demand(path, stores, chain, reserve_bytes=args.reserve_bytes)
        demand = EntryDemand(path)
    exported = demand.export_requests(output / 'requests' / sid)
    proof.check_evidence()
    result = dict(security_id=sid, report=report, export_batches=len(exported['batches']),
                  seconds=time.monotonic() - started,
                  receipts={str((p / 'complete.json').resolve()): sha(p / 'complete.json')
                            for p in (path, output / 'requests' / sid)},
                  kernel_proof_sha256=binding['kernel_proof_sha256'])
    with transaction(checkpoint) as temp:
        write(temp / 'result.json', result)
        receipt(temp, dict(identity=identity(binding), research_ready=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--completion', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kernel-proof', type=Path, required=True)
    parser.add_argument('--active', type=Path, default=ROOT / 'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json')
    parser.add_argument('--storage-plan', type=Path)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--validate-kernel', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    parser.add_argument('--reserve-bytes', type=int, default=original.RESERVE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.chdir(ROOT)
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    for name in ('completion', 'output', 'kernel_proof', 'active'):
        setattr(args, name, getattr(args, name).resolve())
    if (not 1 <= args.workers <= 4 or args.reserve_bytes < original.RESERVE or
            any(not p.is_relative_to(ROOT / 'nn_meta/validation') for p in (args.output, args.kernel_proof)) or
            args.validate_kernel and (args.run or args.worker)):
        parser.error('Bounded validation paths and separate validation/production modes required')
    if args.validate_kernel:
        validate_kernel(args)
        return 0
    if args.worker:
        run_security(args)
        return 0
    proof = KernelCatalogProof(args.completion, args.kernel_proof)
    if args.storage_plan is None:
        parser.error('Sealed storage plan required')
    verify(args.storage_plan)
    plan = read(args.storage_plan / 'report.json')
    cap = plan['stage_output_limit_bytes']
    if (plan['schema'] != 'v7-demand-storage-plan-v1' or plan['securities'] != 591 or
            plan['stress_forecast_bytes'] > cap or
            plan['baseline_project_allocated_bytes'] + cap > plan['total_project_budget_bytes'] or
            plan['required_free_reserve_bytes'] < original.RESERVE or
            any(sha(p) != h for p, h in plan['inputs'].items())):
        raise ValueError('Invalid recovery allocation or changed planning inputs')
    used, free = original.output_bytes(args.output), shutil.disk_usage(ROOT).free
    if cap <= used or free - (cap - used) < original.RESERVE:
        raise ValueError('Stage allocation exceeds available disk reserve')
    legacy_plan = read(args.output / 'declaration/plan.json')
    verify(args.output / 'declaration', expected_identity=identity(legacy_plan))
    if (legacy_plan['securities'] != proof.security_ids or
            legacy_plan['catalog_root'] != str(proof.root) or
            legacy_plan['scheduler_sha256'] != sha(original.__file__) or
            legacy_plan['active_sha256'] != sha(args.active) or
            legacy_plan['completion_sha256'] != sha(args.completion / 'complete.json')):
        raise ValueError('Original scheduler declaration changed')
    print(json.dumps(dict(selected=len(proof.security_ids), stage_budget_bytes=cap,
                          existing_stage_bytes=used, free_bytes=free)), flush=True)
    if not args.run:
        return 0
    recovery = args.output / 'kernel-recovery'
    recovery.mkdir(exist_ok=True)
    binding = dict(kernel_proof_sha256=sha(args.kernel_proof / 'complete.json'),
                   storage_plan_sha256=sha(args.storage_plan / 'complete.json'),
                   original_declaration_sha256=sha(args.output / 'declaration/complete.json'),
                   recovery_source_sha256=sha(__file__))
    with (args.output / 'scheduler.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (recovery / 'declaration').exists():
            verify(recovery / 'declaration', expected_identity=identity(binding))
        else:
            with transaction(recovery / 'declaration') as temp:
                write(temp / 'binding.json', binding)
                receipt(temp, dict(identity=identity(binding)))
        pending = original.select_securities(proof, None)
        running, completed, failed = {}, [], {}
        last_print = 0
        floor = max(original.RESERVE, free - (cap - used))
        def progress(state):
            value = dict(stage='v7-3-kernel-recovery', state=state, selected=591,
                         completed=len(completed), completed_ids=completed,
                         running=sorted(running), pending=len(pending), failed=failed,
                         full_scope_complete=len(completed) == 591,
                         output_bytes=original.output_bytes(args.output), max_output_bytes=cap,
                         updated_at=datetime.now(timezone.utc).isoformat(), research_ready=False)
            write(recovery / 'progress.json', value)
            return value
        try:
            while pending or running:
                if original.output_bytes(args.output) >= cap or shutil.disk_usage(ROOT).free < floor:
                    raise RuntimeError('Stage budget/reserve exhausted; partial evidence retained')
                while pending and len(running) < args.workers and not failed:
                    sid = pending.pop(0)
                    log = (recovery / f'{sid}.log').open('a')
                    command = [sys.executable, str(Path(__file__).resolve()), '--completion', str(args.completion),
                               '--output', str(args.output), '--kernel-proof', str(args.kernel_proof),
                               '--active', str(args.active), '--reserve-bytes', str(floor), '--worker', sid]
                    running[sid] = (subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT), log)
                for sid, (process, log) in list(running.items()):
                    code = process.poll()
                    if code is None:
                        continue
                    log.close(); del running[sid]
                    if code:
                        failed[sid] = dict(exit_code=code, log=str(recovery / f'{sid}.log'))
                    else:
                        completed.append(sid)
                state = progress('running')
                if time.monotonic() - last_print >= 30:
                    print(json.dumps({k: v for k, v in state.items() if k != 'completed_ids'}), flush=True)
                    last_print = time.monotonic()
                if failed:
                    raise RuntimeError('Recovery worker failed')
                if pending or running:
                    time.sleep(2)
            proof.check_evidence()
            print(json.dumps(progress('complete')), flush=True)
        except BaseException as exc:
            for process, _ in running.values():
                process.terminate()
            for process, log in running.values():
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
                log.close()
            failed['scheduler'] = dict(error=type(exc).__name__, reason=str(exc))
            running.clear()
            progress('failed')
            raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
