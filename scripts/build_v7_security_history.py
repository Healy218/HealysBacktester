"""Stitch raw daily histories across exact-date listed identities for all active IDs."""
from pathlib import Path
import argparse
from collections import Counter
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.v7.causal_daily import timeline
    from nn_meta.v7.security_history import security_history
    from nn_meta.v7.scope import HISTORY_START,HISTORY_END
    from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
    from scripts.build_v7_surfaces import availability_calendar
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('stock-daily','identities','source','availability-calendar','aliases','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):raise ValueError('Repository artifact disk required')
    inputs={}
    def merge(values):
        for path,digest in values.items():
            if path in inputs and inputs[path]!=digest:raise ValueError('Conflicting history parent bindings')
            inputs[path]=digest
    def bind(path):
        doc=verify(path)
        merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/name):digest for name,digest in doc['files'].items()})
        return doc
    bind(args.stock_daily/'summary');bind(args.identities);bind(args.availability_calendar);bind(args.aliases)
    merge(json.loads((args.aliases/'report.json').read_text())['sources'])
    aliases=pd.read_parquet(args.aliases/'session_aliases.parquet')
    merge(json.loads((args.identities/'inputs.json').read_text()))
    stock_binding=json.loads((args.stock_daily/'summary/binding.json').read_text())
    merge(stock_binding['declaration']['inputs']);merge(stock_binding['declaration']['sources'])
    calendar_path=args.source/'calendar.json'
    merge({str(calendar_path):sha(calendar_path)})
    calendar=availability_calendar(calendar_path,args.availability_calendar)
    clock=timeline(calendar,HISTORY_START,HISTORY_END)
    for path in [Path(__file__),ROOT/'nn_meta/v7/security_history.py',ROOT/'nn_meta/v7/causal_daily.py',
                 ROOT/'nn_meta/v7/causal_prices.py',ROOT/'nn_meta/v7/scope.py',ROOT/'nn_meta/v7/storage.py',
                 ROOT/'nn_meta/v7/runtime.py',ROOT/'nn_meta/session_calendar.py',ROOT/'scripts/build_v7_surfaces.py']:
        merge({str(path):sha(path)})
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Security history parents changed')
    frames=[]
    for receipt_path,digest in stock_binding['shards'].items():
        path=Path(receipt_path).parent
        if sha(receipt_path)!=digest:raise ValueError('Raw daily shard changed')
        bind(path);frames.append(pd.read_parquet(path/'daily.parquet'))
    raw=pd.concat(frames,ignore_index=True)
    panel=pd.read_parquet(args.identities/'identities.parquet')
    keys=['stock_ticker','source_date']
    columns=keys+['listed_security_id','identity_status','identity_evidence_identity']
    mapped=raw.merge(panel[columns],on=keys,how='outer',validate='one_to_one',indicator=True)
    if not mapped._merge.eq('both').all():raise ValueError('Identity and raw panels do not match exactly')
    mapped=mapped.drop(columns='_merge')
    eligible=pd.read_parquet(args.stock_daily/'summary/eligible_daily.parquet',columns=keys+['security_id'])
    securities=sorted(eligible.security_id.unique())
    grouped={key:frame for key,frame in mapped[mapped.listed_security_id.isin(securities)].groupby('listed_security_id')}
    empty=mapped.iloc[:0]
    rows=renames=spans=0;statuses=Counter();checks=[]
    with transaction(args.output) as temp:
        writer=None
        try:
            for sid in securities:
                overrides=[dict(source_date=r['date'],stock_ticker=r['stock_ticker'],security_id=sid,
                    evidence_identity=identity(dict(alias=r,receipt=sha(args.aliases/'complete.json'))))
                    for r in aliases[aliases.security_id.eq(sid)].to_dict('records')]
                result=security_history(grouped.get(sid,empty),clock,security_id=sid,source_overrides=overrides)
                table=pa.Table.from_pandas(result,preserve_index=False)
                if writer is None:writer=pq.ParquetWriter(temp/'history.parquet',table.schema,compression='zstd')
                # Different IDs can have all-null strings, so use one declared schema.
                writer.write_table(table.cast(writer.schema))
                expected=eligible[eligible.security_id.eq(sid)]
                check=expected.merge(result[['security_id','source_date','stock_ticker','source_status']],
                    on=['security_id','source_date'],how='left',validate='one_to_one',suffixes=('_expected','_selected'))
                check['source_matches']=check.stock_ticker_expected.eq(check.stock_ticker_selected).fillna(False)
                checks.append(check)
                rows+=len(result);renames+=int(result.ticker_changed.sum());spans+=result.identity_span.nunique()
                statuses.update(result.source_status)
        finally:
            if writer is not None:writer.close()
        comparison=pd.concat(checks,ignore_index=True)
        comparison.to_parquet(temp/'eligible_sources.parquet',index=False)
        if rows!=len(securities)*len(clock) or len(comparison)!=len(eligible):
            raise ValueError('Incomplete security history grid')
        report=dict(securities=len(securities),sessions=len(clock),security_calendar_rows=rows,
            identity_spans=spans,dated_ticker_changes=renames,source_statuses=dict(statuses),
            eligible_rows=len(comparison),eligible_source_matches=int(comparison.source_matches.sum()),
            eligible_source_unresolved=int((~comparison.source_matches).sum()),
            action_adjustments_applied=False,research_ready=False,
            remaining='Review unresolved sources/lifecycle and apply complete reviewed action/no-event evidence')
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Security history inputs changed')
        for name,value in [('report',report),('inputs',inputs)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
