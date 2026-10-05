"""Supplemental independent reconciliation of daily inputs to frozen minute grids."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from nn_meta.etfe.acquisition import save,sha,write_new
from nn_meta.etfe.remaining_feature_pilot import verify,PILOT


def audit(root):
    root=Path(root).resolve();p=verify(root);shared=json.load(open(root/'SHARED.json'))
    f=shared['files'][2];assert sha((root/f['path']).read_bytes())==f['sha256']
    actual=pd.read_parquet(root/f['path']);checked=invalid=0
    for ticker in ('SPY','QQQ','VOO'):
        s=next(x for x in p['scopes'] if x['ticker']==ticker and x['minutes']==1)
        bars=pd.read_parquet(PILOT/s['underlying']['path']);out=actual[actual.ticker.eq(ticker)].set_index('session_date')
        assert set(out.index)==set(bars.session_date)
        for day,b in bars.groupby('session_date',sort=True):
            a=out.loc[day];expected=pd.date_range(b.session_open.iloc[0],b.session_close.iloc[0],freq='min',inclusive='left')
            assert b.index.equals(expected)
            valid=bool(b.valid.all() and np.isfinite(b.Close).all() and b.Close.gt(0).all())
            assert bool(a.complete)==valid
            assert a.session_open==b.session_open.iloc[0] and a.session_close==b.session_close.iloc[0]
            assert a.session_ordinal==b.session_ordinal.iloc[0]
            if valid:assert a.close==b.Close.iloc[-1]
            else:assert pd.isna(a.close);invalid+=1
            checked+=1
    source=Path(__file__);dest=root/'audit_extensions'/source.name;dest.parent.mkdir(exist_ok=True)
    write_new(dest,source.read_bytes())
    r=dict(plan_sha256=p['sha256'],auditor_sha256=sha(source.read_bytes()),source_snapshot=str(dest.relative_to(root)),
           minute_input_daily_rows_reconciled=checked,invalid_daily_closes=invalid,raw_aggregation_reconciled=True)
    save(root/'DAILY_INPUT_AUDIT.json',r);return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    print(json.dumps(audit(p.parse_args().root),indent=2))
