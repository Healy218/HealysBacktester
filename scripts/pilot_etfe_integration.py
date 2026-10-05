"""Finite synthetic shared-scheduler/stress study with immutable restart evidence."""
import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import save,sha,write_new
from nn_meta.etfe.integration_ledger import Scheduler,stress_profiles

FIXTURE='docs/specs/ETFE_INTEGRATION_FIXTURES_20261005.json'
SOURCES=['nn_meta/etfe/integration_ledger.py','nn_meta/etfe/expiry_ledger.py',
 'nn_meta/etfe/execution_ledger.py','nn_meta/etfe/vwap_reference.py','nn_meta/etfe/purchase_policy_v2.py',
 'nn_meta/etfe/acquisition.py','docs/specs/ETFE_SCOPE_0DTE_20261004.json',
 'docs/specs/ETFE_EXECUTION_20261003.md','docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md',
 'docs/specs/ETFE_INTEGRATION_COMPONENTS_20261005.md',FIXTURE,
 'scripts/pilot_etfe_integration.py','tests/test_etfe_integration_ledger.py']


def read(p):return json.loads(p.read_text())


def prepare(root):
    plan=dict(schema='etfe-integration-study-v1',sources={p:sha((ROOT/p).read_bytes()) for p in SOURCES},
              profiles=stress_profiles(),evidence_kind='synthetic',training_admitted=False)
    if not (root/'PLAN.json').exists():
        root.mkdir(parents=True,exist_ok=True)
        for p in SOURCES:
            dest=root/'sources'/p;dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():write_new(dest,(ROOT/p).read_bytes())
            assert sha(dest.read_bytes())==plan['sources'][p]
        save(root/'PLAN.json',plan)
    if read(root/'PLAN.json')!=plan:raise ValueError('Frozen source mismatch; successor required')
    for p,d in plan['sources'].items():assert sha((root/'sources'/p).read_bytes())==d
    return read(root/'sources'/FIXTURE)['cases']


def publish(path,value):
    if not path.exists():save(path,value)
    else:assert read(path)==value,'Existing artifact differs'
    receipt=path.with_suffix('.sha256.json')
    digest=sha(path.read_bytes())
    if not receipt.exists():save(receipt,dict(sha256=digest))
    assert read(receipt)['sha256']==digest


def checked(path):
    if read(path.with_suffix('.sha256.json'))['sha256']!=sha(path.read_bytes()):
        raise ValueError('Checkpoint/result corruption')
    return read(path)


def recover_receipt(path,tape,policy,final=False):
    """A payload published before a crash is trusted only after fresh replay."""
    if path.with_suffix('.sha256.json').exists():return
    saved=read(path);state=saved['snapshot'] if final else saved
    sim=Scheduler(tape,policy);sim.run(state['cursor'])
    expected=dict(report=sim.report(),snapshot=sim.snapshot()) if final else sim.snapshot()
    if saved!=expected:raise ValueError('Uncommitted artifact differs from replay')
    publish(path,expected)


def run(root,max_events=None):
    cases=prepare(root);summaries={};prior={};remaining=max_events
    if remaining is not None and remaining<1:raise ValueError('Positive event budget required')
    for case in cases:
        for name,policy in stress_profiles().items():
            key=case['id']+'--'+name;final=root/(key+'.result.json')
            if final.exists():
                recover_receipt(final,case['tape'],policy,final=True)
                summaries[key]=checked(final)['report'];prior[final.name]=sha(final.read_bytes());continue
            if remaining is not None and remaining<=0:return dict(complete=False,completed=len(summaries))
            checkpoints=sorted(root.glob(key+'.checkpoint-*.json'))
            checkpoints=[p for p in checkpoints if not p.name.endswith('.sha256.json')]
            sim=Scheduler(case['tape'],policy)
            if checkpoints:
                for p in checkpoints:recover_receipt(p,case['tape'],policy)
                states=[(checked(p),p) for p in checkpoints]
                state,path=max(states,key=lambda pair:pair[0]['cursor'])
                sim=Scheduler.restore(case['tape'],state)
                prior.update({p.name:sha(p.read_bytes()) for p in checkpoints})
            before=sim.cursor;report=sim.run(remaining)
            if remaining is not None:remaining-=sim.cursor-before
            if not report['complete']:
                publish(root/f'{key}.checkpoint-{sim.cursor}.json',sim.snapshot())
                return dict(complete=False,completed=len(summaries),cursor=sim.cursor)
            publish(final,dict(report=report,snapshot=sim.snapshot()))
            summaries[key]=report
    for p,d in prior.items():assert sha((root/p).read_bytes())==d
    complete=dict(complete=True,combinations=len(summaries),results=summaries,training_admitted=False)
    publish(root/'COMPLETE.json',complete)
    if prior:publish(root/f'RESUME-{len(prior)}.json',dict(unchanged=prior,complete=True))
    return dict(complete=True,combinations=len(summaries),reused_files=len(prior))


