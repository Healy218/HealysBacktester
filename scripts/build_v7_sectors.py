"""Freeze dated coarse research sectors for every active eligible security session."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.sectors import POLICY, classify, assign_sessions
    from nn_meta.v7.storage import sha, verify, identity, transaction, receipt
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('coverage', 'calendar', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--references', type=Path, action='append', required=True)
    args = parser.parse_args()
    verify(args.coverage)
    inputs = {str(p): sha(p) for p in (args.coverage/'complete.json', args.calendar,
              Path(__file__), ROOT/'nn_meta/v7/sectors.py')}
    sessions = pd.read_parquet(args.coverage/'sessions.parquet')
    symbols = set(sessions.membership_ticker) | set(sessions.stock_ticker)
    ids = set(sessions.security_id)
    observations, skipped, reconciled = {}, {}, []
    for root in args.references:
        for symbol in sorted(symbols):
            for path in sorted((root/symbol).glob('*/complete.json')):
                if path.parent.name == 'events':
                    continue
                doc = verify(path.parent)
                day = path.parent.name
                if doc.get('query') != {'path': f'/v3/reference/tickers/{symbol}', 'params': {'date': day}}:
                    raise ValueError('Reference request differs from dated security query')
                inputs[str(path)] = sha(path)
                if doc['http_status'] == 404:
                    skipped['not_found'] = skipped.get('not_found', 0)+1
                    continue
                if doc['http_status'] != 200:
                    raise ValueError('Unexpected reference capture status')
                record = json.loads((path.parent/'response.json').read_text())['results']
                if record.get('ticker') != symbol:
                    raise ValueError('Reference changed requested symbol')
                security = record.get('composite_figi')
                if security not in ids:
                    skipped['identity_absent_or_outside_scope'] = skipped.get('identity_absent_or_outside_scope', 0)+1
                    continue
                sector, reason = classify(record)
                row = dict(security_id=security, reference_date=day, sector=sector, reason=reason,
                           source_receipt=str(path), source_sha256=sha(path))
                prior = observations.get((security, day))
                if prior and prior['sector'] is not None and sector is not None and prior['sector'] != sector:
                    raise ValueError(f'Conflicting same-identity/date sector references: {security}/{day}')
                if prior and (prior['sector'] is None) != (sector is None):
                    reconciled.append(dict(security_id=security, date=day,
                        sources=[prior['source_receipt'], str(path)],
                        rule='same identity/date; retain populated classification when alias metadata is missing'))
                if prior is None or (prior['sector'] is None and sector is not None):
                    observations[security, day] = row
    obs = pd.DataFrame(list(observations.values()))
    mapping = assign_sessions(sessions, obs, SessionCalendar(json.loads(args.calendar.read_text())))
    counts = mapping.groupby(['sector', 'reason'], dropna=False).size().reset_index(name='sessions')
    report = dict(eligible_sessions=len(sessions), mapped_records=len(mapping),
        security_ids=sorted(ids), symbols=sorted(set(sessions.membership_ticker)),
        known_sector_sessions=int(mapping.sector.notna().sum()), unknown_sector_sessions=int(mapping.sector.isna().sum()),
        missing_reference_sessions=int(mapping.reason.eq('no_prior_identity_reference').sum()),
        first_observations=mapping.sort_values('date').groupby('security_id', sort=True).head(1).to_dict('records'),
        skipped_reference_captures=skipped, reconciled_alias_metadata=reconciled,
        policy_sha256=identity(POLICY), sources=inputs,
        research_ready=False, limits='Frozen coarse taxonomy includes explicit unknowns; feature/row integration must be validated separately')
    with transaction(args.output) as temp:
        obs.to_parquet(temp/'observations.parquet', index=False)
        mapping.to_parquet(temp/'sessions.parquet', index=False)
        counts.to_csv(temp/'coverage.csv', index=False)
        (temp/'policy.json').write_text(json.dumps(POLICY, indent=2)+'\n')
        (temp/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        if any(sha(p) != digest for p, digest in inputs.items()):
            raise ValueError('Sector source changed during build')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps({k: report[k] for k in ('eligible_sessions', 'mapped_records', 'known_sector_sessions',
                                          'unknown_sector_sessions', 'missing_reference_sessions')}))


if __name__ == '__main__': main()
