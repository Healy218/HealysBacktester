"""Derive bounded selected-contract tick requests from actual V7 proposals."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.proposal_store import StoredProposals
    from nn_meta.v7.entry_demand import build_entry_demand,EntryDemand
    from nn_meta.v7.storage import sha
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active',type=Path,default=ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json')
    parser.add_argument('--proposal-root',type=Path,required=True,
                        help='One security directory containing 1/5/15/30 stores')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--export',type=Path,required=True)
    args=parser.parse_args()
    if any(not p.resolve().is_relative_to(ROOT/'nn_meta') for p in (args.output,args.export)):
        raise ValueError('Repository artifact disk required')
    active=json.loads(args.active.read_text())
    chain=ROOT/active['chain']
    if sha(chain/'complete.json')!=active['chain_receipt_sha256']:
        raise ValueError('Observed chain differs from active scope')
    stores=[StoredProposals(args.proposal_root/str(m)/'proposals') for m in (1,5,15,30)]
    for store in stores:
        if not any(Path(p).resolve()==args.active.resolve() and h==sha(args.active)
                   for p,h in store.features.declaration['inputs'].items()):
            raise ValueError('Proposal build did not bind the active execution/data scope')
    report=build_entry_demand(args.output,stores,chain,reserve_bytes=100*1024**3)
    exported=EntryDemand(args.output).export_requests(args.export)
    print(json.dumps(dict(report=report,export_batches=len(exported['batches']))))


if __name__=='__main__':main()
