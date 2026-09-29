"""Fixed-family retraining on an immutable base plus matured candidate rows."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from incubator.continual.storage import sha,identity,write,seal,verify


def assemble_delta(run_dir,features):
    rows=[]
    for inventory in sorted((Path(run_dir)/'symbols').glob('*/inventory.json')):
        verify(inventory.parent)
        cached={}
        for candidate in json.loads(inventory.read_text())['candidates']:
            if candidate['status']!='matured':continue
            origin=Path(candidate['feature_root']);label_root=Path(candidate['label_root'])
            verify(label_root);label=json.loads((label_root/'label.json').read_text())
            if origin not in cached:
                verify(origin)
                from .data import candidate_key
                cached[origin]={candidate_key(r):r for r in pd.read_parquet(origin/'features.parquet').to_dict('records')}
            row=cached[origin][candidate['candidate_id']]
            rows.append({k:row[k] for k in ['symbol','strategy','dte','entry_ts',*features]}|
                        {k:label[k] for k in ['exit_ts','fill_exit_ts','net_return','label_excess']}|
                        {'candidate_id':candidate['candidate_id']})
    frame=pd.DataFrame(rows)
    if len(frame):
        if frame.candidate_id.duplicated().any():raise ValueError('duplicate extension identities')
        frame['entry_ts']=pd.to_datetime(frame.entry_ts)
        frame['exit_ts']=pd.to_datetime(frame.exit_ts)
        frame['fill_exit_ts']=pd.to_datetime(frame.fill_exit_ts)
        frame=frame.sort_values(['entry_ts','symbol','strategy','dte'])
    frame.to_parquet(Path(run_dir)/'delta.parquet',index=False)
    return frame


from incubator.continual.training import prepare_arrays,train_member,evaluate
