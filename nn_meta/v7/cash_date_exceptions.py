"""Finite exchange-documented exception to ordinary ex/record ordering."""

NASDAQ_NOTICE_SHA = '009001c5ed44da54d552665c325643d29c673b43295b93a9f94f217951e5c2f8'


def closed_record_date_allowed(symbol, ex, record, exception, calendar):
    """Nasdaq ETA2025-1 defers Jan 9 ex-dates to Jan 10, retaining records."""
    if (symbol not in ('INTU', 'ORCL', 'MA') or ex != '2025-01-10'
            or record != '2025-01-09' or calendar is None
            or exception != dict(schema='v7-nasdaq-eta2025-1-cash-dates-v1',
                                 notice_payload_sha256=NASDAQ_NOTICE_SHA)):
        return False
    return (calendar.bounds(record) is None and calendar.bounds(ex) is not None
            and calendar.bounds('2025-01-08') is not None
            and not any(record <= d < ex for d in calendar.sessions))
