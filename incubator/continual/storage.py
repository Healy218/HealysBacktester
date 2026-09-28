"""Immutable receipts and atomic pointers for research-only daily updates."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import os


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):digest.update(block)
    return digest.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n');temp.replace(path)


def seal(root, declaration, files, **extra):
    root=Path(root)
    receipt=dict(schema='incubator-continual-artifact-v1',identity=identity(declaration),
                 declaration=declaration,files={name:sha(root/name) for name in files},**extra)
    if (root/'complete.json').exists():raise ValueError('refusing to replace completed artifact')
    write(root/'complete.json',receipt)
    return receipt


def verify(root, declaration=None):
    root=Path(root);receipt=json.loads((root/'complete.json').read_text())
    if receipt['identity']!=identity(receipt['declaration']):raise ValueError('declaration hash differs')
    if declaration is not None and receipt['identity']!=identity(declaration):raise ValueError('artifact inputs changed')
    for name,digest in receipt['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path)!=digest:raise ValueError('artifact payload changed: '+name)
    return receipt


def publish_candidate(root,candidate,through,verdict):
    """Recover pointer publication without ever regressing a newer candidate."""
    root=Path(root);candidate=Path(candidate);verify(candidate)
    pointer=dict(path=str(candidate),sha256=sha(candidate/'complete.json'),through=through,verdict=verdict)
    names=['latest-candidate.json']+(['latest-accepted.json'] if verdict=='passed' else [])
    for name in names:
        path=root/name
        if path.exists() and json.loads(path.read_text())['through']>through:continue
        write(path,pointer)
    return pointer
