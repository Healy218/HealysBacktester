"""Read-only receipt and capture freshness checks; JSON output and nonzero on gaps."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def age(value,now):
    ts=datetime.fromisoformat(value.replace('Z','+00:00'))
    if ts.tzinfo is None:raise ValueError('Receipt timestamp needs timezone')
    return (now-ts).total_seconds()


def check_job(folder,max_age,now):
    folder=Path(folder)
    try:
        latest=json.loads((folder/'latest.json').read_text())
        success=json.loads((folder/'last-success.json').read_text())
        elapsed=age(success['updated'],now)
        latest_age=age(latest['updated'],now)
        healthy=(latest['state']=='success' and success['state']=='success' and latest['returncode']==0
                 and success['returncode']==0 and latest['updated']==success['updated']
                 and 0<=elapsed<=max_age and 0<=latest_age<=max_age)
        return dict(job=folder.name,healthy=healthy,state=latest['state'],success_age_seconds=elapsed)
    except (OSError,ValueError,KeyError,TypeError):
        return dict(job=folder.name,healthy=False,state='missing-or-invalid-receipt')


def check_capture(folder,max_age,now):
    import pandas as pd
    folder=Path(folder)
    paths=sorted(folder.glob('*.parquet'))
    try:
        # Bounded inspection of the latest capture-month partition, not file mtime.
        if not paths:raise ValueError('No archive')
        ts=pd.to_datetime(pd.read_parquet(paths[-1],columns=['ts_utc'])['ts_utc'],utc=True,errors='raise')
        if ts.empty or ts.isna().any():raise ValueError('Missing capture times')
        elapsed=(pd.Timestamp(now)-ts.max()).total_seconds()
        return dict(source=folder.name,healthy=0<=elapsed<=max_age,capture_age_seconds=elapsed)
    except (OSError,ValueError,KeyError,TypeError):
        return dict(source=folder.name,healthy=False,state='missing-or-invalid-captures')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir',type=Path,default=ROOT/'logs/job-health')
    p.add_argument('--job',action='append',default=[],help='NAME:MAX_AGE_HOURS (repeat)')
    p.add_argument('--archive',type=Path,default=ROOT/'fa/archive')
    p.add_argument('--source',action='append',default=[],help='SOURCE:MAX_AGE_HOURS (repeat)')
    a=p.parse_args();now=datetime.now(timezone.utc);results=[]
    import re
    for values,base,fn in [(a.job,a.state_dir,check_job),(a.source,a.archive,check_capture)]:
        for item in values:
            name,hours=item.rsplit(':',1)
            if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',name) or not 0<float(hours)<100000:p.error('Invalid name or maximum age')
            results.append(fn(base/name,float(hours)*3600,now))
    if not results:p.error('Specify at least one --job or --source')
    print(json.dumps(dict(checked=now.isoformat(),checks=results),indent=2))
    return 0 if all(r['healthy'] for r in results) else 1


if __name__=='__main__':raise SystemExit(main())
