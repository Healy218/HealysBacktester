"""ETFE dataset v1 freeze: join audited features and labels, seal immutable partitions + manifest."""
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import acquisition as a
from nn_meta.etfe.joined_features import schema
from nn_meta.etfe.label_kernel import END_NS

ROOT=Path(__file__).resolve().parents[2]
LABELS=ROOT/'nn_meta/validation/etfe-labels-v1-20261007-r2'
FEATURES=ROOT/'nn_meta/validation/etfe-features-v1-20261007-r0'
SCOPES=[f'{t}-{m}' for t in ('SPY','QQQ') for m in (1,5,15)]
KEYS=['chart_row','signal_at_ns','right','target_dte','contract']
LABEL_COLUMNS=['status','reason','debit_cents','pnl_cents','quantity','entry_vwap','exit_kind','terminal_ns','rolls','pin','exit_signal_ns','logical_memberships']
AMENDMENTS=['docs/specs/ETFE_ROW_UNIT_AMENDMENT_20261007.md','docs/specs/ETFE_FEATURE_AMENDMENT_20261007.md']


def feature_schema_sha256():
    sc=schema()
    return a.digest(dict(matrix_columns=sc['matrix_columns'],groups=sc['groups'],value_dtype='float64',mask_dtype='uint8',
        amendments={p:a.sha((ROOT/p).read_bytes()) for p in AMENDMENTS}))


def build_partition(tag,labels=LABELS):
    lab=pq.read_table(labels/f'{tag}.parquet').to_pandas()
    feat=pq.read_table(FEATURES/f'{tag}.parquet')
    keys=feat.select(KEYS).to_pandas()
    lab=lab.rename(columns={'contract':'contract'})
    if len(lab)!=len(keys):raise ValueError(f'{tag}: row count mismatch')
    for k in KEYS:
        if not (lab[k].to_numpy()==keys[k].to_numpy()).all():raise ValueError(f'{tag}: key mismatch {k}')
    settled=(lab.status=='settled').to_numpy()
    R=np.where(settled,lab.pnl_cents/np.where(lab.debit_cents>0,lab.debit_cents,1),np.nan)
    session=pd.to_datetime(lab.signal_at_ns,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    horizon=np.where(settled,lab.terminal_ns,END_NS)
    extra=pa.table({'session_date':session.to_numpy(),'purge_horizon_ns':horizon.astype('int64'),
        'target_return':R,'target_win':np.where(settled,(R>0).astype(float),np.nan),
        'target_weight':np.where(settled,np.clip(np.abs(R),.01,5),np.nan),'labeled':settled})
    labels=pa.Table.from_pandas(lab[LABEL_COLUMNS],preserve_index=False)
    out=feat.select(['ticker','minutes']+KEYS)
    for t in (extra,labels):
        for name,col in zip(t.column_names,t.columns):out=out.append_column(name,col)
    for name in feat.column_names:
        if name not in out.column_names:out=out.append_column(name,feat[name])
    return out


def freeze(root,labels=LABELS):
    root=Path(root);labels=Path(labels);root.mkdir(parents=True,exist_ok=False);parts={};census={}
    for tag in SCOPES:
        t=build_partition(tag,labels);path=root/f'{tag}.parquet'
        tmp=root/f'.{tag}.tmp';pq.write_table(t,tmp,compression='zstd',row_group_size=200000)
        a.write_new(path,tmp.read_bytes());tmp.unlink()
        st=pd.Series(t['status'].to_numpy()).value_counts().to_dict()
        parts[tag]=dict(path=path.name,sha256=a.sha(path.read_bytes()),rows=t.num_rows,labeled=int(np.sum(t['labeled'].to_numpy())))
        census[tag]={k:int(v) for k,v in st.items()}
    inputs={}
    for base in (labels,FEATURES):
        for p in sorted(base.glob('*')):
            if p.is_file():inputs[str(p.relative_to(ROOT))]=a.sha(p.read_bytes())
    sessions=sorted({s for tag in SCOPES for s in pq.read_table(root/f'{tag}.parquet',columns=['session_date'])['session_date'].to_pylist()})
    fill_rule=json.loads((labels/'SPY.json').read_text()).get('kernel_policy',{}).get('fill_rule','signal_bar_vwap')
    manifest=dict(schema='etfe-dataset-v1',labels_root=str(labels.relative_to(ROOT)),fill_rule=fill_rule,feature_schema_sha256=feature_schema_sha256(),scopes=SCOPES,partitions=parts,census=census,
        rows=sum(p['rows'] for p in parts.values()),labeled_rows=sum(p['labeled'] for p in parts.values()),
        sessions=sessions,history_start='2024-01-18',history_end_inclusive='2026-10-02',
        row_identity=['ticker','minutes']+KEYS,targets=dict(return_huber='P/A',win='float(P/A>0)',weighted_win_weight='clip(abs(P/A),.01,5)'),
        purge_horizon='final cash settlement for settled rows; fixed end for all others',
        inputs=inputs,amendments={p:a.sha((ROOT/p).read_bytes()) for p in AMENDMENTS},frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        immutable=True,ready_for_training=True)
    manifest['sha256']=a.digest({k:v for k,v in manifest.items() if k!='frozen_at'})
    a.save(root/'MANIFEST.json',manifest)
    return {k:v for k,v in manifest.items() if k not in ('inputs','sessions','partitions')}


def verify(root):
    """Independent reload: partition hashes, inputs unchanged, labels/targets recomputed, keys unique."""
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_text());problems=[]
    if a.digest({k:v for k,v in m.items() if k not in ('frozen_at','sha256')})!=m['sha256']:problems.append('manifest digest')
    for p,h in m['inputs'].items():
        if a.sha((ROOT/p).read_bytes())!=h:problems.append(f'input drift {p}')
    if m['feature_schema_sha256']!=feature_schema_sha256():problems.append('feature schema drift')
    for tag,info in m['partitions'].items():
        path=root/info['path']
        if a.sha(path.read_bytes())!=info['sha256']:problems.append(f'{tag}: partition hash');continue
        t=pq.read_table(path,columns=['ticker','minutes','chart_row','signal_at_ns','right','target_dte','contract','status','debit_cents','pnl_cents','target_return','target_win','labeled']).to_pandas()
        if t.duplicated(['ticker','minutes','chart_row','signal_at_ns','right','target_dte']).any():problems.append(f'{tag}: duplicate row identity')
        s=t[t.status=='settled']
        if not np.allclose(s.target_return,s.pnl_cents/s.debit_cents,rtol=0,atol=1e-15):problems.append(f'{tag}: target_return')
        if not ((s.target_win==1)==(s.pnl_cents>0)).all():problems.append(f'{tag}: target_win')
        if t[t.status!='settled'].target_return.notna().any():problems.append(f'{tag}: unlabeled target present')
        if int(t.labeled.sum())!=info['labeled'] or len(t)!=info['rows']:problems.append(f'{tag}: census')
    result=dict(schema='etfe-dataset-v1-verify',manifest_sha256=m['sha256'],problems=problems,passed=not problems)
    a.save(root/'VERIFY.json',result);return result
