"""Evidence-preserving market access for the frozen V6 forward experiment.

Option features use MASSIVE SIP windows, exactly as in training. Retrieval
time is recorded separately and is never represented as a historical receipt.
Stock technical prices remain Alpaca SIP adjustment=all; option spot is raw.
"""
from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import time
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import numpy as np
import pandas as pd
import requests

from nn_meta.live.v6_release import sha
from options.data.provider import OptionContract, parse_occ_symbol
from options.data.massive_ticks import MassiveTicks, verify_capture


def utcnow():
    return pd.Timestamp.now(tz="UTC")


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


class MassiveMarket:
    point_in_time_chain = True

    def __init__(self, root, *, session=None, tick_client=None, clock=utcnow):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        if session is None:
            self.session.headers["Authorization"] = "Bearer " + os.environ["MASSIVE_API_KEY"]
        self.ticks = tick_client or MassiveTicks()
        self.clock = clock
        self.evidence = []
        self._chains = {}
        self._features = {}

    def pages(self, path, params, *, max_pages=100):
        """Never accept a partial, delayed or cross-origin response as complete."""
        url = "https://api.massive.com" + path
        seen, rows, page_hashes = set(), [], []
        for _ in range(max_pages):
            identity = (url, json.dumps(params, sort_keys=True))
            if identity in seen:
                raise ValueError("MASSIVE pagination repeated a page")
            seen.add(identity)
            response = None
            for attempt in range(4):
                try:
                    response = self.session.get(url, params=params, timeout=30)
                except requests.RequestException:
                    if attempt == 3:
                        raise RuntimeError("MASSIVE transport failed") from None
                else:
                    if response.status_code != 429 and response.status_code < 500:
                        break
                time.sleep(min(2 ** attempt, 4))
            if response is None or response.status_code != 200:
                raise RuntimeError(f"MASSIVE HTTP {response.status_code if response is not None else 'transport'}")
            body = response.json()
            if body.get("status") != "OK" or not isinstance(body.get("results", []), list):
                raise ValueError("MASSIVE response is not complete/OK")
            rows.extend(body.get("results", []))
            page_hashes.append(hashlib.sha256(json.dumps(body.get("results", []), sort_keys=True).encode()).hexdigest())
            if not body.get("next_url"):
                return rows, {"provider": "massive", "path": path, "query": params if len(seen) == 1 else None,
                              "pages": len(seen), "page_sha256": page_hashes,
                              "complete": True, "retrieved_at": self.clock().isoformat()}
            parsed = urlsplit(body["next_url"])
            if parsed.scheme != "https" or parsed.netloc != "api.massive.com" or parsed.path != path:
                raise ValueError("MASSIVE pagination changed origin or endpoint")
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
            params = {k: v for k, v in parse_qsl(parsed.query) if k.lower() != "apikey"}
        raise ValueError("MASSIVE pagination budget exhausted")

    def get_chain(self, symbol, *, right, expiration_gte, expiration_lte, as_of):
        # Cache the whole 1..65-DTE envelope per root/date; never cache a spot
        # band. Provider reference as_of is historical catalogue evidence,
        # distinct from the old archive's first-print date proxy.
        key = (symbol, str(as_of))
        if key not in self._chains:
            path = self.root / "chains" / str(as_of) / f"{symbol}.json"
            if path.exists():
                doc = read(path)
                if doc["symbol"] != symbol or doc["as_of"] != str(as_of):
                    raise ValueError("chain cache identity mismatch")
            else:
                from nn_meta import config
                fetch = config.FETCH_ALIASES.get(symbol, symbol)
                start = pd.Timestamp(as_of) + pd.Timedelta(days=1)
                end = start + pd.Timedelta(days=65)
                params = {"underlying_ticker": fetch, "as_of": str(as_of),
                    "expiration_date.gte": start.date().isoformat(),
                    "expiration_date.lte": end.date().isoformat(), "limit": 1000, "sort": "ticker", "order": "asc"}
                rows, receipt = self.pages("/v3/reference/options/contracts", params)
                doc = {"symbol": symbol, "as_of": str(as_of), "query": params,
                       "receipt": receipt, "contracts": rows}
                save(path, doc)
            if not doc["receipt"]["complete"] or pd.Timestamp(doc["receipt"]["retrieved_at"]) > self.clock():
                raise ValueError("invalid catalogue capture")
            self.evidence.append({"path": str(path), "sha256": sha(path), "kind": "prior_date_reference_chain"})
            excluded = [r for r in doc["contracts"] if not re.fullmatch(r"O:[A-Z]+\d{6}[CP]\d{8}", r["ticker"])]
            if excluded:
                self.evidence.append({"kind": "chain_scope", "symbol": symbol, "as_of": str(as_of),
                    "excluded_count": len(excluded), "rule": "same letters-only standard OCC grammar as frozen v3.flatfiles and v3.derive_contracts",
                    "excluded_rows_sha256": hashlib.sha256(json.dumps(excluded, sort_keys=True).encode()).hexdigest()})
            self._chains[key] = doc
        out = []
        for row in self._chains[key]["contracts"]:
            # The frozen raw archive never admitted adjusted numerical OCC
            # roots (e.g. BABA2). Reference listings include them; preserve the
            # original standard-contract grammar and record the exclusions.
            if not re.fullmatch(r"O:[A-Z]+\d{6}[CP]\d{8}", row["ticker"]):
                continue
            occ = row["ticker"].removeprefix("O:")
            root, expiry, side, strike = parse_occ_symbol(occ)
            # Corporate-action contracts with changed deliverables do not
            # support the frozen 100-share accounting. Fail instead of drop.
            if side == right and expiration_gte <= expiry <= expiration_lte:
                if root != symbol or row.get("shares_per_contract", 100) != 100 or row.get("additional_underlyings"):
                    raise ValueError(f"{symbol}: nonstandard/aliased contract requires explicit membership evidence")
                if row["strike_price"] != strike or row["expiration_date"] != expiry.isoformat():
                    raise ValueError("catalogue OCC identity mismatch")
                out.append(OptionContract(occ, symbol, expiry, strike, side))
        return out

    def tick_features(self, request, policy):
        from nn_meta.option_tick_dataset import compute_feature_row
        from options.tick_features import window_features
        key = request["request_id"]
        if key in self._features:
            return self._features[key]
        if policy["availability"] != "sip" or policy["condition_namespace"] != "massive_integer":
            raise ValueError("MASSIVE feature capture requires the frozen SIP/integer policy")
        start, end = int(request["window_start_ns"]), int(request["window_end_ns"])
        if end > self.clock().value:
            raise ValueError("cannot capture an unfinished feature window")
        directory = self.root / "ticks" / str(pd.Timestamp(end, tz="UTC").date()) / key
        directory.mkdir(parents=True, exist_ok=True)
        captures = {}
        for kind in ("quotes", "trades"):
            record = directory / f"{kind}.json.gz"
            receipt = directory / f"{kind}.manifest.json"
            if receipt.exists():
                manifest = read(receipt)
                if sha(record) != manifest["file_sha256"]:
                    raise ValueError("saved option tick capture changed")
                with gzip.open(record, "rt") as stream:
                    rows = json.load(stream)
            else:
                rows, manifest = self.ticks.capture(request["contract"], kind=kind, start_ns=start, end_ns=end, max_pages=100)
                with gzip.open(record.with_suffix(".tmp"), "wt") as stream:
                    json.dump(rows, stream, separators=(",", ":"), allow_nan=False)
                record.with_suffix(".tmp").replace(record)
                manifest["file_sha256"] = sha(record)
                save(receipt, manifest)
            verify_capture(rows, manifest, contract=request["contract"], kind=kind, start_ns=start, end_ns=end)
            if pd.Timestamp(manifest["retrieved_at"]) > self.clock():
                raise ValueError("capture retrieval is in the future")
            self.evidence.append({"path": str(receipt), "sha256": sha(receipt), "kind": kind})
            captures[kind] = rows
        kwargs = dict(start_ns=start, end_ns=end, coverage_start_ns=start, coverage_end_ns=end,
            complete=True, availability="sip", max_quote_age_ns=policy["max_quote_age_ns"],
            allowed_trade_conditions=policy["allowed_trade_conditions"], allow_unconditioned_trades=False)
        eligible = [r for r in captures["trades"] if r.get("conditions") and
                    all(c in policy["allowed_trade_conditions"] for c in r["conditions"])]
        result = compute_feature_row(window_features(captures["quotes"], captures["trades"], **kwargs), request,
                                     eligible=window_features(captures["quotes"], eligible, **kwargs))
        self._features[key] = result
        return result

    def execution_quote(self, contract, *, after, max_age_seconds=30):
        """Fresh current quote for midpoint paper prices; no broker execution."""
        now = self.clock()
        lower = max(pd.Timestamp(after), now - pd.Timedelta(seconds=max_age_seconds))
        rows, receipt = self.pages("/v3/quotes/O:" + contract.removeprefix("O:"),
            {"timestamp.gte": int(lower.value), "timestamp.lt": int(now.value),
             "order": "desc", "sort": "timestamp", "limit": 1000}, max_pages=100)
        # Account delay/empty tape, crossed markets and zero sizes fail closed.
        if not rows:
            raise ValueError("no fresh post-decision option quote")
        quote = max(rows, key=lambda r: int(r["sip_timestamp"]))
        bid, ask = float(quote["bid_price"]), float(quote["ask_price"])
        received = self.clock()
        age = (received.value - int(quote["sip_timestamp"])) / 1e9
        if (not np.isfinite([bid, ask]).all() or not 0 < bid <= ask or
                quote.get("bid_size", 0) <= 0 or quote.get("ask_size", 0) <= 0 or not 0 <= age <= max_age_seconds):
            raise ValueError("option quote is stale, crossed, empty or invalid")
        return {"contract": contract, "bid": bid, "ask": ask, "bid_size": quote["bid_size"],
                **{k: quote[k] for k in ('mid', 'midpoint', 'mid_price', 'midpoint_price', 'last', 'last_price') if k in quote},
                "ask_size": quote["ask_size"], "sip_timestamp_ns": int(quote["sip_timestamp"]),
                "received_at": received.isoformat(), "provider": "massive", "receipt": receipt}

    def underlying_mark(self, symbol, now):
        """Fresh Alpaca SIP stock midpoint for expiry ITM classification only."""
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        from alpaca.data.enums import DataFeed
        from nn_meta import config
        from options.paper_pricing import option_midpoint
        fetch = config.FETCH_ALIASES.get(symbol, symbol)
        client = getattr(self, '_stock_client', None)
        if client is None:
            client = self._stock_client = StockHistoricalDataClient(
                os.environ['ALPACA_API_KEY'], os.environ['ALPACA_API_SECRET'])
        quotes = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=fetch, feed=DataFeed.SIP))
        if fetch not in quotes:
            raise ValueError('No observed Alpaca underlying quote for expiry classification')
        quote = quotes[fetch]
        stamp, received = pd.Timestamp(quote.timestamp), self.clock()
        if stamp.tzinfo is None or not 0 <= (received-stamp).total_seconds() <= 30:
            raise ValueError('Underlying quote is stale or in the future')
        basis = option_midpoint(dict(bid=quote.bid_price, ask=quote.ask_price))
        record = dict(symbol=symbol, fetched_symbol=fetch, provider='alpaca', feed='sip',
            price=basis['price'], bid=basis['bid'], ask=basis['ask'],
            sip_timestamp=int(stamp.value), received_at=received.isoformat())
        path = self.root/'underlying-quotes'/f'{fetch}-{received.value}.json'
        save(path, record)
        self.evidence.append(dict(path=str(path), sha256=sha(path), kind='underlying_quote'))
        return record

    def verify_current_access(self, contract):
        """An actual liquid option verifies both current endpoint entitlements.

        Historical OK responses alone cannot certify Monday's live access.
        A successful REST page also does not imply exchange completeness past
        the API response time; the full-window captures retain their receipts.
        """
        now = self.clock()
        quote = self.execution_quote(contract, after=now-pd.Timedelta(seconds=30))
        rows, receipt = self.pages('/v3/trades/O:'+contract.removeprefix('O:'),
            {'timestamp.gte':int((now-pd.Timedelta(seconds=120)).value),
             'timestamp.lt':int(now.value), 'order':'desc', 'sort':'timestamp', 'limit':1000})
        if not rows or max(int(r['sip_timestamp']) for r in rows) < (self.clock()-pd.Timedelta(seconds=120)).value:
            raise ValueError('fresh liquid-option trades missing; current trade entitlement is unverified')
        report = {'status':'passed','contract':contract,'checked_at':self.clock().isoformat(),
            'quote':quote,'trade_receipt':receipt,'latest_trade_sip_ns':max(int(r['sip_timestamp']) for r in rows)}
        save(self.root/'current-access.json',report)
        return report


