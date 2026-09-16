"""Dated, identity-bound research sectors from captured company references.

These are coarse research groups, not GICS or the legacy hand-picked V6 map.
Unavailable and unclassifiable references remain explicit unknowns.
"""
import re
import numpy as np
import pandas as pd

SECTORS = ('idx_etf', 'sec_etf', 'tech', 'semis', 'fin', 'crypto', 'defensive', 'cyclical', 'spec')
POLICY = {
    'schema': 'v7-dated-sector-policy-v1',
    'categories': list(SECTORS),
    'source': 'historical dated company reference, composite FIGI bound',
    'availability': 'strictly after reference date, at next captured session open',
    'carry': 'latest prior reference classification, including unknown, for the same security; never backfill from a future reference',
    'unknown': 'all nine sector indicators zero; reason and source date retained',
    'funds': 'five broad index names; every other ETF/ETV/ETN/FUND is sec_etf',
    'crypto': 'explicit crypto mining/exchange/treasury business phrase in dated description',
    'semis': 'SIC 3674',
    'tech': 'SIC 3570-3579, 3660-3669, 7370-7379',
    'spec': 'SIC 6770 blank checks only; no retrospective meme-stock labels',
    'fin': 'SIC 6000-6799 except blank checks',
    'defensive': 'SIC 2000-2199, 2830-2849, 4810-4899, 4900-4999, 5140-5149, 5400-5499, 8000-8099',
    'cyclical': 'remaining SIC 0100-5999, 7000-8999',
    'references': [
        'https://www.massive.com/blog/announcing-our-new-point-in-time-company-details-api',
        'https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list'],
    'historical_vendor_reconstruction': True,
    'original_publication_vintage_verified': False,
}
INDEX_NAMES = (
    r'\b(?:SPDR|Vanguard) S&P 500 (?:ETF|Trust)',
    r'\bInvesco QQQ Trust\b',
    r'\biShares Russell 2000 ETF\b',
    r'\bSPDR Dow Jones Industrial Average ETF Trust\b',
)
CRYPTO = re.compile(r'\b(?:bitcoin|cryptocurrency|crypto currency|digital asset) '
                    r'(?:mining|miner|exchange|treasury)\b', re.I)


def classify(record):
    """Deterministic frozen taxonomy; no symbol-specific contemporary lookup."""
    kind = record.get('type')
    if kind in ('ETF', 'ETV', 'ETN', 'FUND'):
        name = record.get('name') or ''
        if not name:
            return None, 'fund_name_missing'
        # Exact benchmark phrases avoid treating a leveraged/sector fund as broad index.
        broad = any(re.search(pattern, name, re.I) for pattern in INDEX_NAMES)
        return ('idx_etf', 'dated_broad_index_name') if broad else ('sec_etf', 'dated_other_fund')
    if kind not in ('CS', 'ADRC'):
        return None, 'unsupported_security_type'
    if CRYPTO.search(record.get('description') or ''):
        return 'crypto', 'dated_crypto_business_description'
    code = str(record.get('sic_code') or '')
    if not re.fullmatch(r'\d{3,4}', code):
        return None, 'sic_missing_or_invalid'
    code = int(code)
    if code == 3674:
        return 'semis', 'dated_sic'
    if any(lo <= code <= hi for lo, hi in ((3570,3579), (3660,3669), (7370,7379))):
        return 'tech', 'dated_sic'
    if code == 6770:
        return 'spec', 'dated_sic'
    if 6000 <= code <= 6799:
        return 'fin', 'dated_sic'
    if any(lo <= code <= hi for lo, hi in ((2000,2199), (2830,2849), (4810,4999),
                                          (5140,5149), (5400,5499), (8000,8099))):
        return 'defensive', 'dated_sic'
    if 100 <= code <= 5999 or 7000 <= code <= 8999:
        return 'cyclical', 'dated_sic'
    return None, 'sic_unclassified'


