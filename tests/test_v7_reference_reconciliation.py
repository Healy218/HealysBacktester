import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from nn_meta.v7.packed_references import query, write_pack
from nn_meta.v7.storage import identity, receipt, sha
from scripts import audit_v7_reference_campaign as auditor

CONTRACT = 'AAPL260918C00200000'
DAY = '2026-09-14'


def prepare(tmp_path, monkeypatch, *, extra_demand=False, duplicate=False):
    monkeypatch.setattr(auditor, 'ROOT', tmp_path)
    code = tmp_path / 'nn_meta/v7/packed_references.py'
    code.parent.mkdir(parents=True)
    code.write_text('test fixture source')
    from nn_meta.v7 import contract_blackouts
    monkeypatch.setattr(contract_blackouts, 'BlackoutPolicy',
                        lambda _: SimpleNamespace(inputs={}, at=lambda c, d: None))
    plan = tmp_path / 'plan'
    parent = tmp_path / 'plan.checkpoints/sid'
    parent.mkdir(parents=True)
    with sqlite3.connect(parent / 'references.sqlite3') as db:
        db.execute('CREATE TABLE requests(contract,date)')
        db.execute('INSERT INTO requests VALUES(?,?)', (CONTRACT, DAY))
        if extra_demand:
            db.execute('INSERT INTO requests VALUES(?,?)', (CONTRACT, '2026-09-15'))
    receipt(parent, {'identity': 'demand'})
    digest = sha(parent / 'complete.json')
    plan.mkdir()
    (plan / 'report.json').write_text(json.dumps(dict(
        contract_dates=1 + int(extra_demand), checkpoints={'sid': digest})))
    receipt(plan, {'identity': 'plan'})
    campaign = tmp_path / 'campaign'
    declaration = campaign / 'declaration'
    declaration.mkdir(parents=True)
    packs = tmp_path / 'packs'
    doc = dict(plan=str(plan), plan_sha256=sha(plan / 'complete.json'),
               sources={}, output=str(packs))
    (declaration / 'declaration.json').write_text(json.dumps(doc))
    receipt(declaration, {'identity': identity(doc)})
    binding = dict(requests=1, campaign_identity=identity(doc), scope=dict(
        security_id='sid', demand_receipt_sha256=digest, pairs=[[CONTRACT, DAY]]))
    record = (CONTRACT, DAY, 404, b'{"status":"NOT_FOUND"}',
              dict(query=query(CONTRACT, DAY)))
    write_pack(packs / 'sid/one', [record], binding)
    if duplicate:
        write_pack(packs / 'sid/two', [record], binding)
    output = tmp_path / 'nn_meta/validation/audit'
    monkeypatch.setattr(sys, 'argv', ['audit', '--campaign', str(campaign),
        '--blackouts', str(tmp_path / 'policy'), '--output', str(output)])
    return output


def test_captured_missing_reference_does_not_mean_admitted(tmp_path, monkeypatch):
    output = prepare(tmp_path, monkeypatch)
    auditor.main()
    report = json.loads((output / 'report.json').read_text())
    assert report['full_planned_reference_capture'] is True
    assert report['admitted_under_existing_exclusions'] is False
    assert report['counts'] == {'unavailable_404': 1}


def test_missing_demand_prevents_complete_audit(tmp_path, monkeypatch):
    output = prepare(tmp_path, monkeypatch, extra_demand=True)
    with pytest.raises(ValueError, match='still incomplete'):
        auditor.main()
    assert not output.exists()


def test_duplicate_pairs_cannot_inflate_capture_coverage(tmp_path, monkeypatch):
    output = prepare(tmp_path, monkeypatch, duplicate=True)
    with pytest.raises(ValueError, match='Duplicate'):
        auditor.main()
    assert not output.exists()
