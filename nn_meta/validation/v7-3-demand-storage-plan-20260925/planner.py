from nn_meta.v7.runtime import configure_threads
configure_threads(1)
from pathlib import Path
from collections import Counter
import json, shutil
import polars as pl
from nn_meta.v7.storage import sha,verify,identity,receipt,transaction
from scripts.run_v7_entry_demand import CatalogProof
proof=CatalogProof(Path('nn_meta/validation/v7-2-completion-20260925'))
census=Path('nn_meta/validation/v7-3-demand-census-20260925')
verify(census/'summary');summary=json.loads((census/'summary/report.json').read_text())
active=Path('docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json');a=json.loads(active.read_text());chain=Path(a['chain']);assert sha(chain/'complete.json')==a['chain_receipt_sha256'];verify(chain)
# Counting all expiries regardless of first_seen/right/strike deliberately gives
# an upper bound on how many distinct expiries the five targets can select.
groups=pl.read_parquet(chain/'contracts.parquet',columns=['root','expiry']).unique().sort(['root','expiry']).partition_by('root',as_dict=True)
maxima={}
for (root,),table in groups.items():
 dates=table['expiry'].to_list();left=maximum=0
 for i,day in enumerate(dates):
  while (day-dates[left]).days>8:left+=1
  maximum=max(maximum,i-left+1)
 maxima[root]=min(5,maximum)
rows=[];request_bound=0;distribution=Counter()
for sid in proof.security_ids:
 path=census/'securities'/sid;verify(path);r=json.loads((path/'report.json').read_text())
 declaration=proof.root/sid/'5/proposals/declaration';verify(declaration)
 d=json.loads((declaration/'declaration.json').read_text())
 symbols=set((d['symbols_by_date'] or {}).values()) or {d['symbol']}
 multiplicity=max((maxima.get(s.replace('.',''),0) for s in symbols),default=0)
 maximum=2*multiplicity*r['feature_decisions'];request_bound+=maximum;distribution[multiplicity]+=1
 rows.append(dict(security_id=sid,maximum_distinct_expiries=multiplicity,maximum_requests=maximum))
# Generous page/index/JSON row allowances; these are planning estimates, not a
# claim that SQLite has a strict maximum file size per row.
coefficients={'decisions':96,'selections':256,'requests_and_index':384,'export_request':384,'feature_links':224}
components={'decisions':summary['feature_decisions']*96,'selections':summary['targets']*256,
 'requests_and_index':request_bound*384,'export_requests':request_bound*384,
 'feature_links':summary['maximum_links']*224,'lineage_and_working_margin':8*1024**3}
report=dict(schema='v7-demand-storage-plan-v1',securities=591,proposals=summary['proposals'],
 feature_decisions=summary['feature_decisions'],selection_decisions=summary['selection_decisions'],
 target_selections=summary['targets'],maximum_feature_links=summary['maximum_links'],
 maximum_requests_using_observed_expiry_inventory=request_bound,expiry_multiplicity_securities=dict(distribution),
 row_allowances_bytes=coefficients,forecast_components_bytes=components,stress_forecast_bytes=sum(components.values()),
 baseline_project_allocated_bytes=421285347328,baseline_measurement='du -sx --block-size=1 . on this session',
 stage_output_limit_bytes=200*1024**3,total_project_budget_bytes=640_000_000_000,
 required_free_reserve_bytes=100*1024**3,disk_free_bytes=shutil.disk_usage('.').free,
 acquisition_bytes=0,research_ready=False,
 assumptions=['Full-scope exact decision census; no pilot-volume extrapolation.',
 'At most five distinct contracts per decision; for one expiry all targets use the same nearest eligible strike.',
 'Per-security request bound uses maximum dated-root expiry inventory over any nine-day future window. Ignoring right/first_seen/strike/freshness is conservative.',
 'The row allowances are a storage stress forecast, not guaranteed SQLite byte bounds. The stage cap and free-space guard stop work if reached.',
 '640 GB is the total-project budget for this demand stage. New option captures require a separate forecast against actual remaining disk.'],
 inputs={str(census/'summary/complete.json'):sha(census/'summary/complete.json'),str(chain/'complete.json'):sha(chain/'complete.json'),str(active):sha(active)},rows=rows)
print(json.dumps({k:v for k,v in report.items() if k not in ['rows','inputs']},indent=2))
out=Path('nn_meta/validation/v7-3-demand-storage-plan-20260925')
with transaction(out) as temp:
 (temp/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 (temp/'planner.py').write_text(Path(__file__).read_text())
 receipt(temp,dict(identity=identity(report)))
