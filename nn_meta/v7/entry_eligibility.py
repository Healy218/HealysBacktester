"""Point-in-time entry admission; never truncate an already-held exit horizon."""
from bisect import bisect_right

import pandas as pd

from nn_meta.v7.storage import identity


class EntryEligibility:
    def __init__(self, sessions, calendar, *, security_id, sources):
        required = {'date', 'security_id', 'stock_ticker', 'membership_available_at'}
        if (not required.issubset(sessions) or not security_id or not sources
                or not sessions.security_id.eq(security_id).all() or sessions.date.duplicated().any()):
            raise ValueError('Exact dated entry membership and security identity required')
        hours = {s['date']: s for s in calendar['sessions']}
        self.rows = []
        for row in sessions.sort_values('date').itertuples():
            day = row.date
            if day not in hours or not isinstance(row.stock_ticker, str) or not row.stock_ticker:
                raise ValueError('Entry membership lacks a session or dated stock ticker')
            def clock(value):
                t = pd.Timestamp(value)
                if pd.isna(t):raise ValueError('Missing membership availability')
                return (t.tz_localize('America/New_York') if t.tzinfo is None else t).tz_convert('UTC').value
            opened = clock(day+' '+hours[day]['open'])
            closed = clock(day+' '+hours[day]['close'])
            available = clock(row.membership_available_at)
            if opened >= closed or available > closed:
                raise ValueError('Membership is unavailable during its declared session')
            self.rows.append(dict(date=day, opening_ns=opened, closing_ns=closed,
                available_ns=available, stock_ticker=row.stock_ticker))
        self.opens = [r['opening_ns'] for r in self.rows]
        self.binding = dict(schema='v7-pit-entry-eligibility-v1',security_id=security_id,
            sessions=len(self.rows),sessions_identity=identity(self.rows),sources=dict(sources),
            rule='Known membership at entry decision only; held exit horizons remain unfiltered')

    def admits(self, decision_ns, symbol):
        if type(decision_ns) is not int:
            raise ValueError('Integer decision clock required')
        position = bisect_right(self.opens, decision_ns)-1
        if position < 0:return False
        row = self.rows[position]
        if decision_ns > row['closing_ns'] or decision_ns < row['available_ns']:return False
        if symbol != row['stock_ticker']:
            raise ValueError('Entry ticker differs from the dated membership source')
        return True
