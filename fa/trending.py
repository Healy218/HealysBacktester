# fa/trending.py — daily "what's the crowd trading" report (FA Stage 1-2 lite).
"""Turns the raw reddit + news archives into a morning digest: the day's
top movers by ATTENTION, split by sentiment DIRECTION (upward = buzzing +
bullish, downward = buzzing + bearish). Delivered to Telegram.

Deliberately simple while history is thin (days, not the 90-day baseline
FA_SPEC ultimately wants): attention velocity = today's mentions vs the mean
of prior collected days. It sharpens automatically as the archive grows.

Design choices (the "what's useful" answers, encoded):
- Rank by VELOCITY, not raw count — raw count is always SPY/NVDA and carries
  no information; the delta surfaces what's NEW today.
- Require CORROBORATION-friendly signal: a min mention floor kills 1-2 mention
  noise; names seen in >=2 sources are marked (harder to manipulate).
- LIQUIDITY filter: only names in the tradeable universe — a trending ticker
  we can't trade options on is trivia.
- Show CONTEXT (a sample headline / mention) so each line is actionable.

Run:  python -m fa.trending [--dry-run] [--date YYYY-MM-DD]
"""
import argparse
import re
from collections import Counter, defaultdict

import pandas as pd

from fa import config

try:
    from v3.universe import BOOTSTRAP_UNIVERSE as UNIVERSE
except Exception:                          # universe module optional
    from nn_meta.config import UNDERLYINGS as UNIVERSE

# bare tickers that collide with English / WSB slang → cashtag-only for these
AMBIGUOUS = {"A", "I", "IT", "ALL", "SO", "ON", "AI", "GO", "ARE", "FOR",
             "NOW", "OPEN", "REAL", "PLAY", "HOOD", "RUN", "KEY", "U", "W",
             "DD", "CEO", "USA", "EDIT", "K", "O", "D", "F", "T", "C", "ONE",
             "OR", "BE", "AN", "AT", "BY", "PM", "AM", "EV", "PT", "YOLO",
             "CALL", "PUT", "BIG", "LOW", "NEW", "SEE", "ANY", "GDP", "IV",
             # common false-positive tickers (words/acronyms in retail slang)
             "USB", "CAT", "DD", "IT", "ET", "ELF", "GO", "TV", "APP", "NICE",
             "OUT", "PAY", "FIX", "TECH", "LOVE", "MOON", "FAT", "WELL", "EDIT",
             "SO", "BOX", "GOOD", "HE", "SHE", "US", "AI", "MAX", "VS", "CEO"}
BARE_OK = {t for t in UNIVERSE if t not in AMBIGUOUS and len(t) >= 2}

_BULL = re.compile(r"\b(calls?|long|buy(ing)?|moon|rip|breakout|squeeze|bull"
                   r"|pump|rocket|📈|🚀|ath|green|up\b)", re.I)
_BEAR = re.compile(r"\b(puts?|short(ing)?|sell(ing)?|dump|crash|bear|drill"
                   r"|tank|red|baghold|📉|rug|down\b|collapse)", re.I)
_CASHTAG = re.compile(r"\$([A-Za-z]{1,5})\b")
_BARE = re.compile(r"\b([A-Z]{2,5})\b")

MIN_MENTIONS = 4          # below this = noise, not a trend
TOP_N = 5


def _tickers(text: str) -> set[str]:
    out = {m.upper() for m in _CASHTAG.findall(text)}
    out |= {t for t in _BARE.findall(text) if t in BARE_OK}
    return out & set(UNIVERSE)


def _load(src: str, since=None) -> pd.DataFrame:
    parts = sorted((config.ARCHIVE / src).glob("*.parquet"))
    if not parts:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["day"] = df["ts_utc"].dt.date
    return df


def _reddit_signal(as_of):
    """Per-ticker, per-day: mention count, bull/bear lean, a sample body."""
    frames = []
    for src, textcols in (("reddit_comments", ["body"]),
                          ("reddit", ["title", "selftext"])):
        d = _load(src)
        if d.empty:
            continue
        d["text"] = d[textcols].fillna("").agg(" ".join, axis=1)
        frames.append(d[["day", "text"]])
    if not frames:
        return {}, {}, {}
    d = pd.concat(frames, ignore_index=True)
    per_day = defaultdict(Counter)          # day -> ticker -> mentions
    lean = defaultdict(lambda: [0, 0])      # ticker -> [bull, bear] (today)
    sample = {}
    for row in d.itertuples():
        ticks = _tickers(row.text)
        if not ticks:
            continue
        b, s = bool(_BULL.search(row.text)), bool(_BEAR.search(row.text))
        for t in ticks:
            per_day[row.day][t] += 1
            if row.day == as_of:
                lean[t][0] += b
                lean[t][1] += s
                if t not in sample and 20 < len(row.text) < 180:
                    sample[t] = row.text.strip().replace("\n", " ")
    return per_day, lean, sample


