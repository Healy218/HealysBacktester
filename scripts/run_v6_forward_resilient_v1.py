"""V6 paper consumer v1: overlap bounded quote recovery with candidate work.

Derived from frozen run_v6_forward.py cfdee72d1a8ee9b386825a255412007bc108bbe73b5b2f2b001afcd9398137c2.
Uses the unchanged frozen feature, model, portfolio and pricing modules.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import time
import sys
import threading

# The admitted dispatcher runs this consumer from the verified frozen checkout.
if __name__ in ("__main__", "__mp_main__"):
    sys.path.insert(0, str(Path.cwd()))

from nn_meta.live.v6_release import read, sha, verify_release
from nn_meta.live.v6_market import save, utcnow
from nn_meta.live.v6_option_sessions import expiry_cutoff


def configure(release, anchor):
    verified = verify_release(release, anchor)
    os.environ.update(NN_META_POOL="v6", NN_META_CAMPAIGN=verified["campaign"],
        NN_META_V6_ACCELERATE="1",
        NN_META_V6_EXPANDED="1", NN_META_V6_PARITY_POLICY="deferred",
        NN_META_V6_INPUTS=str(release / "training-inputs.json"),
        NN_META_V6_INPUTS_SHA256=verified["training_inputs_sha256"])
    return verified


def recent_risk_observation(state, position, bar_close, current):
    """Accept only this leg's post-close, freshly priced minute-risk check.

    The independent worker applies the same checked_quote 30-second SIP rule.
    This fallback never supplies an execution price or settles an exit.
    """
    from options.paper_pricing import MIDPOINT_POLICY
    from options.paper_risk import V6_OPTION_RISK
    from dataclasses import asdict
    import pandas as pd
    try:
        report = read(Path(state) / 'option-risk-status.json')
        if (report.get('schema') != 'v6-option-risk-status-v1' or
                report.get('status') not in ('complete', 'failed') or
                report.get('broker_orders') is not False or
                report.get('pricing_policy') != MIDPOINT_POLICY or
                report.get('option_risk_policy') != asdict(V6_OPTION_RISK)):
            return False
        close, now = pd.Timestamp(bar_close), pd.Timestamp(current)
        for result in report.get('results', []):
            if result.get('key') != position['key'] or result.get('status') != 'holding':
                continue
            if any(error.get('key') == position['key'] for error in report.get('errors', [])):
                return False
            observed = result['observed']
            if (observed['contract'] != position['contract'] or
                    observed['rolls'] != int(position.get('rolls', 0)) or
                    observed['opened_at'] != position['opened_at']):
                return False
            quote_at = pd.Timestamp(int(observed['quote_at_ns']), tz='UTC')
            received = pd.Timestamp(observed['quote_received_at'])
            assessed = pd.Timestamp(observed['assessed_at'])
            checked = pd.Timestamp(report['checked_at'])
            if any(x.tzinfo is None for x in (close, now, received, assessed, checked)):
                return False
            return (close <= quote_at <= received <= assessed <= checked <= now and
                    (assessed - quote_at).total_seconds() <= 30 and
                    (now - assessed).total_seconds() <= 60 and
                    (now - close).total_seconds() <= 300)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return False
    return False


def monitor_positions(data, book, market, now, *, alerts):
    """Held-strategy exits get priority over unrelated candidate capture."""
    import pandas as pd
    from copy import deepcopy
    from nn_meta.live.v6_forward_inputs import detect_symbol
    from nn_meta.decision_contracts import DecisionContractSelector
    from nn_meta.live.v6_option_risk import monitor_option_position
    errors=[]
    for position in book.open_positions():
        symbol=position['symbol']
        try:
            checked_leg=position
            try:
                risk = monitor_option_position(book,position,market,clock=utcnow,alerts=alerts,
                    calendar=data.calendar,underlying_mark=market.underlying_mark)
            except ValueError as exc:
                if str(exc) != 'no fresh post-decision option quote':
                    raise
                starts = data.calendar.closed_starts(now.tz_convert('America/New_York').date().isoformat(), now)
                bar_close = starts[-1].tz_localize('UTC') + pd.Timedelta(minutes=15)
                if not recent_risk_observation(book.path.parent, position, bar_close, utcnow()):
                    raise
                risk = {'status':'holding', 'source':'validated_minute_risk_observation'}
            remaining=[p for p in book.open_positions() if p['key']==position['key']]
            if not remaining:continue
            position=remaining[0]
            if position['state']=='exit_due':continue
            starts=data.calendar.closed_starts(now.tz_convert('America/New_York').date().isoformat(), now)
            bar=starts[-1]
            bars=data.bars[symbol].loc[:bar].copy()
            if bars.index[-1]!=bar: raise ValueError('held underlying has no current closed bar')
            spec=deepcopy(data.spec['symbols'][symbol])
            spec['strategies']={position['strategy']:spec['strategies'][position['strategy']]}
            result=detect_symbol((symbol,bars,data.raw[symbol].loc[:bar],spec,data.training,data.calendar_doc,[position]))
            event=result['exits'].get(position['key'])
            if event:
                at=pd.Timestamp(event['bar'],tz='UTC')+pd.Timedelta(minutes=15)
                book.trigger(position['key'],kind='exit',reason=event['reason'],at=at,alerts=alerts)
            elif risk['status']=='otm_expiry':
                book.trigger(position['key'],kind='roll',reason='15-minute final-session expiry cutoff',
                    at=expiry_cutoff(checked_leg['contract'],data.calendar),alerts=alerts,
                    expected_leg=checked_leg)
            remaining=[p for p in book.open_positions() if p['key']==position['key']]
            if not remaining: continue
            current=remaining[0]
            replacement=None
            if current['state'] in ('roll_due','roll_pending'):
                selected=DecisionContractSelector(market).select(symbol,as_of=now.date(),
                    right='P' if position['context']['direction'] else 'C',
                    raw_spot=float(data.raw[symbol].loc[bar,'Close']),target_dte=int(position['dte']))
                replacement=selected.symbol if selected else None
            book.settle(position['key'],quote_loader=market.execution_quote,clock=utcnow,
                replacement=replacement,alerts=alerts)
        except Exception as exc:
            errors.append({'symbol':symbol,'error':f'{type(exc).__name__}: {exc}'})
    if alerts: book.export(book.path.parent/'alert-spool')
    return errors


def close_expiring_without_bars(book, calendar, market, now, *, alerts):
    """Premium stops and ITM expiry exits work during a stock-bar outage."""
    from nn_meta.live.v6_option_risk import monitor_option_position
    errors=[]
    for position in book.open_positions():
        try:
            result=monitor_option_position(book,position,market,clock=utcnow,alerts=alerts,
                calendar=calendar,underlying_mark=market.underlying_mark)
            if result['status']=='otm_expiry':
                book.trigger(position['key'],kind='roll',reason='OTM option expiry cutoff',
                    at=expiry_cutoff(position['contract'],calendar),alerts=alerts,expected_leg=position)
                book.settle(position['key'],quote_loader=market.execution_quote,clock=utcnow,alerts=alerts)
        except Exception as exc:
            errors.append({'symbol':position['symbol'],'error':f'{type(exc).__name__}: {exc}'})
    return errors



class PositionMonitor:
    """Retry quiet-tape observations concurrently; never authorize allocation."""
    def __init__(self, check, *, deadline, receipt, clock=utcnow, interval=2.0):
        self.check, self.deadline, self.receipt = check, deadline, receipt
        self.clock, self.interval = clock, interval
        self.stop = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v6-held-risk")
        self.future = self.pool.submit(self._run)

    def _run(self):
        attempts = []
        while True:
            try:
                errors = self.check()
            except Exception as exc:
                save(self.receipt, dict(schema="v6-held-monitor-retry-v1",
                    checked_at=self.clock().isoformat(), status="blocked", attempts=attempts,
                    error=type(exc).__name__ + ": " + str(exc)))
                raise
            attempts.append(dict(at=self.clock().isoformat(), errors=errors))
            retry = bool(errors) and all(e.get("error") ==
                "ValueError: no fresh post-decision option quote" for e in errors)
            remaining = (self.deadline - self.clock()).total_seconds()
            terminal = not retry or remaining <= 0 or self.stop.is_set()
            save(self.receipt, dict(schema="v6-held-monitor-retry-v1",
                checked_at=self.clock().isoformat(), deadline=self.deadline.isoformat(),
                status=("blocked" if errors else "complete") if terminal else "waiting_for_quote",
                attempts=attempts))
            if terminal:
                return errors
            if self.stop.wait(min(self.interval, remaining)):
                save(self.receipt, dict(schema="v6-held-monitor-retry-v1",
                    checked_at=self.clock().isoformat(), status="cancelled", attempts=attempts,
                    error="Scan ended before quote recovery; no monitoring clearance"))
                return errors

    def require_complete(self):
        errors = self.future.result()
        if errors:
            raise ValueError("unresolved position monitoring; new entries withheld: " + json.dumps(errors))

    def close(self):
        self.stop.set()
        self.pool.shutdown(wait=True)


def run(args):
    started = time.monotonic()
    position_monitor = None
    args.state.mkdir(parents=True, exist_ok=True)
    with (args.state / ".forward.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = {"schema": "v6-forward-status-v1", "checked_at": utcnow().isoformat(),
                  "alerts_enabled": False, "broker_orders": False, "experimental": True}
        def report(**values):
            status.update(values, elapsed_seconds=round(time.monotonic() - started, 3))
            save(args.state / "status.json", status)
        try:
            from dotenv import load_dotenv
            load_dotenv(args.env)
            verified = configure(args.release, args.anchor)
            from nn_meta.live.v6_forward_inputs import ForwardData, detect_symbol, init_worker, process_symbol
            from nn_meta.live.v6_portfolio import ForwardPortfolio
            from nn_meta.live.v6_release import FrozenGBT
            from nn_meta.live.v6_market import MassiveMarket
            from nn_meta.live.v6_shadow import canonical
            import pandas as pd
            from nn_meta import config
            from nn_meta.decision_contracts import DecisionContractSelector
            actual = utcnow()
            now = pd.Timestamp(args.replay_time) if args.replay_time else actual
            if now.tzinfo is None:
                raise ValueError("runtime/replay time requires timezone")
            report(status="running", phase="verify_data", model_sha256=verified["model_sha256"],
                   replay=bool(args.replay_time), signal_clock=now.isoformat())
            data = ForwardData(args.data, expected_sha256=args.data_anchor, release=args.release, anchor=args.anchor)
            day = now.tz_convert("America/New_York").date().isoformat()
            if not data.calendar.scan_open(now):
                report(status="idle", phase="outside_market_hours", next_session=min(d for d in data.calendar.sessions if d > day),
                       universe=len(data.spec["symbols"]), data_through=data.document["through"])
                return status
            starts = data.calendar.closed_starts(day, now)
            if not len(starts):
                report(status="idle", phase="awaiting_first_closed_bar")
                return status
            bar = starts[-1]
            close = bar.tz_localize("UTC") + pd.Timedelta(minutes=15)
            if args.replay_time and args.enable_alerts:
                raise ValueError("historical replay cannot enable alerts")
            if args.enable_alerts:
                activation = read(args.activation)
                if activation.get("status") != "passed" or activation.get("release_sha256") != args.anchor:
                    raise ValueError("missing verified activation receipt")
                if activation.get("expiry_cutoff_minutes") != 15:
                    raise ValueError("expiry execution convention was not bound")
                from dataclasses import asdict
                from options.paper_pricing import MIDPOINT_POLICY
                from options.paper_risk import V6_OPTION_RISK
                if (activation.get('pricing_policy')!=MIDPOINT_POLICY
                        or activation.get('option_risk_policy')!=asdict(V6_OPTION_RISK)):
                    raise ValueError('Option-midpoint stop and expiry rules were not activated')
                for path, digest in activation["runtime_sha256"].items():
                    if sha(Path(__file__).resolve().parents[1] / path) != digest:
                        raise ValueError("runtime changed since activation validation")
                report(alerts_enabled=True)
            book = ForwardPortfolio(args.state / "portfolio.sqlite3", scope={
                "release_sha256": args.anchor, "slots": 5, "fraction": .1, "threshold": .05,
                "dd_brake": None, "cost_per_side": .0015, "expiry_cutoff_minutes": 15,
                "sizing": "fractional_paper", "feature_clock": "massive_sip", "research_only": True})
            if not args.replay_time and book.cycle_seen(bar):
                report(status="idle", phase="bar_already_processed", portfolio=book.summary())
                return status
            report(phase="refresh_bars", universe=len(data.spec["symbols"]), data_through=data.document["through"])
            market = MassiveMarket(args.state / "market")
            if not args.replay_time or getattr(args,'refresh_replay_bars',False) or getattr(args,'stock_capture',None):
                try:
                    captured=None
                    if getattr(args,'stock_capture',None):
                        if sha(args.stock_capture)!=args.stock_capture_sha256:
                            raise ValueError('stock capture receipt changed')
                        receipt=read(args.stock_capture)
                        if receipt['data_manifest_sha256']!=args.data_anchor or pd.Timestamp(receipt['signal_close'])!=close:
                            raise ValueError('stock capture belongs to a different data seed or bar')
                        captured=receipt['stock_queries']
                    data.update(now,capture=args.state/'stock-captures',captured=captured)
                except Exception:
                    if not args.replay_time:
                        report(expiry_fallback_errors=close_expiring_without_bars(book,data.calendar,market,utcnow(),alerts=args.enable_alerts))
                    raise
            if not args.replay_time:
                # Each risk attempt uses its own provider session. Detection only
                # reads bars and held-leg snapshots; allocation waits for this gate.
                risk_market = MassiveMarket(args.state / "market")
                held_snapshot = book.open_positions()
                position_monitor = PositionMonitor(
                    lambda: monitor_positions(data, book, risk_market, now, alerts=args.enable_alerts),
                    deadline=min(utcnow()+pd.Timedelta(seconds=120), close+pd.Timedelta(seconds=270)),
                    receipt=args.state / "position-monitor-status.json")
                report(position_monitoring="concurrent", monitoring_receipt=str(position_monitor.receipt))
                reference=DecisionContractSelector(market).select('SPY',as_of=now.date(),right='C',
                    raw_spot=float(data.raw['SPY'].Close.iloc[-1]),target_dte=1)
                if reference is None: raise ValueError('liquid reference option unavailable')
                report(current_access=market.verify_current_access(reference.symbol))
            report(phase="detect", fresh_symbols=0)
            tasks = list(data.tasks(bar, held_snapshot if position_monitor else book.open_positions()))
            missing = [symbol for symbol, task in tasks if task is None]
            active_tasks = [task for _, task in tasks if task is not None]
            if any(p["symbol"] in missing for p in book.open_positions()):
                raise ValueError("a held position is missing its current underlying bar")
            fresh, exits, errors = [], {}, []
            batches, contexts, tick_evidence = [], {}, []
            source_reuse={'hits':0,'misses':0}
            cycle_dir = args.state / "passes" / close.strftime("%Y%m%dT%H%M%SZ")
            cycle_dir.mkdir(parents=True, exist_ok=True)
            def collect(result):
                fresh.extend(result["fresh"]); exits.update(result["exits"])
                for k in source_reuse: source_reuse[k]+=result.get('source_reuse',{}).get(k,0)
                if "batch" in result:
                    batches.append(result["batch"])
                    contexts.update(result["contexts"])
                    tick_evidence.extend(result["evidence"])
            if args.workers == 1:
                init_worker(args.data, args.release, args.state / "market", cycle_dir)
                for task in active_tasks:
                    collect(process_symbol(task))
            else:
                with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"),
                        initializer=init_worker, initargs=(args.data, args.release, args.state / "market", cycle_dir)) as pool:
                    jobs = {pool.submit(process_symbol, task): task[0] for task in active_tasks}
                    for completed_count, done in enumerate(as_completed(jobs), 1):
                        try:
                            collect(done.result())
                        except Exception as exc:
                            errors.append({"symbol": jobs[done], "error": f"{type(exc).__name__}: {exc}"})
                        if completed_count % 10 == 0 or errors:
                            report(symbol_results=completed_count, fresh_signals=len(fresh), errors=len(errors), detection_errors=errors)
            # Preserve deterministic frozen symbol/strategy ordering regardless
            # of process completion order (including equal-EV tie behavior).
            order = {s: i for i, s in enumerate(data.spec["symbols"])}
            strategies = {s: i for i, s in enumerate(config.PROPOSAL_STRATEGIES)}
            fresh.sort(key=lambda p: (order[p["symbol"]], strategies[p["strategy"]]))
            if errors:
                report(detection_errors=errors)
                raise ValueError("incomplete universe detection; allocation withheld")
            report(phase="capture_and_score", detected=len(active_tasks), symbol_results=len(active_tasks),
                   no_current_bar=missing, fresh_signals=len(fresh),fresh_symbols=len({p['symbol'] for p in fresh}),source_reuse=source_reuse)
            batch = pd.concat(batches, ignore_index=True) if batches else pd.DataFrame()
            if not batch.empty:
                batch["_symbol_order"] = batch.symbol.map(order)
                batch["_strategy_order"] = batch.strategy.map(strategies)
                batch = batch.sort_values(["_symbol_order", "_strategy_order", "dte"], kind="stable").drop(columns=["_symbol_order", "_strategy_order"]).reset_index(drop=True)
                model = FrozenGBT(args.release, args.anchor)
                batch["score"], batch["decision"] = model.score(batch), model.ev(batch)
                batch.to_parquet(cycle_dir / "candidates.parquet", index=False)
            save(cycle_dir / "receipt.json", {"signal_close": close.isoformat(), "retrieved_at": utcnow().isoformat(),
                "replay": bool(args.replay_time), "data_manifest_sha256": args.data_anchor,
                "market_evidence": tick_evidence + market.evidence, "stock_queries": data.market_receipts,
                "full_universe": list(data.spec["symbols"]), "no_current_bar": missing,
                "candidate_rows": len(batch), "candidate_sha256": sha(cycle_dir / "candidates.parquet") if len(batch) else None,
                "clock_limitation": "SIP feature chronology; actual REST retrieval and paper decision are later and recorded separately"})
            if args.replay_time:
                report(status="replayed", phase="complete", candidate_rows=len(batch), evidence=str(cycle_dir), portfolio=book.summary())
            else:
                report(phase="await_position_monitor")
                if position_monitor:
                    position_monitor.require_complete()
                result = book.allocate(batch, bar=bar, now=utcnow(), quote_loader=market.execution_quote,
                    contexts=contexts, clock=utcnow, alerts=args.enable_alerts)
                if args.enable_alerts:
                    book.export(args.state / "alert-spool")
                report(status="recorded", phase="complete", candidate_rows=len(batch), allocation=result,
                       portfolio=book.summary(), evidence=str(cycle_dir))
            return status
        except Exception as exc:
            report(status="failed", phase=status.get("phase"), error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            if position_monitor:
                position_monitor.close()
            if 'book' in locals() and args.enable_alerts and not args.replay_time:
                # Exit/roll notices already committed must survive a later
                # scoring failure, missed entry deadline, or network error.
                book.export(args.state / "alert-spool")
            print(json.dumps(status, sort_keys=True), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--release", type=Path, required=True)
    ap.add_argument("--anchor", required=True)
    data_group=ap.add_mutually_exclusive_group(required=True)
    data_group.add_argument("--data", type=Path)
    data_group.add_argument("--data-index", type=Path)
    ap.add_argument("--data-anchor")
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--env", type=Path, default=Path(".env"))
    ap.add_argument("--replay-time")
    ap.add_argument("--refresh-replay-bars",action='store_true',help='Fetch stock bars through a retrospective replay clock; never permits alerts')
    ap.add_argument('--stock-capture',type=Path,help='Replay immutable captured stock queries with no stock API request')
    ap.add_argument('--stock-capture-sha256')
    ap.add_argument("--enable-alerts", action="store_true")
    ap.add_argument("--activation", type=Path)
    args = ap.parse_args()
    if args.workers < 1 or args.workers > 16:
        ap.error("workers must be 1..16")
    if args.refresh_replay_bars and not args.replay_time: ap.error('--refresh-replay-bars requires --replay-time')
    if args.stock_capture and (not args.replay_time or not args.stock_capture_sha256):
        ap.error('--stock-capture requires --replay-time and --stock-capture-sha256')
    if args.data_index:
        pointer=read(args.data_index)
        if pointer.get('schema')!='v6-forward-data-index-v1' or pointer.get('release_sha256')!=args.anchor:
            ap.error('data pointer belongs to another release')
        args.data=Path(pointer['path']); args.data_anchor=pointer['sha256']
    if not args.data_anchor: ap.error('--data requires --data-anchor')
    args.release, args.data, args.state = args.release.absolute(), args.data.absolute(), args.state.absolute()
    if args.enable_alerts: ap.error("This consumer is paper-adapter only; alerts are not supported")
    run(args)
