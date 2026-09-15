"""Build dated-identity V7 membership and surface unresolved identity boundaries."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.universe import security_masters,membership,daily_identity_overrides
    from nn_meta.v7.storage import transaction,receipt,identity,sha,verify
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('audit','masters','calendar','output'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--references',type=Path)
    ap.add_argument('--identity-requests',type=Path)
    args=ap.parse_args();frames=[];sources={}
    for p in sorted((args.audit/'options').glob('*/roots.parquet')):
        verify(p.parent);frames.append(pd.read_parquet(p));sources[str(p)]=sha(p)
    masters,master_sources=security_masters(args.masters)
    identity_days, identity_sources = {}, {}
    if bool(args.references) != bool(args.identity_requests):
        raise ValueError('Dated requests and reference root are required together')
    if args.references:
        identity_days, identity_sources = daily_identity_overrides(args.references,
                                               json.loads(args.identity_requests.read_text()))
    rows,report=membership(pd.concat(frames,ignore_index=True),masters,json.loads(args.calendar.read_text()),
                           identity_days=identity_days)
    relevant=rows[rows.month>='2022-02'];symbols=sorted(set(relevant.ticker))
    report.update(historical_symbols=len(symbols),historical_securities=relevant.security_id.nunique(),rows=len(relevant))
    with transaction(args.output) as temp:
        rows.to_parquet(temp/'membership.parquet',index=False)
        (temp/'symbols.txt').write_text('\n'.join(symbols)+'\n')
        (temp/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        receipt(temp,{'identity':identity({'daily':sources,'masters':master_sources,'identity_days':identity_sources,'calendar':sha(args.calendar),
                                        'code':sha(ROOT/'nn_meta/v7/universe.py')}),'research_ready':False})
    print(json.dumps({k:v for k,v in report.items() if k!='unmapped_root_months'},indent=2))


if __name__=='__main__':main()