def cents(x):return int(x.quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)*100)


def reconcile(sim):
    ledger=sim.ledger;buys=0;options={};capacity={};stock_sold=0
    cost=Decimal(str(sim.policy['cost_multiplier']))
    for e in ledger.events:
        if e['kind'] not in ('fill','stock_sale'):continue
        option=e['kind']=='fill';buy=option and e['side']=='buy'
        price=e['reference']['price'] if option else e['quote']['bid']
        mult=ledger.fixture['contracts'][e['contract']]['multiplier'] if option else 1
        gross=Decimal(e['quantity'])*Decimal(str(price))*Decimal(str(mult))
        fee,slip=gross*Decimal('.001')*cost,gross*Decimal('.0005')*cost
        raw=gross+fee+slip if buy else gross-fee-slip
        assert cents(raw)==e['cash_cents']
        for field,value in [('gross',gross),('fee',fee),('slippage',slip),('rounding_residual',Decimal(e['cash_cents'])/100-raw)]:
            assert abs(Decimal(str(e[field]))-value)<Decimal('1e-8')
        if buy:buys+=e['cash_cents']
        if option:
            c=e['contract'];options[c]=options.get(c,0)+(e['quantity'] if buy else -e['quantity'])
            ref=e['reference'];key=ref['key'];capacity[key]=capacity.get(key,0)+e['quantity']
            assert capacity[key]<=int(Decimal(str(ref['volume']))*Decimal(str(sim.policy['participation'])))
        else:
            stock_sold+=e['quantity']
            assert e['quantity']<=int(Decimal(str(e['quote']['bid_size']))*Decimal(str(e['quote']['size_to_shares'])))
    for x in ledger.expired:options[x['contract']]-=x['quantity']
    assert {c:q for c,q in options.items() if q}=={c:p['quantity'] for c,p in ledger.positions.items()}
    net_exercise=0;shares=0
    for d in ledger.deliveries:
        terms=ledger.lifecycle['terms'][d['contract']];q=Decimal(d['quantity'])
        strike=cents(q*Decimal(str(terms['strike_cash_per_contract'])))
        cash=cents(q*Decimal(str(terms['cash_per_contract'])))
        fee=cents(q*Decimal(str(sim.policy['exercise_fee'])))
        assert d['debit_cents']==(strike if d['right']=='C' else cash)+fee
        assert d['credit_cents']==(cash if d['right']=='C' else strike)
        assert d['shares']==d['quantity']*terms['shares_per_contract']
        if d['settled']:
            net_exercise+=d['credit_cents']-d['debit_cents']
            shares+=d['shares']*(1 if d['right']=='C' else -1)
    assert ledger.cash==10_000_000-buys+net_exercise+sum(r['cents'] for r in ledger.receivables if r['settled'])
    assert shares-stock_sold==sum(lot['shares'] for lot in ledger.stocks.values())
    assert ledger.available_cash()>=0
    report=sim.report()
    assert sum(report['census'].values())==report['proposal_count']==report['registered_count']
    assert all(p['target'] is None and not p['training_admitted'] for p in report['paths'].values())


def audit(root):
    cases=prepare(root);count=0;replayed=0;baseline={};census={}
    complete=checked(root/'COMPLETE.json')
    for case in cases:
        for name,policy in stress_profiles().items():
            key=case['id']+'--'+name;sim=Scheduler(case['tape'],policy)
            checkpoints=[p for p in root.glob(key+'.checkpoint-*.json') if not p.name.endswith('.sha256.json')]
            for p in sorted(checkpoints,key=lambda p:checked(p)['cursor']):
                expected=checked(p);sim.run(expected['cursor']-sim.cursor)
                assert sim.snapshot()==expected;replayed+=1
            result=sim.run();saved=checked(root/(key+'.result.json'))
            assert result==saved['report'] and sim.snapshot()==saved['snapshot']
            assert complete['results'][key]==result
            reconcile(sim)
            if name=='baseline':
                assert result['cash_cents']==case['baseline_expected']['cash_cents']
                assert result['census']==case['baseline_expected']['census']
                baseline[case['id']]=result
            for status,n in result['census'].items():census[status]=census.get(status,0)+n
            count+=1
    assert complete['combinations']==count and len(complete['results'])==count
    result=dict(schema='etfe-integration-independent-audit-v1',combinations=count,checkpoint_prefixes=replayed,
                baseline=baseline,stress_path_census=census,training_admitted=False,
                checks=['all_saved_states_and_reports','decimal_cash_costs_rounding','shares_and_contracts',
                        'participation_and_reservations','complete_census_and_null_targets','manual_baselines'])
    publish(root/'INDEPENDENT_AUDIT.json',result)
    return dict(combinations=count,checkpoint_prefixes=replayed,stress_path_census=census)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','audit']);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--max-events',type=int)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-integration-components-'):
        parser.error('Isolated integration-components study root required')
    print(json.dumps(run(root,args.max_events) if args.command=='run' else audit(root),indent=2))
