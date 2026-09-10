"""Prospective, immutable monthly cohorts with captured inputs and safe retries."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import pandas as pd

from fa import config, ranker
from fa.universe_loop import freeze_ranking, RANKING_RECIPE_VERSION


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def utc(value):
    return pd.Timestamp(value).tz_convert('UTC') if pd.Timestamp(value).tzinfo else pd.Timestamp(value).tz_localize('UTC')


def plan(now=None):
    now = utc(now if now is not None else pd.Timestamp.now(tz='UTC'))
    start = now.normalize().replace(day=1)
    return dict(month=(start-pd.Timedelta(days=1)).strftime('%Y-%m'),
                cutoff=(start-pd.Timedelta(nanoseconds=1)).isoformat(),
                available_at=now.isoformat(), within_freeze_window=now < start+pd.Timedelta(days=7))


def verify(folder):
    folder = Path(folder)
    manifest = json.loads((folder/'manifest.json').read_text())
    if manifest['recipe_version'] != RANKING_RECIPE_VERSION:
        raise ValueError('Historical recipe is not a prospective cohort.')
    for relative, expected in manifest['files'].items():
        path = folder/relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink() or sha(path) != expected:
            raise ValueError('Cohort input/output hash mismatch: '+relative)
    return manifest


def freeze(root, archive, liquid, baseline, aliases=None, *, now=None):
    root, archive = Path(root), Path(archive)
    if aliases is None and ranker.ALIASES.exists():
        aliases = ranker.ALIASES
    info = plan(now)
    final = root/info['month']
    with locked(root/'.monthly.lock'):
        if final.exists():
            return verify(final)  # Retry uses the original cohort, never today's inputs.
        if not info['within_freeze_window']:
            raise ValueError('New prospective freezes are restricted to the first seven UTC days of the month; no late backfill.')
        if not archive.is_dir():
            raise ValueError('Capture archive is missing.')
        staged = Path(tempfile.mkdtemp(prefix='.pending-'+info['month']+'-', dir=root))
        try:
            inputs = staged/'inputs'; inputs.mkdir()
            for name, source in [('liquid.json', liquid), ('baseline.json', baseline)]:
                values = json.loads(Path(source).read_text())
                if not isinstance(values,list) or not values or not all(isinstance(v,str) and v for v in values) or len(set(values)) != len(values):
                    raise ValueError('Universe must be a nonempty list of distinct tickers.')
                (inputs/name).write_text(json.dumps(values,sort_keys=True)+'\n')
            if aliases is not None:
                shutil.copyfile(aliases, inputs/'aliases.json')
            copied = 0
            for source in sorted(archive.iterdir()):
                if not source.is_dir() or source.is_symlink():
                    continue
                with locked(source/'.archive.lock'):
                    for path in sorted(source.glob('*.parquet')):
                        if path.is_symlink():
                            raise ValueError('Archive symlinks are not accepted.')
                        dest = inputs/'archive'/source.name/path.name
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        before = sha(path)
                        shutil.copyfile(path,dest)
                        if sha(path) != before or sha(dest) != before:
                            raise ValueError('Capture changed during snapshot.')
                        copied += 1
            if not copied:
                raise ValueError('No archived captures; refusing an empty-input cohort.')
            ranking, meta = ranker.build_monthly_ranking(info['cutoff'],archive=inputs/'archive',
                        aliases_path=inputs/'aliases.json',liquid_path=inputs/'liquid.json',training_path=inputs/'baseline.json')
            out = staged/f"top10_{info['month']}.json"
            freeze_ranking(out,ranking,as_of=info['cutoff'])
            payload = json.loads(out.read_text())
            if now is None:
                info['available_at'] = pd.Timestamp.now(tz='UTC').isoformat()
            payload['available_at'] = info['available_at']
            # Conservative daily forward measurement starts after publication day.
            payload['tracking_start'] = (utc(info['available_at']).normalize()+pd.Timedelta(days=1)).isoformat()
            out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
            markdown = ranker.render_md(ranking,meta).replace(' — frozen ', ' — input cutoff ')
            markdown = markdown.split('\nForward tracking begins')[0]
            markdown += f"\nPublished: {payload['available_at']}. Daily forward measurement starts {payload['tracking_start']}.\n"
            (staged/'ranking.md').write_text(markdown)
            sources = {p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}
            manifest = dict(info,recipe_version=RANKING_RECIPE_VERSION,ranked=len(ranking),
                            tracking_start=payload['tracking_start'],source_sha256=sources,
                            files={p.relative_to(staged).as_posix():sha(p) for p in sorted(staged.rglob('*')) if p.is_file()})
            (staged/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
            os.rename(staged,final)
            return verify(final)
        except Exception as exc:
            (staged/'failure.json').write_text(json.dumps(dict(error=type(exc).__name__)))
            raise


def track(root, prices, *, as_of):
    """Local daily prices only; each cohort keeps its frozen baseline and start."""
    from fa.tracker import forward_returns
    root, prices = Path(root), Path(prices)
    cutoff = utc(as_of).normalize()
    reports=[]
    with locked(root/'.monthly.lock'):
        for cohort in sorted(root.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9]')):
            manifest=verify(cohort)
            target=cohort/'tracking'/f'{cutoff.date()}.json'
            if target.exists():
                if sha(target) != target.with_suffix('.sha256').read_text().strip():
                    raise ValueError('Tracking report hash mismatch.')
                reports.append(json.loads(target.read_text())); continue
            payload=json.loads((cohort/f'top10_{cohort.name}.json').read_text())
            start=utc(payload['tracking_start'])
            if start>=cutoff: continue
            baseline=json.loads((cohort/'inputs/baseline.json').read_text())
            tickers=sorted(set(baseline)|{r['ticker'] for r in payload['rows']})
            frames={}; hashes={}
            for ticker in tickers:
                if not ticker or Path(ticker).name!=ticker or ticker in ('.','..'):
                    raise ValueError('Invalid price ticker.')
                path=prices/(ticker+'.parquet')
                before=sha(path)
                df=pd.read_parquet(path)
                if sha(path)!=before: raise ValueError('Prices changed during read.')
                index=pd.to_datetime(df.index,utc=True)
                if index.has_duplicates: raise ValueError('Duplicate daily price timestamps.')
                series=pd.Series(df['Close'].to_numpy(),index=index).sort_index()
                series=series[(series.index>=start)&(series.index<=cutoff)]
                if len(series)<2 or not ((series>0)&series.map(lambda x: bool(pd.notna(x)) and float(x)!=float('inf'))).all():
                    raise ValueError('Insufficient or invalid forward price history: '+ticker)
                frames[ticker]=series; hashes[ticker]=before
            # All baseline and pick returns must use identical observed dates.
            if frames and any(not s.index.equals(next(iter(frames.values())).index) for s in frames.values()):
                raise ValueError('Forward price dates differ across the frozen cohort/baseline.')
            ranks=pd.DataFrame([dict(ticker=r['ticker'],ranking_date=start) for r in payload['rows']],columns=['ticker','ranking_date'])
            rets=forward_returns(ranks,frames.get,as_of=cutoff,baseline=baseline)
            result=dict(as_of=cutoff.isoformat(),cohort=cohort.name,tracking_start=start.isoformat(),
                        baseline=baseline,price_sha256=hashes,
                        observed_start=next(iter(frames.values())).index[0].isoformat() if frames else None,
                        observed_end=next(iter(frames.values())).index[-1].isoformat() if frames else None,
                        rows=json.loads(rets.to_json(orient='records',date_format='iso')),
                        graduation_applied=False)
            target.parent.mkdir(exist_ok=True)
            temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n')
            target.with_suffix('.sha256').write_text(sha(temp)+'\n')
            os.replace(temp,target)
            reports.append(result)
    return reports


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=config.ARTIFACTS/'prospective')
    parser.add_argument('--archive',type=Path,default=config.ARCHIVE)
    parser.add_argument('--liquid',type=Path,default=ranker.UNIVERSE_LIQUID)
    parser.add_argument('--baseline',type=Path,default=ranker.UNIVERSE_TRAINING)
    parser.add_argument('--aliases',type=Path)
    parser.add_argument('--prices',type=Path,default=os.environ.get('FA_DAILY_PRICES'),help='Optional local daily Close parquet directory for forward tracking')
    parser.add_argument('--track-only',action='store_true')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.track_only and args.prices is None:parser.error('--track-only requires --prices or FA_DAILY_PRICES')
    if not args.run:
        print(json.dumps(dict(plan(),track_only=args.track_only),indent=2));return
    if not args.track_only:
        print(json.dumps(freeze(args.root,args.archive,args.liquid,args.baseline,args.aliases),indent=2))
    if args.prices:
        print(json.dumps(track(args.root,args.prices,as_of=pd.Timestamp.now(tz='UTC').normalize()-pd.Timedelta(days=1)),indent=2))


if __name__=='__main__': main()
