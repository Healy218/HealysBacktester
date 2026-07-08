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


def symbol_section(symbol: str) -> list[str]:
    df = load_alpaca_bars(symbol, config.WINDOW_START,
                          date.today().isoformat(), "1D")
    print(f"{symbol}: {len(df)} daily bars "
          f"{df.index[0].date()} → {df.index[-1].date()}", flush=True)
    close = df["Close"]

    fmt = lambda v: f"{v:+.1%}"
    lines = [f"## {symbol} ({df.index[0].date()} → {df.index[-1].date()})", ""]
    header = "| strategy | " + " | ".join(n for n, *_ in REGIMES) + \
             " | full window | trades |"
    lines += [header, "|" + "---|" * (len(REGIMES) + 3)]

    strategies = list(build_signals(df).items()) + \
        [("buy & hold", (pd.Series(True, close.index),
                         pd.Series(False, close.index)))]
    for name, (entries, exits) in strategies:
        en = entries.shift(1, fill_value=False)
        ex = exits.shift(1, fill_value=False)
        cells = []
        for _, s, e in REGIMES:
            r = run_window(close, en, ex, s, e)
            cells.append(f"{fmt(r['return'])} ({fmt(r['maxdd'])})" if r else "—")
        full = run_window(close, en, ex, config.WINDOW_START, None)
        lines.append(f"| {name} | " + " | ".join(cells) +
                     f" | {fmt(full['return'])} ({fmt(full['maxdd'])}) "
                     f"| {full['trades']} |")
    return lines + [""]


# V3_SPEC stage-5 diverse basket: indexes, mega-caps, high-IV retail,
# rate-sensitive, sector. (PLTR/COIN listed mid-window; their tables start
# at first data.)
BASKET = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA",
          "GME", "PLTR", "COIN", "TLT", "XLE"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(BASKET))
    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    lines = [f"# TV-strategy pilot — daily bars, {config.WINDOW_START} → "
             f"{date.today().isoformat()}", "",
             "Honest next-bar fills, 5 bps/side, TV default params, "
             "long-only. Cells: total return (max drawdown).", ""]
    for symbol in symbols:
        try:
            lines += symbol_section(symbol)
        except Exception as e:
            lines += [f"## {symbol}", "", f"FAILED: {e}", ""]
            print(f"{symbol}: FAILED {e}", flush=True)

    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    tag = "basket" if len(symbols) > 1 else symbols[0].lower()
    out = config.ARTIFACTS / f"tv_pilot_{tag}.md"
    out.write_text("\n".join(lines))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
