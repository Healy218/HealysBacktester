# nn_meta/live/run_live.py
"""Live signal scan — one pass, alert-only. Cron this every 15m during RTH:

    */15 13-20 * * 1-5  cd <repo> && venv/bin/python -m nn_meta.live.run_live --once

The script self-gates to regular trading hours and only acts on CLOSED bars,
so a loose cron schedule is fine. Alerts go to Telegram (or Pushover as the
fallback transport, or the console with --dry-run / when neither TELEGRAM_*
nor PUSHOVER_* is set). It never places orders.

    --once            single pass then exit (default; loop mode is TODO)
    --dry-run         print alerts instead of sending; force console notifier
    --symbols A,B     restrict to a subset (default: whole frozen universe)
    --nn              filter with the model_final ensemble (recommended);
                      without it, EVERY mechanical entry alerts (baseline)
    --threshold F     override the NN keep threshold (default: bundle's own)
    --ignore-hours    scan even outside RTH (testing)
"""
import argparse
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd

from utils.logging_utils import setup_logging
from data import vbt_data_loader
from nn_meta import config
from nn_meta.download_data import filter_rth
from nn_meta.live.scanner import (Scanner, aliased_bar_loader, is_rth,
                                  format_alert, _LOOKBACK_DAYS)
from nn_meta.live.notifier import get_notifier

logger = setup_logging(log_file="logs/backtester.log")

_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


_FEED_MAX_AGE_MIN = 3      # streamed bars older than this → fall back to REST for today


def _feed_is_fresh(now: datetime) -> bool:
    from nn_meta.live.feeds.barstore import read_heartbeat
    from nn_meta.live.feeds.stock_stream import HEARTBEAT
    hb = read_heartbeat(HEARTBEAT)
    if not hb or not hb.get("ts"):
        return False
    age = (now - datetime.fromisoformat(hb["ts"])).total_seconds() / 60
    return age <= _FEED_MAX_AGE_MIN


def _bar_loader(symbol: str, now: datetime | None = None):
    """Recent 15m RTH bars for one symbol (may include the forming last bar;
    the scanner trims it).

    Composition (2026-09-05, after the stale-cache incident):
      * HISTORY — closed sessions up to yesterday — through the smart loader's
        day-keyed cache. Those sessions never change, so the cache is valid.
      * TODAY — the streamed bar store (Alpaca SIP 1m → 15m, bar-identical to
        REST, parity-checked) when its heartbeat is fresh; otherwise today's
        bars over REST with the cache BYPASSED. The day-keyed cache is never
        consulted for the current session again.
    """
    now = now or datetime.now(timezone.utc)
    today = now.date()
    start = today - timedelta(days=_LOOKBACK_DAYS)
    yesterday = today - timedelta(days=1)
    # Vendor symbol (2026-09-05): BRKB is "BRK.B" at Alpaca (config.FETCH_ALIASES);
    # without this the live scan never saw BRKB at all ("NoneType has no
    # attribute 'empty'" on every pass).
    fetch_sym = getattr(config, "FETCH_ALIASES", {}).get(symbol.upper(), symbol)
    hist = vbt_data_loader.load_price_data_smart(
        fetch_sym, start.isoformat(), yesterday.isoformat(), "15m")
    hist = filter_rth(hist[_OHLCV]) if hist is not None and not hist.empty else None
    today_bars = None
    if _feed_is_fresh(now):
        from nn_meta.live.feeds.barstore import BarStore
        tb = BarStore().read_15m(symbol, days=[today.isoformat()])
        today_bars = tb if not tb.empty else None
    if today_bars is None:
        raw = vbt_data_loader.load_price_data_smart(
            fetch_sym, today.isoformat(), today.isoformat(), "15m", force_download=True)
        if raw is not None and not raw.empty:
            today_bars = filter_rth(raw[_OHLCV])
    parts = [p for p in (hist, today_bars) if p is not None and not p.empty]
    if not parts:
        return hist if hist is not None else today_bars
    out = pd.concat(parts)
    return out[~out.index.duplicated(keep="last")].sort_index()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--workers", type=int, default=None,
                    help="detection processes (default SCAN_WORKERS env, else min(4, cpus))")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--symbols", type=str, default=None)
    ap.add_argument("--nn", action="store_true", help="filter with the NN ensemble")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--ignore-hours", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    if not args.ignore_hours and not is_rth(now):
        logger.info("[live] outside regular trading hours — no scan")
        print("Outside RTH — nothing to scan.")
        return

    symbols = [s.strip().upper() for s in args.symbols.split(",")] \
        if args.symbols else None

    scorer, threshold = None, (args.threshold or 0.5)
    if args.nn:
        from nn_meta.live.scorer import NNScorer     # lazy: pulls in TensorFlow
        scorer = NNScorer()
        threshold = args.threshold or scorer.threshold
        logger.info(f"[live] NN filter enabled (threshold {threshold:.2f})")
    else:
        logger.warning("[live] NO NN filter — alerting every mechanical entry "
                       "(baseline mode); pass --nn to filter")

    # alias wrapper is inert for v2/v3 (no renamed tickers in their specs);
    # under v31 it revives the SQ seat by fetching bars as XYZ.
    from nn_meta.live.parallel import default_workers
    scanner = Scanner(aliased_bar_loader(_bar_loader), scorer=scorer,
                      workers=args.workers if args.workers is not None else default_workers(),
                      threshold=threshold)
    notifier = get_notifier(force_console=args.dry_run)

    signals = scanner.scan_once(symbols=symbols, now=now)
    if not signals:
        print("No fresh signals this pass.")
        return

    for sig in signals:
        title, msg = format_alert(sig)
        notifier.send(msg, title=title)
    print(f"{len(signals)} signal(s) alerted: "
          f"{', '.join(s.symbol for s in signals)}")


if __name__ == "__main__":
    main()
