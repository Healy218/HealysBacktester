# fa/collect.py — run every available Stage-0 collector once. Cron hourly.
"""python -m fa.collect

Each collector is independent; one failing (or not yet implemented — reddit
needs API credentials) never blocks the others. Exit 0 if anything succeeded,
1 if every collector failed — so the scheduler can flag total outages without
paging about single-source blips.
"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from utils.logging_utils import setup_logging
from fa.collectors import edgar, news, reddit, stocktwits

logger = setup_logging(log_file="logs/backtester.log")

COLLECTORS = [("stocktwits", stocktwits), ("edgar", edgar),
              ("news", news), ("reddit", reddit)]


def main() -> int:
    ok, failed = 0, 0
    for name, mod in COLLECTORS:
        try:
            n = mod.collect()
            logger.info(f"[fa.collect] {name}: +{n} rows")
            print(f"{name}: +{n} rows")
            ok += 1
        except NotImplementedError:
            print(f"{name}: skipped (not implemented)")
        except Exception as e:
            logger.exception(f"[fa.collect] {name} failed: {e}")
            print(f"{name}: FAILED ({e})")
            failed += 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
