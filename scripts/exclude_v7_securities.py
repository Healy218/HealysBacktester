"""Derive restricted V7 membership without changing historical scores or ranks."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.v7.exclusions import exclude_securities
    from nn_meta.v7.storage import sha, verify, transaction, receipt, identity
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('universe', 'exclusions', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    verify(args.universe)
    original = pd.read_parquet(args.universe/'membership.parquet')
    declaration = json.loads(args.exclusions.read_text())
    kept, removed = exclude_securities(original, declaration)
    relevant = kept[kept.month >= '2022-02']
    provenance = json.loads((args.universe/'provenance.json').read_text())
    for name, digest in provenance['code'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Parent universe source changed')
    provenance['code'].update({str(p.relative_to(ROOT)):sha(p) for p in
                              (Path(__file__), ROOT/'nn_meta/v7/exclusions.py')})
    provenance['study_exclusions'] = dict(parent=str(args.universe),
        parent_receipt_sha256=sha(args.universe/'complete.json'),
        declaration=str(args.exclusions), declaration_sha256=sha(args.exclusions))
    report = json.loads((args.universe/'report.json').read_text())
    report.update(historical_symbols=relevant.ticker.nunique(), historical_securities=relevant.security_id.nunique(),
                  rows=len(relevant), removed_membership_rows=len(removed),
                  excluded_security_ids=sorted(removed.security_id.unique()),
                  exclusion_declaration_sha256=sha(args.exclusions),
                  study_scope='Conditioned on user-directed ex-post issuer exclusions; retained ranks/scores unchanged',
                  research_ready=False)
    with transaction(args.output) as temp:
        kept.to_parquet(temp/'membership.parquet', index=False)
        removed.to_parquet(temp/'excluded_membership.parquet', index=False)
        (temp/'symbols.txt').write_text('\n'.join(sorted(relevant.ticker.unique()))+'\n')
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        (temp/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
        verify(args.universe)
        if sha(args.exclusions) != provenance['study_exclusions']['declaration_sha256']:
            raise ValueError('Exclusion declaration changed')
        receipt(temp, dict(identity=identity(provenance), research_ready=False))
    print(json.dumps({k: report[k] for k in ('historical_symbols', 'historical_securities', 'rows',
                                          'removed_membership_rows', 'excluded_security_ids')}))


if __name__ == '__main__': main()
