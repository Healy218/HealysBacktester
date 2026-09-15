"""Reconstitute V7 monthly eligibility from verified whole-market observations."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.universe_pit import monthly_membership
    from nn_meta.v7.storage import transaction,receipt,verify,identity,sha
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    plan=json.loads(args.plan.read_text())['plan'];end=plan['historical_window'][1]
    # Only completed calendar months can be reconstituted; the current partial
    # month can supply market inputs but never its own universe membership.
    through=str(pd.Period(end,freq='M')-1)
    paths=sorted((args.audit/'options').glob('*/roots.parquet'))
    frames=[];sources={}
    for path in paths:
        verify(path.parent);frames.append(pd.read_parquet(path));sources[str(path)]=sha(path)
    daily=pd.concat(frames,ignore_index=True)
    membership=monthly_membership(daily,through=through)
    relevant=membership[(membership.month>='2022-02') & (membership.available_at<=end)]
    symbols=sorted(set(relevant.ticker))
    current=set(plan['catalog']['symbols'])
    report={'schema':'v7-pit-universe-audit-v1','through_month':through,
            'observed_sessions':daily.date.nunique(),'membership_rows':len(relevant),
            'historical_members':len(symbols),'additional_stock_symbols':sorted(set(symbols)-current),
            'reference_symbols_never_eligible':sorted(current-set(symbols)),
            'aliases':'existing SQ/XYZ FI/FISV BITF/DRAM mapping; reference identity audit still required',
            'research_ready':False}
    with transaction(args.output) as temp:
        membership.to_parquet(temp/'membership.parquet',index=False)
        (temp/'symbols.txt').write_text('\n'.join(symbols)+'\n')
        (temp/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        receipt(temp,{'identity':identity({'sources':sources,'plan':sha(args.plan),
                                        'code':sha(ROOT/'nn_meta/universe_pit.py')}),
                      'research_ready':False})
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
