"""V3 preserves colliding trade occurrences and verified r2 checkpoints."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import json
import shutil
import time

import numpy as np
import pandas as pd

from incubator.continual.storage import identity,seal,verify,sha,write

KEYS=['symbol','strategy','dte','entry_ts']


def candidate_key(row):
    value={k:(pd.Timestamp(row[k]).isoformat() if k=='entry_ts' else
              int(row[k]) if k=='dte' else row[k]) for k in KEYS}
    ordinal=int(row.get('proposal_ordinal',0))
    if ordinal<0:raise ValueError('negative proposal ordinal')
    if ordinal:value['proposal_ordinal']=ordinal
    return identity(value)


def terminal_label(record, exit_ts):
    """A partial roll path cannot stand in for the complete trade outcome."""
    return (not record['executed'] or
            (record.get('fill_exit_ts') is not None and
             pd.Timestamp(record['fill_exit_ts']) >= pd.Timestamp(exit_ts)+pd.Timedelta(minutes=15)))


def proposal_records(symbol,bars,spec,start,through):
    """Retain vectorBT open status, never use its end-of-window mark as an exit."""
    from nn_meta import config,proposals
    from nn_meta.baseline import _SIM_KWARGS
    from portfolio import simulator
    rows=[]
    for strategy,entry in spec['strategies'].items():
        signals=proposals.single_signals(strategy,bars,entry['params'])
        price=bars.loc[config.WINDOW_START:through]
        signals=[s.loc[config.WINDOW_START:through] if s is not None else None for s in signals]
        pf=simulator.run_backtest(price_df=price,entries_series=signals[0],exits_series=signals[1],
             short_entries_series=signals[2],short_exits_series=signals[3],frequency='15min',**_SIM_KWARGS)
        if pf is None:raise ValueError(f'{symbol}/{strategy}: no simulator result')
        single=pf[pf.wrapper.columns[0]] if len(pf.wrapper.columns) else pf
        trades=pd.DataFrame(single.trades.records).sort_values('entry_idx',kind='stable')
        prior=None;occurrences=defaultdict(int)
        for t in trades.itertuples(index=False):
            ts=price.index[int(t.entry_idx)];pos=int(bars.index.get_loc(ts))
            gap=pos-prior if prior is not None else pos;prior=pos
            if ts<pd.Timestamp(start):continue
            if int(t.status) not in (0,1):raise ValueError('unknown vectorBT trade status')
            ordinal=occurrences[ts];occurrences[ts]+=1
            rows.append(dict(symbol=symbol,strategy=strategy,entry_ts=ts,proposal_ordinal=ordinal,
                exit_ts=price.index[int(t.exit_idx)] if int(t.status)==1 else None,
                closed=int(t.status)==1,direction=int(t.direction),bars_since_signal=gap,
                spot=float(bars.loc[ts,'Close']),param_label=entry.get('param_label','')))
    return rows


def load_symbol(snapshot,release,symbol):
    from nn_meta.live.v6_forward_inputs import ForwardData
    from nn_meta.session_calendar import SessionCalendar
    manifest=json.loads((snapshot/'manifest.json').read_text())
    obj=ForwardData.__new__(ForwardData)
    obj.root=snapshot;obj.document=manifest
    obj.training=json.loads((release/'training-inputs.json').read_text())
    obj.spec=json.loads((release/'baseline_spec.json').read_text())
    if set(manifest['symbols'])!=set(obj.spec['symbols']):raise ValueError('snapshot frozen universe differs')
    for name in ('calendar.json','surface.parquet','context.parquet'):
        if sha(snapshot/name)!=manifest['files'][name]:raise ValueError('daily context seal changed')
    obj.calendar_doc=json.loads((snapshot/'calendar.json').read_text());obj.calendar=SessionCalendar(obj.calendar_doc)
    obj.surface=pd.read_parquet(snapshot/'surface.parquet');obj.context=pd.read_parquet(snapshot/'context.parquet')
    obj.bars={};obj.raw={}
    for kind,dest in [('all',obj.bars),('raw',obj.raw)]:
        ref=manifest['symbols'][symbol]['files'][kind];path=snapshot/ref['path']
        if sha(path)!=ref['sha256']:raise ValueError('stock seed seal changed')
        dest[symbol]=pd.read_parquet(path)
    if not obj.bars[symbol].index.equals(obj.raw[symbol].index):raise ValueError('raw/adjusted bars not aligned')
    return obj


def build_symbol(config,snapshot,symbol,root,through,run_dir,deadline):
    from nn_meta.live.v6_forward_inputs import attach_context
    from nn_meta.v6_expansion import bars_sha256
    from nn_meta.baseline import execute_at_dte
    from nn_meta.price_basis import raw_spot_provenance
    from nn_meta.weekly_expiry import dte_grid_for
    from nn_meta import config as model_config
    from .market import ResearchMarket
    from .inheritance import ParentArtifacts
    inherited=ParentArtifacts(config)
    started=time.monotonic();root=Path(root);run_dir=Path(run_dir)
    if time.monotonic()>deadline:raise TimeoutError('nightly build deadline reached')
    if shutil.disk_usage(root).free<12_000_000_000:raise ValueError('research disk reserve reached')
    release=Path(config['release']);obj=load_symbol(Path(snapshot),release,symbol)
    bars=obj.bars[symbol].loc[:through].copy();raw=obj.raw[symbol].loc[:through].copy()
    prior_path=root/'history'/f'{symbol}.json'
    if prior_path.exists():
        prior=json.loads(prior_path.read_text())
        for name,frame in [('all',bars),('raw',raw)]:
            if bars_sha256(frame.loc[:prior['last_bar']])!=prior[name]:
                raise ValueError(f'{symbol}: previously consumed stock history revised; new lineage required')
    attach_context(symbol,bars,obj.training,obj.calendar_doc)
    proposals=proposal_records(symbol,bars,obj.spec['symbols'][symbol],config['append_start'],through)
    expected=[];counts=dict(proposals=len(proposals),candidates=0,new_features=0,matured=0,pending=0,unfilled=0)
    groups=defaultdict(list)
    for p in proposals:groups[p['entry_ts']].append(p)
    market=ResearchMarket(Path(config.get('market_root',root/'market'))/symbol,deadline=deadline)
    raw_close=raw.Close.copy()
    raw_close.attrs=dict(raw_spot_provenance('15m',provider='alpaca',feed='sip'),symbol=symbol)
    for ts,fresh in sorted(groups.items()):
        if time.monotonic()>deadline:raise TimeoutError('nightly build deadline reached')
        if shutil.disk_usage(root).free<12_000_000_000:raise ValueError('research disk reserve reached')
        write(run_dir/'progress'/f'{symbol}.json',dict(symbol=symbol,entry_ts=ts.isoformat(),counts=counts,
            elapsed_seconds=time.monotonic()-started))
        prefix=bars.loc[:ts].copy();obj.bars={symbol:prefix};obj.raw={symbol:raw.loc[:ts].copy()}
        entry_root=root/'features'/symbol/ts.strftime('%Y%m%dT%H%M%S')
        declaration=dict(schema='v6-continual-features-v1',release_sha256=config['release_sha256'],
            symbol=symbol,entry_ts=ts.isoformat(),all_prefix=bars_sha256(prefix),
            raw_prefix=bars_sha256(raw.loc[:ts]),contract=config['contract_identity'],
            proposals=[{k:(v.isoformat() if isinstance(v,pd.Timestamp) else v)
                        for k,v in p.items() if k not in {'exit_ts','closed'}} for p in fresh])
        if not (entry_root/'complete.json').exists():
            parent=inherited.resolve(entry_root.relative_to(root),declaration)
            if parent is not None:entry_root=parent
        if (entry_root/'complete.json').exists():
            if entry_root.is_relative_to(root):verify(entry_root,declaration)
            else:verify(entry_root)
        else:
            batch,_=candidate_batch(obj,fresh,market,run_dir/'context'/symbol/ts.strftime('%Y%m%dT%H%M%S'))
            features=json.loads((release/'model/ensemble_config.json').read_text())['features']
            if len(batch)!=len(fresh)*len(dte_grid_for(symbol,obj.spec)) or not set(features)<=set(batch):
                raise ValueError('candidate coverage/schema mismatch')
            if batch.duplicated(KEYS+['proposal_ordinal']).any() or np.isinf(batch[features].to_numpy(float)).any():
                raise ValueError('duplicate proposal occurrence or infinite candidate features')
            entry_root.mkdir(parents=True,exist_ok=True);batch.to_parquet(entry_root/'features.parquet',index=False)
            seal(entry_root,declaration,['features.parquet'],rows=len(batch),
                 snapshot=str(snapshot),snapshot_sha256=sha(Path(snapshot)/'manifest.json'),
                 market_evidence=list(market.evidence),availability='historical SIP reconstruction, retrieval separately recorded')
            counts['new_features']+=len(batch)
        batch=pd.read_parquet(entry_root/'features.parquet');counts['candidates']+=len(batch)
        by_strategy={(p['strategy'],p['proposal_ordinal']):p for p in fresh}
        for row in batch.to_dict('records'):
            if time.monotonic()>deadline:raise TimeoutError('nightly label deadline reached')
            key=candidate_key(row);p=by_strategy[row['strategy'],int(row.get('proposal_ordinal',0))]
            target=root/'labels'/symbol/key
            if not (target/'complete.json').exists():
                parent=inherited.resolve(target.relative_to(root),dict(candidate_id=key,feature_sha256=sha(entry_root/'complete.json'),contract=config['contract_identity']))
                if parent is not None:target=parent
            if (target/'complete.json').exists():
                receipt=verify(target)
                if receipt['declaration']['feature_sha256']!=sha(entry_root/'complete.json'):
                    raise ValueError('label feature lineage differs')
                label=json.loads((target/'label.json').read_text())
            elif not p['closed']:
                label=dict(status='pending',candidate_id=key)
            else:
                records,meta=execute_at_dte(symbol,[(ts,p['exit_ts'],p['direction'])],bars,
                    int(row['dte']),market,through,raw_close=raw_close)
                if meta['capped'] or len(records)!=1:raise ValueError('incomplete candidate execution')
                r=records[0]
                if not terminal_label(r,p['exit_ts']):
                    counts['pending']+=1
                    expected.append(dict(candidate_id=key,feature_root=str(entry_root),label_root=str(target),
                        status='pending',reason='execution_path_not_terminal'))
                    continue
                label=dict(status='matured' if r['executed'] else 'unfilled',candidate_id=key,
                    entry_ts=ts.isoformat(),exit_ts=pd.Timestamp(p['exit_ts']).isoformat(),
                    net_return=r['net_return'],executed=r['executed'],
                    und_period_return=float(bars.loc[p['exit_ts'],'Close']/bars.loc[ts,'Close']-1),
                    fill_exit_ts=pd.Timestamp(r['fill_exit_ts']).isoformat() if r['executed'] else None)
                if r['executed']:
                    if not np.isfinite(r['net_return']):raise ValueError('non-finite completed label')
                    label['label_excess']=int(r['net_return']>label['und_period_return'])
                target.mkdir(parents=True,exist_ok=True);write(target/'label.json',label)
                seal(target,dict(candidate_id=key,feature_sha256=sha(entry_root/'complete.json'),
                    contract=config['contract_identity']),['label.json'],snapshot=str(snapshot),
                    snapshot_sha256=sha(Path(snapshot)/'manifest.json'),market_evidence=list(market.evidence))
            counts[label['status']]+=1
            expected.append(dict(candidate_id=key,feature_root=str(entry_root),label_root=str(target),status=label['status']))
    # Existing features cannot disappear silently under an extended history.
    previous=set()
    paths=list((root/'features'/symbol).glob('*/features.parquet'))
    paths.extend(inherited.root/anchor.removesuffix('/complete.json')/'features.parquet'
                 for anchor in inherited.anchors if anchor.startswith(f'features/{symbol}/'))
    for path in paths:
        frame=pd.read_parquet(path)
        previous.update(candidate_key(r) for r in frame.to_dict('records'))
    if previous!={r['candidate_id'] for r in expected}:raise ValueError('candidate history changed or disappeared')
    write(prior_path,dict(last_bar=bars.index[-1].isoformat(),all=bars_sha256(bars),raw=bars_sha256(raw)))
    directory=run_dir/'symbols'/symbol;directory.mkdir(parents=True,exist_ok=True)
    write(directory/'inventory.json',dict(candidates=expected,counts=counts,seconds=time.monotonic()-started))
    seal(directory,dict(symbol=symbol,through=through,snapshot_sha256=sha(Path(snapshot)/'manifest.json'),
                       contract=config['contract_identity']),['inventory.json'])
    return counts


def candidate_batch(obj, fresh, market, output):
    """Identical calls within one prefix reuse values; older prefixes are released."""
    from v3._source_memo import reuse_identical_sources
    with reuse_identical_sources():
        if len({p['strategy'] for p in fresh})==len(fresh):
            batch,contexts=obj.candidates(fresh,market,output)
            return batch.assign(proposal_ordinal=0),contexts
        batches=[];contexts={}
        for proposal in fresh:
            ordinal=proposal['proposal_ordinal']
            batch,context=obj.candidates([proposal],market,Path(output)/proposal['strategy']/str(ordinal))
            batches.append(batch.assign(proposal_ordinal=ordinal));contexts.update(context)
        return pd.concat(batches,ignore_index=True),contexts
