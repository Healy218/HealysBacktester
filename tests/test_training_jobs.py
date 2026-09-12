import json
import numpy as np
import pandas as pd
import pytest
from nn_meta import training_jobs as jobs
from nn_meta.v4_evaluate import _matrix, fit_gbt, winsor_bounds
from nn_meta.training_experiments import event_weights


def frames():
    rng = np.random.default_rng(37)
    f = pd.DataFrame({'a':rng.normal(size=1800), 'b':rng.normal(size=1800), 'constant':1.})
    f['label'] = (f.a + rng.normal(size=len(f)) > 0).astype(float)
    f['net_return'] = f.a*.1 + rng.normal(size=len(f))*.2
    f.loc[0,'b'] = np.nan
    f.loc[2,'label'] = np.nan
    f.loc[5,'net_return'] = np.nan
    return f.iloc[:1400].copy(), f.iloc[1400:].copy(), ['a','b','constant']


def test_prepared_arrays_match_reference_and_ignore_validation_scaler(tmp_path):
    tr, va, features = frames()
    path = jobs.prepare(tr, va, features, 'label', root=tmp_path)
    doc = json.loads((path/'arrays.json').read_text())
    labeled = tr[tr.label.notna()]
    mu, sd = labeled[features].mean(), labeled[features].std().replace(0,1.)
    np.testing.assert_array_equal(np.load(path/'train_x.npy'), _matrix(labeled,features,mu,sd))
    np.testing.assert_array_equal(np.load(path/'val_x.npy'), _matrix(va,features,mu,sd))
    np.testing.assert_allclose(doc['bounds'], winsor_bounds(labeled.net_return.dropna()))
    assert jobs.prepare(tr,va,features,'label',root=tmp_path) == path
    (path/'val_y.npy').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='changed'):
        jobs.prepare(tr,va,features,'label',root=tmp_path)


def test_seed_receipt_rejects_changed_settings_and_corruption(tmp_path):
    model = tmp_path/'model'; model.write_bytes(b'model')
    jobs._json(tmp_path/'complete.json', {'settings':{'seed':2}, 'hashes':{'model':jobs.sha(model)}})
    assert jobs.reusable(tmp_path,{'seed':2})
    with pytest.raises(ValueError,match='configuration'):
        jobs.reusable(tmp_path,{'seed':3})
    model.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):
        jobs.reusable(tmp_path,{'seed':2})


def test_parallel_gbt_matches_reference_and_resumes(tmp_path,monkeypatch):
    tr,va,features=frames()
    monkeypatch.setenv('NN_META_TRAIN_WORKERS','2')
    monkeypatch.setenv('NN_META_TRAIN_THREADS','2')
    prepared=jobs.prepare(tr,va,features,'label',root=tmp_path/'arrays')
    paths=jobs.run_seeds(prepared,'gbt',[0,1],epochs=1,estimators=20,out=tmp_path/'jobs')
    reference=fit_gbt(tr,va,features=features,label='label',n_estimators=20)
    np.testing.assert_allclose(jobs.disk_predict('gbt',paths[:1],va,features),reference.predict(va),rtol=1e-10,atol=1e-10)
    np.testing.assert_allclose(jobs.disk_predict('gbt',paths[:1],va,features,magnitude=True),reference.predict_ev(va),rtol=1e-10,atol=1e-10)
    before=[(p/'complete.json').stat().st_mtime_ns for p in paths]
    jobs.run_seeds(prepared,'gbt',[0,1],epochs=1,estimators=20,out=tmp_path/'jobs')
    assert before==[(p/'complete.json').stat().st_mtime_ns for p in paths]


def test_duplicate_event_weight_is_constant_across_variants():
    rows=pd.DataFrame({'symbol':['A','A','B'], 'entry_ts':pd.to_datetime(['2026-01-01']*3), 'dir_short':[0,0,0]})
    w=event_weights(rows)
    assert w.mean()==pytest.approx(1.)
    assert w[0]+w[1]==pytest.approx(w[2])
    rows.loc[0,'dir_short']=np.nan
    with pytest.raises(ValueError,match='complete'):
        event_weights(rows)


