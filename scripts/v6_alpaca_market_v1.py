"""Alpaca OPRA option quotes for V6 paper; no Massive network dependency.

This adapter deliberately does not claim historical quote-window parity.
"""
from pathlib import Path
import hashlib
import json
import os

import numpy as np
import pandas as pd
import requests


def utcnow():
    return pd.Timestamp.now(tz='UTC')


class AlpacaOptionQuotes:
    def __init__(self, root, *, session=None, clock=utcnow):
        self.root = Path(root)
        self.session = session or requests.Session()
        if session is None:
            key, secret = os.environ.get('ALPACA_PAPER_API_KEY'), os.environ.get('ALPACA_PAPER_API_SECRET')
            if not key or not secret:
                raise ValueError('Dedicated Alpaca paper data credentials missing')
            self.session.headers.update({'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret})
        self.clock = clock
        self.evidence = []

    def execution_quote(self, contract, *, after, max_age_seconds=30):
        symbol = contract.removeprefix('O:')
        after = pd.Timestamp(after)
        if after.tzinfo is None:
            raise ValueError('Option quote decision requires timezone')
        try:
            response = self.session.get('https://data.alpaca.markets/v1beta1/options/quotes/latest',
                params={'symbols': symbol, 'feed': 'opra'}, timeout=15)
        except requests.RequestException:
            raise RuntimeError('Alpaca OPRA quote transport failed') from None
        if response.status_code != 200:
            raise RuntimeError(f'Alpaca OPRA quote HTTP {response.status_code}')
        body = response.json()
        row = (body.get('quotes') or {}).get(symbol)
        if not row:
            raise ValueError('no fresh post-decision option quote')
        stamp, received = pd.Timestamp(row['t']), self.clock()
        if (stamp.tzinfo is None or received.tzinfo is None or stamp < after or
                not 0 <= (received-stamp).total_seconds() <= max_age_seconds):
            raise ValueError('no fresh post-decision option quote')
        bid, ask, bs, az = [float(row[k]) for k in ('bp', 'ap', 'bs', 'as')]
        if not np.isfinite([bid, ask, bs, az]).all() or not 0 < bid <= ask or min(bs, az) <= 0:
            raise ValueError('option quote is crossed, empty or invalid')
        receipt = dict(provider='alpaca', feed='opra', contract=symbol,
            endpoint='/v1beta1/options/quotes/latest', retrieved_at=received.isoformat(),
            raw_quote=row)
        encoded = json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        path = self.root/'alpaca-opra-quotes'/f'{symbol}-{received.value}-{digest}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        # Content-addressed, independent observation; never overwrite old provider captures.
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(encoded)
        self.evidence.append(dict(path=str(path), sha256=digest, kind='execution_quote'))
        return dict(contract=contract, bid=bid, ask=ask, bid_size=bs, ask_size=az,
            sip_timestamp_ns=int(stamp.value), received_at=received.isoformat(),
            provider='alpaca', feed='opra', receipt=dict(path=str(path), sha256=digest))


class AlpacaRecordedMarket(AlpacaOptionQuotes):
    """Alpaca marks plus retained immutable catalogues; no Massive requests.

    Entry feature admission remains blocked until preceding windows and full
    subscription capacity have been validated. Never turn missing ticks into
    zero features or a latest-quote approximation.
    """
    point_in_time_chain = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chains = {}

    def pages(self, *args, **kwargs):
        raise ValueError('Prior-date catalogue unavailable locally; Alpaca catalogue capture required')

    def get_chain(self, *args, **kwargs):
        # Reuse the already admitted catalogue parser and hashes, without a
        # provider constructor or network fallback. Existing observations retain
        # their original Massive provenance; they are never relabelled Alpaca.
        from nn_meta.live.v6_market import MassiveMarket
        return MassiveMarket.get_chain(self, *args, **kwargs)

    def underlying_mark(self, *args, **kwargs):
        from nn_meta.live.v6_market import MassiveMarket
        # This method already uses Alpaca SIP stocks exclusively.
        return MassiveMarket.underlying_mark(self, *args, **kwargs)

    def verify_current_access(self, contract):
        now=self.clock()
        quote=self.execution_quote(contract,after=now-pd.Timedelta(seconds=30))
        return dict(status='quotes_verified_features_pending',provider='alpaca',feed='opra',
            quote=quote,checked_at=self.clock().isoformat(),historical_quote_windows_available=False)

    def tick_features(self, request, policy):
        raise ValueError('Alpaca preceding option quote window is not admitted; full-universe stream capacity and feature validation required')
