# fa/ranker.py — Stage 4: composite ranking → frozen monthly Top-10.
"""Heuristic weights first (documented), learned weights only after tracker
history exists. Anti-footgun gates (FA_SPEC.md):

- **Corroboration**: >= ``config.CORROBORATION_MIN`` independent source
  FAMILIES (reddit posts/comments + StockTwits pool as ``social``; Finnhub/
  AlphaVantage news is ``news``; filings and options flow join when the
  overlay ships). A social-only spike never enters the Top-10.
- **Liquidity floor**: v1 embodies MIN_ADV_USD via the whole-market
  $-volume universe (``v3/artifacts/universe_300.json``) as the valid-ticker
  set — trending-but-untradeable never ranks. Names outside the current
  training pool (``universe_120.json``) are flagged ``new`` (spec leaning:
  rank all, flag newcomers).
- **Point-in-time**: only rows observed at/before ``--as-of`` score;
  the artifact is write-once (``freeze_ranking`` refuses overwrites).

Output: ``fa/artifacts/top10_<yyyy-mm>.json`` + ``.md`` — frozen,
timestamped, committed to git, never edited retroactively.

Run:  ./venv/bin/python -m fa.ranker --freeze            # this month, today
      ./venv/bin/python -m fa.ranker --as-of 2026-08-31  # explicit cutoff
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd

from fa import config
from fa.entities import load_aliases
from fa.scores import build_score_table
from fa.universe_loop import freeze_ranking, monthly_rank

ALIASES = config.ARTIFACTS / "aliases.json"
UNIVERSE_LIQUID = Path(__file__).resolve().parent.parent / "v3/artifacts/universe_300.json"
UNIVERSE_TRAINING = Path(__file__).resolve().parent.parent / "v3/artifacts/universe_120.json"


def _read_source(source: str, archive: Path) -> pd.DataFrame:
    files = sorted(glob.glob(str(archive / source / "*.parquet")))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def load_mention_sources(archive: Path = config.ARCHIVE, *, as_of=None) -> list[tuple]:
    """The ``(source_family, raw_df, colmap)`` triples ``build_score_table``
    consumes. Families are the corroboration unit: everything social pools as
    one family so reddit echoing StockTwits never counts as corroboration."""
    sources: list[tuple] = []

    reddit = _read_source("reddit", archive)
    if not reddit.empty:
        reddit = reddit.assign(
            text=reddit["title"].fillna("") + " " + reddit["selftext"].fillna(""),
            ref="reddit:" + reddit["post_id"].astype(str))
        sources.append(("social", reddit,
                        {"text_col": "text", "ts_col": "created_utc", "ref_col": "ref"}))

    comments = _read_source("reddit_comments", archive)
    if not comments.empty:
        comments = comments.assign(
            ref="reddit_comment:" + comments["comment_id"].astype(str))
        sources.append(("social", comments,
                        {"text_col": "body", "ts_col": "created_utc", "ref_col": "ref"}))

    st = _read_source("stocktwits", archive)
    if not st.empty:
        # trending-list rows carry the symbol directly — resolve() still runs
        # (as a cashtag) so the valid-ticker floor applies uniformly
        st = st.assign(text="$" + st["symbol"].astype(str),
                       ref="stocktwits:" + st["ts_utc"].astype(str)
                           + ":" + st["symbol"].astype(str))
        sources.append(("social", st,
                        {"text_col": "text", "ts_col": "ts_utc", "ref_col": "ref"}))

    news = _read_source("news", archive)
    if not news.empty:
        news = news[news["tickers"].astype(str).str.len() > 0].assign(
            text=news["tickers"].astype(str).map(
                lambda value: " ".join("$" + t.strip() for t in value.split(",") if t.strip())),
            ref="news:" + news["provider"].astype(str) + ":" + news["url"].astype(str))
        sources.append(("news", news,
                        {"text_col": "text", "ts_col": "published", "ref_col": "ref"}))

    filtered = []
    cutoff = pd.Timestamp(as_of) if as_of is not None else None
    if cutoff is not None:
        cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    for family, raw, cols in sources:
        raw = raw.copy()
        captured = pd.to_datetime(raw["ts_utc"], utc=True)
        raw = raw.assign(ts_utc=captured).sort_values("ts_utc")
        if cutoff is not None:
            raw = raw[raw["ts_utc"] <= cutoff]
        raw = raw.drop_duplicates(cols["ref_col"], keep="first")
        # Availability is first capture, not provider publication time.
        filtered.append((family, raw, {**cols, "ts_col": "ts_utc"}))
    return filtered


def build_monthly_ranking(as_of, *, archive: Path = config.ARCHIVE,
                          top_n: int = config.TOP_N, aliases_path=None, liquid_path=None,
                          training_path=None) -> tuple[pd.DataFrame, dict]:
    """Score table → corroborated, liquidity-floored, point-in-time Top-N."""
    aliases_path = Path(aliases_path) if aliases_path is not None else ALIASES
    liquid_path = Path(liquid_path) if liquid_path is not None else UNIVERSE_LIQUID
    training_path = Path(training_path) if training_path is not None else UNIVERSE_TRAINING
    aliases = load_aliases(aliases_path) if aliases_path.exists() else {}
    liquid = set(json.loads(liquid_path.read_text()))
    training = (set(json.loads(training_path.read_text()))
                if training_path.exists() else set())
    scores = build_score_table(load_mention_sources(archive, as_of=as_of), aliases,
                               valid_tickers=liquid)
    ranking = monthly_rank(scores, as_of=as_of, top_n=top_n,
                           min_source_families=config.CORROBORATION_MIN)
    if not ranking.empty:
        ranking["new"] = ~ranking["ticker"].isin(training)
    meta = {"as_of": pd.Timestamp(as_of).isoformat(),
            "score_rows": int(len(scores)),
            "tickers_scored": int(scores["ticker"].nunique()) if len(scores) else 0,
            "liquidity_floor": liquid_path.name,
            "corroboration_min": config.CORROBORATION_MIN,
            "baseline_days": config.BASELINE_DAYS,
            "aliases": len(aliases)}
    return ranking, meta


def render_md(ranking: pd.DataFrame, meta: dict) -> str:
    lines = [f"# FA discovery Top-{len(ranking)} — frozen {meta['as_of'][:10]}",
             "",
             f"Velocity z-scores vs each name's own {meta['baseline_days']}d "
             f"baseline; corroboration ≥ {meta['corroboration_min']} source "
             f"families; liquidity floor: {meta['liquidity_floor']}. "
             f"{meta['tickers_scored']} tickers scored from "
             f"{meta['score_rows']} score rows.",
             "",
             "| # | ticker | score | families | new? |",
             "|---|---|---|---|---|"]
    for i, r in enumerate(ranking.itertuples(index=False), 1):
        lines.append(f"| {i} | {r.ticker} | {r.score:+.2f} | "
                     f"{r.source_families} | {'NEW' if r.new else ''} |")
    lines += ["", "Forward tracking begins from the freeze date "
                  "(`fa/tracker.py`); graduation only after "
                  f"{config.PROBATION_MONTHS} months' probation, point-in-time."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=None, help="cutoff (default: today UTC)")
    ap.add_argument("--prior-month", action="store_true",
                    help="cutoff = last day of the previous month (the monthly "
                         "cron runs on the 1st and freezes the completed month)")
    ap.add_argument("--top", type=int, default=config.TOP_N)
    ap.add_argument("--freeze", action="store_true",
                    help="write the frozen artifact (default: print only)")
    args = ap.parse_args()
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    if args.prior_month:
        as_of = today.replace(day=1) - pd.Timedelta(nanoseconds=1)
    else:
        as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp.utcnow()
    ranking, meta = build_monthly_ranking(as_of, top_n=args.top)
    print(render_md(ranking, meta))
    if args.freeze:
        stamp = pd.Timestamp(as_of).strftime("%Y-%m")
        jpath = config.ARTIFACTS / f"top10_{stamp}.json"
        freeze_ranking(jpath, ranking, as_of=as_of)
        (config.ARTIFACTS / f"top10_{stamp}.md").write_text(render_md(ranking, meta))
        print(f"frozen: {jpath} (+ .md)")


if __name__ == "__main__":
    main()
