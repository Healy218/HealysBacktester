import json
from pathlib import Path
import pytest
from scripts.run_v6_next_stage import prerequisites


def test_downstream_stages_require_successful_predecessors(tmp_path):
    campaign='trial'
    prep=tmp_path/'nn_meta/expanded_inputs'/campaign/'full-run/worker-trial'
    base=tmp_path/'nn_meta/campaigns'/campaign/'v6'
    prep.mkdir(parents=True);(base/'artifacts').mkdir(parents=True)
    with pytest.raises(ValueError,match='full freeze'):prerequisites(tmp_path,campaign,'build')
    (prep/'result.json').write_text(json.dumps({'returncode':0,'freeze_completed':True}))
    with pytest.raises(ValueError,match='merged freeze'):prerequisites(tmp_path,campaign,'build')
    (base/'artifacts/baseline_spec.json').write_text('{}')
    prerequisites(tmp_path,campaign,'build')
    with pytest.raises(ValueError,match='build and assembly'):prerequisites(tmp_path,campaign,'evaluate')
    records=base/'runs/next-stage';records.mkdir(parents=True)
    (records/'build-result.json').write_text('{"returncode":0}')
    with pytest.raises(ValueError,match='dataset artifact'):prerequisites(tmp_path,campaign,'evaluate')
    for name in ['meta_dataset.parquet','meta_dataset.marks.parquet']:(base/'artifacts'/name).touch()
    prerequisites(tmp_path,campaign,'evaluate')
    with pytest.raises(ValueError,match='evaluation'):prerequisites(tmp_path,campaign,'finalize')
    (records/'evaluate-result.json').write_text('{"returncode":1}')
    with pytest.raises(ValueError):prerequisites(tmp_path,campaign,'finalize')
    (records/'evaluate-result.json').write_text('{"returncode":0}')
    prerequisites(tmp_path,campaign,'finalize')
