"""Atomic local job receipts; an old success cannot hide a new failure."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write(path, payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(payload,stream,indent=2);stream.write('\n')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def record(root, name, state, *, started=None, returncode=None, details=None):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',name):raise ValueError('Invalid job name')
    payload=dict(job=name,state=state,started=started or stamp(),updated=stamp(),returncode=returncode,details=details or {})
    folder=Path(root)/name
    write(folder/'latest.json',payload)
    if state=='success':write(folder/'last-success.json',payload)
    return payload
