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
from contextlib import nullcontext
from nn_meta.live.state import preview_state
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from utils.logging_utils import setup_logging
from data import vbt_data_loader
from nn_meta.download_data import filter_rth
from nn_meta.live.scanner import (Scanner, aliased_bar_loader, is_rth,
                                  format_alert, _LOOKBACK_DAYS, _STATE_PATH)
from nn_meta.live.notifier import get_notifier

logger = setup_logging(log_file="logs/backtester.log")

_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _bar_loader(symbol: str):
    """Recent 15m RTH bars for one symbol (may include the forming last bar;
    the scanner trims it)."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=_LOOKBACK_DAYS)
    raw = vbt_data_loader.load_price_data_smart(
        symbol, start.isoformat(), end.isoformat(), "15m")
    if raw is None or raw.empty:
        return raw
    return filter_rth(raw[_OHLCV])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", default=True)
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
    with (preview_state(_STATE_PATH.parent) if args.dry_run else nullcontext(_STATE_PATH.parent)) as sdir:
        scanner = Scanner(aliased_bar_loader(_bar_loader), scorer=scorer,
                          threshold=threshold, state_path=sdir / _STATE_PATH.name)
        notifier = get_notifier(force_console=args.dry_run)
        signals = scanner.scan_once(symbols=symbols, now=now)
        delivered = scanner.deliver_pending(notifier)
        if not signals and not delivered:
            print("No fresh signals this pass.")
        else:
            print(f"{delivered} signal(s) alerted: "
                  f"{', '.join(s.symbol for s in signals)}")



if __name__ == "__main__":
    main()
