"""Restore one explicitly chosen GCS object to temporary storage and compare bytes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fa.monthly import sha
from scripts.job_receipts import record, stamp


def verify(source,uri,*,gsutil,state_dir):
    source=Path(source)
    if not uri.startswith('gs://') or any(c in uri for c in '*?[]'):
        raise ValueError('Supply one exact gs:// object, without wildcards')
    started=stamp();record(state_dir,'backup-restore','running',started=started)
    try:
        before=sha(source)
        with tempfile.TemporaryDirectory(prefix='healys-restore-') as temp:
            restored=Path(temp)/'restored'
            subprocess.run([str(gsutil),'cp',uri,str(restored)],check=True,timeout=300,stdout=subprocess.DEVNULL)
            matched=sha(restored)==before and sha(source)==before
        if not matched:raise ValueError('Restored bytes differ or source changed during verification')
    except Exception:
        record(state_dir,'backup-restore','failed',started=started,returncode=1)
        raise
    return record(state_dir,'backup-restore','success',started=started,returncode=0,
                  details=dict(source=str(source),object=uri,sha256=before,scope='one explicitly selected object'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--object',required=True)
    p.add_argument('--gsutil',type=Path,default=Path.home()/'google-cloud-sdk/bin/gsutil')
    p.add_argument('--state-dir',type=Path,default=ROOT/'logs/job-health')
    p.add_argument('--run',action='store_true')
    a=p.parse_args()
    if not a.run:print(json.dumps(dict(source=str(a.source),object=a.object,action='restore to temporary directory and compare')));return
    print(json.dumps(verify(a.source,a.object,gsutil=a.gsutil,state_dir=a.state_dir),indent=2))


if __name__=='__main__':main()
