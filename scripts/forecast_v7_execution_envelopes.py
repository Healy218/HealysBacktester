#!/usr/bin/env python3
"""Sensitivity of first-leg envelopes to measured pre-entry quote-byte rates.

This is a transfer-rate scenario, not a realized-path forecast or capacity gate.
No trade bytes are added to held-option demand. New roll/physical/assembly costs
remain unpriced until their actual paths and consumer inputs are known.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('envelopes','sample','forecast','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    for key in vars(args):setattr(args,key,getattr(args,key).resolve())
    if not args.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Separate validation output required')
    inputs={str(Path(__file__).resolve()):sha(__file__)}
    def load(path):
        head=verify(path);inputs[str(path/'complete.json')]=sha(path/'complete.json')
        inputs.update({str(path/n):h for n,h in head['files'].items()})
        return json.loads((path/'report.json').read_text())
    envelopes,sample,forecast=map(load,(args.envelopes,args.sample,args.forecast))
    strata=defaultdict(list)
    for row in sample['samples']:
        capture=row['captures']['quotes']
        value=forecast['measurements'][capture['capture_id']]['logical_bytes']
        strata[row['stratum']].append(value)
    rates=defaultdict(lambda:dict(quote_bytes=0.,population_ns=0))
    for key,values in strata.items():
        group='-'.join(key.split('-')[:2])
        rates[group]['quote_bytes']+=sample['population'][key]*sum(values)/len(values)
        rates[group]['population_ns']+=sample['seconds_ns'][key]
    added=defaultdict(int)
    for sid,digest in envelopes['checkpoints'].items():
        checkpoint=args.envelopes.with_suffix('.checkpoints')/sid
        if sha(checkpoint/'complete.json')!=digest:raise ValueError('Envelope checkpoint changed')
        report=load(checkpoint)
        q=sample['security_quartiles'][sid]
        for year,ns in report['additional_quote_ns_by_year'].items():added[f'{year}-q{q}']+=ns
    cells=[]
    for group,ns in sorted(added.items()):
        rate=rates[group];bps=rate['quote_bytes']/(rate['population_ns']/1e9)
        cells.append(dict(group=group,additional_quote_seconds=ns/1e9,
            pre_entry_quote_bytes_per_second=bps,transferred_additional_bytes=ns/1e9*bps))
    value=sum(c['transferred_additional_bytes'] for c in cells)
    if sum(added.values())!=envelopes['additional_quote_ns']:raise ValueError('Execution time census drift')
    report=dict(schema='v7-first-leg-volume-sensitivity-v1',
        quote_hours=envelopes['envelope_quote_ns']/3.6e12,additional_quote_hours=sum(added.values())/3.6e12,
        transferred_additional_quote_bytes=round(value),cells=cells,
        scenarios=[dict(held_to_entry_byte_rate_ratio=r,additional_quote_bytes=round(value*r)) for r in (.25,.5,1.,2.)],
        caveat='Finite first-leg upper envelope, not realized path demand. Rates transfer measured entry quote density/compression by year and security-demand quartile; held quotes can have different density. Scenarios are not confidence bounds.',
        excludes=['new roll contracts','physical stock data','additional reference metadata','assembly and training','recovery and new index overhead'],
        authorizes_bulk=False,full_execution_coverage=False,research_ready=False)
    binding=dict(inputs=inputs)
    if any(sha(f)!=h for f,h in inputs.items()):raise ValueError('Volume sensitivity inputs changed')
    if args.output.exists():verify(args.output,expected_identity=identity(binding))
    else:
        with transaction(args.output) as temp:
            for name,doc in [('binding.json',binding),('report.json',report)]:
                (temp/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='cells'},indent=2))


if __name__=='__main__':main()
