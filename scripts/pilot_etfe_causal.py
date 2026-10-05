"""Build fresh ETFE session diagnostics and the all-family phase-B component pilot."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.causal_pilot import prepare,run,verify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run','verify'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--max-scopes',type=int)
    a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-causal-'):
        p.error('Isolated ETFE causal validation root required')
    if a.command=='prepare':
        r=prepare(root);print(json.dumps(dict(plan_sha256=r['sha256'],scopes=len(r['scopes']))))
    elif a.command=='verify':print(json.dumps(dict(plan_sha256=verify(root)['sha256'])))
    else:
        r=run(root,max_scopes=a.max_scopes);print(json.dumps(r,indent=2))
        if not r['complete']:raise SystemExit(2)


if __name__=='__main__':main()
