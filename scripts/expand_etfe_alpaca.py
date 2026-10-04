"""Fresh calendar, stock-history and option-stratum expansion for ETFE."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import HTTP,capture
from nn_meta.etfe.expansion import capture_calendar,discovery_jobs,option_jobs,prepare_expansion,read_calendar,stock_jobs,verify_expansion


def credentials():
    from dotenv import dotenv_values
    values=dotenv_values(ROOT/'.env')
    result={role:(values.get(key),values.get(secret)) for role,key,secret in (
        ('data','ALPACA_API_KEY','ALPACA_API_SECRET'),('metadata','ALPACA_PAPER_API_KEY','ALPACA_PAPER_API_SECRET'))}
    if not all(all(pair) for pair in result.values()):
        raise ValueError('Missing Alpaca credential pairs')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['calendar','prepare-stocks','prepare-discovery','prepare-options','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--calendar',type=Path)
    p.add_argument('--stocks',type=Path)
    p.add_argument('--discovery',type=Path)
    p.add_argument('--request-budget',type=int)
    a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        p.error('Fresh isolated ETFE capture root required')
    if a.command=='calendar':
        result=capture_calendar(root,credentials());print(json.dumps(dict(calendar_rows=result['rows'])))
    elif a.command=='run':
        verify_expansion(root)
        r=capture(root,HTTP(credentials()),request_budget=a.request_budget)
        print(json.dumps({k:r[k] for k in ('capture_complete','requests_this_run','stop_reason','elapsed_seconds','peak_rss_bytes')}))
        print(json.dumps(dict(partitions=len(r['partitions']),terminal=sum(x['terminal'] for x in r['partitions']),rows=sum(x['rows'] for x in r['partitions']))))
        if not r['capture_complete'] or r['stop_reason']:raise SystemExit(2)
    else:
        if a.command=='prepare-stocks':
            jobs,details=stock_jobs(),{}
        elif a.command=='prepare-discovery':
            if a.calendar is None:p.error('--calendar required')
            jobs,details=discovery_jobs(read_calendar(a.calendar)),dict(calendar_root=str(a.calendar.resolve()))
        else:
            if a.stocks is None or a.discovery is None:p.error('--stocks and --discovery required')
            jobs,details=option_jobs(a.stocks,a.discovery)
        plan=prepare_expansion(root,jobs,a.command,**details)
        print(json.dumps(dict(plan_sha256=plan['sha256'],jobs=len(jobs))))


if __name__=='__main__':main()
