"""Source-bound bounded ETFE thirteen-scope diagnostic materialization."""
import importlib
import importlib.metadata
import json
from pathlib import Path
import resource
import sys
import time
import uuid

import numpy as np
import pandas as pd

from nn_meta.etfe.acquisition import ROOT, digest, save, sha, write_new
from nn_meta.etfe.causal_pilot import (STOCK, CALENDAR, START, STOP, verify as verify_causal,
                                      parquet_new, checked_scope)
from nn_meta.etfe.causal_inputs import stock_minutes, session_bars
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.option_feature_pilot import guard
from nn_meta.etfe.tv_features import bindings, compute, REGISTRY

PILOT = ROOT / 'nn_meta/validation/etfe-causal-20261004-r0'
OWN = ('nn_meta/etfe/tv_features.py', 'nn_meta/etfe/tv_feature_pilot.py',
       'scripts/pilot_etfe_tv_features.py', 'scripts/audit_etfe_tv_features.py',
       'docs/specs/ETFE_TV_FEATURE_PILOT_20261005.md')


def source_files():
    for scope in json.loads(REGISTRY.read_text())['tv_scopes']:
        importlib.import_module(scope['calculator'].rsplit('.', 1)[0])
    importlib.import_module('nn_meta.v7.setup')
    sources = set(OWN)
    for module in list(sys.modules.values()):
        f = getattr(module, '__file__', None)
        if not f: continue
        p = Path(f).resolve()
        if p.is_relative_to(ROOT) and p.suffix == '.py':
            name = str(p.relative_to(ROOT))
            if name.startswith(('v3/', 'nn_meta/etfe/', 'scripts/prepare_etfe', 'indicators/')):
                sources.add(name)
    sources.update(['nn_meta/v7/setup.py', str(REGISTRY.relative_to(ROOT))])
    return sorted(sources)


def prepare(root):
    verify_causal(PILOT)
    complete = json.loads((PILOT/'COMPLETE.json').read_text())
    paths = [PILOT/n for n in ('PLAN.json','COMPLETE.json','INDEPENDENT_AUDIT.json')]
    paths += [STOCK/n for n in ('PLAN.json','NORMALIZED.json','INDEPENDENT_AUDIT.json')]
    paths.append(CALENDAR/'CALENDAR.json'); scopes = []
    for name, h in complete['scope_receipts'].items():
        p = PILOT/name
        if sha(p.read_bytes()) != h: raise ValueError('Causal receipt drift')
        r = checked_scope(PILOT, p); paths.append(p)
        paths += [PILOT/f['path'] for f in r['files'][:2]]
        scopes.append(dict(**r['scope'], underlying=r['files'][0], events=r['files'][1]))
    plan = dict(schema='etfe-tv-feature-component-plan-v1',
        sources={n:sha((ROOT/n).read_bytes()) for n in source_files()},
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths},
        bindings=bindings(), scopes=scopes, observation_start=str(START), observation_end=str(STOP),
        calculation_origin='2024-01-02', native_external_parity=False,
        packages={n:importlib.metadata.version(n) for n in ('numpy','pandas','pyarrow')},
        limits=dict(max_root_bytes=2**30, max_run_seconds=1800),
        model_feature_admitted=False, full_feature_schema_complete=False, ready_for_training=False)
    plan['sha256'] = digest(plan); root = Path(root); root.mkdir(parents=True, exist_ok=False)
    save(root/'PLAN.json', plan)
    for n in plan['sources']:
        p = root/'source'/n; p.parent.mkdir(parents=True, exist_ok=True); write_new(p, (ROOT/n).read_bytes())
    return plan


def verify(root):
    root = Path(root); plan = json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in plan.items() if k != 'sha256'}) != plan['sha256']: raise ValueError('Plan drift')
    for n,h in plan['sources'].items():
        if sha((ROOT/n).read_bytes()) != h or sha((root/'source'/n).read_bytes()) != h: raise ValueError(f'Source drift: {n}')
    for n,h in plan['inputs'].items():
        if sha((ROOT/n).read_bytes()) != h: raise ValueError('Input drift')
    for n,v in plan['packages'].items():
        if importlib.metadata.version(n) != v: raise ValueError('Package drift')
    verify_causal(PILOT)
    if plan['bindings'] != bindings(): raise ValueError('Binding drift')
    return plan


def inputs(scope):
    raw = stock_minutes(STOCK, scope['ticker'], end=STOP)
    calendar = read_calendar(CALENDAR)
    bars = session_bars(raw, calendar, scope['minutes'], as_of=STOP)
    prior = pd.read_parquet(PILOT/scope['underlying']['path'])
    prior = prior.loc[bars.index, bars.columns].copy()
    # Parquet may preserve a different timestamp unit across DST-spanning data.
    for column in ('bar_end', 'available_at', 'session_open', 'session_close'):
        bars[column] = bars[column].dt.as_unit('ns')
        prior[column] = prior[column].dt.as_unit('ns')
    pd.testing.assert_frame_equal(bars, prior)
    if not bars.valid.all(): raise ValueError('Bounded study requires complete prefix')
    return raw, bars


