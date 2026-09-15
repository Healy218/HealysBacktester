"""Request daily identity evidence in months with a changed candidate ticker identity."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.universe import security_masters
    from nn_meta.v7.storage import transaction, receipt, sha, identity
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('masters', 'symbols', 'calendar', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    args = ap.parse_args()
    masters, sources = security_masters(args.masters)
    symbols = set(args.symbols.read_text().split())
    calendar = json.loads(args.calendar.read_text())
    known, changes, requests = {}, [], set()
    for day, records in masters.items():
        for root, record in records.items():
            if root not in symbols:
                continue
            previous = known.get(root)
            if previous and previous['composite_figi'] != record['composite_figi']:
                changes.append({'root': root, 'month': day[:7],
                                'previous': previous, 'current': record})
                for session in calendar['sessions']:
                    if session['date'][:7] == day[:7]:
                        requests.add((record['ticker'], session['date']))
            known[root] = record
    rows = [{'symbol': s, 'date': d} for s, d in sorted(requests)]
    with transaction(args.output) as temp:
        (temp / 'requests.json').write_text(json.dumps(rows, indent=2) + '\n')
        (temp / 'changes.json').write_text(json.dumps(changes, indent=2) + '\n')
        receipt(temp, {'identity': identity({'masters': sources, 'symbols': sha(args.symbols),
                                            'calendar': sha(args.calendar), 'code': sha(__file__)}),
                       'requests': len(rows), 'changed_roots': len({r['root'] for r in changes}),
                       'research_ready': False})
    print(json.dumps({'requests': len(rows), 'transitions': len(changes)}))


if __name__ == '__main__':
    main()
