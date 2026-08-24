# fa/tracker.py — Stage 5: forward-return tracking + graduation.
"""THE metric: forward returns of past top-10s vs the existing-universe
baseline. Every pick tracked monthly from its ranking date; graduation only
after ``config.PROBATION_MONTHS`` of probation, point-in-time (as of the
ranking date, not today). If discovery picks don't outperform after 6+
months of tracking, the ranker is redecorating, not discovering.

``forward_returns`` is pure: the caller supplies a ``price_loader(ticker) ->
daily Close Series`` (bars_daily cache / Alpaca crawl) so the computation is
testable and never fetches. Output rows are exactly what
``fa.universe_loop.eligible_graduates`` consumes.

Run (monthly, after the freeze):
    ./venv/bin/python -m fa.tracker            # prints the scoreboard
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd

from fa import config

RETURN_COLUMNS = ["ticker", "ranking_date", "as_of", "fwd_return",
                  "baseline_return", "excess_return"]


def load_frozen_rankings(artifacts: Path = config.ARTIFACTS) -> pd.DataFrame:
    """All frozen top10_*.json artifacts → (ticker, ranking_date) rows."""
    rows = []
    for f in sorted(glob.glob(str(artifacts / "top10_*.json"))):
        payload = json.loads(Path(f).read_text())
        for r in payload["rows"]:
            rows.append({"ticker": r["ticker"],
                         "ranking_date": pd.Timestamp(payload["as_of"]).normalize(),
                         "artifact": Path(f).name})
    return pd.DataFrame(rows, columns=["ticker", "ranking_date", "artifact"])


def _window_return(closes: Optional[pd.Series], start: pd.Timestamp,
                   end: pd.Timestamp) -> Optional[float]:
    """Close-to-close return from the first bar at/after ``start`` to the last
    bar at/before ``end``; None when either edge has no bar (never guessed)."""
    if closes is None or closes.empty:
        return None
    closes = closes.sort_index()
    a = closes[closes.index >= start]
    b = closes[closes.index <= end]
    if a.empty or b.empty or b.index[-1] <= a.index[0]:
        return None
    return float(b.iloc[-1] / a.iloc[0] - 1.0)


def forward_returns(rankings: pd.DataFrame,
                    price_loader: Callable[[str], Optional[pd.Series]], *,
                    as_of, baseline: Iterable[str]) -> pd.DataFrame:
    """Each pick's return from its ranking date to ``as_of``, and the excess
    over the equal-weight baseline basket measured over the SAME window."""
    as_of = pd.Timestamp(as_of).normalize()
    cache: dict[str, Optional[pd.Series]] = {}

    def _closes(t: str) -> Optional[pd.Series]:
        if t not in cache:
            try:
                cache[t] = price_loader(t)
            except Exception:
                cache[t] = None
        return cache[t]

    out = []
    for r in rankings.itertuples(index=False):
        start = pd.Timestamp(r.ranking_date)
        if start >= as_of:
            continue
        fwd = _window_return(_closes(r.ticker), start, as_of)
        if fwd is None:
            continue
        base_rets = [x for x in (_window_return(_closes(b), start, as_of)
                                 for b in baseline) if x is not None]
        if not base_rets:
            continue
        base = float(pd.Series(base_rets).mean())
        out.append({"ticker": r.ticker, "ranking_date": start, "as_of": as_of,
                    "fwd_return": fwd, "baseline_return": base,
                    "excess_return": fwd - base})
    return pd.DataFrame(out, columns=RETURN_COLUMNS)


def main() -> None:
    from fa.ranker import UNIVERSE_TRAINING
    ranks = load_frozen_rankings()
    if ranks.empty:
        print("no frozen rankings yet — run fa.ranker --freeze first")
        return
    baseline = json.loads(UNIVERSE_TRAINING.read_text())
    from data import vbt_data_loader  # lazy: network-capable loader

    def loader(t: str):
        df = vbt_data_loader.load_alpaca_bars(
            t, str(ranks["ranking_date"].min().date()),
            str(pd.Timestamp.utcnow().date()), "1Day")
        return None if df is None or df.empty else df["Close"]

    rets = forward_returns(ranks, loader, as_of=pd.Timestamp.utcnow().normalize(),
                           baseline=baseline)
    if rets.empty:
        print("no resolvable windows yet (too soon after the freeze)")
        return
    print(rets.to_string(index=False))
    print(f"\nmean excess vs baseline: {rets['excess_return'].mean():+.2%} "
          f"({(rets['excess_return'] > 0).mean():.0%} of picks ahead)")


if __name__ == "__main__":
    main()
