"""Seal a measured resume allocation without changing frozen parents/producers."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--project-allocated-bytes', type=int, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = args.repo.resolve()
sys.path.insert(0, str(root))
from nn_meta.v7.storage import sha, verify, identity, receipt, transaction
from scripts.run_v7_entry_demand import CatalogProof, output_bytes

base = root / 'nn_meta/validation'
proof = CatalogProof(base / 'v7-2-completion-20260925')
stage = base / 'v7-3-scheduler-20260925'
original = base / 'v7-3-demand-storage-plan-20260925'
verify(original)
old = json.loads((original / 'report.json').read_text())
inputs = dict(proof.bindings)
inputs[str(original / 'complete.json')] = sha(original / 'complete.json')
inputs.update({str((root / p).resolve()): h for p, h in old['inputs'].items()})
active = root / 'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json'
scheduler = root / 'scripts/run_v7_entry_demand.py'
inputs[str(scheduler)] = sha(scheduler)
for (sid, minute), expected in proof.receipts.items():
    for kind, key in [('features', 'feature_receipt_sha256'), ('proposals', 'proposal_receipt_sha256')]:
        path = proof.root / sid / str(minute) / kind / 'summary/complete.json'
        assert sha(path) == expected[key], path
        inputs[str(path)] = expected[key]

completed = []
for sid in proof.security_ids:
    path = stage / 'checkpoints' / sid
    if not path.exists():
        continue
    binding = dict(security_id=sid, completion_sha256=sha(proof.completion / 'complete.json'),
                   active_sha256=sha(active), scheduler_sha256=sha(scheduler))
    verify(path, expected_identity=identity(binding))
    result = json.loads((path / 'result.json').read_text())
    assert result['security_id'] == sid
    inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
    inputs.update(result['receipts'])
    completed.append(sid)

census = base / 'v7-3-demand-census-20260925'
verify(census / 'summary')
summary = json.loads((census / 'summary/report.json').read_text())
bounds = {r['security_id']: r['maximum_requests'] for r in old['rows']}
remaining = sorted(set(proof.security_ids) - set(completed))
components = dict(decisions=0, selections=0, requests_and_exports=0, feature_links=0,
                  lineage_and_working_margin=8 * 1024**3)
for sid in remaining:
    path = census / 'securities' / sid
    assert sha(path / 'complete.json') == summary['security_receipts'][sid]
    verify(path)
    inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
    row = json.loads((path / 'report.json').read_text())
    components['decisions'] += row['feature_decisions'] * 96
    components['selections'] += row['targets'] * 256
    components['requests_and_exports'] += bounds[sid] * 768
    components['feature_links'] += row['maximum_links'] * 224

assert all(sha(p) == h for p, h in inputs.items())
used = output_bytes(stage)
remaining_forecast = sum(components.values())
cap = 140 * 1024**3
free = shutil.disk_usage(root).free
reserve = 100 * 1024**3
additional_allocation = cap - used
assert used + remaining_forecast <= cap < old['stage_output_limit_bytes']
assert free - additional_allocation >= reserve
stage_allocated = int(subprocess.check_output(
    ['du', '-sx', '--block-size=1', str(stage)], text=True).split()[0])
baseline = args.project_allocated_bytes - stage_allocated
assert baseline >= 0 and baseline + cap <= old['total_project_budget_bytes']
report = dict(schema='v7-demand-storage-plan-v1', checked_at=datetime.now(timezone.utc).isoformat(),
    securities=591, completed_checkpoints=len(completed), remaining_securities=remaining,
    existing_stage_bytes=used, remaining_forecast_components_bytes=components,
    remaining_stress_forecast_bytes=remaining_forecast,
    stress_forecast_bytes=used + remaining_forecast, stage_output_limit_bytes=cap,
    current_project_allocated_bytes=args.project_allocated_bytes,
    current_stage_allocated_bytes=stage_allocated,
    baseline_project_allocated_bytes=baseline,
    baseline_measurement='Current du -x --block-size=1 --max-depth=1 . minus du -sx --block-size=1 of existing demand stage.',
    total_project_budget_bytes=old['total_project_budget_bytes'],
    disk_free_bytes=free, required_free_reserve_bytes=reserve,
    free_if_full_allocation_used=free-additional_allocation,
    preserved_catalog_store_pairs=1773, frozen_payloads_rehashed=False,
    completed_checkpoint_ids=completed, inputs=inputs, research_ready=False, acquisition_bytes=0,
    assumptions=['Exact original per-security census and request bounds for all remaining securities.',
      'Same original row allowances and full 8 GiB working margin; no sparse-pilot extrapolation.',
      'Existing output includes partial evidence; budget includes retaining it plus rebuilding incomplete securities.',
      'Catalog summary receipt pairs match the deep audit; this recovery does not repeat all payload hashing.',
      'Existing scheduler verifies completed demand payloads and source bindings on reuse.',
      'Original forecast, frozen stores, gates and producers remain unchanged.'])
with transaction(args.output) as temp:
    (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (temp / 'planner.py').write_text(Path(__file__).read_text())
    receipt(temp, dict(identity=identity(report), research_ready=False))
print(json.dumps({k: v for k, v in report.items() if k not in ('inputs','completed_checkpoint_ids','remaining_securities')}, indent=2))
