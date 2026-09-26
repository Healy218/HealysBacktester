import copy
import json

import pytest

from scripts import resume_v7_entry_demand as recovery
from nn_meta.v7.storage import sha, receipt, identity


def runtimes():
    old = dict(python='exact python', executable='/exact/python', packages=[['example', '1']],
               platform=recovery.OLD_PLATFORM)
    new = dict(old, platform=recovery.NEW_PLATFORM)
    return old, new


def test_kernel_exception_is_exact_and_does_not_mutate_provenance():
    old, new = runtimes()
    before = copy.deepcopy(old)
    recovery.runtime_allowed(old, new)
    recovery.runtime_allowed(new, new)
    assert old == before
    for field, value in [('python', 'different'), ('executable', '/other'),
                         ('packages', [['example', '2']]), ('platform', recovery.NEW_PLATFORM + '-other')]:
        changed = dict(new, **{field: value})
        with pytest.raises(ValueError, match='approved kernel pair'):
            recovery.runtime_allowed(old, changed)
    with pytest.raises(ValueError, match='approved kernel pair'):
        recovery.runtime_allowed(new, old)


def test_kernel_reader_still_rejects_source_drift(tmp_path, monkeypatch):
    old, new = runtimes()
    monkeypatch.setattr(recovery, 'runtime_manifest', lambda: new)
    source = tmp_path / 'parent'
    source.write_text('original')
    reader = object.__new__(recovery.KernelEntryDemand)
    reader.declaration = dict(runtime=old, inputs={str(source): sha(source)})
    reader.verify_bindings()
    source.write_text('changed')
    with pytest.raises(ValueError, match='source or input changed'):
        reader.verify_bindings()


def test_kernel_view_runs_original_binding_checks_without_modifying_saved_declaration(tmp_path, monkeypatch):
    from tests.test_v7_entry_scheduler import proof_fixture
    from nn_meta.v7 import provenance
    base = proof_fixture(tmp_path)
    proof = object.__new__(recovery.KernelCatalogProof)
    proof.__dict__.update(base.__dict__)
    old, new = runtimes()
    monkeypatch.setattr(recovery, 'runtime_manifest', lambda: new)
    monkeypatch.setattr(provenance, 'runtime_manifest', lambda: new)
    directory = proof.root / 'fixture/5'
    hashes = {}
    for kind in ('features', 'proposals'):
        p = directory / kind / 'summary/complete.json'
        p.parent.mkdir(parents=True); p.write_text(kind)
        hashes[kind] = sha(p)
    proof.receipts['fixture', 5] = dict(feature_receipt_sha256=hashes['features'],
                                       proposal_receipt_sha256=hashes['proposals'])
    source = tmp_path / 'source'
    source.write_text('original')
    declaration = dict(security_id='fixture', minutes=5, runtime=old,
                       sources={str(source): sha(source)}, inputs={})
    before = copy.deepcopy(declaration)
    assert proof.current_bindings(directory / 'features', declaration)['sources'] == declaration['sources']
    assert declaration == before
    source.write_text('different')
    with pytest.raises(ValueError, match='Unproved'):
        proof.current_bindings(directory / 'features', declaration)


def test_kernel_proof_requires_all_cases_and_unchanged_evidence(tmp_path, monkeypatch):
    _, current = runtimes()
    monkeypatch.setattr(recovery, 'runtime_manifest', lambda: current)
    completion = tmp_path / 'completion'; completion.mkdir()
    (completion / 'complete.json').write_text('frozen')
    evidence = tmp_path / 'evidence'; evidence.write_text('parity')
    proof = tmp_path / 'proof'; proof.mkdir()
    report = dict(schema='v7-kernel-demand-equivalence-v1', passed=True,
        recovery_source_sha256=sha(recovery.__file__),
        original_scheduler_sha256=sha(recovery.original.__file__),
        completion_sha256=sha(completion / 'complete.json'), current_runtime=current,
        old_platform=recovery.OLD_PLATFORM, new_platform=recovery.NEW_PLATFORM,
        cases=[dict(security_id=sid, sqlite_byte_equal=True, report_equal=True, exports_byte_equal=True)
               for sid in recovery.CASES], inputs={str(evidence): sha(evidence)})
    def seal():
        (proof / 'complete.json').unlink(missing_ok=True)
        (proof / 'report.json').write_text(json.dumps(report))
        receipt(proof, dict(identity=identity(report)))
    seal()
    recovery.verify_kernel_proof(proof, completion)
    evidence.write_text('changed')
    with pytest.raises(ValueError, match='evidence changed'):
        recovery.verify_kernel_proof(proof, completion)
    evidence.write_text('parity')
    report['cases'][0]['sqlite_byte_equal'] = False
    seal()
    with pytest.raises(ValueError, match='parity failed'):
        recovery.verify_kernel_proof(proof, completion)
    report['cases'].pop(0)
    seal()
    with pytest.raises(ValueError, match='Foreign or stale'):
        recovery.verify_kernel_proof(proof, completion)
