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
    ap.add_argument("--out", type=str, default=None,
                    help="output spec path (for sharded parallel freeze)")
    ap.add_argument("--strategies", type=str, default=None,
                    help="additive freeze: sweep only these families (comma list)")
    ap.add_argument("--base-spec", type=str, default=None,
                    help="additive freeze: inherit every other family's frozen "
                         "entry from this earlier pool's baseline_spec.json")
    ap.add_argument("--merge", type=str, default=None,
                    help="comma-separated shard spec paths to merge, then exit")
    args = ap.parse_args()
    if args.merge:
        baseline.merge_specs(args.merge.split(","), out_path=args.out)
        return
    symbols = [s.strip().upper() for s in args.symbols.split(",")] \
        if args.symbols else None
    baseline.freeze_all(symbols, out_path=args.out,
                        strategies=[x.strip() for x in args.strategies.split(",")] if args.strategies else None,
                        base_spec=args.base_spec)


if __name__ == "__main__":
    main()