def alpaca_bars(symbols, start, end, *, timeframe, adjustment, session=None):
    """Complete paginated SIP history, with explicit price adjustment semantics."""
    from nn_meta import config
    reverse = {}
    for symbol in symbols:
        fetch = config.FETCH_ALIASES.get(symbol) or config.TICKER_ALIASES.get(symbol, symbol)
        reverse.setdefault(fetch, []).append(symbol)
    session = session or requests.Session()
    headers = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET"]}
    params = {"symbols": ",".join(sorted(reverse)), "start": pd.Timestamp(start).isoformat(),
              "end": pd.Timestamp(end).isoformat(), "timeframe": timeframe,
              "adjustment": adjustment, "feed": "sip", "limit": 10000, "sort": "asc"}
    rows, seen = [], set()
    # A full adjusted-history restatement for the complete 453-symbol V6
    # universe can legitimately exceed 1,000 SIP pages. Keep a hard bound,
    # but leave enough room for the documented full-history repair path.
    for _ in range(5000):
        try:
            response = session.get("https://data.alpaca.markets/v2/stocks/bars", headers=headers, params=params, timeout=45)
        except requests.RequestException:
            raise RuntimeError("Alpaca stock transport failed") from None
        if response.status_code != 200:
            raise RuntimeError(f"Alpaca stock HTTP {response.status_code}")
        body = response.json()
        for fetched, values in (body.get("bars") or {}).items():
            if fetched not in reverse:
                raise ValueError("Alpaca returned an unrequested stock")
            for b in values:
                for symbol in reverse[fetched]:
                    rows.append([symbol, pd.Timestamp(b["t"]).tz_convert("UTC").tz_localize(None),
                                 *[float(b[k]) for k in ("o", "h", "l", "c", "v")]])
        token = body.get("next_page_token")
        if not token:
            break
        if token in seen:
            raise ValueError("Alpaca pagination repeated a page")
        seen.add(token)
        params["page_token"] = token
    else:
        raise ValueError("Alpaca pagination budget exhausted")
    frame = pd.DataFrame(rows, columns=["symbol", "timestamp", "Open", "High", "Low", "Close", "Volume"])
    if frame.duplicated(["symbol", "timestamp"]).any():
        raise ValueError("Alpaca stock history has duplicate keys")
    frame.attrs.update(provider="alpaca", feed="sip", adjustment=adjustment, received_at=utcnow().isoformat())
    return frame
