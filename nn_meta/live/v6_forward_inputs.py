"""Build full-history causal V6 candidates from a completed data refresh."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.live.v6_market import alpaca_bars, read, save
from nn_meta.live.v6_release import sha
from nn_meta.price_basis import require_raw_surface, raw_spot_provenance
from nn_meta.session_calendar import SessionCalendar


def captured_panel(receipt, *, start, now, adjustment):
    path=Path(receipt['path'])
    if (receipt.get('adjustment')!=adjustment or pd.Timestamp(receipt['query_start'])!=start
            or pd.Timestamp(receipt['query_end'])!=now or sha(path)!=receipt['sha256']):
        raise ValueError('captured stock query identity, clock or bytes changed')
    frame=pd.read_parquet(path)
    if (frame.attrs.get('provider')!='alpaca' or frame.attrs.get('feed')!='sip'
            or frame.attrs.get('adjustment')!=adjustment or len(frame)!=receipt['rows']):
        raise ValueError('captured stock query metadata differs')
    return frame


def attach_context(symbol, bars, training, calendar):
    from scripts.prepare_v6_local_context import local_context
    flags, context = local_context(bars, calendar, symbol=symbol,
        minimum_tick=training["symbols"][symbol]["context"]["minimum_tick"])
    prior = training["symbols"][symbol]["context"]["dependency_metadata"]
    for field in ("history_origin", "calendar_id", "htf_period", "vwap_anchor", "timeframe_flag_basis", "chart_session"):
        if context["dependency_metadata"][field] != prior[field]:
            raise ValueError(f"{symbol}: forward {field} differs from frozen training context")
    bars.attrs["v6_tradingview_context"] = dict(context, timeframe_flags=flags)
    return flags, context


def held_signal_exit(price, signals, position, config):
    """First actual exit/opposite signal after entry, excluding generic price stops."""
    entry = pd.Timestamp(position['entry_ts'])
    short = int(position['context']['direction']) == 1
    def channel(number):
        value = signals[number]
        if value is None:return pd.Series(False,index=price.index)
        if (not value.index.equals(price.index) or len(value.columns)!=1
                or value.isna().any().any() or not pd.api.types.is_bool_dtype(value.iloc[:,0])):
            raise ValueError('Held strategy requires exact single-variant boolean signals')
        return value.iloc[:,0]
    exit_signal = channel(3 if short else 1)
    same_entry = channel(2 if short else 0)
    opposite = channel(0 if short else 2)
    window = config.get('TREND_FILTER_WINDOW',0)
    if window:
        trend = price.Close.rolling(window,min_periods=1).mean()
        opposite = opposite & (price.Close.ge(trend) if short else price.Close.le(trend))
        same_entry = same_entry & (price.Close.le(trend) if short else price.Close.ge(trend))
    # Match the frozen simulator's entry-over-exit conflict rule, then its
    # opposite-entry reversal rule. Only the generic stock stop is removed.
    exits = price.index[(price.index>entry) & ((exit_signal & ~same_entry)|opposite)]
    return None if not len(exits) else exits[0]


def detect_symbol(task):
    """Keep frozen model entry features; held exits use actual strategy signals."""
    from nn_meta import config, proposals
    from nn_meta.baseline import _SIM_KWARGS
    from portfolio import simulator
    symbol, bars, raw, spec_entry, training, calendar, held = task
    flags, context = attach_context(symbol, bars, training, calendar)
    fresh, exits = [], {}
    for strategy in config.PROPOSAL_STRATEGIES:
        entry = spec_entry["strategies"].get(strategy)
        if entry is None:
            continue
        signals = proposals.single_signals(strategy, bars, entry["params"])
        price = bars.loc[config.WINDOW_START:]
        signals = [s.loc[config.WINDOW_START:] if s is not None else None for s in signals]
        pf = simulator.run_backtest(price_df=price, entries_series=signals[0], exits_series=signals[1],
            short_entries_series=signals[2], short_exits_series=signals[3], frequency="15min", **_SIM_KWARGS)
        if pf is None:
            raise ValueError(f"{symbol}/{strategy}: simulator returned no portfolio")
        single = pf[pf.wrapper.columns[0]] if len(pf.wrapper.columns) else pf
        records = single.trades.records
        if not isinstance(records, pd.DataFrame):
            records = pd.DataFrame(single.trades.records_arr)
        records = records.sort_values("entry_idx")
        if not records.empty:
            last = records.iloc[-1]
            if int(last.entry_idx) == len(price) - 1:
                gap = (int(last.entry_idx - records.iloc[-2].entry_idx) if len(records) > 1
                       else int(bars.index.get_loc(price.index[int(last.entry_idx)])))
                fresh.append({"symbol": symbol, "strategy": strategy, "direction": int(last.direction),
                    "entry_ts": bars.index[-1], "bars_since_signal": gap, "spot": float(bars.Close.iloc[-1]),
                    "param_label": entry.get("param_label", "")})
        for position in held:
            if position["strategy"] != strategy:
                continue
            entry_ts = pd.Timestamp(position["entry_ts"])
            if entry_ts not in bars.index or not np.isclose(float(bars.loc[entry_ts, "Close"]), position["context"]["spot"], rtol=1e-7, atol=1e-8):
                raise ValueError(f"{symbol}: original paper entry history changed")
            stamp = held_signal_exit(price,signals,position,config.SIM_CONFIG)
            if stamp is not None:
                exits[position["key"]] = {"bar": stamp.isoformat(), "reason": "underlying strategy sell signal"}
    return {"symbol": symbol, "fresh": fresh, "exits": exits, "latest_bar": bars.index[-1].isoformat()}


_worker_inputs = None


def init_worker(data_root, release_root, market_root, cycle_root):
    """Each process owns its provider session and shared daily context once."""
    global _worker_inputs
    import logging
    from nn_meta.live.v6_market import MassiveMarket
    # Source simulators log every indicator; keep operational output bounded.
    from utils.logging_utils import setup_logging
    setup_logging(log_level=logging.ERROR)
    obj = ForwardData.__new__(ForwardData)
    obj.root = Path(data_root)
    obj.training = read(Path(release_root) / "training-inputs.json")
    obj.spec = read(Path(release_root) / "baseline_spec.json")
    obj.calendar_doc = read(obj.root / "calendar.json")
    obj.surface = pd.read_parquet(obj.root / "surface.parquet")
    obj.context = pd.read_parquet(obj.root / "context.parquet")
    obj.bars, obj.raw = {}, {}
    _worker_inputs = obj, MassiveMarket(market_root), Path(cycle_root)


def process_symbol(task):
    """Detection and any feature capture run concurrently across symbols."""
    from v3._source_memo import reuse_identical_sources
    with reuse_identical_sources() as reuse:
        result = detect_symbol(task)
        obj, market, directory = _worker_inputs
        if result["fresh"]:
            symbol = task[0]
            obj.bars, obj.raw = {symbol: task[1]}, {symbol: task[2]}
            before = len(market.evidence)
            batch, contexts = obj.candidates(result["fresh"], market, directory)
            result.update(batch=batch, contexts=contexts, evidence=market.evidence[before:])
        result['source_reuse']={'hits':reuse['hits'],'misses':reuse['misses']}
        return result


class ForwardData:
    def __init__(self, root, *, expected_sha256, release, anchor):
        self.root = Path(root)
        self.release_root = Path(release)
        self.path = self.root / "manifest.json"
        if sha(self.path) != expected_sha256:
            raise ValueError("forward data manifest differs from its external anchor")
        self.digest = expected_sha256
        self.document = read(self.path)
        if self.document.get("schema") != "v6-forward-data-v1" or self.document["release_sha256"] != anchor:
            raise ValueError("forward data belongs to a different model release")
        for name, digest in self.document["files"].items():
            if sha(self.root / name) != digest:
                raise ValueError(f"forward daily input changed: {name}")
        self.calendar_doc = read(self.root / "calendar.json")
        self.calendar = SessionCalendar(self.calendar_doc)
        self.training = read(self.release_root / "training-inputs.json")
        self.spec = read(self.release_root / "baseline_spec.json")
        if set(self.document["symbols"]) != set(self.spec["symbols"]):
            raise ValueError("forward data must cover the complete frozen universe")
        self.surface = pd.read_parquet(self.root / "surface.parquet")
        require_raw_surface(self.surface)
        self.context = pd.read_parquet(self.root / "context.parquet")
        self.bars, self.raw = {}, {}
        for symbol, entry in self.document["symbols"].items():
            for adjustment, dest in [("all", self.bars), ("raw", self.raw)]:
                ref = entry["files"][adjustment]
                path = self.root / ref["path"]
                if sha(path) != ref["sha256"]:
                    raise ValueError(f"{symbol}: stock seed changed")
                dest[symbol] = pd.read_parquet(path)
        self.market_receipts = []

    def update(self, now, *, capture=None, captured=None):
        """Fetch complete queries for every frozen symbol; never synthesize bars."""
        from concurrent.futures import ThreadPoolExecutor
        now = pd.Timestamp(now)
        day = now.tz_convert("America/New_York").date().isoformat()
        prior = max(d for d in self.calendar.sessions if d < day)
        if self.document["through"] != prior:
            raise ValueError(f"daily context is stale: {self.document['through']} vs required {prior}")
        # Include the seed's last day to detect adjusted-price restatements.
        start = self.calendar.bounds(prior)[0].tz_localize("UTC")
        if captured is not None and sorted(r.get('adjustment') for r in captured)!=['all','raw']:
            raise ValueError('replay requires both complete adjusted and raw stock queries')
        def fetch(adjustment):
            if captured is not None:
                ref=next(r for r in captured if r['adjustment']==adjustment)
                return adjustment,captured_panel(ref,start=start,now=now,adjustment=adjustment)
            return adjustment, alpaca_bars(list(self.spec["symbols"]), start, now, timeframe="15Min", adjustment=adjustment)
        frames = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            for adjustment, panel in pool.map(fetch, ("all", "raw")):
                frames[adjustment] = panel
                receipt={"kind": "stock_bars", "adjustment": adjustment,
                    "rows": len(panel), "symbols": panel.symbol.nunique(), "received_at": panel.attrs["received_at"],
                    "query_start": start.isoformat(), "query_end": now.isoformat()}
                if capture is not None:
                    from nn_meta.live.v6_market import utcnow
                    path=Path(capture)/(utcnow().strftime('%Y%m%dT%H%M%S%fZ')+'.'+adjustment+'.parquet')
                    path.parent.mkdir(parents=True,exist_ok=True)
                    panel.to_parquet(path,index=False)
                    receipt.update(path=str(path.absolute()),sha256=sha(path))
                self.market_receipts.append(receipt)
        for symbol in self.spec["symbols"]:
            for adjustment, dest in [("all", self.bars), ("raw", self.raw)]:
                panel = frames[adjustment]
                extra = panel[panel.symbol == symbol].set_index("timestamp").drop(columns="symbol")
                extra = self.calendar.filter(extra)
                extra = extra[extra.index + pd.Timedelta(minutes=15) <= now.tz_convert("UTC").tz_localize(None)]
                old = dest[symbol]
                overlap = old.index.intersection(extra.index)
                if len(overlap) and not np.allclose(old.loc[overlap, "Close"], extra.loc[overlap, "Close"], rtol=1e-7, atol=1e-8):
                    raise ValueError(f"{symbol}: {adjustment} price vintage changed; a full data refresh is required")
                attrs = dict(old.attrs)
                old.attrs = {}; extra.attrs = {}
                dest[symbol] = pd.concat([old, extra[extra.index > old.index[-1]]]).sort_index()
                dest[symbol].attrs = attrs
            if not self.bars[symbol].index.equals(self.raw[symbol].index):
                raise ValueError(f"{symbol}: current raw and technical stock timelines differ")
        expected = self.calendar.closed_starts(day, now)
        if len(expected) and self.bars["SPY"].index[-1] != expected[-1]:
            raise ValueError("fresh current SPY bar missing from completed Alpaca query")

    def tasks(self, bar, held):
        bar = pd.Timestamp(bar)
        for symbol in self.spec["symbols"]:
            bars = self.bars[symbol].loc[:bar].copy()
            # An authoritative completed query can contain no bar for a
            # halted/inactive/illiquid name; it remains in the pass inventory.
            if bars.index[-1] != bar:
                yield symbol, None
                continue
            training = {**self.training, "symbols": {symbol: self.training["symbols"][symbol]}}
            yield symbol, (symbol, bars, self.raw[symbol].loc[:bar], self.spec["symbols"][symbol],
                training, self.calendar_doc, [p for p in held if p["symbol"] == symbol])

    def candidates(self, fresh, market, output):
        from nn_meta.v6_expansion import ExpandedInputs, bars_sha256
        from nn_meta.live.v4_scan import candidate_frame
        from nn_meta.live.v4_candidates import build_candidate_batch
        from nn_meta.option_tick_dataset import NUMERIC_FEATURES
        class CapturedInputs(ExpandedInputs):
            def matrix(inner, symbol, bars):
                from nn_meta.v6_expansion import aware_bars
                from nn_meta.tradingview_features import tradingview_features
                context = inner.context(symbol, bars)
                context["as_of"] = pd.Timestamp(context["as_of"])
                if symbol not in inner._matrices:
                    complete = aware_bars(bars)
                    inner._matrices[symbol] = tradingview_features(complete,
                        observation_index=complete.index[-1:], **context)
                return inner._matrices[symbol]

            def join_ticks(inner, requested, *, symbol):
                rows = []
                for request in requested.to_dict("records"):
                    row = {**request, "option_tick_status": "unselected", **{f: np.nan for f in NUMERIC_FEATURES}}
                    if request["contract"] is not None:
                        row.update(market.tick_features(request, inner.document["tick_feature_policy"]))
                    rows.append(row)
                frame = pd.DataFrame(rows)
                frame.attrs["feature_policy"] = inner.document["tick_feature_policy"]
                return frame
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        by_symbol, contexts, batches = {}, {}, []
        for proposal in fresh:
            by_symbol.setdefault(proposal["symbol"], []).append(proposal)
        for symbol, proposals in by_symbol.items():
            from nn_meta.live.v6_portfolio import key_of
            bars = self.bars[symbol].loc[:pd.Timestamp(proposals[0]["entry_ts"])].copy()
            flags, context = attach_context(symbol, bars, self.training, self.calendar_doc)
            flag_path = output / f"{symbol}.flags.parquet"
            flags.to_parquet(flag_path)
            doc = deepcopy(self.training)
            doc["context_references"] = [{"path": str((self.root / "calendar.json").absolute()), "sha256": sha(self.root / "calendar.json")}]
            doc["symbols"] = {symbol: {"bars_sha256": bars_sha256(bars), "context": context,
                "timeframe_flags": {"path": flag_path.name, "sha256": sha(flag_path)}}}
            path = output / f"{symbol}.inputs.json"
            save(path, doc)
            expanded = CapturedInputs(path, sha(path), parity_policy="deferred")
            raw = self.raw[symbol].loc[:bars.index[-1], "Close"].copy()
            raw.attrs = dict(raw_spot_provenance("15m", provider="alpaca", feed="sip"), symbol=symbol)
            batch = build_candidate_batch(candidate_frame(proposals, self.spec), {symbol: bars},
                self.surface, self.spec, context=self.context, expanded_inputs=expanded,
                option_provider=market, raw_close_by_symbol={symbol: raw})
            batches.append(batch)
            for p in proposals:
                from nn_meta import config
                contexts[key_of(p)] = {"sim_start": bars.index[0].isoformat(), "entry_ts": bars.index[-1].isoformat(),
                    "symbol": symbol, "strategy": p["strategy"], "params": self.spec["symbols"][symbol]["strategies"][p["strategy"]]["params"],
                    "direction": p["direction"], "spot": p["spot"], "sim_config": config.SIM_CONFIG,
                    "held_exit_policy":"strategy signals plus option-premium risk; generic stock stop disabled"}
        return pd.concat(batches, ignore_index=True) if batches else pd.DataFrame(), contexts
