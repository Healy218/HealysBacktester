"""Proof boundary, frozen-store parity and scheduler restart regressions."""
import copy
from pathlib import Path
import shutil

import pytest

from scripts import run_v7_entry_demand as scheduler
from nn_meta.v7.storage import sha
from nn_meta.v7.provenance import runtime_manifest


def proof_fixture(tmp_path):
    proof = object.__new__(scheduler.CatalogProof)
    proof.root = tmp_path / 'catalog'
    proof.bindings = {}
    proof.reused = {'fixture': {}}
    proof.extra = set()
    proof.security_ids = ['fixture']
    proof.receipts = {}
    return proof


def test_narrow_proof_rejects_unknown_input_drift_runtime_and_foreign_store(tmp_path, monkeypatch):
    proof = proof_fixture(tmp_path)
    monkeypatch.setattr(scheduler, 'ROOT', tmp_path)
    source = tmp_path / 'scripts/build_v7_proposals.py'
    source.parent.mkdir()
    source.write_text('reviewed new loader')
    monkeypatch.setattr(scheduler, 'LOADER_CURRENT', sha(source))
    base = proof.root / 'fixture/5'
    for kind in ('features', 'proposals'):
        p = base / kind / 'summary/complete.json'
        p.parent.mkdir(parents=True)
        p.write_text(kind)
    proof.receipts['fixture', 5] = dict(feature_receipt_sha256=sha(base / 'features/summary/complete.json'),
                                       proposal_receipt_sha256=sha(base / 'proposals/summary/complete.json'))
    declaration = dict(security_id='fixture', minutes=5, runtime=runtime_manifest(), sources={},
                       inputs={str(source): scheduler.LOADER_OLD})
    original = copy.deepcopy(declaration)
    translated = proof.current_bindings(base / 'features', declaration)
    assert translated['inputs'][str(source)] == sha(source)
    assert declaration == original  # Historical declaration must never be relabeled.
    proof.reused = {}
    with pytest.raises(ValueError, match='Unproved'):
        proof.current_bindings(base / 'features', declaration)
    proof.extra = {'fixture'}
    assert proof.current_bindings(base / 'features', declaration) == translated
    source.write_text('unreviewed third loader')
    with pytest.raises(ValueError, match='Unproved'):
        proof.current_bindings(base / 'features', declaration)
    source.write_text('reviewed new loader')
    declaration['runtime'] = {}
    with pytest.raises(ValueError, match='runtime'):
        proof.current_bindings(base / 'features', declaration)
    declaration['runtime'] = original['runtime']
    with pytest.raises(ValueError, match='exact deep-audited'):
        proof.current_bindings(tmp_path / 'elsewhere', declaration)
    (base / 'proposals/summary/complete.json').write_text('changed')
    with pytest.raises(ValueError, match='exact deep-audited'):
        proof.current_bindings(base / 'features', declaration)


def test_proof_evidence_must_remain_unchanged(tmp_path):
    proof = proof_fixture(tmp_path)
    evidence = tmp_path / 'evidence.json'
    evidence.write_text('reviewed')
    proof.bindings = {str(evidence): sha(evidence)}
    proof.check_evidence()
    evidence.write_text('different')
    with pytest.raises(ValueError, match='evidence changed'):
        proof.check_evidence()


def test_demand_view_preserves_rows_and_math_and_receipts(tmp_path, monkeypatch):
    from tests.test_v7_entry_demand import fixture
    from nn_meta.v7.entry_demand import build_entry_demand, EntryDemand
    from nn_meta.v7.proposal_store import StoredProposals
    from nn_meta.v7.storage import receipt, identity, verify
    store, chain = fixture(tmp_path)
    # Place fixtures at production's security/timeframe layout before sealing
    # the proposal declaration against that path.
    base = tmp_path / 'catalog/fixture/5'
    base.mkdir(parents=True)
    shutil.move(store.features.path, base / 'features')
    shutil.move(store.path, base / 'proposals')
    declaration_path = base / 'proposals/declaration'
    declaration = scheduler.read(declaration_path / 'declaration.json')
    declaration['feature_store'] = str(base / 'features')
    scheduler.write(declaration_path / 'declaration.json', declaration)
    (declaration_path / 'complete.json').unlink()
    receipt(declaration_path, dict(identity=identity(declaration)))
    summary = base / 'proposals/summary'
    report = scheduler.read(summary / 'report.json')
    for batch in report['batches']:
        directory = base / 'proposals/batches' / str(batch['batch'])
        records = [r for r in declaration['variants'] if r['variant_id'] in batch['variants']]
        (directory / 'complete.json').unlink()
        receipt(directory, dict(identity=identity(dict(parent=identity(declaration), variants=records))))
        batch['receipt_sha256'] = sha(directory / 'complete.json')
    scheduler.write(summary / 'report.json', report)
    (summary / 'complete.json').unlink()
    receipt(summary, dict(identity=identity(dict(parent=identity(declaration), report=report))))
    strict = StoredProposals(base / 'proposals')
    proof = proof_fixture(tmp_path)
    proof.receipts['fixture', 5] = dict(feature_receipt_sha256=sha(base / 'features/summary/complete.json'),
                                       proposal_receipt_sha256=sha(summary / 'complete.json'))
    evidence = tmp_path / 'review.json'
    evidence.write_text('reviewed fixture')
    proof.bindings = {str(evidence): sha(evidence)}
    monkeypatch.setattr(scheduler, 'MINUTES', (5,))
    before = {str(p): sha(p) for p in base.rglob('*') if p.is_file()}
    adapted = scheduler.proven_stores(proof, 'fixture')
    assert list(adapted[0].rows()) == list(strict.rows())
    kwargs = dict(reserve_bytes=0, expected_timeframes=(5,))
    expected = build_entry_demand(tmp_path / 'strict', [strict], chain, **kwargs)
    actual = build_entry_demand(tmp_path / 'adapted', adapted, chain, **kwargs)
    assert actual == expected
    assert list(EntryDemand(tmp_path / 'strict').request_batches()) == list(EntryDemand(tmp_path / 'adapted').request_batches())
    assert {str(p): sha(p) for p in base.rglob('*') if p.is_file()} == before
    declaration = scheduler.read(tmp_path / 'adapted/declaration.json')
    assert declaration['inputs'][str(evidence)] == sha(evidence)
    assert declaration['inputs'][str(base / 'features/declaration/declaration.json')] == sha(base / 'features/declaration/declaration.json')
    verify(tmp_path / 'adapted')
    monkeypatch.setattr(adapted[0], 'rows', lambda **kw: pytest.fail('Repeated proposal scan'))
    assert build_entry_demand(tmp_path / 'adapted', adapted, chain, **kwargs) == actual
    evidence.write_text('changed proof')
    with pytest.raises(ValueError, match='inputs'):
        EntryDemand(tmp_path / 'adapted')


def test_scheduler_selection_retains_zero_proposal_securities_and_rejects_duplicates(tmp_path):
    proof = proof_fixture(tmp_path)
    proof.security_ids = ['busy', 'zero']
    proof.receipts = {(sid, m): {'proposals': int(sid == 'busy')} for sid in proof.security_ids for m in scheduler.MINUTES}
    assert scheduler.select_securities(proof, None) == ['zero', 'busy']
    assert scheduler.select_securities(proof, ['busy']) == ['busy']
    for invalid in (['zero', 'zero'], ['foreign']):
        with pytest.raises(ValueError, match='distinct catalog'):
            scheduler.select_securities(proof, invalid)
