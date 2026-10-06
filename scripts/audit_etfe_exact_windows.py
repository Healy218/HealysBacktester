"""Independently reconcile factored ETFE decision clocks and time bounds."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe import acquisition as a, exact_windows as e, window_demand as w


def audit(root):
    root = Path(root)
    plan = e.load(root)
    demand = json.loads((root/'DEMAND.json').read_text())
    if demand['plan_sha256'] != plan['sha256']:
        raise ValueError('Demand plan mismatch')
    scope_reports = []
    for scope in w.load(Path(plan['source']))['scopes']:
        tag = f"{scope['ticker']}-{scope['minutes']}"
        receipt = json.loads((root/(tag+'.json')).read_text())
        file = root/receipt['data']
        if a.sha(file.read_bytes()) != receipt['data_sha256']:
            raise ValueError('Decision file hash mismatch')
        chart = pq.read_table(Path(plan['source'])/(tag+'/chart.parquet')).to_pandas()
        seen, counts = set(), Counter()
        candidate_clocks = 0
        for batch in pq.ParquetFile(file).iter_batches(batch_size=20_000):
            for r in batch.to_pylist():
                key = (r['chart_row'],r['right'],r['target_dte'])
                if key in seen or r['target_dte'] not in (0,1,5) or r['entry_eligible']:
                    raise ValueError('Duplicate or admitted decision row')
                seen.add(key)
                bar = chart.iloc[r['chart_row']]
                if not (r['signal_at_ns'] == bar['bar_end'].value
                        and r['entry_start_ns'] == r['signal_at_ns']-60_000_000_000
                        and r['entry_end_ns'] == r['signal_at_ns']):
                    raise ValueError('Decision clock bound mismatch')
                if r['feature_start_ns'] != -1:
                    if r['feature_start_ns'] != r['signal_at_ns']-(scope['minutes']+1)*60_000_000_000 or r['feature_end_ns'] != r['signal_at_ns']-60_000_000_000:
                        raise ValueError('Feature bound mismatch')
                if r['acquisition_candidate'] and r['reason'] != 'dated_selection_unresolved':
                    raise ValueError('Candidate missing dated-selection reason')
                candidate_clocks += bool(r['acquisition_candidate'])
                counts['decision_clocks'] += 1
                if r['target_dte'] == 0:
                    counts['signal_memberships'] += r['logical_memberships']
                counts[r['reason']] += r['logical_memberships']
        if len(seen) != receipt['counts']['decision_clocks']:
            raise ValueError('Decision clock census differs')
        if dict(counts) != receipt['counts'] or receipt['holding_paths_realized'] != 0:
            raise ValueError(f"Logical memberships or holding claim differs for {tag}: {dict(counts)} != {receipt['counts']}")
        scope_reports.append(dict(scope=tag,decision_clocks=len(seen),logical_memberships=sum(counts.values()),
            unresolved_reasons=dict(counts),candidate_clocks=candidate_clocks))
    if len(scope_reports) != 9 or sum(x['decision_clocks'] for x in scope_reports) != 4_311_060:
        raise ValueError('Nine-scope full decision clock inventory mismatch')
    result = dict(schema='etfe-exact-window-independent-audit-v1',plan_sha256=plan['sha256'],
        scopes=scope_reports,decision_rows=sum(x['decision_clocks'] for x in scope_reports),
        logical_memberships=demand['logical_target_memberships'],
        physical_interval_counts=demand['totals'],holding_paths_realized=0,
        full_strategy_demand_complete=False,ready_for_build=False,ready_for_training=False,
        audit_source_sha256=a.sha(Path(__file__).read_bytes()))
    output=root/'INDEPENDENT_AUDIT.json'
    if output.exists():
        saved=json.loads(output.read_text())
        expected={k:v for k,v in result.items() if k!='audit_source_sha256'}
        actual={k:v for k,v in saved.items() if k!='audit_source_sha256'}
        if actual!=expected:
            raise ValueError('Existing independent audit differs from recomputation')
        return saved
    a.save(output,result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve()),indent=2))
