"""Configured FA archive synchronization, daily prices and scheduled job dispatch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fa.monthly import locked, sha, freeze, track
from scripts.job_receipts import write


def archive_inventory(host,remote,sources):
    code=('import hashlib,json;from pathlib import Path;'
          f'r=Path({remote!r});sources={sources!r};'
          'print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() '
          'for s in sources for p in sorted((r/s).glob("*.parquet"))}))')
    return json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,
                                              'python3 -c '+shlex.quote(code)],text=True,timeout=90))


def pull_archive(cfg,seed=False):
    sources=['news','reddit','reddit_comments','edgar']
    archive=Path(cfg['archive'])
    if seed:
        sources+=['stocktwits','stocktwits_sentiment']
        if any((archive/s).exists() for s in sources[-2:]):raise ValueError('StockTwits seed requires empty local destinations')
    before=archive_inventory(cfg['server'],cfg['server_archive'],sources)
    if any(not any(p.startswith(s+'/') for p in before) for s in sources):raise ValueError('Server archive source missing')
    archive.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.incoming-',dir=archive.parent) as temp:
        stage=Path(temp)
        for source in sources:
            dest=stage/source;dest.mkdir()
            subprocess.run(['rsync','-az','--include=*.parquet','--exclude=*','-e','ssh -o BatchMode=yes',
                            f"{cfg['server']}:{cfg['server_archive']}/{source}/",str(dest)+'/'],check=True,timeout=180)
        after=archive_inventory(cfg['server'],cfg['server_archive'],sources)
        actual={p.relative_to(stage).as_posix():sha(p) for p in stage.glob('*/*.parquet')}
        if before!=after or actual!=before:raise ValueError('Server archive changed during transfer; retry without publishing')
        for source in sources:
            with locked(archive/source/'.archive.lock'):
                for p in sorted((stage/source).glob('*.parquet')):os.replace(p,archive/source/p.name)
    result=dict(sources=sources,files=len(before),sha256=before)
    write(Path(cfg['state'])/'archive-inputs.json',result)
    return result


def daily_prices(cfg,*,now=None,fetch=None):
    import pandas as pd
    from nn_meta import config
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    today=now.tz_convert('UTC').normalize()
    symbols=set(json.loads(Path(cfg['baseline']).read_text()))
    start=today-pd.Timedelta(days=90)
    for p in Path(cfg['cohorts']).glob('????-??/top10_*.json'):
        cohort=json.loads(p.read_text())
        symbols.update(r['ticker'] for r in cohort['rows'])
        symbols.update(json.loads((p.parent/'inputs/baseline.json').read_text()))
        start=min(start,pd.Timestamp(cohort['tracking_start']))
    if not symbols or any(not re.fullmatch(r'[A-Z][A-Z0-9.]{0,14}',s) for s in symbols):raise ValueError('Invalid price universe')
    calendar=json.loads(Path(cfg['calendar']).read_text())
    if not calendar['coverage_start']<=str(start.date())<=str(today.date())<=calendar['coverage_end']:
        raise ValueError('Captured calendar does not cover daily price request')
    dates=pd.DatetimeIndex(sorted(pd.Timestamp(s['date']) for s in calendar['sessions']
                                  if str(start.date())<=s['date']<str(today.date())))
    if len(dates)<2:raise ValueError('Insufficient completed sessions')
    aliases={s:getattr(config,'FETCH_ALIASES',{}).get(config.TICKER_ALIASES.get(s,s),config.TICKER_ALIASES.get(s,s)) for s in symbols}
    if fetch is None:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from dotenv import load_dotenv
        load_dotenv(ROOT/'.env')
        client=StockHistoricalDataClient(os.environ['ALPACA_API_KEY'],os.environ['ALPACA_API_SECRET'])
        def fetch(names):
            request=StockBarsRequest(symbol_or_symbols=names,timeframe=TimeFrame.Day,start=start.to_pydatetime(),
                                    end=today.to_pydatetime(),adjustment='all',feed='sip')
            return client.get_stock_bars(request).df
    prices=Path(cfg['prices']);prices.mkdir(parents=True,exist_ok=True)
    with locked(prices/'.prices.lock'), tempfile.TemporaryDirectory(prefix='.prices-',dir=prices.parent) as temp:
        stage=Path(temp);hashes={}
        ordered=sorted(symbols)
        for offset in range(0,len(ordered),30):
            batch=ordered[offset:offset+30]
            data=fetch(sorted(set(aliases[s] for s in batch)))
            for symbol in batch:
                df=data.xs(aliases[symbol],level='symbol').copy()
                df.index=pd.to_datetime(df.index,utc=True).tz_convert('America/New_York').normalize().tz_localize(None)
                df=df.rename(columns={'close':'Close'})[['Close']].sort_index()
                df=df[(df.index>=dates[0])&(df.index<=dates[-1])]
                if df.index.has_duplicates or not df.index.equals(dates) or not ((df.Close>0)&(df.Close<float('inf'))).all():
                    raise ValueError('Incomplete/invalid daily prices for '+symbol)
                df.to_parquet(stage/(symbol+'.parquet'));hashes[symbol]=sha(stage/(symbol+'.parquet'))
        for p in stage.glob('*.parquet'):os.replace(p,prices/p.name)
        result=dict(provider='Alpaca SIP',adjustment='all',first=str(dates[0].date()),last=str(dates[-1].date()),
                    sessions=len(dates),symbols=len(symbols),calendar_sha256=sha(cfg['calendar']),files=hashes)
        write(prices/'manifest.json',result)
    return result


def packed_backup(cfg):
    """Shard tiny cache files into tar archives; publish manifest only after upload."""
    import tarfile
    from datetime import datetime, timezone
    source=Path(cfg['packed_backup']['source'])
    destination=cfg['packed_backup']['destination'].rstrip('/')+'/'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    files=sorted(p for p in source.rglob('*') if p.is_file())
    if not files or any(p.is_symlink() for p in files):raise ValueError('Missing or symlinked packed backup inputs')
    def inventory():return {str(p.relative_to(source)):(p.stat().st_size,p.stat().st_mtime_ns) for p in source.rglob('*') if p.is_file()}
    before=inventory()
    files=sorted(source/name for name in before)
    if any(p.is_symlink() for p in files):raise ValueError('Symlinked packed backup input')
    with tempfile.TemporaryDirectory(prefix='healys-packed-backup-') as temp:
        stage=Path(temp);parts=[]
        for offset in range(0,len(files),1000):
            target=stage/f'part-{offset//1000:05d}.tar'
            with tarfile.open(target,'w') as tar:
                for p in files[offset:offset+1000]:tar.add(p,arcname=str(p.relative_to(source)),recursive=False)
            parts.append(dict(name=target.name,sha256=sha(target),files=len(files[offset:offset+1000]),bytes=target.stat().st_size))
        if before!=inventory():raise ValueError('Backup source changed during packing; no snapshot published')
        print(f'Uploading {len(parts)} shards for {len(files)} files to {destination}',flush=True)
        subprocess.run([cfg['gsutil'],'-o','GSUtil:parallel_process_count=1','-o','GSUtil:parallel_thread_count=8',
                        '-m','cp',*[str(stage/p['name']) for p in parts],destination+'/'],check=True)
        from scripts.verify_backup_sample import verify
        sample=parts[0]
        verify(stage/sample['name'],destination+'/'+sample['name'],gsutil=cfg['gsutil'],state_dir=cfg['state'])
        result=dict(source=str(source),destination=destination,format='tar shards, paths relative to source',files=len(files),parts=parts)
        write(stage/'manifest.json',result)
        subprocess.run([cfg['gsutil'],'cp',str(stage/'manifest.json'),destination+'/manifest.json'],check=True)
        write(Path(cfg['state'])/'packed-backup.json',result)
        return dict(source=str(source),destination=destination,files=len(files),shards=len(parts),restored_sample=sample['name'])


def backup(cfg):
    gsutil=cfg['gsutil'];results=[]
    for source,dest in cfg['backup_roots']:
        if not Path(source).is_dir():raise ValueError('Configured backup source missing: '+source)
        subprocess.run([gsutil,'-o','GSUtil:parallel_process_count=1','-o','GSUtil:parallel_thread_count=2',
                        '-m','-q','rsync','-r','-x',r'.*(\.tmp.*|\.lock)$',source,dest],check=True)
        results.append(dict(source=source,destination=dest))
    if cfg.get('packed_backup'):results.append(packed_backup(cfg))
    write(Path(cfg['state'])/'backup-scope.json',dict(completed=results))
    return results


def health(cfg):
    from datetime import datetime, timezone
    from scripts.check_ops_health import check_job,check_capture
    now=datetime.now(timezone.utc);results=[]
    for name,hours in cfg['job_hours'].items():
        folder=Path(cfg['state'])/name
        first=cfg.get('not_before',{}).get(name)
        if not (folder/'latest.json').exists() and first and now<datetime.fromisoformat(first):
            results.append(dict(job=name,healthy=True,state='awaiting-first-scheduled-run',due=first));continue
        results.append(check_job(folder,hours*3600,now))
    for source,hours in cfg['capture_hours'].items():results.append(check_capture(Path(cfg['archive'])/source,hours*3600,now))
    print(json.dumps(results,indent=2))
    return 0 if all(r['healthy'] for r in results) else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('job',choices=['archive','seed','prices','monthly','tracker','backup','health','preflight'])
    p.add_argument('--config',type=Path,default=ROOT/'deploy/fa-runtime.json')
    a=p.parse_args();cfg=json.loads(a.config.read_text())
    if a.job=='health':return health(cfg)
    if a.job in ('archive','seed'):result=pull_archive(cfg,seed=a.job=='seed')
    elif a.job=='prices':result=daily_prices(cfg)
    elif a.job=='backup':result=backup(cfg)
    elif a.job=='monthly':
        pull_archive(cfg)
        result=freeze(cfg['cohorts'],cfg['archive'],cfg['liquid'],cfg['baseline'],cfg.get('aliases'))
    elif a.job=='tracker':
        from scripts.check_ops_health import check_job
        from datetime import datetime, timezone
        if not check_job(Path(cfg["state"])/"fa-prices", 48*3600, datetime.now(timezone.utc))["healthy"]:
            raise ValueError("Daily price refresh is missing, stale or failed")
        import pandas as pd
        with locked(Path(cfg['prices'])/'.prices.lock'):
            result=track(cfg['cohorts'],cfg['prices'],as_of=pd.Timestamp.now(tz='UTC').normalize()-pd.Timedelta(days=1))
    else:
        from fa import ranker
        import pandas as pd
        manifest=json.loads((Path(cfg['prices'])/'manifest.json').read_text())
        ranking,meta=ranker.build_monthly_ranking(pd.Timestamp.now(tz='UTC'),archive=Path(cfg['archive']),
                    liquid_path=cfg['liquid'],training_path=cfg['baseline'],aliases_path=cfg.get('aliases'))
        result=dict(status='preflight-only',price_symbols=manifest['symbols'],last_price=manifest['last'],
                    ranking_candidates=len(ranking),score_rows=meta['score_rows'],cohort_created=False)
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
