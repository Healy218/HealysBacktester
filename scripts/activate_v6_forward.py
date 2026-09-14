"""Bind successful replay/parity/test evidence to the installed paper runtime."""
import argparse
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from nn_meta.live.v6_market import read, save, utcnow
from nn_meta.live.v6_release import verify_release, sha

ROOT=Path(__file__).resolve().parents[1]


def activate(args):
    verify_release(args.release,args.anchor)
    parity=read(args.parity)
    replay=read(args.replay)
    if (parity.get('status')!='passed' or parity.get('release_sha256')!=args.anchor
            or len(parity.get('cases',[]))<3
            or any(c['features']!=164 or c['max_feature_absolute_error']!=0 for c in parity['cases'])):
        raise ValueError('complete historical feature parity has not passed')
    if (replay.get('status')!='replayed' or replay.get('errors')!=0
            or replay.get('universe')!=449 or replay.get('candidate_rows',0)<1
            or replay.get('elapsed_seconds',999)>=280):
        raise ValueError('complete-universe replay has not passed with entry-deadline headroom')
    evidence={str(p.absolute()):sha(p) for p in [args.parity,args.replay,*args.tests]}
    count=0
    for path in args.tests:
        for suite in ET.parse(path).getroot().iter('testsuite'):
            if any(int(suite.get(key,'0')) for key in ('failures','errors','skipped')):
                raise ValueError('activation tests must pass without skipped checks')
            count+=int(suite.get('tests','0'))
    if count<180: raise ValueError('required numerical/portfolio/dispatcher checks are missing')
    # Bind implementation dependencies as well as the top-level entry point.
    paths=set()
    for directory in ('nn_meta','v3','options','portfolio','indicators'):
        paths.update((ROOT/directory).rglob('*.py'))
    paths.update(ROOT/'scripts'/name for name in ('run_v6_forward.py','prepare_v6_forward_data.py',
        'prepare_v6_local_context.py','v6_forward_ops.py','activate_v6_forward.py'))
    runtime={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if '__pycache__' not in p.parts}
    receipt={'status':'passed','schema':'v6-forward-activation-v1','release_sha256':args.anchor,
        'runtime_sha256':runtime,'evidence_sha256':evidence,'tests':count,'activated_at':utcnow().isoformat(),
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'expiry_cutoff_minutes':15,'experimental':True,'broker_orders':False,
        'current_market_access':'required automatically before each live allocation; not certified by historical replay',
        'feature_clock':'MASSIVE SIP, with actual REST receipt recorded separately',
        'feature_parity':'local frozen-training feature parity passed; external Pine parity remains deferred',
        'producer_host':'home','notification_host':'server','replay_seconds':replay['elapsed_seconds']}
    save(args.output,receipt)
    print({'status':'passed','tests':count,'files_bound':len(runtime),'output':str(args.output)})


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--release',type=Path,required=True); ap.add_argument('--anchor',required=True)
    ap.add_argument('--parity',type=Path,required=True); ap.add_argument('--replay',type=Path,required=True)
    ap.add_argument('--tests',type=Path,nargs='+',required=True); ap.add_argument('--output',type=Path,required=True)
    activate(ap.parse_args())
