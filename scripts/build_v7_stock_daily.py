"""Build the active universe's raw daily stock facts and exact eligible joins.

Independent, resumable symbol/year shards keep at most one minute year per
worker. This does not admit adjusted daily features or unseen identity periods.
"""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def worker(task):
    from nn_meta.v7.stock_daily import build_shard
    return build_shard(*task)


def main():
    from nn_meta.v7.runtime import worker_pool, configure_threads
    configure_threads(1)
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.v7.scope import require_active_inputs, HISTORY_START, HISTORY_END
    from nn_meta.v7.stock_daily import join_eligible, source_hashes
    from nn_meta.v7.storage import sha, identity, verify, transaction, receipt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active', type=Path, default=ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or not 1 <= args.workers <= 4:
        raise ValueError('Repository artifact disk and 1–4 workers required')
    active = json.loads(args.active.read_text())
    source, coverage, universe = [ROOT/active[key] for key in ('working_inputs','coverage_inventory','universe')]
    require_active_inputs(source)
    for path, key in [(coverage,'coverage_receipt_sha256'),(universe,'universe_receipt_sha256')]:
        verify(path)
        if sha(path/'complete.json') != active[key]: raise ValueError('Active scope receipt changed')
    exclusion = ROOT/active['universe_exclusions']
    if sha(exclusion) != active['universe_exclusions_sha256']: raise ValueError('User exclusions changed')
    excluded = {r['security_id'] for r in json.loads(exclusion.read_text())['exclusions']}
    sessions = pd.read_parquet(coverage/'sessions.parquet')
    if (sessions.security_id.isin(excluded).any() or sessions.date.min() < HISTORY_START
            or sessions.date.max() > HISTORY_END or sessions.duplicated(['security_id','date']).any()):
        raise ValueError('Invalid active eligible scope')
    groups = {(symbol,int(year)):group for (symbol,year),group in
              sessions.groupby(['stock_ticker', sessions.date.str[:4]], sort=True)}
    # Preserve available raw history in all scoped years for these source symbols.
    # These extra dates receive NO inferred security identity/eligibility.
    pairs = sorted((symbol,year) for symbol in set(sessions.stock_ticker)
        for year in range(2022,2027) if (source/f'stock_1m/raw/{symbol}/{year}/complete.json').exists())
    if not set(groups).issubset(pairs): raise ValueError('Missing active raw stock capture')
    sources = source_hashes()
    inputs = {str(p):sha(p) for p in (args.active,coverage/'complete.json',universe/'complete.json',exclusion)}
    tasks = [(source,symbol,year,args.output/'shards'/symbol/str(year)) for symbol,year in pairs]
    args.output.mkdir(parents=True,exist_ok=True)
    declaration = dict(schema='v7-all-stock-daily-build-v1',inputs=inputs,sources=sources,
        pairs=pairs,eligible_sessions=len(sessions),workers=args.workers,research_ready=False)
    request_path=args.output/'request.json'
    if request_path.exists():
        if json.loads(request_path.read_text()) != json.loads(json.dumps(declaration)):
            raise ValueError('Daily build resume declaration differs')
    else:request_path.write_text(json.dumps(declaration,indent=2)+'\n')
    with worker_pool(args.workers,threads=1) as pool:
        for completed, report in enumerate(pool.map(worker,tasks,chunksize=1),1):
            if completed%25==0 or completed==len(tasks):
                print(json.dumps(dict(completed_shards=completed,total_shards=len(tasks),latest=report)),flush=True)
    summary=args.output/'summary'
    shard_inputs={str(task[3]/'complete.json'):sha(task[3]/'complete.json') for task in tasks}
    binding=dict(declaration=declaration,shards=shard_inputs)
    if summary.exists():
        verify(summary,expected_identity=identity(binding))
        print((summary/'report.json').read_text());return
    total=zero=aliases=raw_days=0
    with transaction(summary) as temp:
        writer=None
        try:
            for symbol,year in pairs:
                path=args.output/'shards'/symbol/str(year)
                verify(path)
                daily=pd.read_parquet(path/'daily.parquet')
                raw_days+=len(daily)
                if (symbol,year) not in groups:continue
                joined=join_eligible(groups[(symbol,year)],daily)
                joined['daily_receipt_sha256']=shard_inputs[str(path/'complete.json')]
                table=pa.Table.from_pandas(joined,preserve_index=False)
                if writer is None:writer=pq.ParquetWriter(temp/'eligible_daily.parquet',table.schema,compression='zstd')
                writer.write_table(table)
                total+=len(joined);zero+=int(joined.observed_minutes.eq(0).sum())
                aliases+=int(joined.status.eq('verified_session_alias').sum())
        finally:
            if writer is not None:writer.close()
        if total!=len(sessions):raise ValueError('Incomplete eligible daily assembly')
        if any(sha(p)!=digest for p,digest in {**inputs,**sources,**shard_inputs}.items()):
            raise ValueError('Daily assembly source changed')
        report=dict(shards=len(tasks),source_tickers=len(set(sessions.stock_ticker)),
            security_ids=sessions.security_id.nunique(),raw_calendar_rows=raw_days,
            eligible_sessions=total,observed_eligible_sessions=total-zero,zero_sessions=zero,
            verified_alias_sessions=aliases,research_ready=False,
            limitations=['Raw observations only; no causal actions or option surfaces applied',
                         'Dates outside active membership have no inferred security identity',
                         'Zero sessions require lifecycle routing, never forward-fill'])
        (temp/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        (temp/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
