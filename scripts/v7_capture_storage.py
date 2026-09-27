"""Live free-space routing with immutable, locally discoverable overflow packs."""
import fcntl
import json
from pathlib import Path
import shutil
import subprocess

RESERVE = 10_000_000_000  # User requested decimal GB, not GiB.
METADATA_RESERVATION = 1024**2


def verify_mount(mount, uuid):
    mount = Path(mount).resolve()
    doc = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-T', str(mount), '-o', 'TARGET,UUID,FSTYPE,OPTIONS'], text=True))
    rows = doc.get('filesystems', [])
    if (len(rows) != 1 or Path(rows[0]['target']).resolve() != mount
            or rows[0].get('uuid') != uuid or 'rw' not in rows[0].get('options', '').split(',')):
        raise ValueError('Authorized overflow drive is not mounted read-write at the bound path')
    return rows[0]


def physical_bytes(root):
    """Count stored bytes once; local payload symlinks are represented on MRHA."""
    total=0;seen=set()
    for path in Path(root).rglob('*'):
        if path.is_file() and not path.is_symlink():
            s=path.stat();key=(s.st_dev,s.st_ino)
            if key not in seen:total+=s.st_size;seen.add(key)
    return total


def route(local_free, external_free, pending, reservation, *, force_external=False):
    local_jobs=sum(tier=='local' for tier in pending)
    external_jobs=len(pending)-local_jobs
    local_reserved=local_jobs*reservation+external_jobs*METADATA_RESERVATION
    if not force_external and local_free >= RESERVE+local_reserved+reservation:
        return 'local'
    if (local_free >= RESERVE+local_reserved+METADATA_RESERVATION
            and external_free >= RESERVE+(external_jobs+1)*reservation):
        return 'external'
    return None


def publish_locator(logical, physical):
    """Keep real local directories/receipts, linking only the immutable SQLite file."""
    from nn_meta.v7.storage import verify, transaction
    logical,physical=Path(logical),Path(physical).resolve()
    doc=verify(physical)
    if set(doc['files']) != {'binding.json','captures.sqlite3'}:
        raise ValueError('Unexpected overflow pack layout')
    if logical.exists():
        if verify(logical)!=doc:raise ValueError('Overflow locator receipt mismatch')
        return
    with transaction(logical) as temp:
        for name in ('binding.json','complete.json'):
            shutil.copyfile(physical/name,temp/name)
        (temp/'captures.sqlite3').symlink_to(physical/'captures.sqlite3')
        verify(temp)
    verify(logical)


def expand_quota(budget, additional_bytes, *, authorization):
    """Keep charged usage/reservations; replace the obsolete fixed allocation cap."""
    from scripts.download_v7_data import save
    budget=Path(budget)
    with (budget/'.quota.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        q=json.loads((budget/'quota.json').read_text())
        if q['reservations']:
            raise ValueError('Drain acquisition reservations before capacity amendment')
        before=dict(q)
        q['limit_bytes']=q['used_bytes']+max(0,additional_bytes)
        q['capacity_authorization']=authorization
        save(budget/'quota.json',q)
    return dict(before=before,after=q)
