import copy
import json
import pandas as pd
import pytest
from scripts import v6_daily_append_v5 as daily
from incubator.continual.storage import seal, sha, write


def declaration():
    return dict(schema='features', contract='old', symbol='CRSP', entry_ts='2026-09-28T19:45:00',
                all_prefix='frozen', raw_prefix='raw', proposals=[dict(strategy='tv_rating',
                proposal_ordinal=0, spot=54.1, bars_since_signal=85)])


def extended():
    d = declaration()
    d['contract'] = 'new'
    d['proposals'].append(dict(d['proposals'][0], proposal_ordinal=1, bars_since_signal=0))
    return d


def test_append_keeps_old_occurrences_and_normalizes_legacy_zero():
    old = declaration()
    old['proposals'][0].pop('proposal_ordinal')
    assert daily.matching_occurrences(old, extended()) == {('tv_rating', 0)}


@pytest.mark.parametrize('mutation', ['prefix', 'spot', 'removed', 'duplicate'])
def test_rejects_changed_or_removed_frozen_inputs(mutation):
    old, new = declaration(), extended()
    if mutation == 'prefix': new['all_prefix'] = 'changed'
    if mutation == 'spot': new['proposals'][0]['spot'] = 99
    if mutation == 'removed': new['proposals'] = new['proposals'][1:]
    if mutation == 'duplicate': new['proposals'].append(copy.deepcopy(new['proposals'][0]))
    with pytest.raises(ValueError): daily.matching_occurrences(old, new)


def test_feature_parts_keep_parent_seal_and_new_shard_distinct(tmp_path):
    relative = 'features/CRSP/20260928T194500'
    parent = tmp_path/'parent'; location = parent/relative
    location.mkdir(parents=True)
    pd.DataFrame([dict(strategy='tv_rating', proposal_ordinal=0, feature=42)]).to_parquet(location/'features.parquet')
    seal(location, declaration(), ['features.parquet'])
    before = sha(location/'complete.json')
    census = tmp_path/'census.json'
    write(census, dict(root=str(parent), contract_identity='old', anchors={relative+'/complete.json':before}))
    inherited = daily.ParentArtifacts(dict(inherited_artifacts=dict(path=str(census),sha256=sha(census))))
    root = tmp_path/'new'
    parts, missing = inherited.feature_parts(root, relative, extended())
    assert parts[0][0] == location
    assert [p['proposal_ordinal'] for p in missing] == [1]
    new = root/relative; new.mkdir(parents=True)
    pd.DataFrame([dict(strategy='tv_rating', proposal_ordinal=1, feature=84)]).to_parquet(new/'features.parquet')
    seal(new, dict(extended(), proposals=missing), ['features.parquet'])
    parts, missing = inherited.feature_parts(root, relative, extended())
    assert not missing
    assert {int(r.proposal_ordinal) for _,frame in parts for r in frame.itertuples()} == {0,1}
    assert sha(location/'complete.json') == before
    # A subsequent daily shard at the same timestamp is discovered on resume.
    next_decl = extended()
    next_decl['proposals'].append(dict(next_decl['proposals'][1],proposal_ordinal=2))
    shard = new/'2026-10-01'; shard.mkdir()
    pd.DataFrame([dict(strategy='tv_rating', proposal_ordinal=2, feature=126)]).to_parquet(shard/'features.parquet')
    seal(shard, dict(next_decl,proposals=[next_decl['proposals'][-1]]), ['features.parquet'])
    parts, missing = inherited.feature_parts(root, relative, next_decl)
    assert not missing
    assert sum(len(frame) for _,frame in parts) == 3


def test_new_single_occurrence_keeps_nonzero_ordinal(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, 'candidate_batch', lambda *args: (pd.DataFrame([{'proposal_ordinal':0}]),{}))
    frame = daily.new_occurrence_batch(None,[extended()['proposals'][1]],None,tmp_path)
    assert frame.proposal_ordinal.tolist() == [1]
