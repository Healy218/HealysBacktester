"""Reuse prior-session context and append completed-session stock bars."""
import json
from pathlib import Path
import shutil
import pandas as pd
from .storage import sha,write


def select_snapshot(config,root,through):
    from nn_meta.live.v6_forward_inputs import ForwardData
    from nn_meta.session_calendar import SessionCalendar
    index=json.loads(Path(config['data_index']).read_text());source=Path(index['path'])
    if sha(source/'manifest.json')!=index['sha256']:raise ValueError('daily snapshot anchor changed')
    manifest=json.loads((source/'manifest.json').read_text())
    if (manifest['release_sha256']!=config['release_sha256']
            or index.get('release_sha256')!=config['release_sha256']):
        raise ValueError('daily snapshot belongs to another release')
    if index['through']>=through:return source
    calendar=SessionCalendar(json.loads((source/'calendar.json').read_text()))
    prior=max(d for d in calendar.sessions if d<through)
    if index['through']!=prior:raise ValueError(f'awaiting prior-session context: need {prior}, have {index["through"]}')
    dest=Path(root)/'snapshots'/through
    if (dest/'manifest.json').exists():return dest
    data=ForwardData(source,expected_sha256=index['sha256'],release=Path(config['release']),anchor=config['release_sha256'])
    dest.mkdir(parents=True,exist_ok=True)
    closed=calendar.bounds(through)[1].tz_localize('UTC')+pd.Timedelta(minutes=30)
    if closed>pd.Timestamp.now(tz='UTC'):raise ValueError('session not fully closed')
    data.update(closed,capture=dest/'stock-captures')
    for name in ['calendar.json','surface.parquet','context.parquet']:
        shutil.copyfile(source/name,dest/name)
    inventory={}
    for symbol in sorted(data.spec['symbols']):
        refs={}
        for kind,frames in [('all',data.bars),('raw',data.raw)]:
            relative=f'stocks/{symbol}.{kind}.parquet';path=dest/relative;path.parent.mkdir(exist_ok=True)
            frames[symbol].to_parquet(path)
            refs[kind]=dict(path=relative,sha256=sha(path))
        inventory[symbol]=dict(files=refs,rows=len(data.bars[symbol]),last_bar=data.bars[symbol].index[-1].isoformat())
    write(dest/'manifest.json',dict(schema='v6-forward-data-v1',through=through,
        release_sha256=config['release_sha256'],symbols=inventory,
        files={name:sha(dest/name) for name in ['calendar.json','surface.parquet','context.parquet']},
        daily_context_through=prior,parent_snapshot_sha256=index['sha256'],
        sources=dict(parent_snapshot=str(source)),stock_receipts=data.market_receipts,
        research_only=True))
    return dest
