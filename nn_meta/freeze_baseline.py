# nn_meta/freeze_baseline.py
"""CLI: freeze the mechanical baseline on TRAIN data only.

Run:  python -m nn_meta.freeze_baseline [--symbols SPY,QQQ]
"""
import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nn_meta import baseline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=str, default=None,
                    help="comma-separated subset (default: full universe)")
    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")] \
        if args.symbols else None
    baseline.freeze_all(symbols)


if __name__ == "__main__":
    main()
