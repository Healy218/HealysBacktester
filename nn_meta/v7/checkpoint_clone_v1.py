"""Copy-on-write checkpoint inheritance; originals retain independent inodes."""
import fcntl,json,os,shutil,sqlite3,subprocess,uuid
from pathlib import Path
from nn_meta.v7.storage import sha,identity,verify
from incubator.continual.storage import write


def clone_file(source, destination):
    # Fail explicitly on an unsupported filesystem, never silently allocate a full copy.
    subprocess.run(['cp', '--reflink=always', '--preserve=mode,timestamps', '--',
                    str(source), str(destination)], check=True, capture_output=True)
    if source.stat().st_ino == destination.stat().st_ino:
        raise ValueError('Checkpoint clone must not be a hardlink')


def _inherit_checkpoint(parent,output,declaration,sid):
    """Copy a verified stopped predecessor, preserving its hashes as lineage.

    Never rewrite the predecessor binding to excuse a new source revision.
    """
    parent,output=Path(parent).resolve(),Path(output).resolve()
    receipt_path=output/'inherited-checkpoint.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        if receipt['parent']!=str(parent):raise ValueError('Checkpoint parent changed')
        return receipt
    if (output/'securities').exists():raise ValueError('Unreceipted import; retain and inspect partial output')
    with (parent/'lock').open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((parent/'declaration.json').read_text())
        if any(sha(p)!=h for p,h in old['inputs'].items()):raise ValueError('Parent source changed')
        if old['securities']!=[sid] or old['plan']!=declaration['plan'] or old['entry_root']!=declaration['entry_root']:raise ValueError('Parent scientific scope differs')
        # All frozen scientific inputs must be inherited, independent of producer files.
        for p,h in old['inputs'].items():
            if not p.endswith('.py') and declaration['inputs'].get(p)!=h:raise ValueError('Parent scientific input changed')
        if old.get('replay_plan')!=declaration.get('replay_plan'):raise ValueError('Parent replay scope differs')
        src=parent/'securities'/sid;binding=json.loads((src/'binding.json').read_text())
        if binding['campaign_identity']!=identity(old):raise ValueError('Parent wave binding differs')
        if binding['jobs_sha256']!=sha(Path(old['plan'])/'jobs'/sid/'complete.json'):raise ValueError('Parent jobs differ')
        verify(parent/'indexes'/sid)
        if binding['quote_index_sha256']!=sha(parent/'indexes'/sid/'complete.json'):raise ValueError('Parent quote index differs')
        output.mkdir(parents=True,exist_ok=True)
        shutil.copytree(parent/'indexes',output/'indexes')
        dst=output/'securities'/sid;dst.mkdir(parents=True)
        originals={}
        for name in ['wave.sqlite3','wave.sqlite3-journal','wave.sqlite3-wal','wave.sqlite3-shm']:
            if (src/name).exists():
                originals[name]=sha(src/name);clone_file(src/name,dst/name)
                if sha(src/name)!=originals[name] or sha(dst/name)!=originals[name]:raise ValueError('Parent changed while copying')
        with sqlite3.connect(dst/'wave.sqlite3') as db:
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Inherited checkpoint corrupt')
        receipt=dict(parent=str(parent),parent_declaration_sha256=sha(parent/'declaration.json'),
            parent_identity=identity(old),parent_files=originals,recovered_database_sha256=sha(dst/'wave.sqlite3'))
        (dst/'parent-binding.json').write_text(json.dumps(binding,sort_keys=True)+'\n')
        receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        return receipt


def inherit_checkpoint(parent, output, declaration, sid):
    parent, output = Path(parent).resolve(), Path(output).resolve()
    final = output / 'inherited-checkpoint.json'
    if final.exists():
        doc = json.loads(final.read_text())
        if doc['parent'] != str(parent) or doc['parent_declaration_sha256'] != sha(parent/'declaration.json'):
            raise ValueError('Checkpoint parent changed')
        return doc
    stage = output / '.checkpoint-import'
    if stage.exists() and not (stage/'inherited-checkpoint.json').exists():
        stage.rename(output / ('.abandoned-import-' + uuid.uuid4().hex))
    if not stage.exists():
        if (output/'securities').exists() or (output/'indexes').exists():
            raise ValueError('Unreceipted checkpoint destination')
        stage.mkdir(parents=True)
        _inherit_checkpoint(parent, stage, declaration, sid)
        # Durable staging receipt precedes idempotent directory publication.
        for path in stage.rglob('*'):
            if path.is_file():
                with path.open('rb') as stream: os.fsync(stream.fileno())
    doc = json.loads((stage/'inherited-checkpoint.json').read_text())
    if doc['parent'] != str(parent) or doc['parent_declaration_sha256'] != sha(parent/'declaration.json'):
        raise ValueError('Staged checkpoint parent changed')
    for name in ['indexes', 'securities']:
        src, dst = stage/name, output/name
        if src.exists():
            if dst.exists(): raise ValueError('Ambiguous checkpoint publication')
            src.rename(dst)
        elif not dst.exists(): raise ValueError('Incomplete staged checkpoint')
    write(final, {**doc, 'copy_method': 'reflink-always', 'independent_inodes': True})
    return json.loads(final.read_text())
