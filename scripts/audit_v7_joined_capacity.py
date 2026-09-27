#!/usr/bin/env python3
"""Reconcile the measured packed-entry forecast with references and both caps.

Reports local and archived historical storage separately. This is not the
missing full held-path forecast and cannot authorize bulk acquisition/training.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('forecast','index-proof','reference-plan','reference-requests','references','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from nn_meta.v7.contracts import ContractReferences
    from scripts.download_v7_data import save,tree_bytes
    for name in ('forecast','index_proof','reference_plan','reference_requests','references','output'):
        setattr(args,name,getattr(args,name).resolve())
    if not args.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use separate validation evidence')
    for root in (args.forecast,args.index_proof,args.reference_plan):verify(root)
    inputs={str(root/'complete.json'):sha(root/'complete.json') for root in (args.forecast,args.index_proof,args.reference_plan)}
    inputs[str(args.reference_requests)]=sha(args.reference_requests)
    forecast=json.loads((args.forecast/'report.json').read_text())
    index=json.loads((args.index_proof/'report.json').read_text())
    refplan=json.loads((args.reference_plan/'report.json').read_text())
    requests=json.loads(args.reference_requests.read_text())
    refs=ContractReferences(args.references)
    sizes=[];statuses=Counter();failures=[]
    for item in requests:
        root=args.references/item['contract']/item['date']
        doc=verify(root);inputs[str(root/'complete.json')]=sha(root/'complete.json')
        sizes.append(tree_bytes(root))
        try:refs.standard(item['contract'],item['date']);statuses['verified_standard']+=1
        except ValueError as exc:
            statuses['unavailable_or_nonstandard']+=1
            failures.append(dict(item,http_status=doc['http_status'],reason=str(exc)))
    policy_path=ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json'
    policy=json.loads(policy_path.read_text());inputs[str(policy_path)]=sha(policy_path)
    quota=json.loads((ROOT/'nn_meta/data_v7/quota.json').read_text())
    if quota['reservations']:raise ValueError('Wait for acquisition writers before final capacity snapshot')
    local=int(subprocess.check_output(['du','-sb',str(ROOT)],text=True).split()[0])
    locator=ROOT/'nn_meta/expanded_inputs/v6-local-20260906.ARCHIVED.json'
    inputs[str(locator)]=sha(locator)
    archive=Path(json.loads(locator.read_text())['external_folder'])
    if not archive.is_dir():raise ValueError('Historical external archive must be present for inventory')
    external=int(subprocess.check_output(['du','-sb',str(archive)],text=True).split()[0])
    routing=index['estimated_population_index_bytes']
    reference_allowance=max(sizes)*refplan['contract_dates']
    entry=forecast['estimated_capture_bytes']+routing
    stress=forecast['mean_plus_three_se_bytes']+routing
    remaining=quota['limit_bytes']-quota['used_bytes']
    free=shutil.disk_usage(ROOT).free
    report=dict(schema='v7-joined-capture-capacity-review-v1',observed_at=datetime.now(timezone.utc).isoformat(),
        entry_estimate_with_routing_bytes=entry,entry_three_se_with_routing_bytes=stress,
        reference_sample_statuses=dict(statuses),reference_failures=failures,
        reference_sample_bytes=sum(sizes),max_sample_reference_bytes=max(sizes),
        entry_reference_planning_allowance_bytes=reference_allowance,
        reference_allowance_note='Maximum measured sample directory bytes times exact contract/date census; not a proved bound.',
        acquisition_remaining_bytes=remaining,quota=quota,
        entry_and_reference_stress_bytes=stress+reference_allowance,
        entry_and_reference_stress_fits_acquisition=stress+reference_allowance<=remaining,
        disk_free_bytes=free,disk_reserve_bytes=policy['disk_reserve_bytes'],
        local_project_bytes=local,external_historical_archive_bytes=external,
        local_project_entry_and_reference_stress_bytes=local+stress+reference_allowance,
        all_locations_entry_and_reference_stress_bytes=local+external+stress+reference_allowance,
        project_limit_bytes=policy['project_limit_bytes'],
        measurement_note='Non-atomic apparent bytes. Reflink copies count logically; gross new forecast does not subtract retained samples.',
        missing_budget=['Additional purchase/mark/exit/roll/physical-delivery captures','full assembly and training outputs','in-flight/recovery headroom'],
        bulk_launch_allowed=False,full_execution_coverage=False,research_ready=False)
    binding=dict(inputs=inputs,producer_sha256=sha(__file__))
    if args.output.exists():verify(args.output,expected_identity=identity(binding));return
    with transaction(args.output) as temp:
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('reference_failures','quota')},indent=2))


if __name__=='__main__':main()
