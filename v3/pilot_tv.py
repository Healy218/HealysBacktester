# v3/pilot_tv.py — Stage 4 mini-test: TV-derived strategies on SPY daily.
"""Plumbing + economics check for the TradingView indicator set on the full
audited window (2017-01-20 → present, Alpaca daily bars). Honest fills:
signals computed on bar t execute on bar t+1 (shift(1)); 5 bps fees/side.

Strategies (long-only, vs buy & hold):
  rating_buy    — enter rating > 0.1, exit rating < -0.1  (TV "Buy"..hysteresis)
  rating_strong — enter rating > 0.5, exit rating < 0.1   (TV "Strong Buy")
  supertrend    — long while SuperTrend(10,3) direction is +1
  squeeze       — enter on squeeze release with positive momentum, exit on
                  momentum sign flip

NOT tuning anything here (V3_SPEC stage 4 rule) — parameters are TV defaults.
Output: v3/artifacts/tv_pilot_spy.md (+ printed table), per-regime slices.

Run (repo root):  python -m v3.pilot_tv [--symbol SPY]
"""
import argparse
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd
import vectorbt as vbt

from data.alpaca_loader import load_alpaca_bars
from v3 import config
from v3 import indicators as ta
from v3 import tv_rating

FEES = 0.0005
REGIMES = [("2017-2019", "2017-01-20", "2019-12-31"),
           ("2020 covid", "2020-01-01", "2020-12-31"),
           ("2021 meme", "2021-01-01", "2021-12-31"),
           ("2022 bear", "2022-01-01", "2022-12-31"),
           ("2023-now", "2023-01-01", None)]


def build_signals(df: pd.DataFrame) -> dict[str, tuple[pd.Series, pd.Series]]:
    r = tv_rating.rating(df)["rating"]
    st = ta.supertrend(df)["direction"]
    sq = ta.squeeze_momentum(df)
    released = sq["squeeze_on"].shift(1, fill_value=False) & ~sq["squeeze_on"]
    return {
        "rating_buy": (r > 0.1, r < -0.1),
        "rating_strong": (r > 0.5, r < 0.1),
        "supertrend": (st == 1, st == -1),
        "squeeze": (released & (sq["momentum"] > 0), sq["momentum"] < 0),
    }


def run_window(close: pd.Series, entries: pd.Series, exits: pd.Series,
               start: str, end: str | None) -> dict:
    sl = slice(start, end or date.today().isoformat())
    c, en, ex = close.loc[sl], entries.loc[sl], exits.loc[sl]
    if c.empty:
        return {}
    pf = vbt.Portfolio.from_signals(c, en, ex, fees=FEES, freq="1D")
    return {"return": pf.total_return(), "maxdd": pf.max_drawdown(),
            "trades": pf.trades.count()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    args = ap.parse_args()

    df = load_alpaca_bars(args.symbol, config.WINDOW_START,
                          date.today().isoformat(), "1D")
    print(f"{args.symbol}: {len(df)} daily bars "
          f"{df.index[0].date()} → {df.index[-1].date()}")
    close = df["Close"]

    fmt = lambda v: f"{v:+.1%}"
    lines = [f"# TV-strategy pilot — {args.symbol} daily, "
             f"{df.index[0].date()} → {df.index[-1].date()}", "",
             "Honest next-bar fills, 5 bps/side, TV default params, "
             "long-only. Per-regime total return (max drawdown).", ""]
    header = "| strategy | " + " | ".join(n for n, *_ in REGIMES) + \
             " | full window | trades |"
    lines += [header, "|" + "---|" * (len(REGIMES) + 3)]

    for name, (entries, exits) in build_signals(df).items():
        en, ex = entries.shift(1, fill_value=False), exits.shift(1, fill_value=False)
        cells = []
        for _, s, e in REGIMES:
            r = run_window(close, en, ex, s, e)
            cells.append(f"{fmt(r['return'])} ({fmt(r['maxdd'])})" if r else "—")
        full = run_window(close, en, ex, config.WINDOW_START, None)
        lines.append(f"| {name} | " + " | ".join(cells) +
                     f" | {fmt(full['return'])} ({fmt(full['maxdd'])}) "
                     f"| {full['trades']} |")

    cells = []
    for _, s, e in REGIMES:
        r = run_window(close, pd.Series(True, close.index),
                       pd.Series(False, close.index), s, e)
        cells.append(f"{fmt(r['return'])} ({fmt(r['maxdd'])})")
    full = run_window(close, pd.Series(True, close.index),
                      pd.Series(False, close.index), config.WINDOW_START, None)
    lines.append(f"| buy & hold | " + " | ".join(cells) +
                 f" | {fmt(full['return'])} ({fmt(full['maxdd'])}) | 1 |")

    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = config.ARTIFACTS / f"tv_pilot_{args.symbol.lower()}.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines[4:]))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
