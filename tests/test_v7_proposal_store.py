import json

import numpy as np
import pandas as pd
import pytest

from nn_meta.multitimeframe_catalog import registered_catalog
from nn_meta.v7.causal_features import CausalFeatures
from nn_meta.v7.causal_prices import split_action
from nn_meta.v7.proposal_store import StoredFeatures, StoredProposals, build_features, build_proposals
from nn_meta.v7.storage import sha


def chart_fixture():
    days = ['2022-03-15', '2022-03-16']
    index = pd.date_range(days[0]+'T13:30Z', periods=81, freq='min').append(
        pd.date_range(days[1]+'T13:30Z', periods=83, freq='min'))
    close = 100 + np.sin(np.arange(len(index))*.3)*5
    raw = pd.DataFrame(dict(Open=close, High=close+1, Low=close-1, Close=close, Volume=100.), index=index)
    raw.loc[index >= days[1], ['Open', 'High', 'Low', 'Close']] /= 2
    raw['available_at'] = index+pd.Timedelta(minutes=1)
    calendar = dict(timezone='America/New_York', coverage_start=days[0], coverage_end=days[-1],
                    sessions=[dict(date=d, open='09:30', close='16:00') for d in days])
    action = split_action(old_shares=1, new_shares=2, event_id='split',
        effective_at=pd.Timestamp(days[1]+'T13:30Z'), available_at=pd.Timestamp('2022-03-01T00:00Z'),
        source_identity='fixture')
    chart = CausalFeatures(raw, [action], calendar, security_id='fixture', minutes=1,
                           start=days[0], end=days[-1])
    catalog = [v for v in registered_catalog(['TEST'])['records'] if v['signal_minutes']==1]
    variants = [next(v for v in catalog if v['strategy']==s) for s in sorted({v['strategy'] for v in catalog})]
    return chart, variants


def build(tmp_path):
    chart, variants = chart_fixture()
    source = tmp_path/'source.txt'
    source.write_text('retained inputs')
    inputs = {str(source): sha(source)}
    report = build_features(tmp_path/'features', chart, variants, inputs=inputs, reserve_bytes=0,
                            batch_columns=7)
    return chart, variants, inputs, report, StoredFeatures(tmp_path/'features')


def test_epoch_cache_matches_all_families_and_causal_prices(tmp_path):
    from nn_meta.v7.signals import signal_batches
    chart, variants, _, report, store = build(tmp_path)
    batches = list(store.signal_batches(batch_columns=3))
    actual = [pd.concat([values[i] for _, values in batches], axis=1) for i in range(4)]
    assert report['variants'] == 20 and report['observations'] == 164
    assert report['packed_signal_bytes'] == 4*20*(11+11)
    assert not report['full_timeframe_catalog'] and not report['research_ready']
    for number, epoch in enumerate(chart.epochs()):
        saved = pd.read_parquet(tmp_path/f'features/epochs/{number}/features.parquet')
        pd.testing.assert_frame_equal(saved, epoch.technical.loc[epoch.observed].join(epoch.tv))
        for records, channels in signal_batches(epoch.bars, variants, sources=epoch.sources, batch_columns=3):
            ids = [v['variant_id'] for v in records]
            for left, right in zip(actual, channels):
                pd.testing.assert_frame_equal(left.loc[epoch.observed, ids], right.loc[epoch.observed, ids])
    pd.testing.assert_frame_equal(store.basis, chart.proposal_basis())
    averages = pd.read_parquet(tmp_path/'features/epochs/1/averages.parquet')
    last = list(chart.epochs())[-1]
    for window in averages:
        pd.testing.assert_series_equal(averages[window],
            (last.bars.Close.rolling(int(window)).mean()/last.bars.Close).loc[last.observed], check_names=False)