def test_parallel_nn_matches_reference_heads(tmp_path,monkeypatch):
    from nn_meta.v4_evaluate import fit_nn
    from nn_meta.v4_loader import ensemble_score, ensemble_ev
    tr,va,features=frames()
    monkeypatch.setenv('NN_META_TRAIN_WORKERS','2')
    prepared=jobs.prepare(tr,va,features,'label',root=tmp_path/'arrays')
    paths=jobs.run_seeds(prepared,'nn',[0,1],epochs=2,estimators=20,out=tmp_path/'jobs')
    reference=fit_nn(tr,va,features=features,label='label',seed=0,epochs=2)
    np.testing.assert_allclose(jobs.disk_predict('nn',paths[:1],va,features),reference.predict(va),rtol=1e-5,atol=1e-6)
    np.testing.assert_allclose(jobs.disk_predict('nn',paths[:1],va,features,magnitude=True),reference.predict_ev(va),rtol=1e-5,atol=1e-6)
    members=[{'disk_path':str(p),'magnitude':True} for p in paths]
    for magnitude,score in [(False,ensemble_score),(True,ensemble_ev)]:
        expected=np.mean([jobs.disk_predict('nn',[p],va,features,magnitude=magnitude) for p in paths],axis=0)
        np.testing.assert_array_equal(score('nn',members,va,features),expected)


def test_objective_comparisons_use_purged_partitions_and_remain_research(tmp_path,monkeypatch):
    from nn_meta import training_experiments as ex, baseline, build_meta_dataset as builder, config
    from nn_meta.feature_contract import CONTRACT_VERSION, baseline_spec_fingerprint
    rng=np.random.default_rng(42)
    n=1200
    rows=pd.DataFrame({'a':rng.normal(size=n),'symbol':['SPY']*n,'dir_short':[0.]*n})
    rows['entry_ts']=pd.to_datetime(['2025-12-01']*600+['2026-02-02']*300+['2026-05-01']*300)
    rows['exit_ts']=rows.entry_ts+pd.Timedelta(days=1)
    rows['net_return']=rows.a*.1+rng.normal(size=n)*.1
    rows['label_excess']=(rows.net_return>0).astype(float)
    # A training label that arrives in validation must be excluded.
    rows.loc[0,'exit_ts']=pd.Timestamp('2026-02-02')
    spec={'train_window':['2024-08-26','2025-12-19']}
    rows.attrs={'feature_contract_version':CONTRACT_VERSION,'baseline_spec_sha256':baseline_spec_fingerprint(spec)}
    monkeypatch.setattr(baseline,'load_spec',lambda:spec)
    monkeypatch.setattr(builder,'V4_META_FEATURES',['a','dir_short'])
    path=tmp_path/'rows.parquet'; rows.to_parquet(path,index=False)
    out=tmp_path/'experiment'
    ex.run(path,out,estimators=20)
    plan=json.loads((out/'plan.json').read_text())
    result=json.loads((out/'results.json').read_text())
    assert plan['research_only'] and not plan['test_used_for_selection']
    assert plan['split']['train']['rows']==599
    assert set(result['models'])=={'baseline','event_balanced','downside_q10'}
    assert result['complete']


def test_finalizer_preserves_completed_seeds_on_resume_and_gate_failure(tmp_path,monkeypatch):
    import nn_meta.v4_finalize as fz
    from tests.test_v4_finalize import _install_finalize_stubs
    from nn_meta.v4_evaluate import Predictor
    final=_install_finalize_stubs(monkeypatch,tmp_path,eligible=False)
    monkeypatch.setattr(fz.config,'REPORTS_DIR',tmp_path/'reports')
    monkeypatch.setenv('NN_META_PREPARED_TRAINING','1')
    monkeypatch.setattr(jobs,'fit_family',lambda *a,**k:Predictor('gbt',lambda rows:np.full(len(rows),.6),lambda rows:np.zeros(len(rows))))
    monkeypatch.setattr(jobs,'prepare',lambda *a,**k:tmp_path/'arrays')
    staging=final.with_name(final.name+'.staging');staging.mkdir()
    marker=staging/'existing-seed';marker.write_text('keep')
    def resumed(*a,**k):
        assert marker.read_text()=='keep'
        seed=staging/'v4-gbt-xs-s0';seed.mkdir(exist_ok=True)
        (seed/'model.joblib').write_bytes(b'stub')
        jobs._json(seed/'complete.json',{'hashes':{'model.joblib':jobs.sha(seed/'model.joblib')}})
        return [seed]
    monkeypatch.setattr(jobs,'run_seeds',resumed)
    monkeypatch.setattr(fz,'_ensemble_ev',lambda *a:np.zeros(4))
    with pytest.raises(SystemExit) as exc:
        fz.main()
    assert exc.value.code==1 and marker.exists() and not final.exists()
