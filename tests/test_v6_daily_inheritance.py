from pathlib import Path
import pytest
from incubator.continual.storage import seal,sha,write
from incubator.daily_v6.inheritance import ParentArtifacts


def setup(tmp_path):
    ancestor=tmp_path/'r2';ancestor.mkdir()
    a=tmp_path/'ancestor.json'
    write(a,dict(root=str(ancestor),contract_identity='r2',anchors={}))
    parent=tmp_path/'r3';feature=parent/'features/SPY/entry';feature.mkdir(parents=True)
    (feature/'features.parquet').write_text('fixture')
    declaration=dict(contract='r3',proposals=[{'proposal_ordinal':1}])
    seal(feature,declaration,['features.parquet'])
    census=tmp_path/'census.json'
    write(census,dict(root=str(parent),contract_identity='r3',anchors={'features/SPY/entry/complete.json':sha(feature/'complete.json')},ancestor={'path':str(a),'sha256':sha(a)}))
    return ParentArtifacts({'inherited_artifacts':{'path':str(census),'sha256':sha(census)}}),feature


def test_r3_occurrence_and_seal_preserved(tmp_path):
    parent,feature=setup(tmp_path)
    assert parent.resolve('features/SPY/entry',dict(contract='r4',proposals=[{'proposal_ordinal':1}]))==feature
    assert parent.feature_paths('SPY')==[feature/'features.parquet']
    with pytest.raises(ValueError):parent.resolve('features/SPY/entry',dict(contract='r4',proposals=[{'proposal_ordinal':0}]))


def test_changed_parent_payload_fails(tmp_path):
    parent,feature=setup(tmp_path)
    (feature/'features.parquet').write_text('modified')
    with pytest.raises(ValueError):parent.resolve('features/SPY/entry')
