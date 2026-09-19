"""Show live checkpoint progress for a V7 proposal build.

This is a read-only companion to ``build_v7_proposals.py``. It watches sealed
receipts only, so partial directories never count as completed work.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def _count(path: Path) -> int:
    return sum(1 for receipt in path.glob("*/complete.json") if receipt.is_file())


def _summary(path: Path) -> bool:
    return (path / "complete.json").is_file()


def _bar(done: int, total: int, width: int = 24) -> str:
    if total < 1:
        return "[no catalog]"
    filled = min(width, int(width * done / total))
    return "[" + "#" * filled + "." * (width - filled) + f"] {done}/{total}"


def snapshot(root: Path, minutes: tuple[int, ...], variants: int) -> tuple[str, bool]:
    lines = []
    finished = True
    for minute in minutes:
        base = root / str(minute)
        features = base / "features"
        proposals = base / "proposals"
        epochs = _count(features / "epochs") if (features / "epochs").is_dir() else 0
        batches = _count(proposals / "batches") if (proposals / "batches").is_dir() else 0
        feature_done = _summary(features / "summary")
        proposal_done = _summary(proposals / "summary")
        finished &= feature_done and proposal_done
        lines.append(
            f"{minute:>2}m features {_bar(epochs, 0) if feature_done else f'{epochs} sealed'}  "
            f"proposals {_bar(batches, variants)}"
            + ("  COMPLETE" if proposal_done else "")
        )
    return "\n".join(lines), finished


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="Security output root, e.g. nn_meta/validation/.../BBG...")
    parser.add_argument("--minutes", type=int, nargs="+", choices=(1, 5, 15, 30),
                        default=(1, 5, 15, 30))
    parser.add_argument("--variants", type=int, default=2817,
                        help="Expected catalog variants per timeframe")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    args = parser.parse_args()
    if args.interval <= 0 or args.variants <= 0:
        raise ValueError("Positive interval and variant count required")
    output = args.output.resolve()
    while True:
        text, finished = snapshot(output, tuple(args.minutes), args.variants)
        if args.once:
            print(text)
        else:
            sys.stdout.write("\033[2J\033[H" + text + "\n")
            sys.stdout.flush()
        if finished or args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
