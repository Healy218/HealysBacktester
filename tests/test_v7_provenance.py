import pytest
from nn_meta.v7.provenance import RunBinding


def test_binding_preserves_components_and_detects_source_and_input_mutations(tmp_path):
    source = tmp_path / 'nn_meta'
    source.mkdir()
    code = source / 'example.py'
    code.write_text('x = 1\n')
    data = tmp_path / 'data.json'
    data.write_text('{}')
    bound = RunBinding(tmp_path, inputs=[data], declaration={'scope': 'test'})
    assert bound.finish()['sources']['nn_meta/example.py']
    code.write_text('x = 2\n')
    with pytest.raises(ValueError, match='Source changed'):
        bound.finish()
    code.write_text('x = 1\n')
    data.write_text('{"new": true}')
    with pytest.raises(ValueError, match='Input changed'):
        bound.finish()
