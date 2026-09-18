"""Use captured trade-to-settlement mappings without inferring bank holidays."""
from datetime import date

import pandas as pd


class ReportedSettlementSchedule:
    """Alpaca's reported settlement date, with the existing conservative release.

    These are scheduled dates, not proof of a particular broker cash posting.
    A trading calendar alone is insufficient: every trade date needs its own
    captured settlement_date. No business-day union or holiday rule is inferred.
    """
    def __init__(self, document, trading_calendar):
        self.document, self.trading = document, trading_calendar
        if (document.get('schema') != 'v7-reported-stock-settlement-v1'
                or document.get('provider') != 'alpaca_calendar'
                or not document.get('source_identity')
                or document.get('broker_posting_verified') is not False):
            raise ValueError('Explicit captured stock settlement schedule required')
        start, end = document['coverage_start'], document['coverage_end']
        if (date.fromisoformat(start).isoformat() != start
                or date.fromisoformat(end).isoformat() != end or start > end
                or start < self.trading.start or end > self.trading.end):
            raise ValueError('Settlement coverage must lie inside captured trading coverage')
        self.reported = {}
        previous = None
        for row in document['trade_settlements']:
            trade, settled = row['trade_date'], row['settlement_date']
            if (date.fromisoformat(trade).isoformat() != trade
                    or date.fromisoformat(settled).isoformat() != settled
                    or trade in self.reported or not start <= trade <= end or settled <= trade
                    or (previous is not None and (trade <= previous[0] or settled < previous[1]))):
                raise ValueError('Ordered unique trade dates and later reported settlements required')
            self.reported[trade] = settled
            previous = trade, settled
        expected = {d for d in self.trading.sessions if start <= d <= end}
        if not expected or set(self.reported) != expected:
            raise ValueError('Every covered trading session needs its original settlement date')

    def settlement(self, event_ns):
        if type(event_ns) is not int or event_ns < 0:
            raise ValueError('Exact nonnegative settlement event nanoseconds required')
        trade = pd.Timestamp(event_ns, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        if trade not in self.reported:
            raise ValueError('Trade has no captured settlement mapping')
        settled = self.reported[trade]
        following = next((d for d in sorted(self.trading.sessions) if d > settled), None)
        if settled > self.document['coverage_end'] or following is None:
            raise ValueError('Captured settlement or cash-availability horizon exhausted')
        return settled, int(self.trading.bounds(following)[0].tz_localize('UTC').value)


def normalize_reported_settlements(raw_rows, calendar_document, *, start, end, source_identity):
    """Preserve the explicit original field; reject normalization disagreements."""
    raw = {r['date']: r for r in raw_rows}
    normalized = {r['date']: r for r in calendar_document['sessions']}
    if (len(raw) != len(raw_rows) or len(normalized) != len(calendar_document['sessions'])
            or raw != normalized or not source_identity):
        raise ValueError('Normalized calendar differs from the original complete response')
    rows = []
    for day, row in sorted(raw.items()):
        if start <= day <= end:
            if not isinstance(row.get('settlement_date'), str):
                raise ValueError('Original settlement_date is required; never substitute trading days')
            rows.append(dict(trade_date=day, settlement_date=row['settlement_date']))
    return dict(schema='v7-reported-stock-settlement-v1', provider='alpaca_calendar',
        coverage_start=start, coverage_end=end, trade_settlements=rows,
        source_identity=source_identity, broker_posting_verified=False,
        availability_basis='first_captured_regular_open_strictly_after_reported_settlement',
        historical_publication_verified=False, research_ready=False)
