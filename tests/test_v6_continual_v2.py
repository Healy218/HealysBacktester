from types import SimpleNamespace

from incubator.continual.data_v2 import candidate_batch
from v3._source_memo import memoized_source, _scope


def test_numerical_reuse_is_limited_to_one_entry_and_releases_on_failure():
    calls = []

    @memoized_source
    def source(prefix):
        calls.append(prefix)
        return [prefix]

    def candidates(fresh, market, output):
        first = source(fresh)
        first.append('mutated')
        assert source(fresh) == [fresh]
        assert len(_scope.get()['values']) == 1
        if fresh == 'failure':
            raise ValueError('capture failed')
        return source(fresh), {}

    obj = SimpleNamespace(candidates=candidates)
    assert candidate_batch(obj, 'prefix', None, None) == (['prefix'], {})
    assert _scope.get() is None
    assert candidate_batch(obj, 'prefix', None, None) == (['prefix'], {})
    assert calls == ['prefix', 'prefix']
    import pytest
    with pytest.raises(ValueError, match='capture failed'):
        candidate_batch(obj, 'failure', None, None)
    assert _scope.get() is None


def test_resume_keeps_unfinished_date_but_advances_after_freeze(tmp_path):
    import json
    from scripts.v6_continual_resume import unfinished_session
    assert unfinished_session(tmp_path) is None
    path = tmp_path / 'latest-run.json'
    for status in ['running', 'blocked', 'deadline_reached', 'build_complete']:
        path.write_text(json.dumps(dict(scope='full_universe', status=status, through='2026-09-28')))
        assert unfinished_session(tmp_path) == '2026-09-28'
    for status in ['candidate_frozen', 'candidate_already_frozen', 'awaiting_matured_labels']:
        path.write_text(json.dumps(dict(scope='full_universe', status=status, through='2026-09-28')))
        assert unfinished_session(tmp_path) is None


def test_resume_pins_original_snapshot_even_after_data_index_advances(tmp_path):
    import json
    from scripts.v6_continual_resume import resume_config
    config = {'root': str(tmp_path), 'data_index': 'newer-index.json'}
    day = '2026-09-29'
    assert resume_config(config, day) == config
    directory = tmp_path / 'runs' / day
    directory.mkdir(parents=True)
    (directory / 'declaration.json').write_text(json.dumps({
        'through': day, 'snapshot': '/retained/snapshot', 'snapshot_sha256': 'frozen-hash',
    }))
    result = resume_config(config, day)
    assert result['bootstrap_snapshot'] == {
        'path': '/retained/snapshot', 'sha256': 'frozen-hash', 'through': day,
    }
    assert 'bootstrap_snapshot' not in config
