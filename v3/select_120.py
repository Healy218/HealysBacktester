# v3/select_120.py — pick the ~120 most-liquid names for the big run.
"""Rank the 289-name bootstrap universe by average daily dollar volume (from
the 1m crawl) and take the top 120, unioned with the v2 56 (known-good,
already option-liquid). Writes v3/artifacts/universe_120.json.
"""
import json

import pandas as pd

from nn_meta.config import UNDERLYINGS as V2
from v3 import config, underlying
from v3.universe import BOOTSTRAP_UNIVERSE

TARGET = 120


def dollar_volume(sym: str) -> float:
    try:
        df = underlying.load_1m(sym)
    except Exception:
        return 0.0
    dv = (df["Close"] * df["Volume"])
    daily = dv.resample("1D").sum()
    return float(daily[daily > 0].mean() or 0.0)


def main() -> None:
    scored = [(s, dollar_volume(s)) for s in BOOTSTRAP_UNIVERSE]
    scored.sort(key=lambda kv: -kv[1])
    ranked = [s for s, _ in scored]
    keep = list(dict.fromkeys(list(V2) + ranked))[:TARGET]  # v2 first, then liquidity
    # if v2 pushed us over, trim from the tail-liquidity end but keep all v2
    keep = list(dict.fromkeys(list(V2) + [s for s in ranked if s not in V2]))[:TARGET]

    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = config.ARTIFACTS / "universe_120.json"
    out.write_text(json.dumps(sorted(keep), indent=1))
    print(f"selected {len(keep)} symbols → {out}")
    print("top 15 by $vol:", [s for s, _ in scored[:15]])
    print("v2 all included:", set(V2) <= set(keep))


if __name__ == "__main__":
    main()
