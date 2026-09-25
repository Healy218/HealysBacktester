#!/usr/bin/env python3
"""Checkpoint V7 entry demand using the exact completed catalog's loader proofs.

No acquisition or execution-path completeness is implied. Frozen feature readers
and demand math are unchanged; the explicit downstream view binds current files
AND the immutable historical declarations and equivalence evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
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
MINUTES = (5, 15, 30)
RESERVE = 100 * 1024**3
LOADER_OLD = 'f49df275b6c80b364a75f76058fd9c14874cbfe2716d07794958b7722488c4ca'
LOADER_CURRENT = '3c77df2238e498348a74fbea544e68fa1505529344ac19061091f5b082eaca73'
REUSE_OLD = '73d241359cea764adcada0d01140f66f392daeb9f62e4551bd1e300e028775bf'
REUSE_CURRENT = '6a515c5affc33c821870f5ddd8d4cf5ebd9461ae3852b102fcdf4b6097125585'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


class CatalogProof:
    """Only the 415 reuse + ten equivalence cases in the completed gate qualify."""
    def __init__(self, completion):
        from nn_meta.v7.storage import sha, verify
        self.completion = Path(completion).resolve()
        verify(self.completion)
        gate = read(self.completion / 'gate.json')
        if (gate.get('schema') != 'v7-2-completion-v1' or
                gate.get('v7_2_complete') is not True or gate.get('ready_for_v7_3') is not True):
            raise ValueError('Completed V7-2 gate required')
        self.root = Path(gate['catalog_root']).resolve()
        self.bindings = {str(self.completion / 'complete.json'): sha(self.completion / 'complete.json'),
                         str(self.completion / 'gate.json'): sha(self.completion / 'gate.json')}
        self.bindings.update(gate['inputs'])
        catalog_gates = [Path(p) for p in gate['inputs'] if Path(p).name == 'v7-2-final-deep-gate-20260925.json']
        if len(catalog_gates) != 1:
            raise ValueError('Exact catalog gate required')
        self.check_evidence()
        catalog_gate = read(catalog_gates[0])
        if catalog_gate.get('catalog_subgate_passed') is not True:
            raise ValueError('Catalog gate failed')
        for name, digest in catalog_gate['reports'].items():
            if Path(name).name != name:
                raise ValueError('Invalid proof report path')
            self.bindings[str(catalog_gates[0].parent / name)] = digest
        self.check_evidence()
        base = catalog_gates[0].parent
        reuse = read(base / 'v7-2-catalog-reuse-20260924.json')
        equivalence = read(base / 'v7-2-historical-loader-equivalence-20260925.json')
        deep = read(base / 'v7-2-full-catalog-deep-audit-20260925.json')
        self.reused = reuse['securities']
        self.extra = set(equivalence['security_ids'])
        rows = deep['audited_receipts']
        self.receipts = {(r['security_id'], r['minutes']): r for r in rows}
        self.security_ids = sorted({sid for sid, _ in self.receipts})
        if (Path(reuse['output']).resolve() != self.root or len(self.reused) != 415 or
                len(self.extra) != 10 or self.extra & self.reused.keys() or
                equivalence['proved'] != 10 or equivalence['target'] != 10 or
                equivalence['old_loader_sha256'] != LOADER_OLD or
                equivalence['current_loader_sha256'] != LOADER_CURRENT or
                deep.get('technical_store_gate_passed') is not True or
                len(rows) != 1773 or len(self.receipts) != 1773 or len(self.security_ids) != 591 or
                set(self.receipts) != {(sid, m) for sid in self.security_ids for m in MINUTES} or
                not (self.reused.keys() | self.extra) <= set(self.security_ids) or
                gate['security_count'] != 591 or gate['store_count'] != 1773):
            raise ValueError('Incomplete or foreign catalog equivalence proof')
        for sid, timeframes in self.reused.items():
            for minute in MINUTES:
                expected = self.receipts[sid, minute]
                if timeframes[str(minute)] != dict(feature=expected['feature_receipt_sha256'],
                                                   proposal=expected['proposal_receipt_sha256']):
                    raise ValueError('Reuse proof differs from deep audited receipts')

    def check_evidence(self):
        from nn_meta.v7.storage import sha
        if any(sha(p) != h for p, h in self.bindings.items()):
            raise ValueError('Catalog completion/equivalence evidence changed')

    def check_store(self, path, declaration):
        from nn_meta.v7.storage import sha
        sid, minute = declaration['security_id'], declaration['minutes']
        expected = self.receipts.get((sid, minute))
        base = self.root / sid / str(minute)
        if (expected is None or Path(path).resolve() != base / 'features' or
                sha(base / 'features/summary/complete.json') != expected['feature_receipt_sha256'] or
                sha(base / 'proposals/summary/complete.json') != expected['proposal_receipt_sha256']):
            raise ValueError('Store is not an exact deep-audited catalog parent')

    def current_bindings(self, path, declaration):
        """Validate every input; translate only two exact reviewed source pairs."""
        from nn_meta.v7.storage import sha, identity
        from nn_meta.v7.provenance import runtime_manifest
        self.check_evidence()
        self.check_store(path, declaration)
        if identity(runtime_manifest()) != identity(declaration['runtime']):
            raise ValueError('Feature-store runtime changed')
        sid = declaration['security_id']
        translated = {}
        for group in ('inputs', 'sources'):
            translated[group] = {}
            for filename, recorded in declaration[group].items():
                actual = sha(filename)
                if actual != recorded:
                    loader = (Path(filename).resolve() == ROOT / 'scripts/build_v7_proposals.py'
                              and recorded == LOADER_OLD and actual == LOADER_CURRENT
                              and (sid in self.reused or sid in self.extra))
                    audit = (Path(filename).resolve() == ROOT / 'nn_meta/v7/catalog_reuse.py'
                             and recorded == REUSE_OLD and actual == REUSE_CURRENT and sid in self.extra)
                    if not (loader or audit):
                        raise ValueError(f'Unproved feature source/input drift: {sid}: {filename}')
                translated[group][filename] = actual
        return translated


def proven_stores(proof, sid):
    from nn_meta.v7.proposal_store import StoredFeatures, StoredProposals
    from nn_meta.v7.storage import sha

    class HistoricalFeatures(StoredFeatures):
        def verify_bindings(self):
            proof.current_bindings(self.path, self.declaration)

    class DemandFeatureView:
        """Demand-only lineage view, never a replacement feature-store receipt.

        All semantic fields are unchanged. Current dependency hashes plus proof
        files are bound downstream. _parents also binds every historical store
        receipt and declaration, preserving the recorded original hashes.
        """
        def __init__(self, features):
            self.original = features
            translated = proof.current_bindings(features.path, features.declaration)
            self.declaration = dict(features.declaration, **translated)
            self.declaration['inputs'] = dict(self.declaration['inputs'], **proof.bindings)
            self.declaration['sources'][str(Path(__file__).resolve())] = sha(__file__)

        def verify_bindings(self):
            self.original.verify_bindings()
            if any(sha(p) != h for group in ('inputs', 'sources')
                   for p, h in self.declaration[group].items()):
                raise ValueError('Downstream demand proof bindings changed')

        def __getattr__(self, name):
            return getattr(self.original, name)

    if sid not in proof.security_ids:
        raise ValueError('Unknown catalog security')
    return [StoredProposals(proof.root / sid / str(m) / 'proposals',
                features=DemandFeatureView(HistoricalFeatures(proof.root / sid / str(m) / 'features')))
            for m in MINUTES]


def run_security(completion, active, output, sid, reserve_bytes):
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.entry_demand import build_entry_demand, EntryDemand
    from nn_meta.v7.storage import sha, verify, receipt, transaction, identity
    proof = CatalogProof(completion)
    active = Path(active).resolve()
    chain = ROOT / read(active)['chain']
    if sha(chain / 'complete.json') != read(active)['chain_receipt_sha256']:
        raise ValueError('Active chain receipt changed')
    binding = dict(security_id=sid, completion_sha256=sha(Path(completion) / 'complete.json'),
                   active_sha256=sha(active), scheduler_sha256=sha(__file__))
    output = Path(output)
    demand_path, export_path = output / 'demand' / sid, output / 'requests' / sid
    checkpoint = output / 'checkpoints' / sid
    if checkpoint.exists():
        verify(checkpoint, expected_identity=identity(binding))
        result = read(checkpoint / 'result.json')
        for p, digest in result['receipts'].items():
            if sha(p) != digest:
                raise ValueError('Completed security receipt changed')
        demand = EntryDemand(demand_path)
        demand.export_requests(export_path)
        return result
    stores = proven_stores(proof, sid)
    for store in stores:
        if store.features.declaration['inputs'].get(str(active)) != sha(active):
            raise ValueError('Store did not bind the active scope')
    started = time.monotonic()
    report = build_entry_demand(demand_path, stores, chain, reserve_bytes=reserve_bytes)
    exported = EntryDemand(demand_path).export_requests(export_path)
    proof.check_evidence()
    result = dict(security_id=sid, report=report, export_batches=len(exported['batches']),
                  seconds=time.monotonic() - started,
                  receipts={str(p / 'complete.json'): sha(p / 'complete.json')
                            for p in (demand_path, export_path)})
    with transaction(checkpoint) as temp:
        write(temp / 'result.json', result)
        receipt(temp, dict(identity=identity(binding), research_ready=False))
    return result


def output_bytes(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def select_securities(proof, requested):
    selected = requested or proof.security_ids
    if len(selected) != len(set(selected)) or not set(selected) <= set(proof.security_ids):
        raise ValueError('Requested securities must be distinct catalog members')
    # Small jobs first; every member stays in scope for an unrestricted run.
    return sorted(selected, key=lambda sid: (sum(proof.receipts[sid, m]['proposals']
                                                 for m in MINUTES), sid))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--completion', type=Path, required=True)
    parser.add_argument('--active', type=Path, default=ROOT / 'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    parser.add_argument('--max-output-bytes', type=int, required=True,
                        help='Measured allocation for this stage, including partials and exports')
    parser.add_argument('--security-id', action='append', help='Explicit validation subset; full scope remains 591')
    parser.add_argument('--run', action='store_true', help='Default is read-only planning')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    parser.add_argument('--reserve-bytes', type=int, default=RESERVE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.chdir(ROOT)
    args.output = args.output.resolve()
    if (not args.output.is_relative_to(ROOT / 'nn_meta/validation') or
            not 1 <= args.workers <= 4 or args.max_output_bytes <= 0 or args.reserve_bytes < RESERVE):
        parser.error('Require validation output, 1–4 workers, positive stage budget and 100 GiB reserve')
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import identity, sha, receipt, transaction, verify
    if args.worker:
        run_security(args.completion, args.active, args.output, args.worker, args.reserve_bytes)
        return 0
    proof = CatalogProof(args.completion)
    selected = select_securities(proof, args.security_id)
    free = shutil.disk_usage(ROOT).free
    used = output_bytes(args.output) if args.output.exists() else 0
    remaining = args.max_output_bytes - used
    if remaining <= 0 or free - remaining < RESERVE:
        raise ValueError('Stage allocation exceeds the available disk reserve')
    plan = dict(schema='v7-entry-demand-scheduler-v1', catalog_root=str(proof.root),
                securities=proof.security_ids, completion_sha256=sha(args.completion / 'complete.json'),
                active_sha256=sha(args.active), scheduler_sha256=sha(__file__),
                scope='entry feature demand only', acquisition=False, research_ready=False)
    print(json.dumps(dict(catalog_securities=len(proof.security_ids), selected=len(selected),
                          free_bytes=free, stage_budget_bytes=args.max_output_bytes,
                          existing_stage_bytes=used, provider_downloads=False)), flush=True)
    if not args.run:
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'scheduler.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        declaration = args.output / 'declaration'
        if declaration.exists():
            verify(declaration, expected_identity=identity(plan))
        else:
            with transaction(declaration) as temp:
                write(temp / 'plan.json', plan)
                receipt(temp, dict(identity=identity(plan)))
        # A conservative floor also catches unrelated disk growth while workers run.
        floor = max(RESERVE, free - remaining)
        pending = list(selected)
        running, completed, failed = {}, [], {}
        (args.output / 'logs').mkdir(exist_ok=True)
        last_print = 0
        def progress(state):
            value = dict(stage='v7-3-entry-demand', state=state, full_scope=len(proof.security_ids),
                         selected=len(selected), completed=len(completed), completed_ids=completed,
                         running=sorted(running), pending=len(pending), failed=failed,
                         full_scope_complete=len(completed) == len(proof.security_ids),
                         updated_at=datetime.now(timezone.utc).isoformat(), research_ready=False,
                         output_bytes=output_bytes(args.output), max_output_bytes=args.max_output_bytes)
            write(args.output / 'progress.json', value)
            return value
        try:
            while pending or running:
                if output_bytes(args.output) >= args.max_output_bytes or shutil.disk_usage(ROOT).free < floor:
                    raise RuntimeError('Stage disk budget/reserve exhausted; partial evidence retained')
                while pending and len(running) < args.workers and not failed:
                    sid = pending.pop(0)
                    log = (args.output / 'logs' / f'{sid}.log').open('a')
                    command = [sys.executable, str(Path(__file__).resolve()), '--completion', str(args.completion.resolve()),
                               '--active', str(args.active.resolve()), '--output', str(args.output),
                               '--workers', '1', '--max-output-bytes', str(args.max_output_bytes),
                               '--reserve-bytes', str(floor), '--worker', sid]
                    running[sid] = (subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT), log)
                for sid, (process, log) in list(running.items()):
                    code = process.poll()
                    if code is None:
                        continue
                    log.close()
                    del running[sid]
                    if code:
                        failed[sid] = dict(exit_code=code, log=str(args.output / 'logs' / f'{sid}.log'))
                    else:
                        completed.append(sid)
                state = progress('running')
                if time.monotonic() - last_print >= 30:
                    print(json.dumps({k: state[k] for k in ('stage', 'completed', 'selected', 'running', 'pending', 'failed', 'output_bytes')}), flush=True)
                    last_print = time.monotonic()
                if failed and not running:
                    break
                if running:
                    time.sleep(2)
            state = progress('failed' if failed else 'completed')
            print(json.dumps(state), flush=True)
            return 1 if failed else 0
        except BaseException as exc:
            for process, _ in running.values():
                process.terminate()
            for process, log in running.values():
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                log.close()
            failed['scheduler'] = dict(error=type(exc).__name__, reason=str(exc))
            running.clear()
            progress('interrupted')
            raise


if __name__ == '__main__':
    raise SystemExit(main())