def assign_sessions(sessions, observations, calendar):
    """Keep one explicit sector/unknown record for every eligible security session."""
    required = {'date', 'security_id', 'membership_ticker'}
    if not required.issubset(sessions) or sessions.duplicated(['date', 'security_id']).any():
        raise ValueError('Unique dated security sessions required')
    columns = ['security_id', 'reference_date', 'sector', 'reason', 'source_receipt', 'source_sha256']
    if not set(columns).issubset(observations) or observations[columns[:2]].isna().any().any():
        raise ValueError('Explicit dated sector observations required')
    if observations.duplicated(columns[:2]).any():
        raise ValueError('Duplicate security/date reference requires reconciliation')
    if not observations.sector.dropna().isin(SECTORS).all():
        raise ValueError('Unrecognized sector taxonomy')
    output = []
    for security, group in sessions.groupby('security_id', sort=True):
        records = observations[observations.security_id.eq(security)].sort_values('reference_date')
        dates = records.reference_date.to_numpy(dtype=str)
        for row in group.sort_values('date').itertuples():
            bounds = calendar.bounds(row.date)
            if bounds is None:
                raise ValueError('Eligible session is absent from calendar')
            pos = int(np.searchsorted(dates, row.date, side='left')) - 1
            source = records.iloc[pos] if pos >= 0 else None
            output.append(dict(date=row.date, security_id=security, membership_ticker=row.membership_ticker,
                available_ns=bounds[0].tz_localize('UTC').value,
                sector=source.sector if source is not None else None,
                reason=source.reason if source is not None else 'no_prior_identity_reference',
                reference_date=source.reference_date if source is not None else None,
                source_receipt=source.source_receipt if source is not None else None,
                source_sha256=source.source_sha256 if source is not None else None))
    return pd.DataFrame(output)


class DatedSectors:
    """Small security-specific mapping; lookup cannot cross a missing session."""
    def __init__(self, frame, *, security_id):
        if (frame.empty or not frame.security_id.eq(security_id).all()
                or not security_id or frame.date.duplicated().any()
                or not frame.sector.dropna().isin(SECTORS).all()
                or not pd.api.types.is_integer_dtype(frame.available_ns)):
            raise ValueError('Unique security-bound sector history required')
        self.security_id = security_id
        self.records = {}
        for row in frame.to_dict('records'):
            stamp = pd.Timestamp(row['available_ns'], unit='ns', tz='UTC')
            if (stamp.tz_convert('America/New_York').date().isoformat() != row['date']
                    or (pd.notna(row['reference_date']) and row['reference_date'] >= row['date'])):
                raise ValueError('Sector history uses future reference data')
            if pd.isna(row['sector']):
                row['sector'] = None
            self.records[row['date']] = row

    def at(self, decision):
        decision = pd.Timestamp(decision)
        if pd.isna(decision) or decision.tzinfo is None:
            raise ValueError('Explicit aware sector decision clock required')
        day = decision.tz_convert('America/New_York').date().isoformat()
        row = self.records.get(day)
        if row is None or row['available_ns'] > decision.value:
            raise ValueError('No sector record available for this security/session')
        return dict(row)


class SectorStore:
    """Verify a frozen store once, then read bounded per-security projections."""
    def __init__(self, path):
        import json
        from pathlib import Path
        from nn_meta.v7.storage import sha, verify, identity
        self.path = Path(path)
        verify(self.path)
        self.report = json.loads((self.path/'report.json').read_text())
        policy = json.loads((self.path/'policy.json').read_text())
        if policy != POLICY or self.report['policy_sha256'] != identity(POLICY):
            raise ValueError('Dated sector policy changed')
        for source, digest in self.report['sources'].items():
            if sha(source) != digest:
                raise ValueError('Dated sector source changed')
        if self.report['eligible_sessions'] != self.report['mapped_records']:
            raise ValueError('Sector mapping does not cover all eligible sessions')

    def for_security(self, security_id):
        if security_id not in self.report['security_ids']:
            raise ValueError('Security absent from frozen sector universe')
        frame = pd.read_parquet(self.path/'sessions.parquet', filters=[('security_id', '=', security_id)])
        return DatedSectors(frame, security_id=security_id)
