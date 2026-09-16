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
    ap.add_argument('--reviewed-boundaries',type=Path)
    ap.add_argument('--active-source',type=Path,required=True)
    args=ap.parse_args();frames=[];sources={}
    from nn_meta.v7.scope import require_active_inputs, EXCLUDED_START, EXCLUDED_END
    require_active_inputs(args.active_source)
    if args.audit.resolve() != (args.active_source/'audit').resolve():
        raise ValueError('Use the active date-filtered option audits')
    calendar=json.loads(args.calendar.read_text())
    if sha(args.calendar) != sha(args.active_source/'calendar.json'):
        raise ValueError('Use the full captured active-input calendar')
    excluded=[s['date'] for s in calendar['sessions'] if EXCLUDED_START<=s['date']<=EXCLUDED_END]
    for p in sorted((args.audit/'options').glob('*/roots.parquet')):
        verify(p.parent);frames.append(pd.read_parquet(p));sources[str(p)]=sha(p)
    masters,master_sources=security_masters(args.masters)
    identity_days, identity_sources = {}, {}
    if bool(args.references) != bool(args.identity_requests):
        raise ValueError('Dated requests and reference root are required together')
    if args.references:
        identity_days, identity_sources = daily_identity_overrides(args.references,
                                               json.loads(args.identity_requests.read_text()))
    if args.reviewed_boundaries:
        if not args.references:
            raise ValueError('Reviewed boundaries require original dated captures')
        from nn_meta.v7.identity_review import reviewed_overrides
        reviewed, review_sources = reviewed_overrides(args.reviewed_boundaries, masters=masters,
                                                      reference_root=args.references, known=identity_days)
        identity_days.update(reviewed)
        identity_sources.update(review_sources)
    rows,report=membership(pd.concat(frames,ignore_index=True),masters,calendar,
                           identity_days=identity_days,excluded_sessions=excluded)
    sources[str(args.active_source/'scope.json')]=sha(args.active_source/'scope.json')
    sources[str(args.active_source/'report.json')]=sha(args.active_source/'report.json')
    relevant=rows[rows.month>='2022-02'];symbols=sorted(set(relevant.ticker))
    report.update(historical_symbols=len(symbols),historical_securities=relevant.security_id.nunique(),rows=len(relevant))
    provenance={'daily':sources,'masters':master_sources,'identity_days':identity_sources,
                'calendar':sha(args.calendar),'lookback_policy':report['lookback_policy'],
                'code':{str(p.relative_to(ROOT)):sha(p) for p in
                        (Path(__file__),ROOT/'nn_meta/v7/universe.py',ROOT/'nn_meta/v7/identity_review.py')}}
    with transaction(args.output) as temp:
        rows.to_parquet(temp/'membership.parquet',index=False)
        (temp/'symbols.txt').write_text('\n'.join(symbols)+'\n')
        (temp/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        (temp/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        receipt(temp,{'identity':identity(provenance),
                      'research_ready':False})
    print(json.dumps({k:v for k,v in report.items() if k not in ('unmapped_root_months','lookback_windows')},indent=2))


if __name__=='__main__':main()
