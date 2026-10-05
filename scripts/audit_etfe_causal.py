"""Independently reconcile the ETFE component pilot and remaining transport demand."""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import pyarrow.parquet as pq
from nn_meta.etfe.acquisition import sha, save, committed, load_plan
from nn_meta.etfe.causal_pilot import verify, observations, OPTIONS, SETUP


def merge(intervals):
    result=[]
    for a,b in sorted(set(intervals)):
        assert a<b
        if result and a<=result[-1][1]:result[-1][1]=max(result[-1][1],b)
        else:result.append([a,b])
    return result


def subtract(interval, covered):
    pending=[list(interval)]
    for c,d in covered:
        next_pending=[]
        for a,b in pending:
            if d<=a or c>=b:next_pending.append([a,b])
            else:
                if a<c:next_pending.append([a,c])
                if d<b:next_pending.append([d,b])
        pending=next_pending
    return pending


def audit(root):
    root=Path(root);plan=verify(root)
    complete=json.loads((root/'COMPLETE.json').read_text())
    assert complete['complete'] and complete['scopes']==9 and complete['plan_sha256']==plan['sha256']
    contracts=observations();physical=defaultdict(set);reasons=Counter();scopes=[];logical=0;candidate_rows=0
    choices_by_day={}
    catalog=json.loads((SETUP/'catalog.json').read_text())['records']
    membership=[];decision_checks={}
    for filename,checksum in complete['scope_receipts'].items():
        receipt=root/filename;assert sha(receipt.read_bytes())==checksum
        r=json.loads(receipt.read_text());ticker=r['scope']['ticker'];m=r['scope']['minutes']
        expected={x['variant_id']:x for x in catalog if x['signal_minutes']==m}
        assert len(r['variant_census'])==2817 and {x['variant_id'] for x in r['variant_census']}==set(expected)
        assert len(r['families'])==20 and r['all_variant_prefix_and_batch_check']
        for f in r['files']:
            path=(root/f['path']).resolve();assert path.is_relative_to(root.resolve())
            assert sha(path.read_bytes())==f['sha256']
        foundation=pq.read_table(root/r['files'][0]['path']).to_pandas().set_index('bar_end',drop=False)
        assert foundation.index.is_unique and len(foundation)==r['calendar_bins']
        assert (~foundation.valid).sum()==r['invalid_bins']
        for name,count in r['feature_missing'].items():
            assert foundation['raw__'+name].isna().sum()==count
            assert foundation['missing__raw__'+name].eq(foundation['raw__'+name].isna()).all()
        events=pq.read_table(root/r['files'][1]['path']).to_pandas()
        assert len(events)==r['logical_rows'] and not events.entry_eligible.any()
        assert not events.duplicated(['variant_id','direction','signal_at_ns','target_dte']).any()
        assert events.ticker.eq(ticker).all() and events.minutes.eq(m).all()
        counts=events.groupby(['variant_id','direction']).size()
        for c in r['variant_census']:
            assert counts.get((c['variant_id'],'long'),0)==3*c['events'][0]
            assert counts.get((c['variant_id'],'short'),0)==3*c['events'][2]
            assert len(c['prefix_sha256'])==64
        local=defaultdict(set);local_reasons=Counter()
        for e in events.itertuples(index=False):
            at=pd.Timestamp(e.signal_at_ns,tz='UTC');bar=foundation.loc[at]
            assert expected[e.variant_id]['strategy']==e.strategy and e.direction in ('long','short')
            assert e.target_dte in (0,1,5) and e.raw_spot==bar.Close and bar.valid
            a,b=e.signal_at_ns-(m+1)*60_000_000_000,e.signal_at_ns-60_000_000_000
            assert (a,b)==(e.feature_start_ns,e.feature_end_ns)
            assert e.feature_inside_stock_session==(a>=bar.session_open.value and b<=bar.session_close.value)
            key=(ticker,e.signal_at_ns,e.direction,e.target_dte,e.raw_spot)
            if key not in decision_checks:
                day=at.tz_convert('America/New_York').date();right='call' if e.direction=='long' else 'put'
                universe_key=(ticker,day,right)
                if universe_key not in choices_by_day:
                    choices_by_day[universe_key]=[]
                    for c in contracts.values():
                        expiry=pd.Timestamp(c['expiration_date']).date();dte=(expiry-day).days
                        if (c['ticker']==ticker and c['right']==right and 0<=dte<=5
                            and c['first_observed_at'].tz_convert('America/New_York').date()<day):
                            choices_by_day[universe_key].append((c,expiry,dte))
                choices=[]
                for c,expiry,dte in choices_by_day[universe_key]:
                    if .85*e.raw_spot<=c['strike']<=1.15*e.raw_spot:
                        choices.append((abs(dte-e.target_dte),expiry,abs(c['strike']-e.raw_spot),c['strike'],c['symbol']))
                decision_checks[key]=min(choices)[-1] if choices else None
            candidate=decision_checks[key]
            assert e.acquisition_candidate==candidate
            expected_reason='historical_discovery_unresolved' if candidate else 'no_prior_date_observed_candidate'
            assert e.eligibility_reason==expected_reason
            local_reasons[expected_reason]+=1
            if candidate:
                candidate_rows+=1
                if e.feature_inside_stock_session:
                    local[(candidate,'option_trades')].add((a,b));local[(candidate,'option_bars')].add((a,b))
                local[(candidate,'option_bars')].add((b,e.signal_at_ns))
        assert dict(local_reasons)==r['reasons'];reasons.update(local_reasons);logical+=len(events)
        measured=[dict(symbol=s,route=route,intervals=merge(v)) for (s,route),v in sorted(local.items())]
        demand=json.loads((root/r['files'][2]['path']).read_text())
        assert measured==demand['physical']
        for key,intervals in local.items():physical[key].update(intervals)
        scopes.append(dict(scope=r['scope'],calendar_bins=len(foundation),invalid_bins=r['invalid_bins'],
                           logical_rows=len(events),variants=2817,families=20,physical_intervals=sum(len(x['intervals']) for x in measured)))
        membership.append(dict(scope=r['scope'],logical_events=r['files'][1],scope_receipt_sha256=checksum))
    # Verify only raw request chains which overlap actual physical demand.
    coverage=defaultdict(list);coverage_inputs=[]
    raw_roots={x['root'] for p in OPTIONS for x in json.loads((p/'PLAN.json').read_text())['inputs']}
    wanted={s for s,route in physical}
    for raw_root in sorted(raw_roots):
        raw_root=Path(raw_root);raw_plan=load_plan(raw_root)
        for job in raw_plan['jobs']:
            route=job['route']
            if route not in ('option_bars','option_trades'):continue
            params=job['params'];symbols=set(params['symbols'].split(','))&wanted
            a,b=pd.Timestamp(params['start']).value,pd.Timestamp(params['end']).value+1
            if not any(x<b and y>a for s in symbols for x,y in physical.get((s,route),())):continue
            pages,token,done=committed(raw_root,job);assert done
            coverage_inputs.append(dict(root=str(raw_root.relative_to(ROOT)),plan_sha256=raw_plan['sha256'],job_id=job['id'],pages=len(pages)))
            for s in symbols:coverage[(s,route)].append((a,b))
    total=Counter();pending_count=Counter();rows=[]
    for (s,route),intervals in sorted(physical.items()):
        merged=merge(intervals);captured=merge(coverage.get((s,route),[]));pending=[]
        for interval in merged:pending.extend(subtract(interval,captured))
        total[route]+=len(merged);pending_count[route]+=len(pending)
        rows.append(dict(symbol=s,route=route,intervals=merged,uncaptured_intervals=pending))
    result=dict(schema='etfe-causal-independent-audit-v1',plan_sha256=plan['sha256'],
        auditor_sha256=sha(Path(__file__).read_bytes()),complete_sha256=sha((root/'COMPLETE.json').read_bytes()),
        scopes=scopes,ticker_variant_combinations=9*2817,logical_rows=logical,candidate_rows=candidate_rows,
        unique_decision_checks=len(decision_checks),reasons=dict(reasons),physical_keys=len(physical),
        physical_intervals=dict(total),uncaptured_intervals=dict(pending_count),
        logical_to_physical_reconciliation=True,hashes_verified=True,all_candidate_rankings_checked=True,
        no_eligible_entries=True,full_demand_complete=False,full_feature_schema_complete=False,
        ready_for_build=False,ready_for_training=False)
    save(root/'GLOBAL_DEMAND.json',dict(schema='etfe-causal-global-demand-v1',plan_sha256=plan['sha256'],
        logical_rows=logical,membership=membership,physical=rows,verified_transport_inputs=coverage_inputs,
        transport_coverage_is_not_valid_no_trade_or_admission=True))
    result['global_demand_sha256']=sha((root/'GLOBAL_DEMAND.json').read_bytes())
    save(root/'INDEPENDENT_AUDIT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    a=p.parse_args();print(json.dumps(audit(a.root),indent=2))
