"""Independent scalar projection/membership audit; no external Pine parity claim."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from nn_meta.etfe.acquisition import sha, save
from nn_meta.etfe.tv_feature_pilot import verify, inputs, PILOT


def independent_atr(bars):
    result = {}; previous = None; seed = []; state = None
    for row in bars.itertuples():
        tr = row.High - row.Low
        if previous is not None: tr = max(tr, abs(row.High-previous), abs(row.Low-previous))
        previous = row.Close
        if state is None:
            seed.append(tr)
            if len(seed) == 14: state = sum(seed) / 14
        else: state = (1/14)*tr + (1-1/14)*state
        result[row.Index] = state
    return result


def scalar(binding, row, close, atr):
    source = binding['source'] + '__'; raw = row[source + binding['field']]
    value = float({'idle':0, 'accum':1, 'sweepPending':2, 'manip':3, 'dist':4}[raw]) if binding['transform']=='phase' else float(raw)
    reason = 'observed_diagnostic' if math.isfinite(value) else 'native_unavailable'
    for field, operation in binding['gates']:
        x = row[source + field]
        valid = (math.isfinite(x) if operation=='finite' else math.isfinite(x) and x>0 if operation=='positive' else x==True)
        if not valid: value = math.nan; reason = 'native_prerequisite_unavailable'
    if binding['transform'] in ('price','range'):
        if atr is None or not math.isfinite(atr) or atr <= 0:
            value = math.nan; reason = 'atr14_unavailable_or_zero'
        else: value = ((value-close) if binding['transform']=='price' else value)/atr
    elif binding['transform']=='percent': value /= 100
    return value, reason


def audit(root):
    root = Path(root).resolve(); plan = verify(root); complete = json.loads((root/'COMPLETE.json').read_text())
    assert complete['complete'] and complete['plan_sha256'] == plan['sha256']
    assert len(complete['scope_receipts']) == len(plan['scopes']) == 9
    logical = observations = finite = 0; counts = {b['name']:Counter() for b in plan['bindings']}; scopes=[]
    for scope in plan['scopes']:
        name = f"{scope['ticker']}-{scope['minutes']}.json"; path=root/name
        assert sha(path.read_bytes()) == complete['scope_receipts'][name]
        r = json.loads(path.read_text()); assert r['plan_sha256'] == plan['sha256']
        for f in r['files']: assert sha((root/f['path']).read_bytes()) == f['sha256']
        frame, native, links = [pd.read_parquet(root/f['path']) for f in r['files']]
        _, bars = inputs(scope); atr = independent_atr(bars)
        selected = bars.loc[bars.index >= pd.Timestamp(plan['observation_start'])]
        assert frame.index.equals(selected.index) and native.index.equals(frame.index)
        assert frame.signal_at_ns.tolist() == pd.DatetimeIndex(selected.bar_end).as_unit('ns').asi8.tolist()
        assert not frame.model_feature_admitted.any() and not links.model_feature_admitted.any()
        for index, actual, raw in zip(frame.index, frame.to_dict('records'), native.to_dict('records')):
            for b in plan['bindings']:
                n = b['name']; expected, reason = scalar(b, raw, bars.at[index,'Close'], atr[index])
                value = actual['diagnostic__'+n]; missing = actual['missing__diagnostic__'+n]
                assert missing == int(not math.isfinite(expected)) == int(pd.isna(value))
                assert reason == actual['reason__'+n]
                if not missing:
                    assert math.isclose(value,expected,rel_tol=1e-12,abs_tol=1e-12), (scope,n,value,expected)
                    finite += 1
                counts[n][reason] += 1
        for b in plan['bindings']:
            n=b['name']
            assert str(frame['diagnostic__'+n].dtype)=='float64'
            assert str(frame['missing__diagnostic__'+n].dtype)=='uint8'
            assert int(frame['missing__diagnostic__'+n].sum()) == r['missing_by_field'][n]
        events = pd.read_parquet(PILOT/scope['events']['path'])
        assert links.event_ordinal.tolist() == list(range(len(events)))
        assert links.observation_ordinal.between(0,len(frame)-1).all()
        assert frame.signal_at_ns.iloc[links.observation_ordinal].tolist() == events.signal_at_ns.tolist()
        assert len(links) == r['logical_rows'] and len(frame) == r['observations']
        assert len(r['prefix_checks'])==2 and all(c['prefix_and_future_passed'] for c in r['prefix_checks'])
        logical += len(links); observations += len(frame); scopes.append(r['scope'])
    assert logical == complete['logical_rows'] == 458133
    assert observations == complete['observations'] == 2964
    assert finite == complete['nonmissing_values']
    result = dict(schema='etfe-tv-feature-independent-audit-v1', plan_sha256=plan['sha256'],
        auditor_sha256=sha(Path(__file__).read_bytes()), complete_sha256=sha((root/'COMPLETE.json').read_bytes()),
        observations=observations, logical_rows=logical, fields=len(plan['bindings']), native_scopes=13, scopes=scopes,
        nonmissing_values=finite, missing_values=observations*96-finite,
        reasons={n:dict(c) for n,c in counts.items()},
        all_values_masks_reasons_reconciled=True, all_logical_memberships_reconciled=True,
        native_kernel_independent_reimplementation=False, external_pine_parity=False,
        rtol=1e-12, atol=1e-12, model_feature_admitted=False, full_feature_schema_complete=False, ready_for_training=False)
    save(root/'INDEPENDENT_AUDIT.json', result)
    return {k:v for k,v in result.items() if k!='reasons'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True,type=Path)
    print(json.dumps(audit(p.parse_args().root),indent=2))
