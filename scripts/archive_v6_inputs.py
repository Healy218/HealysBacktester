#!/usr/bin/env python3
"""Pack, externally verify, and retire the explicitly authorized old V6 tree.

Three separate commands keep deletion behind completed external verification.
Archives are partitioned by capture symbol for bounded restart and restoration.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('nn_meta/expanded_inputs/v6-local-20260906')
UUID = '62C9-C390'


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    with temporary.open('rb') as f:
        os.fsync(f.fileno())
    temporary.replace(path)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def fingerprint(members, shallow=()):
    digest = hashlib.sha256()
    counts = dict(files=0, directories=0, symlinks=0, bytes=0)
    def visit(relative, recurse):
        path = ROOT / relative
        s = path.lstat()
        if stat.S_ISREG(s.st_mode):
            counts['files'] += 1; counts['bytes'] += s.st_size
        elif stat.S_ISDIR(s.st_mode):
            counts['directories'] += 1
        elif stat.S_ISLNK(s.st_mode):
            counts['symlinks'] += 1
        else:
            raise ValueError(f'Unsupported file type: {path}')
        value = [str(relative), s.st_mode, s.st_uid, s.st_gid, s.st_size,
                 s.st_mtime_ns, os.readlink(path) if path.is_symlink() else None]
        digest.update(json.dumps(value, separators=(',', ':')).encode() + b'\n')
        if recurse and stat.S_ISDIR(s.st_mode):
            for child in sorted(path.iterdir()):
                visit(child.relative_to(ROOT), True)
    for p in shallow:
        visit(Path(p), False)
    for p in members:
        visit(Path(p), True)
    return dict(**counts, metadata_sha256=digest.hexdigest())


def make_plan():
    base = ROOT / SOURCE
    full = base / 'full-run'
    captures = full / 'captures'
    symbols = sorted(captures.iterdir())
    if len(symbols) != 453 or any(not p.is_dir() or p.is_symlink() for p in symbols):
        raise ValueError('Unexpected capture roots; stop for review')
    groups = [dict(id='context-and-stores',
                   shallow=[str(SOURCE), str(SOURCE / 'full-run'),
                            str(SOURCE / 'full-run/captures')],
                   members=[str(p.relative_to(ROOT)) for p in sorted(base.iterdir()) if p != full]
                   + [str(p.relative_to(ROOT)) for p in sorted(full.iterdir()) if p != captures])]
    groups += [dict(id='captures-' + p.name, shallow=[], members=[str(p.relative_to(ROOT))]) for p in symbols]
    return dict(schema='v6-external-archive-plan-v1', source=str(SOURCE), drive_uuid=UUID,
                groups=groups, source_layout=dict(root=sorted(p.name for p in base.iterdir()),
                  full_run=sorted(p.name for p in full.iterdir()), captures=[p.name for p in symbols]))


def check_layout(plan):
    current = make_plan()
    if current != plan:
        raise ValueError('Source layout drifted; stop before retirement')


def tar_args(group, bundle):
    # NUL lists and verbatim mode prevent filenames from becoming tar options.
    lists = []
    for label in ('shallow', 'members'):
        p = bundle / (group['id'] + '.' + label + '.nul')
        p.write_bytes(b''.join(os.fsencode(n) + b'\0' for n in group[label]))
        lists += ['--no-recursion' if label == 'shallow' else '--recursion',
                  '--null', '--verbatim-files-from', '-T', str(p)]
    return lists


def pack_one(group, bundle):
    archive = bundle / (group['id'] + '.tar.zst')
    receipt = bundle / (group['id'] + '.json')
    if receipt.exists():
        result = json.loads(receipt.read_text())
        if archive.stat().st_size != result['archive_bytes'] or sha(archive) != result['sha256']:
            raise ValueError('Completed archive changed')
        return result
    before = fingerprint(group['members'], group['shallow'])
    partial = archive.with_suffix('.zst.partial')
    with (bundle / (group['id'] + '.pack.log')).open('w') as log:
        subprocess.run(['tar', '--format=pax', '--pax-option=delete=atime,delete=ctime',
                        '--xattrs', '--acls', '-I', 'zstd -T1 -3', '-cf', str(partial)]
                       + tar_args(group, bundle), cwd=ROOT, stdout=log, stderr=log, check=True)
    after = fingerprint(group['members'], group['shallow'])
    if before != after:
        raise ValueError(f'Source changed while packing {group["id"]}')
    with partial.open('rb') as f:
        os.fsync(f.fileno())
    partial.replace(archive)
    result = dict(id=group['id'], source=before, archive_bytes=archive.stat().st_size,
                  sha256=sha(archive), state='packed-source-stable')
    save(receipt, result)
    return result


def check_drive(destination):
    mount = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-T', str(destination), '-o', 'UUID,TARGET,FSTYPE']))['filesystems'][0]
    if mount['uuid'] != UUID or mount['fstype'] != 'exfat':
        raise ValueError('Destination is not the MRHA exFAT drive')


def transfer_one(group, bundle, destination):
    check_drive(destination)
    packed = json.loads((bundle / (group['id'] + '.json')).read_text())
    name = group['id'] + '.tar.zst'
    archive = destination / name
    receipt = destination / (group['id'] + '.verified.json')
    if receipt.exists():
        verified = json.loads(receipt.read_text())
        if sha(archive) != packed['sha256'] or verified['packed'] != packed:
            raise ValueError('External verified archive drifted')
        return verified
    if not archive.exists():
        temporary = archive.with_suffix('.zst.partial')
        with (bundle / name).open('rb') as src, temporary.open('wb') as dst:
            shutil.copyfileobj(src, dst, 4 * 1024**2)
            dst.flush(); os.fsync(dst.fileno())
        temporary.replace(archive)
    if sha(archive) != packed['sha256']:
        raise ValueError('External copy hash mismatch')
    log = destination / (group['id'] + '.compare.log')
    # GNU tar checks every archived byte and original type, mode, owner and mtime.
    # zstd decompression also verifies its checksums; any difference is fatal.
    with log.open('w') as f:
        subprocess.run(['tar', '--xattrs', '--acls', '-I', 'zstd -T1 -d',
                        '-df', str(archive)], cwd=ROOT, stdout=f, stderr=f, check=True)
    if log.stat().st_size:
        raise ValueError(f'Unexpected comparison diagnostics: {log}')
    if fingerprint(group['members'], group['shallow']) != packed['source']:
        raise ValueError('Source changed since packing')
    verified = dict(state='external-hash-and-full-source-compare-passed', packed=packed,
                    destination=str(archive), drive_uuid=UUID)
    save(receipt, verified)
    return verified


def restore_sample(bundle, destination, plan):
    group = next(g for g in plan['groups'] if g['id'] == 'captures-AA')
    root = ROOT / group['members'][0]
    sample = next(p for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    relative = sample.relative_to(ROOT)
    smoke = bundle / 'restore-smoke'
    smoke.mkdir(exist_ok=True)
    subprocess.run(['tar', '-I', 'zstd -T1 -d', '-xf', str(destination / 'captures-AA.tar.zst'),
                    '-C', str(smoke), '--', str(relative)], check=True)
    restored = smoke / relative
    if sha(restored) != sha(sample) or restored.stat().st_mode != sample.stat().st_mode:
        raise ValueError('Restoration smoke mismatch')
    result = dict(path=str(relative), sha256=sha(sample), bytes=sample.stat().st_size,
                  state='restored-from-external-and-compared')
    save(bundle / 'restore-smoke.json', result)
    save(destination / 'restore-smoke.json', result)


def retire(bundle, destination, plan):
    check_drive(destination)
    completion = json.loads((destination / 'VERIFIED.json').read_text())
    if completion['plan_sha256'] != sha(bundle / 'plan.json'):
        raise ValueError('Plan differs from externally verified plan')
    journal = bundle / 'retirement.jsonl'
    done = set()
    if journal.exists():
        done = {json.loads(line)['id'] for line in journal.read_text().splitlines()}
    if not done:
        check_layout(plan)
    # Validate every external archive before deleting anything. Recheck each
    # remaining source tree immediately before removing it; never follow links.
    for group in plan['groups']:
        receipt = json.loads((destination / (group['id'] + '.verified.json')).read_text())
        if sha(destination / (group['id'] + '.tar.zst')) != receipt['packed']['sha256']:
            raise ValueError('External content drifted before retirement')
    # Keep context/parent directories until every symbol has been retired.
    ordered = plan['groups'][1:] + plan['groups'][:1]
    with journal.open('a') as log:
        for group in ordered:
            if group['id'] in done:
                continue
            receipt = json.loads((destination / (group['id'] + '.verified.json')).read_text())
            if group['shallow']:
                # Removing child trees changes parent sizes/mtimes. All recursive
                # members still must match their separately sealed fingerprint.
                expected = completion['context_members_fingerprint']
                actual = fingerprint(group['members'])
            else:
                expected = receipt['packed']['source']
                actual = fingerprint(group['members'])
            if actual != expected:
                raise ValueError('Source drift before deletion: ' + group['id'])
            for name in group['members']:
                p = ROOT / name
                if not p.is_relative_to(ROOT / SOURCE):
                    raise ValueError('Retirement escaped approved V6 root')
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            row = dict(id=group['id'], removed=actual, archive_sha256=receipt['packed']['sha256'])
            log.write(json.dumps(row) + '\n'); log.flush(); os.fsync(log.fileno())
            done.add(group['id'])
            save(bundle / 'progress.json', dict(stage='retire', completed=len(done),
                 total=len(ordered), updated_unix=time.time()))
            print('Retired ' + group['id'], flush=True)
    for relative in (SOURCE / 'full-run/captures', SOURCE / 'full-run', SOURCE):
        (ROOT / relative).rmdir()
    locator = ROOT / (str(SOURCE) + '.ARCHIVED.json')
    save(locator, dict(external_folder=str(destination), drive_uuid=UUID,
                       plan_sha256=completion['plan_sha256'], restore='See external RESTORE.md',
                       retired_files=completion['files'], retired_directories=completion['directories']))
    save(bundle / 'RETIRED.json', dict(state='complete', locator=str(locator), **completion))
    shutil.copyfile(bundle / 'RETIRED.json', destination / 'RETIRED.json')
    shutil.copyfile(journal, destination / journal.name)
    os.sync()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=['pack', 'transfer', 'retire'])
    ap.add_argument('--bundle', type=Path, required=True)
    ap.add_argument('--destination', type=Path)
    ap.add_argument('--workers', type=int, required=True)
    args = ap.parse_args()
    if not 1 <= args.workers <= 4:
        ap.error('Use an autosized 1–4 worker count')
    bundle = args.bundle.resolve()
    if not bundle.is_relative_to(ROOT / 'nn_meta/validation'):
        ap.error('Bundle must be inside repo validation')
    bundle.mkdir(parents=True, exist_ok=True)
    lock = (bundle / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan_file = bundle / 'plan.json'
    if not plan_file.exists():
        if args.stage != 'pack':
            ap.error('Pack a plan first')
        save(plan_file, make_plan())
    plan = json.loads(plan_file.read_text())
    destination = args.destination.resolve() if args.destination else None
    if args.stage != 'pack':
        if destination is None:
            ap.error('External destination required')
        check_drive(destination.parent)
        destination.mkdir(exist_ok=True)
    if args.stage == 'retire':
        retire(bundle, destination, plan)
        return
    if args.stage == 'pack' and shutil.disk_usage(bundle).free < 100 * 1024**3:
        raise ValueError('Insufficient local staging capacity')
    if args.stage == 'transfer':
        needed = sum(p.stat().st_size for p in bundle.glob('*.tar.zst'))
        if shutil.disk_usage(destination).free < needed + 20 * 1024**3:
            raise ValueError('Insufficient external capacity')
        shutil.copyfile(plan_file, destination / 'plan.json')
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks = [pool.submit(pack_one, g, bundle) if args.stage == 'pack' else
                 pool.submit(transfer_one, g, bundle, destination) for g in plan['groups']]
        for future in as_completed(tasks):
            result = future.result(); results.append(result)
            print(f'{args.stage}: {len(results)}/{len(tasks)} complete', flush=True)
            save(bundle / 'progress.json', dict(stage=args.stage, completed=len(results),
                 total=len(tasks), updated_unix=time.time()))
    check_layout(plan)
    packed = [json.loads((bundle / (g['id'] + '.json')).read_text()) for g in plan['groups']]
    summary = dict(stage=args.stage, archives=len(packed), plan_sha256=sha(plan_file),
                   files=sum(r['source']['files'] for r in packed),
                   directories=sum(r['source']['directories'] for r in packed),
                   source_bytes=sum(r['source']['bytes'] for r in packed),
                   compressed_bytes=sum(r['archive_bytes'] for r in packed),
                   symlinks=sum(r['source']['symlinks'] for r in packed))
    if summary['files'] != 9541723 or summary['directories'] != 2066117:
        raise ValueError(f'Counts differ from reviewed inventory: {summary}')
    save(bundle / (args.stage + '-complete.json'), summary)
    if args.stage == 'transfer':
        restore_sample(bundle, destination, plan)
        summary['context_members_fingerprint'] = fingerprint(plan['groups'][0]['members'])
        save(destination / 'VERIFIED.json', summary)
        save(bundle / 'VERIFIED.json', summary)
        (destination / 'RESTORE.md').write_text(
            '# V6 historical input archive\n\nOriginal: `' + str(SOURCE) + '`\n\n'
            'Each tar.zst contains repo-relative paths, Unix metadata, ACLs and xattrs. '
            'Extract onto a Linux filesystem, not directly as loose files on exFAT.\n\n'
            'From the repository root, for each archive run:\n\n'
            '    tar --xattrs --acls -I zstd -xf /path/to/archive.tar.zst\n\n'
            'Extract context-and-stores.tar.zst last to restore parent metadata. '
            'Verify every compressed SHA256 against its corresponding verified.json before restoration. '
            'All archives passed full GNU tar source comparisons before source retirement. '
            'restore-smoke.json records a real extraction and hash comparison. '
            'These are historical V6 inputs, not newly admitted V7 data.\n')
        os.sync()
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
