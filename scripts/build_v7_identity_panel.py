"""Join complete daily listed captures to every retained raw daily stock row."""
from pathlib import Path
import argparse
from collections import Counter
import gzip
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.daily_identities import EXCHANGES,query,page_records
    from nn_meta.v7.identity_panel import attach_day,continuity_spans
    from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('stock-daily','identities','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):raise ValueError('Repository artifact disk required')
    inputs={}
    def merge(values):
        for path,digest in values.items():
            if path in inputs and inputs[path]!=digest:raise ValueError('Conflicting identity parent bindings')
            inputs[path]=digest
    def bind(path):
        doc=verify(path)
        merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/name):digest for name,digest in doc['files'].items()})
        return doc
    bind(args.stock_daily/'summary');bind(args.identities/'summary')
    stock_binding=json.loads((args.stock_daily/'summary/binding.json').read_text())
    listing_binding=json.loads((args.identities/'summary/binding.json').read_text())
    capture=listing_binding['declaration'];days=capture['days']
    if capture['exchanges']!=list(EXCHANGES):raise ValueError('Complete listed-exchange capture scope required')
    merge(capture['sources']);merge({capture['calendar']:capture['calendar_sha256']})
    merge(stock_binding['declaration']['inputs']);merge(stock_binding['declaration']['sources'])
    for path in [Path(__file__),ROOT/'nn_meta/v7/identity_panel.py',ROOT/'nn_meta/v7/daily_identities.py',
                 ROOT/'nn_meta/v7/storage.py',ROOT/'nn_meta/v7/runtime.py']:
        merge({str(path):sha(path)})
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Identity parents changed')
    raw=[]
    for receipt_path,digest in stock_binding['shards'].items():
        path=Path(receipt_path).parent
        if sha(receipt_path)!=digest:raise ValueError('Raw daily shard binding differs')
        bind(path)
        frame=pd.read_parquet(path/'daily.parquet',columns=['source_date'])
        frame['stock_ticker']=path.parent.name;raw.append(frame)
    raw=pd.concat(raw,ignore_index=True)
    if not raw.source_date.isin(days).all():raise ValueError('Raw stock dates outside listed capture')
    chunks=[]
    for day,stock in raw.groupby('source_date',sort=True):
        records=[];day_sources={}
        for exchange in EXCHANGES:
            path=args.identities/day/exchange
            expected=listing_binding['shards'].get(str(path/'complete.json'))
            if expected!=sha(path/'complete.json'):raise ValueError('Dated listing shard not in complete capture')
            doc=bind(path)
            if doc['query']!=query(day,exchange):raise ValueError('Listing query differs')
            seen=set();count=0
            for page in sorted(path.glob('page-*.json.gz')):
                rows=page_records(json.loads(gzip.decompress(page.read_bytes())),exchange,seen)
                records.extend(rows);count+=len(rows)
            if count!=doc['records']:raise ValueError('Listing record count differs')
            day_sources[str(path/'complete.json')]=expected
        chunks.append(attach_day(stock,records,day=day,evidence_identity=identity(day_sources)))
    panel=continuity_spans(pd.concat(chunks,ignore_index=True),days)
    eligible=pd.read_parquet(args.stock_daily/'summary/eligible_daily.parquet',
        columns=['stock_ticker','source_date','security_id'])
    joined=eligible.merge(panel,on=['stock_ticker','source_date'],how='left',validate='one_to_one',indicator=True)
    if not joined._merge.eq('both').all():raise ValueError('Missing eligible identity joins')
    joined=joined.drop(columns='_merge')
    joined['eligible_identity_matches']=joined.listed_security_id.eq(joined.security_id).fillna(False)
    report=dict(raw_rows=len(panel),source_tickers=panel.stock_ticker.nunique(),
        provider_dated_securities=panel.listed_security_id.nunique(),identity_spans=panel.identity_span.nunique(),
        identity_statuses=dict(Counter(panel.identity_status)),eligible_rows=len(joined),
        eligible_identity_matches=int(joined.eligible_identity_matches.sum()),
        eligible_identity_unresolved=int((~joined.eligible_identity_matches).sum()),
        historical_publication_vintage_verified=False,full_security_admitted=False,research_ready=False,
        remaining='Review mismatches, stitch dated aliases, and combine with complete action/no-event evidence')
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Identity panel evidence changed')
    with transaction(args.output) as temp:
        panel.to_parquet(temp/'identities.parquet',index=False)
        joined.to_parquet(temp/'eligible_identities.parquet',index=False)
        for name,value in [('report',report),('inputs',inputs)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
