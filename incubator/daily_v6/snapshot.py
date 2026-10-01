"""Extend the prior frozen prefix, recording provider revisions separately."""
import json
from pathlib import Path
import shutil
import pandas as pd
from incubator.continual.storage import sha,write


def append_frozen(old,fresh):
    if old.empty or fresh.empty or not old.index.is_unique or not fresh.index.is_unique:
        raise ValueError('Invalid daily stock indexes')
    if list(old.columns)!=list(fresh.columns):raise ValueError('Daily stock schema differs')
    if not old.index.is_monotonic_increasing or not fresh.index.is_monotonic_increasing:
        raise ValueError('Stock history is not ordered')
    common=old.index.intersection(fresh.index)
    different=old.loc[common].ne(fresh.loc[common]) & ~(old.loc[common].isna() & fresh.loc[common].isna())
    result=pd.concat([old,fresh.loc[fresh.index>old.index[-1]]])
    if not result.loc[old.index].equals(old):raise ValueError('Frozen prefix changed')
    return result,dict(changed_cells=int(different.sum().sum()),changed_columns={k:int(v) for k,v in different.sum().items() if v},
                       frozen_rows=len(old),appended_rows=len(result)-len(old))


def extend_snapshot(previous,fresh,dest):
    previous,fresh,dest=map(Path,(previous,fresh,dest))
    old=json.loads((previous/'manifest.json').read_text());new=json.loads((fresh/'manifest.json').read_text())
    if old['release_sha256']!=new['release_sha256'] or set(old['symbols'])!=set(new['symbols']):
        raise ValueError('Daily universe/release changed')
    if old['through']>=new['through']:raise ValueError('Daily extension must advance date')
    if (dest/'manifest.json').exists():raise ValueError('Daily snapshot already sealed')
    dest.mkdir(parents=True,exist_ok=True)
    for name in ('calendar.json','surface.parquet','context.parquet'):
        if sha(fresh/name)!=new['files'][name]:raise ValueError('Daily context changed')
        shutil.copyfile(fresh/name,dest/name)
    inventory={};audit={}
    for symbol in sorted(old['symbols']):
        refs={};frames={};audit[symbol]={}
        for kind in ('all','raw'):
            a=old['symbols'][symbol]['files'][kind];b=new['symbols'][symbol]['files'][kind]
            if sha(previous/a['path'])!=a['sha256'] or sha(fresh/b['path'])!=b['sha256']:
                raise ValueError('Stock snapshot payload changed')
            frame,changes=append_frozen(pd.read_parquet(previous/a['path']),pd.read_parquet(fresh/b['path']))
            relative=f'stocks/{symbol}.{kind}.parquet';target=dest/relative;target.parent.mkdir(exist_ok=True)
            frame.to_parquet(target);frames[kind]=frame
            refs[kind]=dict(path=relative,sha256=sha(target));audit[symbol][kind]=changes
        if not frames['all'].index.equals(frames['raw'].index):raise ValueError('Adjusted/raw indexes differ')
        inventory[symbol]=dict(files=refs,rows=len(frames['all']),last_bar=frames['all'].index[-1].isoformat())
    write(dest/'revision-audit.json',audit)
    write(dest/'manifest.json',dict(new,symbols=inventory,
          sources=dict(frozen_prefix=str(previous),frozen_prefix_sha256=sha(previous/'manifest.json'),
                       appended_from=str(fresh),appended_from_sha256=sha(fresh/'manifest.json')),
          prefix_policy='retain-observed-frozen-history-append-new-bars-v1',
          revision_audit_sha256=sha(dest/'revision-audit.json')))
    return audit


def select_snapshot(config,root,through):
    from incubator.continual.snapshot import select_snapshot as capture_snapshot
    from incubator.continual.storage import verify
    root=Path(root);dest=root/'snapshots'/through
    if (dest/'manifest.json').exists():return dest
    previous=Path(config['prefix_snapshot']['path'])
    expected=config['prefix_snapshot']['sha256']
    completed=[]
    for path in (root/'runs').glob('*/candidate/complete.json'):
        date=path.parent.parent.name
        if date<through:completed.append((date,path.parent))
    if completed:
        date,candidate=max(completed)
        verify(candidate)
        declaration=json.loads((root/'runs'/date/'declaration.json').read_text())
        previous=Path(declaration['snapshot']);expected=declaration['snapshot_sha256']
    if sha(previous/'manifest.json')!=expected:raise ValueError('Frozen prefix snapshot changed')
    fresh=capture_snapshot(config,root/'provider-updates',through)
    extend_snapshot(previous,fresh,dest)
    return dest
