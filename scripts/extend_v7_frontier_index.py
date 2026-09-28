#!/usr/bin/env python3
"""Reuse completed entry packs relevant to a retained execution frontier.

This is a new immutable snapshot, never a change to the prior index or captures.
Only exact contract matches on actual pending paths are selected from campaign
bindings; selected raw packs and the completed entry campaign are verified.
"""
import argparse,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.v7.storage import sha,verify,identity
from nn_meta.v7.packed_quote_index import write_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('paths','previous-index','campaign','entry-root','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name,value in vars(a).items():setattr(a,name,value.resolve())
    if not a.output.is_relative_to(ROOT/'nn_meta/validation'):raise ValueError('New validation output required')
    verify(a.paths);verify(a.previous_index);verify(a.campaign/'declaration')
    progress=json.loads((a.campaign/'progress.json').read_text())
    declaration=json.loads((a.campaign/'declaration/declaration.json').read_text())
    if not progress.get('full_entry_coverage') or declaration['output']!=str(a.entry_root):
        raise ValueError('Completed bound entry campaign required')
    doc=json.loads((a.paths/'report.json').read_text())
    inputs={str(path):sha(path) for path in [Path(__file__),a.paths/'complete.json',
        a.previous_index/'complete.json',a.campaign/'declaration/complete.json',
        a.campaign/'progress.json',ROOT/'nn_meta/v7/packed_quote_index.py']}
    with sqlite3.connect((a.previous_index/'index.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        packs=[Path(path) for path, in db.execute('SELECT path FROM packs ORDER BY id')]
    known=set(packs);added=[]
    for case in doc['cases']:
        contracts={r['contract'] for r in case['pending'] if r.get('kind') in ('quotes','trades')}
        if not contracts:continue
        for source in sorted((a.entry_root/case['security_id']).glob('*/binding.json')):
            binding=json.loads(source.read_text())
            if not any(r['contract'] in contracts for r in binding['captures']):continue
            pack=source.parent
            if pack in known:continue
            header=verify(pack)
            if header['identity']!=identity(binding):raise ValueError('Entry pack binding mismatch')
            inputs[str(pack/'complete.json')]=sha(pack/'complete.json')
            packs.append(pack);known.add(pack);added.append(str(pack))
    binding=dict(schema='v7-existing-entry-frontier-index-v1',inputs=inputs,added_packs=added)
    if a.output.exists():verify(a.output,expected_identity=identity(binding))
    else:write_index(a.output,packs,binding=binding)
    if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Selected index inputs changed')
    print(json.dumps(dict(packs=len(packs),added_packs=len(added),output=str(a.output))))


if __name__=='__main__':main()