def test_resume_skips_completed_indicators_and_keeps_proposals_identical(tmp_path, monkeypatch):
    from nn_meta.v7.proposals import causal_proposal_batches
    chart, variants, inputs, report, store = build(tmp_path)
    original = chart.epochs
    seen = []
    def reused(*, skip_intervals=()):
        seen.extend(skip_intervals)
        yield from original(skip_intervals=skip_intervals)
    monkeypatch.setattr(chart, 'epochs', reused)
    assert build_features(tmp_path/'features', chart, variants, inputs=inputs, reserve_bytes=0)==report
    assert len(seen)==2
    path = tmp_path/'proposals'
    got = build_proposals(path, store, symbol='TEST', start='2022-03-15', end='2022-03-16',
                          reserve_bytes=0, batch_columns=4)
    actual = {r['proposal_id']:r for r in StoredProposals(path,features=store).rows(batch_size=3)}
    expected = {r['proposal_id']:r for _, rows in causal_proposal_batches('TEST', chart, variants,
        start='2022-03-15', end='2022-03-16', batch_columns=4) for r in rows}
    assert set(actual)==set(expected)
    assert got['variants']==20 and got['proposals']==len(actual)
    for key, row in expected.items():
        assert actual[key]['decision_at']==row['decision_at'].isoformat()
        assert actual[key]['exit_decision_ns']==(row['exit_decision_at'].value if row['proposal_closed'] else None)
        assert actual[key]['bars_since_previous_signal']==row['bars_since_previous_signal']
        serialized = dict(row,security_id='fixture',
                          exit_decision_ns=row['exit_decision_at'].value if row['proposal_closed'] else None)
        for field in ('decision_at','exit_decision_at','censored_at'):
            serialized[field] = None if pd.isna(serialized[field]) else serialized[field].isoformat()
        assert actual[key]==json.loads(json.dumps(serialized))
    renamed = tmp_path/'renamed'
    build_proposals(renamed, store, symbol='fixture', start='2022-03-15', end='2022-03-16',
                    symbols_by_date={'2022-03-15':'OLD', '2022-03-16':'NEW'}, reserve_bytes=0)
    routed = list(StoredProposals(renamed,features=store).rows(batch_size=7))
    assert len(routed)==len(actual) and {r['symbol'] for r in routed}=={'OLD','NEW'}
    for row in routed:
        day = pd.Timestamp(row['decision_at']).tz_convert('America/New_York').date().isoformat()
        assert row['symbol']=={'2022-03-15':'OLD','2022-03-16':'NEW'}[day]
        assert row['security_id']=='fixture'
    import nn_meta.v7.proposals as proposals
    monkeypatch.setattr(proposals, 'proposals_from_signals', lambda *a, **k: pytest.fail('Repeated simulation'))
    assert build_proposals(path, store, symbol='TEST', start='2022-03-15', end='2022-03-16',
                           reserve_bytes=0, batch_columns=4)==got


def test_store_refuses_changed_inputs_and_catalog(tmp_path):
    chart, variants, inputs, _, _ = build(tmp_path)
    with pytest.raises(ValueError, match='identity mismatch'):
        build_features(tmp_path/'features', chart, variants[:-1], inputs=inputs, reserve_bytes=0)
    (tmp_path/'source.txt').write_text('changed')
    with pytest.raises(ValueError, match='inputs changed'):
        StoredFeatures(tmp_path/'features')


def test_tampered_packed_signals_and_insufficient_memory_are_rejected(tmp_path):
    _, _, _, _, store = build(tmp_path)
    with pytest.raises(ValueError, match='one full-history signal column'):
        list(store.signal_batches(working_bytes=1))
    path = tmp_path/'features/epochs/0/signals.npy'
    packed = np.load(path, mmap_mode='r+')
    packed[0,0,0] ^= 1
    packed.flush()
    with pytest.raises(ValueError, match='integrity failure'):
        StoredFeatures(tmp_path/'features')


def test_disk_reserve_is_enforced_before_epoch_work(tmp_path):
    chart, variants = chart_fixture()
    source = tmp_path/'input'
    source.write_text('input')
    with pytest.raises(ValueError, match='disk reserve'):
        build_features(tmp_path/'features', chart, variants, inputs={str(source):sha(source)},
                       reserve_bytes=10**30)
    assert not (tmp_path/'features/epochs').exists()


def test_feature_store_persists_no_event_assumption_and_refuses_resume_with_changed_admission(tmp_path):
    chart, variants = chart_fixture()
    source = tmp_path/'input'; source.write_text('input')
    chart.coverage_declaration = dict(policy_identity='approved-policy', receipt_sha256='coverage-receipt',
        completeness_verified=False, held_position_admitted=False)
    inputs = {str(source):sha(source)}
    build_features(tmp_path/'features', chart, variants[:1], inputs=inputs, reserve_bytes=0)
    store = StoredFeatures(tmp_path/'features')
    assert store.declaration['action_coverage'] == chart.coverage_declaration
    chart.coverage_declaration['policy_identity'] = 'changed'
    with pytest.raises(ValueError, match='identity mismatch'):
        build_features(tmp_path/'features', chart, variants[:1], inputs=inputs, reserve_bytes=0)


def test_interrupted_epoch_keeps_completed_checkpoint_and_resumes(tmp_path, monkeypatch):
    import nn_meta.v7.signals as signals
    chart, variants = chart_fixture()
    source = tmp_path/'input'
    source.write_text('input')
    inputs = {str(source):sha(source)}
    original = signals.signal_batches
    calls = []
    def interrupted(*args, **kwargs):
        calls.append(1)
        if len(calls)==2:
            raise RuntimeError('injected interruption')
        yield from original(*args, **kwargs)
    monkeypatch.setattr(signals, 'signal_batches', interrupted)
    path = tmp_path/'features'
    with pytest.raises(RuntimeError, match='injected interruption'):
        build_features(path, chart, variants, inputs=inputs, reserve_bytes=0)
    receipt = path/'epochs/0/complete.json'
    digest = sha(receipt)
    assert not (path/'summary').exists() and not (path/'epochs/1').exists()
    assert len(list((path/'epochs').glob('1.partial-*')))==1
    build_features(path, chart, variants, inputs=inputs, reserve_bytes=0)
    assert len(calls)==3 and sha(receipt)==digest
    assert StoredFeatures(path).report['observations']==164