def compare(a, b, ar, br):
    pd.testing.assert_frame_equal(a, b, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(ar, br)


def run_scope(root, scope, plan, started):
    raw, bars = inputs(scope); minutes = scope['minutes']; tag = f"{scope['ticker']}-{minutes}"
    observations = bars.index[bars.index >= START]
    values, reasons, frames = compute(bars, raw, minutes, observations)
    cuts = [pd.Timestamp('2024-01-18T21:00Z'), pd.Timestamp('2024-01-19T17:00Z')]
    checks = []
    for at in cuts:
        guard(root, plan, started)
        prefix = bars[bars.bar_end <= at]; selected = observations[observations.isin(prefix.index)]
        v,r,_ = compute(prefix, raw[raw.index < at], minutes, selected)
        compare(values.loc[selected], v, reasons.loc[selected], r)
        altered = bars.copy(); future = altered.index >= at
        altered.loc[future, ['Open','High','Low','Close']] *= 2
        altered.loc[future, 'Volume'] *= 10
        changed_raw = raw.copy(); later = changed_raw.index >= at
        changed_raw.loc[later, ['Open','High','Low','Close']] *= 2
        changed_raw.loc[later, 'Volume'] *= 10
        v,r,_ = compute(altered, changed_raw, minutes, selected)
        compare(values.loc[selected], v, reasons.loc[selected], r)
        checks.append(dict(cutoff=str(at), observations=len(selected), prefix_and_future_passed=True))
    columns = dict(signal_at_ns=pd.DatetimeIndex(bars.loc[observations, 'bar_end']).as_unit('ns').asi8,
                   model_feature_admitted=False)
    native = {}
    for b in plan['bindings']:
        for col in [b['field']] + [g[0] for g in b['gates']]:
            native[b['source']+'__'+col] = frames[b['source']][col]
        n = b['name']; columns['diagnostic__'+n] = values[n]
        columns['missing__diagnostic__'+n] = values[n].isna().astype('uint8')
        columns['reason__'+n] = reasons[n]
    frame = pd.DataFrame(columns, index=observations); natives = pd.DataFrame(native, index=observations)
    events = pd.read_parquet(PILOT/scope['events']['path'])
    lookup = {int(at):i for i,at in enumerate(frame.signal_at_ns)}
    links = pd.DataFrame(dict(event_ordinal=np.arange(len(events),dtype='int64'),
                             observation_ordinal=[lookup[int(at)] for at in events.signal_at_ns],
                             model_feature_admitted=False))
    attempt = uuid.uuid4().hex
    files = [parquet_new(root, f'{tag}-{attempt}-{kind}.parquet', df)
             for kind, df in (('features',frame),('native',natives),('links',links))]
    result = dict(scope=dict(ticker=scope['ticker'], minutes=minutes), plan_sha256=plan['sha256'], files=files,
        observations=len(frame), logical_rows=len(events), nonmissing_values=int(values.notna().sum().sum()),
        missing_by_field=values.isna().sum().to_dict(), prefix_checks=checks, model_feature_admitted=False)
    save(root/f'{tag}.json', result); return result


def run(root, max_scopes=None):
    import fcntl
    root = Path(root); plan = verify(root); started = time.monotonic(); results = []; processed = 0
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for scope in plan['scopes']:
            guard(root, plan, started)
            path = root/f"{scope['ticker']}-{scope['minutes']}.json"
            r = checked_scope(root, path)
            if r is None:
                if max_scopes is not None and processed >= max_scopes: break
                r = run_scope(root, scope, plan, started); processed += 1
            if r['plan_sha256'] != plan['sha256']: raise ValueError('Scope binding drift')
            results.append(r)
            print(json.dumps({k:r[k] for k in ('scope','observations','logical_rows','nonmissing_values')}), flush=True)
        result = dict(plan_sha256=plan['sha256'], complete=len(results)==len(plan['scopes']),
            scope_receipts={f"{r['scope']['ticker']}-{r['scope']['minutes']}.json":sha((root/f"{r['scope']['ticker']}-{r['scope']['minutes']}.json").read_bytes()) for r in results},
            processed_scopes=processed, observations=sum(r['observations'] for r in results),
            logical_rows=sum(r['logical_rows'] for r in results), nonmissing_values=sum(r['nonmissing_values'] for r in results),
            elapsed_seconds=time.monotonic()-started, peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            model_feature_admitted=False, full_feature_schema_complete=False, ready_for_training=False)
        save(root/f'run-{uuid.uuid4().hex}.json', result)
        if result['complete'] and not (root/'COMPLETE.json').exists(): save(root/'COMPLETE.json', result)
    return result
