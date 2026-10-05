"""Prepare, run or verify the bounded ETFE TV-feature component study."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.tv_feature_pilot import prepare,run,verify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run','verify']);p.add_argument('--root',type=Path,required=True);p.add_argument('--max-scopes',type=int)
    a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-tv-features-'):p.error('Isolated ETFE TV-feature root required')
    if a.max_scopes is not None and a.max_scopes<1:p.error('Positive scope limit required')
    if a.command=='prepare':r=prepare(root);print(json.dumps(dict(plan_sha256=r['sha256'],scopes=len(r['scopes']))))
    elif a.command=='verify':print(json.dumps(dict(plan_sha256=verify(root)['sha256'])))
    else:
        r=run(root,a.max_scopes);print(json.dumps(r,indent=2))
        if not r['complete']:raise SystemExit(2)


if __name__=='__main__':main()
