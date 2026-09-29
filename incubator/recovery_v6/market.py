"""Retry transient tick transport failures without weakening capture validation."""
import time
import requests

from incubator.continual.market import ResearchMarket as OriginalMarket
from options.data.massive_ticks import MassiveTicks


class RetrySession:
    def __init__(self, session=None, *, sleep=time.sleep, clock=time.monotonic, deadline=float('inf')):
        self.session = session or requests.Session()
        self.sleep, self.clock, self.deadline = sleep, clock, deadline
        self.events = []

    def get(self, url, **kwargs):
        for attempt in range(5):
            remaining = self.deadline-self.clock()
            if remaining <= 0:
                raise TimeoutError('V6 tick capture deadline reached')
            kwargs['timeout'] = min(kwargs.get('timeout', 45), remaining)
            response = None
            try:
                response = self.session.get(url, **kwargs)
            except requests.RequestException:
                self.events.append(dict(attempt=attempt+1, failure='transport'))
                if attempt == 4:
                    raise requests.RequestException('V6 tick transport retry budget exhausted') from None
            else:
                if response.status_code not in {429, 500, 502, 503, 504}:
                    return response
                self.events.append(dict(attempt=attempt+1, http_status=response.status_code))
                if attempt == 4:
                    return response
                response.close()
            delay = min(2**attempt, 8)
            if self.clock()+delay >= self.deadline:
                raise TimeoutError('V6 tick retry would exceed build deadline')
            self.sleep(delay)


class RetryingTicks(MassiveTicks):
    def __init__(self, *, deadline=float('inf'), session=None, **kwargs):
        super().__init__(session=RetrySession(session, deadline=deadline), **kwargs)

    def capture(self, *args, **kwargs):
        self.session.events.clear()
        rows, manifest = super().capture(*args, **kwargs)
        manifest['transient_retries'] = list(self.session.events)
        return rows, manifest


class ResearchMarket(OriginalMarket):
    def __init__(self, root, *, deadline=float('inf'), **kwargs):
        super().__init__(root, tick_client=RetryingTicks(deadline=deadline), **kwargs)
