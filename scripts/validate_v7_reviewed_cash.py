"""Exercise finite cash reviews with real raw feature consumers."""
from pathlib import Path
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from nn_meta.v7.causal_features import CausalFeatures
    from nn_meta.v7.causal_prices import CausalPriceHistory
    from nn_meta.v7.proposal_store import build_features
    from nn_meta.multitimeframe_catalog import registered_catalog
    from scripts.build_v7_proposals import load_inputs
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','history','actions','previous-actions','coverage','previous-coverage','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();inputs={str(Path(__file__)):sha(__file__)}
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Repository artifact path required')
    for path in (args.history,args.actions,args.previous_actions,args.coverage,args.previous_coverage):
        doc=verify(path)
        inputs[str(path/'complete.json')]=sha(path/'complete.json')
        inputs.update({str(path/n):d for n,d in doc['files'].items()})
        inputs.update(json.loads((path/'inputs.json').read_text()))
    base=json.loads((args.previous_actions/'actions.json').read_text())
    events=json.loads((args.actions/'actions.json').read_text())
    assert events[:len(base)]==base
    reviewed=events[len(base):]
    old=pd.read_parquet(args.previous_coverage/'coverage.parquet').set_index(['security_id','source_date'])
    new=pd.read_parquet(args.coverage/'coverage.parquet').set_index(['security_id','source_date'])
    changed=pd.MultiIndex.from_tuples([(e['security_id'],e['effective_date']) for e in reviewed],names=new.index.names)
    mask=~new.index.isin(changed)
    pd.testing.assert_frame_equal(old.loc[mask],new.loc[mask])
    assert (new.history_admitted>=old.history_admitted).all()
    assert new.loc[changed].history_admitted.all()
    variant=next(v for v in registered_catalog(['_store'])['records'] if v['signal_minutes']==15 and v['strategy']=='ma')
    cases=[]
    for e in reviewed:
        symbol,sid,start,end=e['symbol'],e['security_id'],e.get('prior_source_date') or e['evidence']['prior_source_date'],e['effective_date']
        raw,typed,cal,bound,routing,eligibility,declaration=load_inputs(dict(source=str(args.source),
            history=str(args.history),actions=str(args.actions),action_coverage=str(args.coverage),
            security_id=sid,start=start,end=end))
        action=next(a for a in typed if a.event_id==e['action']['event_id'])
        cash=float(e['cash_amount'])
        prior_close=float(e.get('prior_raw_close') or e['evidence']['prior_raw_close'])
        factor=(prior_close-cash)/prior_close
        assert abs(action.price_factor-factor)<1e-14 and action.volume_factor==1
        before=action.effective_at-pd.Timedelta(nanoseconds=1)
        baseline=[a for a in typed if a.event_id!=action.event_id]
        chart=CausalPriceHistory(raw,typed,security_id=sid)
        pd.testing.assert_frame_equal(chart.view(before),CausalPriceHistory(raw,baseline,security_id=sid).view(before))
        after=chart.view(raw.available_at.iloc[-1])
        original=raw.index<action.effective_at
        pd.testing.assert_series_equal(after.loc[original,'Close'],raw.loc[original,'Close']*factor)
        pd.testing.assert_series_equal(after.loc[original,'Volume'],raw.loc[original,'Volume'],check_dtype=False)
        pd.testing.assert_series_equal(after.loc[~original,'Close'],raw.loc[~original,'Close'])
        features=CausalFeatures(raw,typed,cal,security_id=sid,minutes=15,start=start,end=end)
        features.coverage_declaration=declaration
        store=args.output.parent/(args.output.name+'-features-'+symbol+'-'+end)
        report=build_features(store,features,[variant],inputs=bound,reserve_bytes=100*1024**3)
        assert json.loads((store/'declaration/declaration.json').read_text())['action_coverage']==declaration
        for p in store.rglob('complete.json'):
            doc=verify(p.parent);inputs[str(p)]=sha(p)
            inputs.update({str(p.parent/n):d for n,d in doc['files'].items()})
        inputs.update(bound)
        cases.append(dict(symbol=symbol,effective_date=end,security_id=sid,raw_minutes=len(raw),
            cash_per_share=cash,price_factor=factor,prefix_unchanged=True,report=report,feature_store=str(store)))
        print(symbol,end,len(raw),flush=True)
    assert all(sha(p)==d for p,d in inputs.items())
    report=dict(preserved_existing_events=len(base),reviewed_events=len(reviewed),cases=cases,
        unchanged_history_rows=int(mask.sum()),additional_admitted_sessions=int(new.history_admitted.sum()-old.history_admitted.sum()),
        admitted_history_sessions=int(new.history_admitted.sum()),held_history_admitted=False,research_ready=False)
    with transaction(args.output) as temp:
        for n,v in [('inputs',inputs),('report',report)]:
            (temp/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
