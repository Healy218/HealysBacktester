# fa/collect.py — run every available Stage-0 collector once. Cron hourly.
"""python -m fa.collect

Each collector is independent; one failing (or not yet implemented — reddit
needs API credentials) never blocks the others. Exit 0 if anything succeeded,
1 if every collector failed — so the scheduler can flag total outages without
paging about single-source blips.

FA_SKIP_COLLECTORS (comma-separated names in .env) skips sources that can't
run from this host — e.g. StockTwits sits behind Cloudflare and 403s
datacenter IPs, so the cloud server skips it and a residential box collects it.
"""
import os
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
    skip = {s.strip() for s in
            os.environ.get("FA_SKIP_COLLECTORS", "").split(",") if s.strip()}
    ok, failed = 0, 0
    for name, mod in COLLECTORS:
        if name in skip:
            print(f"{name}: skipped (FA_SKIP_COLLECTORS)")
            continue
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
