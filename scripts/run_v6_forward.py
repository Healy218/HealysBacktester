"""Run the frozen V6 experimental paper expert beside the production experts."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import time

from nn_meta.live.v6_release import read, sha, verify_release
from nn_meta.live.v6_market import save, utcnow


def configure(release, anchor):
    verified = verify_release(release, anchor)
    os.environ.update(NN_META_POOL="v6", NN_META_CAMPAIGN=verified["campaign"],
        NN_META_V6_ACCELERATE="1",
        NN_META_V6_EXPANDED="1", NN_META_V6_PARITY_POLICY="deferred",
        NN_META_V6_INPUTS=str(release / "training-inputs.json"),
        NN_META_V6_INPUTS_SHA256=verified["training_inputs_sha256"])
    return verified


def expiry_cutoff(contract, calendar):
    from options.data.provider import parse_occ_symbol
    import pandas as pd
    expiry = parse_occ_symbol(contract)[1].isoformat()
    calendar.bounds(expiry)  # verifies calendar coverage even for Saturday
    day = max(d for d in calendar.sessions if d <= expiry)
    return calendar.bounds(day)[1].tz_localize("UTC") - pd.Timedelta(minutes=15)


def monitor_positions(data, book, market, now, *, alerts):
    """Held-strategy exits get priority over unrelated candidate capture."""
    import pandas as pd
    from copy import deepcopy
    from nn_meta.live.v6_forward_inputs import detect_symbol
    from nn_meta.decision_contracts import DecisionContractSelector
    errors=[]
    for position in book.open_positions():
        symbol=position['symbol']
        try:
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
            elif utcnow()>=expiry_cutoff(position['contract'],data.calendar):
                book.trigger(position['key'],kind='roll',reason='15-minute final-session expiry cutoff',
                    at=expiry_cutoff(position['contract'],data.calendar),alerts=alerts)
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
    """The expiry cutoff can still sell a leg during a stock-data outage.

    A replacement waits for restored current stock data and strategy replay.
    """
    errors=[]
    for position in book.open_positions():
        try:
            cutoff=expiry_cutoff(position['contract'],calendar)
            if now < cutoff: continue
            book.trigger(position['key'],kind='roll',reason='15-minute final-session expiry cutoff',at=cutoff,alerts=alerts)
            book.settle(position['key'],quote_loader=market.execution_quote,clock=utcnow,alerts=alerts)
        except Exception as exc:
            errors.append({'symbol':position['symbol'],'error':f'{type(exc).__name__}: {exc}'})
    return errors


def run(args):
    started = time.monotonic()
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
            if not args.replay_time:
                try:
                    data.update(now)
                except Exception:
                    report(expiry_fallback_errors=close_expiring_without_bars(book,data.calendar,market,utcnow(),alerts=args.enable_alerts))
                    raise
            if not args.replay_time:
                report(phase="monitor_exits")
                exit_errors=monitor_positions(data,book,market,now,alerts=args.enable_alerts)
                if exit_errors:
                    report(exit_errors=exit_errors)
                    raise ValueError("unresolved position monitoring; new entries withheld")
                reference=DecisionContractSelector(market).select('SPY',as_of=now.date(),right='C',
                    raw_spot=float(data.raw['SPY'].Close.iloc[-1]),target_dte=1)
                if reference is None: raise ValueError('liquid reference option unavailable')
                report(current_access=market.verify_current_access(reference.symbol))
            report(phase="detect", fresh_symbols=0)
            tasks = list(data.tasks(bar, book.open_positions()))
            missing = [symbol for symbol, task in tasks if task is None]
            active_tasks = [task for _, task in tasks if task is not None]
            if any(p["symbol"] in missing for p in book.open_positions()):
                raise ValueError("a held position is missing its current underlying bar")
            fresh, exits, errors = [], {}, []
            batches, contexts, tick_evidence = [], {}, []
            cycle_dir = args.state / "passes" / close.strftime("%Y%m%dT%H%M%SZ")
            cycle_dir.mkdir(parents=True, exist_ok=True)
            def collect(result):
                fresh.extend(result["fresh"]); exits.update(result["exits"])
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
            report(phase="capture_and_score", detected=len(active_tasks), no_current_bar=missing, fresh_signals=len(fresh))
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
    ap.add_argument("--enable-alerts", action="store_true")
    ap.add_argument("--activation", type=Path)
    args = ap.parse_args()
    if args.workers < 1 or args.workers > 16:
        ap.error("workers must be 1..16")
    if args.data_index:
        pointer=read(args.data_index)
        if pointer.get('schema')!='v6-forward-data-index-v1' or pointer.get('release_sha256')!=args.anchor:
            ap.error('data pointer belongs to another release')
        args.data=Path(pointer['path']); args.data_anchor=pointer['sha256']
    if not args.data_anchor: ap.error('--data requires --data-anchor')
    args.release, args.data, args.state = args.release.absolute(), args.data.absolute(), args.state.absolute()
    run(args)