def _stocktwits_lean(as_of):
    """Per-ticker net Bullish/Bearish from StockTwits message tags — the clean
    directional signal (home box collects, pushes here). Returns {sym: (net,
    n_msgs)} aggregated over the day's snapshots."""
    d = _load("stocktwits_sentiment")
    if d.empty:
        return {}
    d = d[d["day"] == as_of]
    out = {}
    for sym, g in d.groupby("symbol"):
        bull, bear = g["bull"].sum(), g["bear"].sum()
        tot = bull + bear
        if tot:
            out[str(sym).upper()] = ((bull - bear) / tot, int(tot))
    return out


def _news_sentiment(as_of):
    """Per-ticker mean AlphaVantage/Finnhub sentiment for the day + headline."""
    d = _load("news")
    if d.empty:
        return {}, {}
    d = d[d["day"] == as_of]
    sent, head = defaultdict(list), {}
    for row in d.itertuples():
        if not isinstance(row.tickers, str):
            continue
        for t in row.tickers.split(","):
            t = t.strip().upper()
            if t in UNIVERSE:
                if pd.notna(row.sentiment):
                    sent[t].append(float(row.sentiment))
                head.setdefault(t, str(row.headline)[:150])
    return ({t: sum(v) / len(v) for t, v in sent.items() if v}, head)


def build_report(as_of=None) -> tuple[str, dict]:
    days = sorted({p for src in ("reddit_comments", "reddit", "news")
                   for p in _load(src).get("day", pd.Series(dtype=object))})
    if not days:
        return "No FA data collected yet.", {}
    as_of = as_of or days[-1]
    prior = [d for d in days if d < as_of]

    per_day, lean, sample = _reddit_signal(as_of)
    news_sent, news_head = _news_sentiment(as_of)
    st_lean = _stocktwits_lean(as_of)
    today = per_day.get(as_of, Counter())

    # attention velocity: today's mentions vs mean of prior collected days
    rows = []
    for t, n in today.items():
        if n < MIN_MENTIONS:
            continue
        base = [per_day[d].get(t, 0) for d in prior]
        base_mean = sum(base) / len(base) if base else 0.0
        velocity = (n - base_mean) / (base_mean + 3)   # +3 damps tiny bases
        # direction priority: StockTwits message tags (explicit Bull/Bear,
        # the clean signal) > reddit keyword lean > news sentiment overlay.
        rl = lean.get(t, [0, 0])
        reddit_dir = (rl[0] - rl[1]) / (rl[0] + rl[1]) if sum(rl) else None
        ns = news_sent.get(t)
        st = st_lean.get(t)
        if st is not None:
            direction = st[0]
        elif reddit_dir is not None:
            direction = reddit_dir
        else:
            direction = ns or 0.0
        sources = 1 + (t in news_sent) + (st is not None)
        rows.append({"ticker": t, "mentions": n, "base": round(base_mean, 1),
                     "velocity": velocity, "direction": direction,
                     "sources": sources,
                     # context = real reddit chatter (self-documents false
                     # positives); never a news headline (wrong-ticker risk).
                     "context": sample.get(t, "")})
    df = pd.DataFrame(rows)
    if df.empty:
        return f"FA trending {as_of}: no ticker cleared the mention floor.", {}

    # up/down = ATTENTION direction (heating vs cooling) — the robust axis
    # that always populates; sentiment rides along as a per-name annotation.
    trending = df.sort_values("velocity", ascending=False)
    up = trending.head(TOP_N)
    down = trending[trending["velocity"] < 0].tail(TOP_N)[::-1]

    def fmt(r):
        mood = ("🐂" if r.direction > 0.15 else
                "🐻" if r.direction < -0.15 else "•")
        src = "⋈" if r.sources > 1 else " "   # ⋈ = corroborated (news+reddit)
        ctx = f"\n   “{r.context[:110]}”" if r.context else ""
        return (f"{mood}{src} {r.ticker}  {r.mentions}x (was {r.base}){ctx}")

    L = [f"📊 FA trending — {as_of}",
         f"reddit·news·stocktwits · {len(prior)+1}d · ⋈=2-src · "
         f"🐂/🐻=sentiment lean (StockTwits snapshot-weighted when available)", "",
         "📈 Heating up (rising chatter)"]
    L += [fmt(r) for r in up.itertuples()] or ["  (none)"]
    L += ["", "📉 Cooling off (fading chatter)"]
    L += [fmt(r) for r in down.itertuples()] or ["  (none)"]
    meta = {"as_of": str(as_of), "n_candidates": len(df),
            "up": up["ticker"].tolist(), "down": down["ticker"].tolist()}
    return "\n".join(L), meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    as_of = pd.to_datetime(args.date).date() if args.date else None

    text, meta = build_report(as_of)
    if meta:                                # freeze the dated artifact
        import json
        config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
        (config.ARTIFACTS / f"trending_{meta['as_of']}.json").write_text(
            json.dumps(meta, indent=2))

    if args.dry_run:
        print(text)
        return
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    from nn_meta.live.notifier import get_notifier
    get_notifier().send(text, title="FA trending")
    print(text)


if __name__ == "__main__":
    main()
